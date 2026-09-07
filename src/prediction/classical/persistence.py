"""Baseline determinístico de persistência."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import PredictionResult, TrajectoryPredictor, validate_prediction_inputs


class PersistencePredictor(TrajectoryPredictor):
    """Prediz que o objeto permanecerá na última posição observada."""

    name = "persistence"

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        positions, requested = validate_prediction_inputs(history, horizons)
        predicted = np.repeat(positions[-1][None, :], len(requested), axis=0)
        return PredictionResult(requested, predicted, metadata={"algorithm": self.name})
