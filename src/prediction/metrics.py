"""Trajectory displacement metrics with explicit horizon alignment."""
from __future__ import annotations

from numbers import Integral
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
    """Historical float32 mean over reported steps, which may be sparse.

    For reported horizons [1,5,10], this averages three endpoint errors; it is
    not dense ADE over steps 1..10. Use dense_trajectory_metrics for that scope.
    """

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
    """Historical float32 metrics over reported, potentially sparse horizons.

    ``ade`` averages only the supplied steps, not missing intervening steps.
    This function remains unchanged numerically for historical consumers.
    """

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


def _strict_metric_horizons(values: Sequence[int], name: str) -> tuple[int, ...]:
    try:
        requested = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be an explicit sequence of integers") from exc
    if (not requested or any(isinstance(value, (bool, np.bool_))
                             or not isinstance(value, Integral) or value <= 0 for value in requested)):
        raise ValueError(f"{name} must contain positive integers, without booleans or coercion")
    if any(right <= left for left, right in zip(requested, requested[1:])):
        raise ValueError(f"{name} must be unique and increasing")
    return tuple(int(value) for value in requested)


def _metric_batch(values: np.ndarray, name: str) -> np.ndarray:
    if (not isinstance(values, np.ndarray) or np.ma.isMaskedArray(values) or values.ndim != 3
            or values.shape[0] == 0 or values.shape[1] == 0 or values.shape[2] != 2):
        raise ValueError(f"{name} must have shape (N>0, Hmax>0, 2)")
    if values.dtype.kind not in "iuf":
        raise ValueError(f"{name} must have a real numeric dtype, excluding bool/object/complex")
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.asarray(values, dtype=np.float64)
    except (ValueError, OverflowError, FloatingPointError) as exc:
        raise ValueError(f"{name} cannot be represented as finite float64") from exc
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite positions")
    return result


def dense_trajectory_metrics(
    predicted: np.ndarray,
    target_positions: np.ndarray,
    *,
    horizons: Sequence[int],
    report_horizons: Sequence[int] = (1, 5, 10),
) -> dict[str, np.ndarray]:
    """Per-window float64 ADE_H/FDE_H in pixels over a dense future 1..Hmax.

    Both batches must be [N,Hmax,2], with explicitly aligned horizons exactly
    1..Hmax. ADE_H averages every Euclidean error from step 1 through H; FDE_H
    uses step H only. Keys ``ade_h1``, ``fde_h1``, etc. contain arrays [N].
    Nothing is aggregated over windows, trajectories, segments or videos here.
    Real numeric arrays are converted directly to float64; no missing step,
    interpolation or non-finite arithmetic is accepted.
    """
    positions = _metric_batch(predicted, "predicted")
    targets = _metric_batch(target_positions, "target_positions")
    if positions.shape != targets.shape:
        raise ValueError("predicted and target_positions must have exactly the same shape")
    dense = _strict_metric_horizons(horizons, "horizons")
    if dense != tuple(range(1, positions.shape[1] + 1)):
        raise ValueError("horizons must be exactly the dense future 1..Hmax")
    reports = _strict_metric_horizons(report_horizons, "report_horizons")
    if reports[-1] > positions.shape[1]:
        raise ValueError("report_horizons must lie inside the dense future")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            differences = positions - targets
            errors = np.hypot(differences[:, :, 0], differences[:, :, 1])
            cumulative = np.cumsum(errors, axis=1)
            result = {}
            for horizon in reports:
                result[f"ade_h{horizon}"] = cumulative[:, horizon - 1] / horizon
                result[f"fde_h{horizon}"] = errors[:, horizon - 1].copy()
    except (OverflowError, FloatingPointError) as exc:
        raise ValueError("dense metric arithmetic overflowed") from exc
    if any(not np.isfinite(values).all() for values in result.values()):
        raise ValueError("dense metrics produced non-finite values")
    return result
