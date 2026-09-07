"""Small NumPy constant-velocity Kalman filter for bounding boxes."""
from __future__ import annotations

import numpy as np


class BoundingBoxKalmanFilter:
    """Track ``(cx, cy, w, h)`` and their four velocities.

    Keeping width and height directly is better behaved for very small objects
    than the area/aspect-ratio parameterization commonly used by pedestrian
    SORT implementations.
    """

    def __init__(
        self,
        bbox: np.ndarray,
        *,
        process_noise: float = 1.0,
        measurement_noise: float = 4.0,
        min_size: float = 1.0,
    ) -> None:
        measurement = np.asarray(bbox, dtype=float).reshape(4)
        if not np.all(np.isfinite(measurement)) or np.any(measurement[2:] <= 0):
            raise ValueError("Initial bbox must be finite with positive size")
        if process_noise <= 0 or measurement_noise <= 0 or min_size <= 0:
            raise ValueError("Kalman noise and minimum size must be positive")
        self.process_noise = float(process_noise)
        self.measurement_noise = float(measurement_noise)
        self.min_size = float(min_size)

        self.x = np.zeros(8, dtype=float)
        self.x[:4] = measurement
        self.P = np.diag([10.0, 10.0, 10.0, 10.0, 100.0, 100.0, 25.0, 25.0])
        self.H = np.zeros((4, 8), dtype=float)
        self.H[:, :4] = np.eye(4)
        self.R = np.eye(4, dtype=float) * self.measurement_noise

    def predict(self, dt: float = 1.0) -> np.ndarray:
        if dt <= 0:
            raise ValueError("dt must be positive")
        identity = np.eye(4, dtype=float)
        transition = np.block(
            [[identity, identity * dt], [np.zeros((4, 4)), identity]]
        )
        q11 = (dt**4) / 4.0
        q12 = (dt**3) / 2.0
        q22 = dt**2
        process = self.process_noise * np.block(
            [[identity * q11, identity * q12], [identity * q12, identity * q22]]
        )
        self.x = transition @ self.x
        self.P = transition @ self.P @ transition.T + process
        self._constrain_size()
        return self.bbox

    def update(self, bbox: np.ndarray) -> np.ndarray:
        measurement = np.asarray(bbox, dtype=float).reshape(4)
        if not np.all(np.isfinite(measurement)) or np.any(measurement[2:] <= 0):
            raise ValueError("Measured bbox must be finite with positive size")
        innovation = measurement - self.H @ self.x
        innovation_covariance = self.H @ self.P @ self.H.T + self.R
        cross_covariance = self.P @ self.H.T
        try:
            gain = np.linalg.solve(innovation_covariance.T, cross_covariance.T).T
        except np.linalg.LinAlgError:  # defensive fallback for degenerate covariance
            gain = cross_covariance @ np.linalg.pinv(innovation_covariance)
        self.x = self.x + gain @ innovation
        identity = np.eye(8, dtype=float)
        residual = identity - gain @ self.H
        # Joseph form preserves symmetry/positive semi-definiteness better.
        self.P = residual @ self.P @ residual.T + gain @ self.R @ gain.T
        self._constrain_size()
        return self.bbox

    def add_position_offset(self, dx: float, dy: float) -> None:
        if not np.isfinite(dx) or not np.isfinite(dy):
            return
        self.x[0] += float(dx)
        self.x[1] += float(dy)

    def _constrain_size(self) -> None:
        for index in (2, 3):
            if self.x[index] < self.min_size:
                self.x[index] = self.min_size
                if self.x[index + 4] < 0:
                    self.x[index + 4] = 0.0

    @property
    def bbox(self) -> np.ndarray:
        value = self.x[:4].copy()
        value[2:] = np.maximum(value[2:], self.min_size)
        return value

    @property
    def velocity(self) -> np.ndarray:
        return self.x[4:].copy()
