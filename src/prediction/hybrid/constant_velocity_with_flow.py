"""Velocidade constante híbrida com compensação do fluxo aparente."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    future_step_flow,
    remove_environmental_motion,
    robust_velocity,
    validate_prediction_inputs,
)


class FlowAwareConstantVelocityPredictor(TrajectoryPredictor):
    """Estima a velocidade intrínseca e soma o fluxo ambiental futuro.

    O movimento aparente observado é removido de cada deslocamento antes da
    estimação robusta da velocidade própria. Se ``future_flow`` não for
    fornecido, o último fluxo observado é mantido constante e a hipótese fica
    registrada nos metadados do resultado.
    """

    name = "flow_aware_constant_velocity"
    uses_flow = True

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
        if flow_history is None:
            raise ValueError("flow-aware constant velocity requires flow_history")
        intrinsic_history, _, observed_flow = remove_environmental_motion(
            positions, flow_history
        )
        intrinsic_velocity = robust_velocity(
            intrinsic_history, window=self.window, method=self.method
        )
        fallback = observed_flow[-1] if len(observed_flow) else np.zeros(2, dtype=np.float32)
        step_flow = future_step_flow(
            future_flow, int(requested[-1]), fallback=fallback
        )
        cumulative_flow = np.cumsum(step_flow, axis=0)
        predicted = np.stack(
            [
                positions[-1] + horizon * intrinsic_velocity + cumulative_flow[horizon - 1]
                for horizon in requested
            ]
        )
        return PredictionResult(
            requested,
            predicted,
            metadata={
                "algorithm": self.name,
                "intrinsic_velocity": intrinsic_velocity.tolist(),
                "future_flow_assumption": (
                    "provided" if future_flow is not None else "last_observed"
                ),
            },
        )
