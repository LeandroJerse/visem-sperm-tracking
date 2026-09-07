"""Common optical-flow abstractions and dependency-free image helpers.

The convention used throughout this package is ``flow[y, x] == (u, v)``:
the pixel at ``(x, y)`` in the previous frame is expected at
``(x + u, y + v)`` in the next frame.  ``valid`` is deliberately separate
from the vector field because sparse algorithms such as Lucas--Kanade do not
measure every pixel.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


class OptionalDependencyError(ImportError):
    """Raised only when an optional implementation is actually requested."""


@dataclass
class FlowResult:
    """Optical-flow field plus validity, confidence, and provenance.

    Parameters
    ----------
    flow:
        ``float32``-compatible array with shape ``(height, width, 2)``.
    valid:
        Boolean array indicating vectors that were measured or considered
        reliable.  If omitted, every finite vector is valid.
    confidence:
        Optional confidence in ``[0, 1]``.  Confidence is algorithm-specific
        and must not be compared across algorithms as if it were calibrated.
    metadata:
        JSON-compatible provenance.  Large arrays do not belong here.
    """

    flow: np.ndarray
    valid: np.ndarray | None = None
    confidence: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        flow = np.asarray(self.flow, dtype=np.float32)
        if flow.ndim != 3 or flow.shape[-1] != 2:
            raise ValueError("flow must have shape (height, width, 2)")
        finite = np.isfinite(flow).all(axis=-1)
        valid = finite if self.valid is None else np.asarray(self.valid, dtype=bool)
        if valid.shape != flow.shape[:2]:
            raise ValueError("valid must have shape flow.shape[:2]")
        valid = valid & finite

        confidence = self.confidence
        if confidence is not None:
            confidence = np.asarray(confidence, dtype=np.float32)
            if confidence.shape != flow.shape[:2]:
                raise ValueError("confidence must have shape flow.shape[:2]")
            confidence = np.clip(confidence, 0.0, 1.0)
            confidence = np.where(valid, confidence, 0.0).astype(np.float32)

        self.flow = flow
        self.valid = valid
        self.confidence = confidence
        self.metadata = dict(self.metadata)

    @property
    def height(self) -> int:
        return int(self.flow.shape[0])

    @property
    def width(self) -> int:
        return int(self.flow.shape[1])

    @property
    def magnitude(self) -> np.ndarray:
        return np.linalg.norm(self.flow, axis=-1)


class FlowEstimator(ABC):
    """Interchangeable interface for pairwise optical-flow estimators.

    ``mask=True`` means a pixel is allowed in the analysis.  Implementations
    may still invalidate it because of tracking failure or consistency checks.
    Stateful estimators should override :meth:`reset`.
    """

    name: str = "base"

    @abstractmethod
    def estimate(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        """Estimate motion from ``previous_frame`` to ``next_frame``."""
        raise NotImplementedError

    def __call__(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        return self.estimate(previous_frame, next_frame, mask=mask)

    def reset(self) -> None:
        """Clear per-video state (no-op for pairwise estimators)."""


def validate_frame_pair(
    previous_frame: np.ndarray, next_frame: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Validate that two frames have the same non-empty spatial shape."""

    previous = np.asarray(previous_frame)
    following = np.asarray(next_frame)
    if previous.ndim not in (2, 3) or following.ndim not in (2, 3):
        raise ValueError("frames must be 2-D grayscale or 3-D color arrays")
    if previous.shape[:2] != following.shape[:2]:
        raise ValueError(
            f"frame sizes differ: {previous.shape[:2]} != {following.shape[:2]}"
        )
    if previous.shape[0] == 0 or previous.shape[1] == 0:
        raise ValueError("frames cannot be empty")
    return previous, following


def as_gray_float(frame: np.ndarray) -> np.ndarray:
    """Convert grayscale/BGR/BGRA input to finite ``float32`` in ``[0, 1]``.

    OpenCV is intentionally not required here, which keeps Horn--Schunck,
    metrics, caches, and prediction features usable in a NumPy-only setup.
    """

    array = np.asarray(frame)
    if array.ndim == 2:
        gray = array
    elif array.ndim == 3 and array.shape[2] == 1:
        gray = array[..., 0]
    elif array.ndim == 3 and array.shape[2] in (3, 4):
        # Frames in this repository follow OpenCV's BGR convention.
        bgr = array[..., :3].astype(np.float32, copy=False)
        gray = 0.114 * bgr[..., 0] + 0.587 * bgr[..., 1] + 0.299 * bgr[..., 2]
    else:
        raise ValueError("frame must be grayscale, BGR, or BGRA")

    gray = np.asarray(gray, dtype=np.float32)
    if not np.isfinite(gray).all():
        raise ValueError("frame contains NaN or infinite values")
    if np.issubdtype(array.dtype, np.integer):
        scale = float(np.iinfo(array.dtype).max)
        if scale > 0:
            gray = gray / scale
    elif gray.size and (float(gray.min()) < 0.0 or float(gray.max()) > 1.0):
        # Float images from OpenCV are commonly still in the 0..255 range.
        scale = 255.0 if float(gray.max()) <= 255.0 else float(gray.max())
        gray = gray / max(scale, np.finfo(np.float32).eps)
    return np.clip(gray, 0.0, 1.0).astype(np.float32, copy=False)


def as_gray_u8(frame: np.ndarray) -> np.ndarray:
    """Convert supported input to contiguous 8-bit grayscale."""

    return np.ascontiguousarray(np.round(as_gray_float(frame) * 255.0).astype(np.uint8))


def normalize_mask(mask: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray:
    """Return a boolean include-mask with ``shape``."""

    if mask is None:
        return np.ones(shape, dtype=bool)
    normalized = np.asarray(mask, dtype=bool)
    if normalized.shape != shape:
        raise ValueError(f"mask shape {normalized.shape} does not match {shape}")
    return normalized


def estimator_config(estimator: FlowEstimator) -> Mapping[str, Any]:
    """Return lightweight public configuration for run provenance."""

    config: dict[str, Any] = {"name": estimator.name}
    for key, value in vars(estimator).items():
        if key.startswith("_") or isinstance(value, FlowEstimator):
            continue
        if isinstance(value, (str, int, float, bool, type(None), tuple, list)):
            config[key] = value
    return config
