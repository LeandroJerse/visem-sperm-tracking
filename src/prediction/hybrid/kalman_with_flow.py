"""Filtro de Kalman híbrido em coordenadas compensadas pelo fluxo."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    future_step_flow,
    remove_environmental_motion,
    validate_prediction_inputs,
)
from ..classical.kalman import KalmanPredictor


class FlowAwareKalmanPredictor(KalmanPredictor):
    """Filtra o movimento intrínseco e recompõe o fluxo ambiental."""

    name = "flow_aware_kalman"
    uses_flow = True

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        positions, requested = validate_prediction_inputs(history, horizons)
        if flow_history is None:
            raise ValueError("flow-aware Kalman requires flow_history")
        intrinsic_positions, environmental_offset, observed_flow = remove_environmental_motion(
            positions, flow_history
        )
        predicted_intrinsic, covariance = self._forecast(intrinsic_positions, requested)
        fallback = observed_flow[-1] if len(observed_flow) else np.zeros(2, dtype=np.float32)
        step_flow = future_step_flow(
            future_flow, int(requested[-1]), fallback=fallback
        )
        cumulative_future = np.cumsum(step_flow, axis=0)
        predicted = np.stack(
            [
                intrinsic_position + environmental_offset + cumulative_future[horizon - 1]
                for intrinsic_position, horizon in zip(predicted_intrinsic, requested)
            ]
        )
        return PredictionResult(
            requested,
            predicted,
            covariance,
            {
                "algorithm": self.name,
                "state_model": "constant_intrinsic_velocity_plus_flow",
                "future_flow_assumption": (
                    "provided" if future_flow is not None else "last_observed"
                ),
            },
        )
