"""Common trajectory-prediction types and input conventions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np


@dataclass
class PredictionResult:
    """Predicted center positions at explicitly named frame horizons."""

    horizons: np.ndarray
    positions: np.ndarray
    covariance: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        horizons = np.asarray(self.horizons, dtype=int)
        positions = np.asarray(self.positions, dtype=np.float32)
        if horizons.ndim != 1 or len(horizons) == 0:
            raise ValueError("horizons must be a non-empty 1-D array")
        if np.any(horizons <= 0) or np.any(np.diff(horizons) <= 0):
            raise ValueError("horizons must be positive, unique, and increasing")
        if positions.shape != (len(horizons), 2):
            raise ValueError("positions must have shape (len(horizons), 2)")
        if not np.isfinite(positions).all():
            raise ValueError("predicted positions must be finite")
        covariance = self.covariance
        if covariance is not None:
            covariance = np.asarray(covariance, dtype=np.float32)
            if covariance.shape != (len(horizons), 2, 2):
                raise ValueError("covariance must have shape (len(horizons), 2, 2)")
        self.horizons = horizons
        self.positions = positions
        self.covariance = covariance
        self.metadata = dict(self.metadata)

    def at(self, horizon: int) -> np.ndarray:
        matches = np.flatnonzero(self.horizons == int(horizon))
        if len(matches) != 1:
            raise KeyError(f"horizon {horizon} is not present")
        return self.positions[int(matches[0])]


class TrajectoryPredictor(ABC):
    """Interface shared by deterministic, Bayesian, and learned predictors.

    ``flow_history`` is environmental displacement per observed transition and
    therefore has shape ``(len(history)-1, 2)`` (a position-aligned ``N x 2``
    array is also accepted and its last transition is ignored).
    ``future_flow`` is displacement for every future step through the maximum
    requested horizon, not only at the reported horizons.
    """

    name: str = "base"
    uses_flow: bool = False

    @abstractmethod
    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        raise NotImplementedError


def validate_prediction_inputs(
    history: np.ndarray,
    horizons: Sequence[int],
) -> tuple[np.ndarray, np.ndarray]:
    positions = np.asarray(history, dtype=np.float32)
    requested = np.asarray(tuple(horizons), dtype=int)
    if positions.ndim != 2 or positions.shape[1] != 2 or len(positions) == 0:
        raise ValueError("history must have shape (time, 2) and be non-empty")
    if not np.isfinite(positions).all():
        raise ValueError("history contains NaN or infinite values")
    if requested.ndim != 1 or len(requested) == 0:
        raise ValueError("horizons must be non-empty")
    requested = np.unique(requested)
    if np.any(requested <= 0):
        raise ValueError("horizons must be positive")
    return positions, requested


def transition_flow(flow_history: np.ndarray | None, history_length: int) -> np.ndarray:
    """Normalize observed flow to one vector for each history transition."""

    if history_length < 1:
        raise ValueError("history_length must be positive")
    expected = max(history_length - 1, 0)
    if flow_history is None:
        return np.zeros((expected, 2), dtype=np.float32)
    flow = np.asarray(flow_history, dtype=np.float32)
    if flow.shape == (history_length, 2):
        flow = flow[:-1]
    if flow.shape != (expected, 2):
        raise ValueError(
            f"flow_history must have shape ({expected}, 2) or ({history_length}, 2)"
        )
    if not np.isfinite(flow).all():
        raise ValueError("flow_history contains NaN or infinite values")
    return flow


def future_step_flow(
    future_flow: np.ndarray | None,
    max_horizon: int,
    *,
    fallback: np.ndarray | None = None,
) -> np.ndarray:
    """Normalize future environmental displacement to every prediction step."""

    if max_horizon <= 0:
        raise ValueError("max_horizon must be positive")
    if future_flow is None:
        vector = np.zeros(2, dtype=np.float32) if fallback is None else np.asarray(fallback, dtype=np.float32)
        if vector.shape != (2,) or not np.isfinite(vector).all():
            raise ValueError("fallback flow must be a finite 2-vector")
        return np.repeat(vector[None, :], max_horizon, axis=0)
    flow = np.asarray(future_flow, dtype=np.float32)
    if flow.shape == (2,):
        flow = np.repeat(flow[None, :], max_horizon, axis=0)
    if flow.ndim != 2 or flow.shape[1] != 2 or len(flow) < max_horizon:
        raise ValueError(
            "future_flow must be a 2-vector or have at least max(horizons) rows"
        )
    flow = flow[:max_horizon]
    if not np.isfinite(flow).all():
        raise ValueError("future_flow contains NaN or infinite values")
    return flow


def robust_velocity(
    positions: np.ndarray,
    *,
    window: int | None = None,
    method: str = "median",
) -> np.ndarray:
    """Estimate recent per-frame displacement robustly."""

    positions = np.asarray(positions, dtype=np.float32)
    if len(positions) < 2:
        return np.zeros(2, dtype=np.float32)
    differences = np.diff(positions, axis=0)
    if window is not None:
        if window <= 0:
            raise ValueError("window must be positive")
        differences = differences[-window:]
    if method == "median":
        return np.median(differences, axis=0).astype(np.float32)
    if method == "mean":
        return np.mean(differences, axis=0).astype(np.float32)
    if method == "last":
        return differences[-1].astype(np.float32)
    raise ValueError("method must be 'median', 'mean', or 'last'")


def remove_environmental_motion(
    history: np.ndarray, flow_history: np.ndarray | None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Transform positions to a flow-compensated coordinate system."""

    positions = np.asarray(history, dtype=np.float32)
    flows = transition_flow(flow_history, len(positions))
    cumulative = np.zeros_like(positions)
    if len(flows):
        cumulative[1:] = np.cumsum(flows, axis=0)
    return positions - cumulative, cumulative[-1], flows
