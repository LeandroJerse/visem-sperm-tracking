"""Filtro de Partículas híbrido com compensação do fluxo aparente."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    future_step_flow,
    remove_environmental_motion,
    validate_prediction_inputs,
)
from ..classical.particle_filter import ParticleFilterPredictor


class FlowAwareParticleFilterPredictor(ParticleFilterPredictor):
    """Filtra o movimento intrínseco por partículas e recompõe o fluxo."""

    name = "flow_aware_particle_filter"
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
            raise ValueError("flow-aware particle filter requires flow_history")
        intrinsic_positions, environmental_offset, observed_flow = remove_environmental_motion(
            positions, flow_history
        )
        intrinsic_prediction, covariance = self._forecast(intrinsic_positions, requested)
        fallback = observed_flow[-1] if len(observed_flow) else np.zeros(2, dtype=np.float32)
        step_flow = future_step_flow(
            future_flow, int(requested[-1]), fallback=fallback
        )
        cumulative_future = np.cumsum(step_flow, axis=0)
        predicted = np.stack(
            [
                intrinsic + environmental_offset + cumulative_future[horizon - 1]
                for intrinsic, horizon in zip(intrinsic_prediction, requested)
            ]
        )
        return PredictionResult(
            requested,
            predicted,
            covariance,
            {
                "algorithm": self.name,
                "particles": self.num_particles,
                "seed": self.seed,
                "future_flow_assumption": (
                    "provided" if future_flow is not None else "last_observed"
                ),
            },
        )
