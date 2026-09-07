"""Sequential Monte Carlo trajectory predictors."""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..base import (
    PredictionResult,
    TrajectoryPredictor,
    validate_prediction_inputs,
)


def _systematic_resample(weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    positions = (rng.random() + np.arange(len(weights))) / len(weights)
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.0
    return np.searchsorted(cumulative, positions)


def _weighted_position_stats(
    particles: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    mean = np.average(particles[:, :2], axis=0, weights=weights)
    centered = particles[:, :2] - mean
    covariance = (centered * weights[:, None]).T @ centered
    return mean.astype(np.float32), covariance.astype(np.float32)


class ParticleFilterPredictor(TrajectoryPredictor):
    """Nonlinear-ready bootstrap particle filter over ``x, y, vx, vy``."""

    name = "particle_filter"

    def __init__(
        self,
        *,
        num_particles: int = 1000,
        position_process_std: float = 0.35,
        velocity_process_std: float = 0.15,
        measurement_std: float = 1.0,
        initial_position_std: float = 1.0,
        initial_velocity_std: float = 1.0,
        resample_threshold: float = 0.5,
        seed: int = 42,
    ) -> None:
        if num_particles < 10:
            raise ValueError("num_particles must be at least 10")
        if min(
            position_process_std,
            velocity_process_std,
            measurement_std,
            initial_position_std,
            initial_velocity_std,
        ) <= 0:
            raise ValueError("all standard deviations must be positive")
        if not 0 < resample_threshold <= 1:
            raise ValueError("resample_threshold must be in (0, 1]")
        self.num_particles = int(num_particles)
        self.position_process_std = float(position_process_std)
        self.velocity_process_std = float(velocity_process_std)
        self.measurement_std = float(measurement_std)
        self.initial_position_std = float(initial_position_std)
        self.initial_velocity_std = float(initial_velocity_std)
        self.resample_threshold = float(resample_threshold)
        self.seed = int(seed)

    def _propagate(self, particles: np.ndarray, rng: np.random.Generator) -> None:
        particles[:, :2] += particles[:, 2:]
        particles[:, :2] += rng.normal(
            0.0, self.position_process_std, size=(self.num_particles, 2)
        )
        particles[:, 2:] += rng.normal(
            0.0, self.velocity_process_std, size=(self.num_particles, 2)
        )

    def _filter(
        self, positions: np.ndarray, rng: np.random.Generator
    ) -> tuple[np.ndarray, np.ndarray]:
        initial_velocity = positions[1] - positions[0] if len(positions) >= 2 else np.zeros(2)
        initial_position = positions[1] if len(positions) >= 2 else positions[0]
        particles = np.empty((self.num_particles, 4), dtype=np.float64)
        particles[:, :2] = initial_position + rng.normal(
            0.0, self.initial_position_std, size=(self.num_particles, 2)
        )
        particles[:, 2:] = initial_velocity + rng.normal(
            0.0, self.initial_velocity_std, size=(self.num_particles, 2)
        )
        weights = np.full(self.num_particles, 1.0 / self.num_particles)
        inverse_variance = 1.0 / (self.measurement_std**2)
        # As in Kalman initialization, the second position already determined
        # the initial velocity and must not be assimilated twice.
        for measurement in positions[2:]:
            self._propagate(particles, rng)
            squared_distance = np.sum((particles[:, :2] - measurement) ** 2, axis=1)
            # Subtracting max log-likelihood prevents underflow on long tracks.
            log_likelihood = -0.5 * squared_distance * inverse_variance
            log_likelihood -= np.max(log_likelihood)
            weights *= np.exp(log_likelihood)
            total = float(weights.sum())
            weights = (
                np.full(self.num_particles, 1.0 / self.num_particles)
                if not np.isfinite(total) or total <= 0
                else weights / total
            )
            effective_size = 1.0 / float(np.sum(weights**2))
            if effective_size < self.resample_threshold * self.num_particles:
                indices = _systematic_resample(weights, rng)
                particles = particles[indices]
                weights.fill(1.0 / self.num_particles)
        return particles, weights

    def _forecast(
        self, positions: np.ndarray, requested: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(self.seed)
        particles, weights = self._filter(positions, rng)
        means: list[np.ndarray] = []
        covariances: list[np.ndarray] = []
        requested_set = set(int(value) for value in requested)
        for step in range(1, int(requested[-1]) + 1):
            self._propagate(particles, rng)
            if step in requested_set:
                mean, covariance = _weighted_position_stats(particles, weights)
                means.append(mean)
                covariances.append(covariance)
        return np.asarray(means, dtype=np.float32), np.asarray(covariances, dtype=np.float32)

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
            {"algorithm": self.name, "particles": self.num_particles, "seed": self.seed},
        )
