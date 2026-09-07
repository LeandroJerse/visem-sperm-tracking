"""Dependency-free classical Horn--Schunck optical flow."""
from __future__ import annotations

import numpy as np

from ..base import (
    FlowEstimator,
    FlowResult,
    as_gray_float,
    normalize_mask,
    validate_frame_pair,
)


def _neighbour_average(field: np.ndarray) -> np.ndarray:
    """Horn--Schunck's weighted eight-neighbour average."""

    padded = np.pad(field, 1, mode="edge")
    axial = (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
    ) / 6.0
    diagonal = (
        padded[:-2, :-2]
        + padded[:-2, 2:]
        + padded[2:, :-2]
        + padded[2:, 2:]
    ) / 12.0
    return (axial + diagonal).astype(np.float32, copy=False)


def _spatial_derivatives(
    previous: np.ndarray, following: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Symmetric derivatives for the brightness-constancy constraint."""

    previous_y, previous_x = np.gradient(previous)
    following_y, following_x = np.gradient(following)
    ix = 0.5 * (previous_x + following_x)
    iy = 0.5 * (previous_y + following_y)
    it = following - previous
    return (
        ix.astype(np.float32, copy=False),
        iy.astype(np.float32, copy=False),
        it.astype(np.float32, copy=False),
    )


class HornSchunckFlow(FlowEstimator):
    """Global smoothness baseline from Horn and Schunck (1981).

    This is the classical, single-scale method: it is most appropriate for
    small inter-frame displacements.  ``tolerance`` provides an efficiency
    adaptation without changing the objective; setting it to zero always runs
    exactly ``iterations`` updates.
    """

    name = "horn_schunck"

    def __init__(
        self,
        *,
        alpha: float = 0.08,
        iterations: int = 150,
        tolerance: float = 1e-4,
    ) -> None:
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        self.alpha = float(alpha)
        self.iterations = int(iterations)
        self.tolerance = float(tolerance)

    def estimate(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        previous, following = validate_frame_pair(previous_frame, next_frame)
        previous_gray = as_gray_float(previous)
        next_gray = as_gray_float(following)
        include = normalize_mask(mask, previous_gray.shape)
        ix, iy, it = _spatial_derivatives(previous_gray, next_gray)
        u = np.zeros_like(previous_gray, dtype=np.float32)
        v = np.zeros_like(previous_gray, dtype=np.float32)
        denominator = self.alpha**2 + ix * ix + iy * iy
        performed = 0

        for iteration in range(self.iterations):
            u_average = _neighbour_average(u)
            v_average = _neighbour_average(v)
            constraint = ix * u_average + iy * v_average + it
            update = constraint / np.maximum(denominator, np.finfo(np.float32).eps)
            next_u = u_average - ix * update
            next_v = v_average - iy * update
            next_u[~include] = 0.0
            next_v[~include] = 0.0
            performed = iteration + 1
            if self.tolerance > 0:
                delta = max(
                    float(np.max(np.abs(next_u - u))),
                    float(np.max(np.abs(next_v - v))),
                )
                u, v = next_u, next_v
                if delta <= self.tolerance:
                    break
            else:
                u, v = next_u, next_v

        flow = np.stack((u, v), axis=-1).astype(np.float32, copy=False)
        gradient_strength = np.hypot(ix, iy)
        confidence = gradient_strength / (gradient_strength + self.alpha)
        confidence[~include] = 0.0
        return FlowResult(
            flow,
            include,
            confidence,
            {
                "algorithm": self.name,
                "alpha": self.alpha,
                "iterations_requested": self.iterations,
                "iterations_performed": performed,
                "single_scale": True,
                "dense": True,
            },
        )
