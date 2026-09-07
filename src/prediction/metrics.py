"""Trajectory displacement metrics with explicit horizon alignment."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import PredictionResult


def displacement_errors(
    predicted: PredictionResult | np.ndarray,
    target_positions: np.ndarray,
) -> np.ndarray:
    """Euclidean error at each reported horizon."""

    positions = predicted.positions if isinstance(predicted, PredictionResult) else np.asarray(predicted, dtype=np.float32)
    target = np.asarray(target_positions, dtype=np.float32)
    if positions.ndim != 2 or positions.shape[1] != 2 or target.shape != positions.shape:
        raise ValueError("predicted and target positions must share shape (horizons, 2)")
    if len(positions) == 0:
        raise ValueError("at least one prediction horizon is required")
    if not np.isfinite(positions).all() or not np.isfinite(target).all():
        raise ValueError("predicted and target positions must be finite")
    return np.linalg.norm(positions - target, axis=1).astype(np.float32)


def ade(predicted: PredictionResult | np.ndarray, target_positions: np.ndarray) -> float:
    """Average Displacement Error over all reported prediction steps."""

    errors = displacement_errors(predicted, target_positions)
    return float(errors.mean())


def fde(predicted: PredictionResult | np.ndarray, target_positions: np.ndarray) -> float:
    """Final Displacement Error at the largest reported horizon."""

    errors = displacement_errors(predicted, target_positions)
    return float(errors[-1])


def trajectory_metrics(
    predicted: PredictionResult | np.ndarray,
    target_positions: np.ndarray,
    horizons: Sequence[int] | None = None,
) -> dict[str, float]:
    """Return ADE, FDE, and one named error per horizon."""

    errors = displacement_errors(predicted, target_positions)
    if isinstance(predicted, PredictionResult):
        named_horizons = predicted.horizons
    elif horizons is not None:
        named_horizons = np.asarray(tuple(horizons), dtype=int)
    else:
        named_horizons = np.arange(1, len(errors) + 1)
    if len(named_horizons) != len(errors):
        raise ValueError("horizon count differs from prediction count")
    result = {"ade": float(errors.mean()), "fde": float(errors[-1])}
    result.update(
        {f"error_h{int(horizon)}": float(error) for horizon, error in zip(named_horizons, errors)}
    )
    return result
