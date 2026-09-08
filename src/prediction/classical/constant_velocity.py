"""Baseline clássico de velocidade constante."""
from __future__ import annotations

from numbers import Integral
from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    robust_velocity,
    validate_prediction_inputs,
)
from .persistence import _validate_batch_inputs


class ConstantVelocityPredictor(TrajectoryPredictor):
    """Extrapola uma velocidade recente robusta, sem usar fluxo ambiental."""

    name = "constant_velocity"

    def __init__(self, *, window: int | None = 5, method: str = "median") -> None:
        self.window = window
        self.method = method

    def predict_batch(
        self, histories: np.ndarray, horizons: Sequence[int] = range(1, 11),
    ) -> np.ndarray:
        """Extrapolate in float64 [N,H,2], using observed differences only.

        The default is the component-wise median of the last five observed
        differences (six positions). A shorter valid history uses all available
        differences. ``window=None`` and the historical mean/last estimators
        remain available, but a scientific run must register its choice before
        data. No target, future position or flow input is accepted here.
        """
        positions, requested = _validate_batch_inputs(histories, horizons, minimum_history=2)
        if self.window is not None and (
            isinstance(self.window, (bool, np.bool_)) or not isinstance(self.window, Integral)
            or self.window <= 0
        ):
            raise ValueError("window must be a positive integer or None")
        if not isinstance(self.method, str) or self.method not in {"median", "mean", "last"}:
            raise ValueError("method must be 'median', 'mean', or 'last'")
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                recent_positions = (positions if self.window is None
                                    else positions[:, -(int(self.window) + 1):, :])
                differences = np.diff(recent_positions, axis=1)
                if self.method == "median":
                    velocity = np.median(differences, axis=1)
                elif self.method == "mean":
                    velocity = np.mean(differences, axis=1)
                else:
                    velocity = differences[:, -1, :]
                predicted = positions[:, -1:, :] + requested[None, :, None] * velocity[:, None, :]
        except (OverflowError, FloatingPointError) as exc:
            raise ValueError("constant-velocity batch arithmetic overflowed") from exc
        if not np.isfinite(predicted).all():
            raise ValueError("constant-velocity batch produced non-finite positions")
        return predicted

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        """Historical single-trajectory API, preserving its float32 behavior."""
        positions, requested = validate_prediction_inputs(history, horizons)
        velocity = robust_velocity(positions, window=self.window, method=self.method)
        predicted = positions[-1] + requested[:, None] * velocity
        return PredictionResult(
            requested,
            predicted,
            metadata={"algorithm": self.name, "velocity": velocity.tolist()},
        )
