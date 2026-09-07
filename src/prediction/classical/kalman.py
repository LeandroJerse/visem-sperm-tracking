"""Pure-NumPy constant-velocity Kalman predictors."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    validate_prediction_inputs,
)


def _motion_matrices(
    dt: float, process_variance: float
) -> tuple[np.ndarray, np.ndarray]:
    transition = np.array(
        [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    dt2, dt3, dt4 = dt * dt, dt**3, dt**4
    process = process_variance * np.array(
        [
            [dt4 / 4, 0, dt3 / 2, 0],
            [0, dt4 / 4, 0, dt3 / 2],
            [dt3 / 2, 0, dt2, 0],
            [0, dt3 / 2, 0, dt2],
        ],
        dtype=np.float64,
    )
    return transition, process


class KalmanPredictor(TrajectoryPredictor):
    """Classical linear Gaussian filter with state ``x, y, vx, vy``."""

    name = "kalman"

    def __init__(
        self,
        *,
        process_variance: float = 0.25,
        measurement_variance: float = 1.0,
        initial_position_variance: float = 4.0,
        initial_velocity_variance: float = 25.0,
        dt: float = 1.0,
    ) -> None:
        if process_variance < 0 or measurement_variance <= 0:
            raise ValueError("process variance >= 0 and measurement variance > 0 required")
        if initial_position_variance <= 0 or initial_velocity_variance <= 0 or dt <= 0:
            raise ValueError("initial variances and dt must be positive")
        self.process_variance = float(process_variance)
        self.measurement_variance = float(measurement_variance)
        self.initial_position_variance = float(initial_position_variance)
        self.initial_velocity_variance = float(initial_velocity_variance)
        self.dt = float(dt)

    def _filter(self, positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Two observations initialize velocity.  Start at the second position
        # and assimilate only subsequent measurements, avoiding counting the
        # second observation once in initialization and again in an update.
        velocity = positions[1] - positions[0] if len(positions) >= 2 else np.zeros(2)
        initial_position = positions[1] if len(positions) >= 2 else positions[0]
        state = np.array(
            [initial_position[0], initial_position[1], velocity[0], velocity[1]],
            dtype=np.float64,
        )
        covariance = np.diag(
            [
                self.initial_position_variance,
                self.initial_position_variance,
                self.initial_velocity_variance,
                self.initial_velocity_variance,
            ]
        ).astype(np.float64)
        transition, process = _motion_matrices(self.dt, self.process_variance)
        observation = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        measurement = np.eye(2) * self.measurement_variance
        identity = np.eye(4)
        for position in positions[2:]:
            state = transition @ state
            covariance = transition @ covariance @ transition.T + process
            innovation = position.astype(np.float64) - observation @ state
            innovation_covariance = observation @ covariance @ observation.T + measurement
            # Solve rather than invert for numerical stability.
            gain = np.linalg.solve(
                innovation_covariance, observation @ covariance
            ).T
            state = state + gain @ innovation
            # Joseph form preserves symmetry and positive semidefiniteness.
            residual = identity - gain @ observation
            covariance = (
                residual @ covariance @ residual.T + gain @ measurement @ gain.T
            )
            covariance = 0.5 * (covariance + covariance.T)
        return state, covariance

    def _forecast(
        self, positions: np.ndarray, requested: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        state, covariance = self._filter(positions)
        transition, process = _motion_matrices(self.dt, self.process_variance)
        predicted: list[np.ndarray] = []
        predicted_covariance: list[np.ndarray] = []
        requested_set = set(int(value) for value in requested)
        for step in range(1, int(requested[-1]) + 1):
            state = transition @ state
            covariance = transition @ covariance @ transition.T + process
            if step in requested_set:
                predicted.append(state[:2].copy())
                predicted_covariance.append(covariance[:2, :2].copy())
        return np.asarray(predicted, dtype=np.float32), np.asarray(predicted_covariance, dtype=np.float32)

    def predict(
        self,
        history: np.ndarray,
        horizons: Sequence[int] = (1, 5, 10),
        *,
        flow_history: np.ndarray | None = None,
        future_flow: np.ndarray | None = None,
    ) -> PredictionResult:
        positions, requested = validate_prediction_inputs(history, horizons)
        predicted, covariance = self._forecast(positions, requested)
        return PredictionResult(
            requested,
            predicted,
            covariance,
            {"algorithm": self.name, "state_model": "constant_velocity"},
        )
