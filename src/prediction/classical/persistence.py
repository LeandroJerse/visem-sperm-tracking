"""Baseline determinístico de persistência."""
from __future__ import annotations

from numbers import Integral
from typing import Sequence

import numpy as np

from ..base import PredictionResult, TrajectoryPredictor, validate_prediction_inputs


def _validate_batch_inputs(
    histories: np.ndarray, horizons: Sequence[int], *, minimum_history: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Strict input contract shared by the two position-only batch baselines."""
    if (not isinstance(histories, np.ndarray) or np.ma.isMaskedArray(histories) or histories.ndim != 3
            or histories.shape[0] == 0 or histories.shape[1] < minimum_history
            or histories.shape[2] != 2):
        raise ValueError(f"histories must have shape (N>0, T>={minimum_history}, 2)")
    if histories.dtype.kind not in "iuf":
        raise ValueError("histories must have a real numeric dtype, excluding bool/object/complex")
    try:
        with np.errstate(over="raise", invalid="raise"):
            positions = np.asarray(histories, dtype=np.float64)
    except (ValueError, OverflowError, FloatingPointError) as exc:
        raise ValueError("histories cannot be represented as finite float64") from exc
    if not np.isfinite(positions).all():
        raise ValueError("histories must contain only finite positions")
    try:
        values = tuple(horizons)
    except TypeError as exc:
        raise ValueError("horizons must be an explicit sequence of integers") from exc
    if (not values or any(isinstance(value, (bool, np.bool_))
                          or not isinstance(value, Integral) or value <= 0 for value in values)):
        raise ValueError("horizons must contain positive integers, without booleans or coercion")
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError("horizons must be unique and increasing")
    try:
        requested = np.asarray(values, dtype=np.int64)
    except (ValueError, OverflowError) as exc:
        raise ValueError("horizons must fit int64") from exc
    return positions, requested


class PersistencePredictor(TrajectoryPredictor):
    """Prediz que o objeto permanecerá na última posição observada."""

    name = "persistence"

    def predict_batch(
        self, histories: np.ndarray, horizons: Sequence[int] = range(1, 11),
    ) -> np.ndarray:
        """Return float64 positions [N,H,2] using only each observed last point.

        Real numeric input arrays are converted directly to float64. This does
        not recover precision already lost in an input float32 array. Unlike the
        historical ``predict`` API, no float32 intermediate/result is created.
        Empty batches and malformed or non-finite inputs are invalid.
        """
        positions, requested = _validate_batch_inputs(histories, horizons, minimum_history=1)
        return np.repeat(positions[:, -1:, :], len(requested), axis=1)

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
        predicted = np.repeat(positions[-1][None, :], len(requested), axis=0)
        return PredictionResult(requested, predicted, metadata={"algorithm": self.name})
