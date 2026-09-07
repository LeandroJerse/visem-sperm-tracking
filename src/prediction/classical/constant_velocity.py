"""Baseline clássico de velocidade constante."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    robust_velocity,
    validate_prediction_inputs,
)


class ConstantVelocityPredictor(TrajectoryPredictor):
    """Extrapola uma velocidade recente robusta, sem usar fluxo ambiental."""

    name = "constant_velocity"

    def __init__(self, *, window: int | None = 5, method: str = "median") -> None:
        self.window = window
        self.method = method

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        positions, requested = validate_prediction_inputs(history, horizons)
        velocity = robust_velocity(positions, window=self.window, method=self.method)
        predicted = positions[-1] + requested[:, None] * velocity
        return PredictionResult(
            requested,
            predicted,
            metadata={"algorithm": self.name, "velocity": velocity.tolist()},
        )
