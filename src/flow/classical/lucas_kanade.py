"""Sparse pyramidal Lucas--Kanade optical flow."""
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
            "LucasKanadeFlow requires opencv-python (pip install opencv-python)"
        ) from exc
    return cv2


class LucasKanadeFlow(FlowEstimator):
    """Classical sparse LK with pyramids and a forward/backward reliability test.

    Vectors are stored only at the original feature coordinates.  Consumers
    must respect ``FlowResult.valid`` instead of interpreting zero-filled
    unmeasured pixels as zero motion.
    """

    name = "lucas_kanade"

    def __init__(
        self,
        *,
        max_corners: int = 1200,
        quality_level: float = 0.01,
        min_distance: float = 5.0,
        block_size: int = 7,
        win_size: tuple[int, int] = (21, 21),
        max_level: int = 3,
        max_iterations: int = 30,
        epsilon: float = 0.01,
        forward_backward_threshold: float = 1.5,
        min_eigen_threshold: float = 1e-4,
    ) -> None:
        if max_corners <= 0 or quality_level <= 0 or min_distance < 0:
            raise ValueError("invalid feature-detection parameters")
        if forward_backward_threshold < 0:
            raise ValueError("forward_backward_threshold must be non-negative")
        self.max_corners = int(max_corners)
        self.quality_level = float(quality_level)
        self.min_distance = float(min_distance)
        self.block_size = int(block_size)
        self.win_size = tuple(int(v) for v in win_size)
        self.max_level = int(max_level)
        self.max_iterations = int(max_iterations)
        self.epsilon = float(epsilon)
        self.forward_backward_threshold = float(forward_backward_threshold)
        self.min_eigen_threshold = float(min_eigen_threshold)

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
        feature_mask = (include.astype(np.uint8) * 255)

        points0 = cv2.goodFeaturesToTrack(
            previous_gray,
            maxCorners=self.max_corners,
            qualityLevel=self.quality_level,
            minDistance=self.min_distance,
            mask=feature_mask,
            blockSize=self.block_size,
        )
        height, width = previous_gray.shape
        flow = np.zeros((height, width, 2), dtype=np.float32)
        valid = np.zeros((height, width), dtype=bool)
        confidence = np.zeros((height, width), dtype=np.float32)
        if points0 is None or len(points0) == 0:
            return FlowResult(
                flow,
                valid,
                confidence,
                {"algorithm": self.name, "tracked_points": 0},
            )

        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            self.max_iterations,
            self.epsilon,
        )
        lk_args = dict(
            winSize=self.win_size,
            maxLevel=self.max_level,
            criteria=criteria,
            minEigThreshold=self.min_eigen_threshold,
        )
        points1, status_forward, error_forward = cv2.calcOpticalFlowPyrLK(
            previous_gray, next_gray, points0, None, **lk_args
        )
        if points1 is None or status_forward is None:
            return FlowResult(
                flow,
                valid,
                confidence,
                {"algorithm": self.name, "tracked_points": 0},
            )
        points0_back, status_back, _ = cv2.calcOpticalFlowPyrLK(
            next_gray, previous_gray, points1, None, **lk_args
        )
        if points0_back is None or status_back is None:
            status_back = np.zeros_like(status_forward)
            points0_back = np.full_like(points0, np.nan)

        p0 = points0.reshape(-1, 2)
        p1 = points1.reshape(-1, 2)
        p0_back = points0_back.reshape(-1, 2)
        fb_error = np.linalg.norm(p0_back - p0, axis=1)
        tracking_error = (
            np.zeros(len(p0), dtype=np.float32)
            if error_forward is None
            else np.maximum(error_forward.reshape(-1), 0.0)
        )
        good = (
            status_forward.reshape(-1).astype(bool)
            & status_back.reshape(-1).astype(bool)
            & np.isfinite(p1).all(axis=1)
            & np.isfinite(fb_error)
            & (fb_error <= self.forward_backward_threshold)
            & (p1[:, 0] >= 0)
            & (p1[:, 0] < width)
            & (p1[:, 1] >= 0)
            & (p1[:, 1] < height)
        )

        # More than one feature may round to the same source pixel.  Keep the
        # most reliable one to preserve a well-defined vector at that pixel.
        best_confidence: dict[tuple[int, int], float] = {}
        for source, target, fb, lk_error in zip(
            p0[good], p1[good], fb_error[good], tracking_error[good]
        ):
            x = int(np.clip(np.rint(source[0]), 0, width - 1))
            y = int(np.clip(np.rint(source[1]), 0, height - 1))
            if not include[y, x]:
                continue
            score = float(1.0 / (1.0 + fb + np.sqrt(lk_error)))
            if score <= best_confidence.get((y, x), -1.0):
                continue
            best_confidence[(y, x)] = score
            flow[y, x] = target - source
            valid[y, x] = True
            confidence[y, x] = score

        return FlowResult(
            flow,
            valid,
            confidence,
            {
                "algorithm": self.name,
                "detected_points": int(len(points0)),
                "tracked_points": int(valid.sum()),
                "forward_backward_threshold": self.forward_backward_threshold,
                "sparse": True,
            },
        )
