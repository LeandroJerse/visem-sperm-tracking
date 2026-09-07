"""Optional compact LSTM trajectory predictor with lazy PyTorch imports."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    transition_flow,
    validate_prediction_inputs,
)


def _require_torch():
    try:
        import torch
        from torch import nn
    except (ImportError, RuntimeError) as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "LSTMPredictor requires a compatible PyTorch installation"
        ) from exc
    return torch, nn


class LSTMPredictor(TrajectoryPredictor):
    """Direct multi-horizon LSTM over observed displacement sequences.

    Positions are converted to translations, so the network does not memorize
    microscope image coordinates.  Training-set-only means/scales normalize
    inputs and relative future targets.  With ``use_flow=True``, the sampled
    environmental ``(u, v)`` is concatenated to each observed displacement.
    The architecture and optimization are otherwise identical, enabling a
    paired ablation of flow versus no flow.
    """

    name = "lstm"

    def __init__(
        self,
        *,
        history_length: int = 20,
        max_horizon: int = 10,
        hidden_size: int = 64,
        num_layers: int = 1,
        dropout: float = 0.0,
        use_flow: bool = False,
        device: str = "auto",
        seed: int = 42,
    ) -> None:
        if history_length < 2 or max_horizon <= 0 or hidden_size <= 0 or num_layers <= 0:
            raise ValueError("invalid LSTM dimensions")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.history_length = int(history_length)
        self.max_horizon = int(max_horizon)
        self.hidden_size = int(hidden_size)
        self.num_layers = int(num_layers)
        self.dropout = float(dropout)
        self.use_flow = bool(use_flow)
        self.uses_flow = self.use_flow
        self.device = device
        self.seed = int(seed)
        self._model = None
        self._resolved_device = None
        self._x_mean: np.ndarray | None = None
        self._x_scale: np.ndarray | None = None
        self._y_mean: np.ndarray | None = None
        self._y_scale: np.ndarray | None = None

    def _build_model(self):
        torch, nn = _require_torch()
        input_size = 4 if self.use_flow else 2
        hidden_size = self.hidden_size
        num_layers = self.num_layers
        dropout = self.dropout if num_layers > 1 else 0.0
        max_horizon = self.max_horizon

        class DirectTrajectoryLSTM(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.recurrent = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    dropout=dropout,
                    batch_first=True,
                )
                self.head = nn.Sequential(
                    nn.Linear(hidden_size, hidden_size),
                    nn.ReLU(),
                    nn.Linear(hidden_size, max_horizon * 2),
                )

            def forward(self, features):
                sequence, _ = self.recurrent(features)
                return self.head(sequence[:, -1]).reshape(-1, max_horizon, 2)

        resolved_device = (
            "cuda" if self.device == "auto" and torch.cuda.is_available() else self.device
        )
        if resolved_device == "auto":
            resolved_device = "cpu"
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        self._model = DirectTrajectoryLSTM().to(resolved_device)
        self._resolved_device = resolved_device
        return torch, self._model

    def _window_features(self, window: Any) -> tuple[np.ndarray, np.ndarray]:
        history = np.asarray(window.history, dtype=np.float32)
        future = np.asarray(window.future, dtype=np.float32)
        if len(history) < self.history_length or len(future) < self.max_horizon:
            raise ValueError("window is shorter than configured history/horizon")
        history = history[-self.history_length :]
        velocity = np.diff(history, axis=0)
        if self.use_flow:
            if window.flow_history is None:
                raise ValueError("flow-aware LSTM requires flow_history in every window")
            flow = np.asarray(window.flow_history, dtype=np.float32)[-(self.history_length - 1) :]
            if flow.shape != velocity.shape:
                raise ValueError("window flow_history is not aligned with history")
            features = np.concatenate((velocity, flow), axis=1)
        else:
            features = velocity
        targets = future[: self.max_horizon] - history[-1]
        return features.astype(np.float32), targets.astype(np.float32)

    def fit(
        self,
        windows: Sequence[Any],
        *,
        epochs: int = 50,
        batch_size: int = 128,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        validation_windows: Sequence[Any] | None = None,
        patience: int = 8,
    ) -> dict[str, list[float]]:
        """Fit with optional early stopping; returns train/validation loss history."""

        if not windows:
            raise ValueError("at least one training window is required")
        if epochs <= 0 or batch_size <= 0 or learning_rate <= 0 or patience <= 0:
            raise ValueError("training parameters must be positive")
        if validation_windows:
            training_videos = {str(window.video_id) for window in windows}
            validation_videos = {str(window.video_id) for window in validation_windows}
            overlap = training_videos & validation_videos
            if overlap:
                raise ValueError(
                    "training/validation video leakage: " + ", ".join(sorted(overlap))
                )
        torch, model = self._build_model()
        training_pairs = [self._window_features(window) for window in windows]
        x = np.stack([pair[0] for pair in training_pairs])
        y = np.stack([pair[1] for pair in training_pairs])
        self._x_mean = x.mean(axis=(0, 1), keepdims=True)
        self._x_scale = x.std(axis=(0, 1), keepdims=True)
        self._x_scale = np.maximum(self._x_scale, 1e-6)
        self._y_mean = y.mean(axis=0, keepdims=True)
        self._y_scale = y.std(axis=0, keepdims=True)
        self._y_scale = np.maximum(self._y_scale, 1e-6)
        x = (x - self._x_mean) / self._x_scale
        y = (y - self._y_mean) / self._y_scale
        x_tensor = torch.as_tensor(x, dtype=torch.float32)
        y_tensor = torch.as_tensor(y, dtype=torch.float32)

        validation_tensors = None
        if validation_windows:
            pairs = [self._window_features(window) for window in validation_windows]
            val_x = (np.stack([pair[0] for pair in pairs]) - self._x_mean) / self._x_scale
            val_y = (np.stack([pair[1] for pair in pairs]) - self._y_mean) / self._y_scale
            validation_tensors = (
                torch.as_tensor(val_x, dtype=torch.float32, device=self._resolved_device),
                torch.as_tensor(val_y, dtype=torch.float32, device=self._resolved_device),
            )

        optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        loss_function = torch.nn.SmoothL1Loss()
        history = {"train_loss": [], "validation_loss": []}
        generator = torch.Generator().manual_seed(self.seed)
        best_loss = float("inf")
        best_state = None
        stale_epochs = 0

        for _ in range(epochs):
            model.train()
            permutation = torch.randperm(len(x_tensor), generator=generator)
            losses = []
            for start in range(0, len(permutation), batch_size):
                indices = permutation[start : start + batch_size]
                batch_x = x_tensor[indices].to(self._resolved_device)
                batch_y = y_tensor[indices].to(self._resolved_device)
                optimizer.zero_grad(set_to_none=True)
                loss = loss_function(model(batch_x), batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()
                losses.append(float(loss.detach().cpu()))
            train_loss = float(np.mean(losses))
            history["train_loss"].append(train_loss)

            if validation_tensors is None:
                monitored_loss = train_loss
                history["validation_loss"].append(float("nan"))
            else:
                model.eval()
                with torch.inference_mode():
                    validation_loss = float(
                        loss_function(model(validation_tensors[0]), validation_tensors[1]).cpu()
                    )
                history["validation_loss"].append(validation_loss)
                monitored_loss = validation_loss
            if monitored_loss < best_loss - 1e-7:
                best_loss = monitored_loss
                best_state = {
                    key: value.detach().cpu().clone()
                    for key, value in model.state_dict().items()
                }
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= patience:
                    break

        if best_state is not None:
            model.load_state_dict(best_state)
        return history

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        positions, requested = validate_prediction_inputs(history, horizons)
        if len(positions) < self.history_length:
            raise ValueError(f"LSTM requires at least {self.history_length} history positions")
        if int(requested[-1]) > self.max_horizon:
            raise ValueError(f"largest requested horizon exceeds {self.max_horizon}")
        if self._model is None or any(
            value is None for value in (self._x_mean, self._x_scale, self._y_mean, self._y_scale)
        ):
            raise RuntimeError("LSTM must be fitted or loaded before prediction")
        torch, _ = _require_torch()
        selected = positions[-self.history_length :]
        velocity = np.diff(selected, axis=0)
        if self.use_flow:
            if flow_history is None:
                raise ValueError("flow-aware LSTM requires flow_history")
            all_flow = transition_flow(flow_history, len(positions))
            selected_flow = all_flow[-(self.history_length - 1) :]
            features = np.concatenate((velocity, selected_flow), axis=1)
        else:
            features = velocity
        normalized = (features[None, ...] - self._x_mean) / self._x_scale
        tensor = torch.as_tensor(
            normalized, dtype=torch.float32, device=self._resolved_device
        )
        self._model.eval()
        with torch.inference_mode():
            normalized_prediction = self._model(tensor).cpu().numpy()
        relative = normalized_prediction * self._y_scale + self._y_mean
        all_positions = positions[-1] + relative[0]
        predicted = all_positions[requested - 1]
        return PredictionResult(
            requested,
            predicted,
            metadata={
                "algorithm": self.name,
                "use_flow": self.use_flow,
                "history_length": self.history_length,
                "max_horizon": self.max_horizon,
                "seed": self.seed,
            },
        )

    def save(self, path: str | Path) -> Path:
        if self._model is None or self._x_mean is None:
            raise RuntimeError("cannot save an unfitted model")
        torch, _ = _require_torch()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "config": {
                    "history_length": self.history_length,
                    "max_horizon": self.max_horizon,
                    "hidden_size": self.hidden_size,
                    "num_layers": self.num_layers,
                    "dropout": self.dropout,
                    "use_flow": self.use_flow,
                    "seed": self.seed,
                },
                "state_dict": self._model.state_dict(),
                "x_mean": self._x_mean,
                "x_scale": self._x_scale,
                "y_mean": self._y_mean,
                "y_scale": self._y_scale,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: str | Path, *, device: str = "auto") -> "LSTMPredictor":
        torch, _ = _require_torch()
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        predictor = cls(device=device, **checkpoint["config"])
        _, model = predictor._build_model()
        model.load_state_dict(checkpoint["state_dict"])
        predictor._x_mean = np.asarray(checkpoint["x_mean"], dtype=np.float32)
        predictor._x_scale = np.asarray(checkpoint["x_scale"], dtype=np.float32)
        predictor._y_mean = np.asarray(checkpoint["y_mean"], dtype=np.float32)
        predictor._y_scale = np.asarray(checkpoint["y_scale"], dtype=np.float32)
        return predictor
