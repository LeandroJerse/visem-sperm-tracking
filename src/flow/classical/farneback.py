"""Dense Gunnar Farneback optical flow."""
from __future__ import annotations

import numpy as np

from ..base import (
    FlowEstimator,
    FlowResult,
    OptionalDependencyError,
    as_gray_u8,
    normalize_mask,
    validate_frame_pair,
)


def _require_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise OptionalDependencyError(
            "FarnebackFlow requires opencv-python (pip install opencv-python)"
        ) from exc
    return cv2


class FarnebackFlow(FlowEstimator):
    """OpenCV's classical dense polynomial-expansion flow baseline."""

    name = "farneback"

    def __init__(
        self,
        *,
        pyr_scale: float = 0.5,
        levels: int = 4,
        winsize: int = 21,
        iterations: int = 5,
        poly_n: int = 7,
        poly_sigma: float = 1.5,
        gaussian: bool = True,
    ) -> None:
        if not 0 < pyr_scale < 1:
            raise ValueError("pyr_scale must be between 0 and 1")
        if levels <= 0 or winsize <= 0 or iterations <= 0:
            raise ValueError("levels, winsize, and iterations must be positive")
        if poly_n not in (5, 7):
            raise ValueError("OpenCV Farneback supports poly_n=5 or poly_n=7")
        self.pyr_scale = float(pyr_scale)
        self.levels = int(levels)
        self.winsize = int(winsize)
        self.iterations = int(iterations)
        self.poly_n = int(poly_n)
        self.poly_sigma = float(poly_sigma)
        self.gaussian = bool(gaussian)

    def estimate(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        cv2 = _require_cv2()
        previous, following = validate_frame_pair(previous_frame, next_frame)
        previous_gray = as_gray_u8(previous)
        next_gray = as_gray_u8(following)
        include = normalize_mask(mask, previous_gray.shape)
        flags = cv2.OPTFLOW_FARNEBACK_GAUSSIAN if self.gaussian else 0
        flow = cv2.calcOpticalFlowFarneback(
            previous_gray,
            next_gray,
            None,
            self.pyr_scale,
            self.levels,
            self.winsize,
            self.iterations,
            self.poly_n,
            self.poly_sigma,
            flags,
        ).astype(np.float32, copy=False)
        flow[~include] = 0.0
        return FlowResult(
            flow,
            include,
            None,
            {"algorithm": self.name, "dense": True},
        )
