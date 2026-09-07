"""Lazy optional wrapper around torchvision's pretrained RAFT models."""
from __future__ import annotations

from typing import Any, Literal

import numpy as np

from ..base import (
    FlowEstimator,
    FlowResult,
    OptionalDependencyError,
    normalize_mask,
    validate_frame_pair,
)


class RAFTFlow(FlowEstimator):
    """Torchvision RAFT wrapper with correct normalization and padding.

    Model construction is lazy, so importing :mod:`src.flow` never imports
    PyTorch.  ``weights='DEFAULT'`` may download pretrained weights when they
    are not in the local torch cache; use ``weights=None`` only for architecture
    tests because an untrained RAFT is not a scientific baseline.
    """

    name = "raft"

    def __init__(
        self,
        *,
        variant: Literal["small", "large"] = "small",
        weights: str | None = "DEFAULT",
        device: str = "auto",
        mixed_precision: bool = True,
        model: Any | None = None,
    ) -> None:
        if variant not in {"small", "large"}:
            raise ValueError("variant must be 'small' or 'large'")
        self.variant = variant
        self.weights = weights
        self.device = device
        self.mixed_precision = bool(mixed_precision)
        self._model = model
        self._torch = None
        self._transform = None
        self._resolved_device = None

    @staticmethod
    def _frame_to_rgb_tensor(frame: np.ndarray, torch: Any) -> Any:
        array = np.asarray(frame)
        if array.ndim == 2:
            array = np.repeat(array[..., None], 3, axis=2)
        elif array.ndim == 3 and array.shape[2] == 1:
            array = np.repeat(array, 3, axis=2)
        elif array.ndim == 3 and array.shape[2] >= 3:
            # Repository convention is BGR; RAFT expects RGB.
            array = array[..., :3][..., ::-1]
        else:
            raise ValueError("RAFT input must be grayscale, BGR, or BGRA")
        array = np.ascontiguousarray(array)
        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).float()
        if np.issubdtype(array.dtype, np.integer):
            tensor = tensor / float(np.iinfo(array.dtype).max)
        elif tensor.numel() and (tensor.min() < 0 or tensor.max() > 1):
            tensor = tensor / 255.0
        return tensor

    def _load(self) -> tuple[Any, Any, Any]:
        try:
            import torch
            from torchvision.models.optical_flow import (
                Raft_Large_Weights,
                Raft_Small_Weights,
                raft_large,
                raft_small,
            )
        except (ImportError, RuntimeError) as exc:  # pragma: no cover - environment
            raise OptionalDependencyError(
                "RAFTFlow requires compatible torch and torchvision installations"
            ) from exc

        resolved_device = (
            "cuda" if self.device == "auto" and torch.cuda.is_available() else self.device
        )
        if resolved_device == "auto":
            resolved_device = "cpu"
        weights_enum = Raft_Small_Weights if self.variant == "small" else Raft_Large_Weights
        constructor = raft_small if self.variant == "small" else raft_large
        if self.weights is None:
            resolved_weights = None
        elif str(self.weights).upper() == "DEFAULT":
            resolved_weights = weights_enum.DEFAULT
        else:
            try:
                resolved_weights = weights_enum[self.weights]
            except KeyError as exc:
                raise ValueError(f"unknown RAFT weights: {self.weights}") from exc

        if self._model is None:
            self._model = constructor(weights=resolved_weights, progress=False)
        self._model = self._model.eval().to(resolved_device)
        self._transform = (
            resolved_weights.transforms() if resolved_weights is not None else None
        )
        self._torch = torch
        self._resolved_device = resolved_device
        return torch, self._model, self._transform

    def estimate(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        previous, following = validate_frame_pair(previous_frame, next_frame)
        torch, model, transform = self._load()
        previous_tensor = self._frame_to_rgb_tensor(previous, torch)
        next_tensor = self._frame_to_rgb_tensor(following, torch)
        if transform is not None:
            previous_tensor, next_tensor = transform(previous_tensor, next_tensor)
        else:
            previous_tensor = previous_tensor * 2.0 - 1.0
            next_tensor = next_tensor * 2.0 - 1.0

        height, width = previous.shape[:2]
        pad_bottom = (-height) % 8
        pad_right = (-width) % 8
        if pad_bottom or pad_right:
            functional = torch.nn.functional
            padding = (0, pad_right, 0, pad_bottom)
            previous_tensor = functional.pad(previous_tensor, padding, mode="replicate")
            next_tensor = functional.pad(next_tensor, padding, mode="replicate")
        previous_tensor = previous_tensor.to(self._resolved_device)
        next_tensor = next_tensor.to(self._resolved_device)

        autocast_enabled = self.mixed_precision and str(self._resolved_device).startswith("cuda")
        with torch.inference_mode():
            with torch.autocast(device_type="cuda", enabled=autocast_enabled):
                predictions = model(previous_tensor, next_tensor)
        final_flow = predictions[-1][0, :, :height, :width]
        flow = final_flow.permute(1, 2, 0).float().cpu().numpy().astype(np.float32)
        include = normalize_mask(mask, (height, width))
        flow[~include] = 0.0
        return FlowResult(
            flow,
            include,
            None,
            {
                "algorithm": self.name,
                "variant": self.variant,
                "weights": self.weights,
                "device": str(self._resolved_device),
                "dense": True,
            },
        )
