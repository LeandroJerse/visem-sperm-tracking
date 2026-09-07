"""Robust hybrid flow: classical baseline, optional RAFT refinement, camera compensation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..base import (
    FlowEstimator,
    FlowResult,
    OptionalDependencyError,
    as_gray_u8,
    normalize_mask,
    validate_frame_pair,
)
from ..classical.farneback import FarnebackFlow
from ..metrics import forward_backward_consistency


def _require_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise OptionalDependencyError(
            "global camera compensation requires opencv-python"
        ) from exc
    return cv2


@dataclass(frozen=True)
class GlobalMotion:
    """Robust affine camera-motion estimate and its dense displacement."""

    matrix: np.ndarray
    flow: np.ndarray
    inlier_fraction: float
    points_used: int


def estimate_global_motion(
    previous_frame: np.ndarray,
    next_frame: np.ndarray,
    mask: np.ndarray | None = None,
    *,
    max_corners: int = 1000,
    ransac_threshold: float = 2.0,
) -> GlobalMotion:
    """Estimate global affine camera motion from RANSAC-filtered LK tracks."""

    cv2 = _require_cv2()
    previous, following = validate_frame_pair(previous_frame, next_frame)
    previous_gray = as_gray_u8(previous)
    next_gray = as_gray_u8(following)
    include = normalize_mask(mask, previous_gray.shape)
    points0 = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=int(max_corners),
        qualityLevel=0.01,
        minDistance=7.0,
        blockSize=7,
        mask=include.astype(np.uint8) * 255,
    )
    identity = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    matrix = identity
    inlier_fraction = 0.0
    points_used = 0
    if points0 is not None and len(points0) >= 3:
        points1, status, _ = cv2.calcOpticalFlowPyrLK(
            previous_gray,
            next_gray,
            points0,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(
                cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                30,
                0.01,
            ),
        )
        if points1 is not None and status is not None:
            good = status.reshape(-1).astype(bool) & np.isfinite(points1.reshape(-1, 2)).all(axis=1)
            source = points0.reshape(-1, 2)[good]
            target = points1.reshape(-1, 2)[good]
            points_used = int(len(source))
            if points_used >= 3:
                estimated, inliers = cv2.estimateAffinePartial2D(
                    source,
                    target,
                    method=cv2.RANSAC,
                    ransacReprojThreshold=float(ransac_threshold),
                    maxIters=2000,
                    confidence=0.99,
                    refineIters=10,
                )
                if estimated is not None and np.isfinite(estimated).all():
                    matrix = estimated.astype(np.float32)
                    if inliers is not None and len(inliers):
                        inlier_fraction = float(np.mean(inliers.astype(bool)))

    height, width = previous_gray.shape
    y, x = np.mgrid[:height, :width].astype(np.float32)
    target_x = matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]
    target_y = matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]
    global_flow = np.stack((target_x - x, target_y - y), axis=-1).astype(np.float32)
    return GlobalMotion(matrix, global_flow, inlier_fraction, points_used)


class RobustHybridFlow(FlowEstimator):
    """Reliable flow for microscopy without hiding the underlying baselines.

    The default is Farneback followed by forward/backward rejection and robust
    camera-motion subtraction.  A second estimator (normally RAFT) can refine
    valid pixels by weighted fusion; it is optional so the classical-only
    hybrid remains inexpensive.  An include-mask should exclude sperm cells
    and artifacts when the scientific target is apparent background motion.

    This estimator returns *camera-compensated residual motion* when
    ``compensate_global=True``.  The removed affine field and matrix are kept in
    metadata for reproducibility.
    """

    name = "robust_hybrid"

    def __init__(
        self,
        *,
        base: FlowEstimator | None = None,
        refiner: FlowEstimator | None = None,
        refiner_weight: float = 0.5,
        compensate_global: bool = True,
        reject_inconsistent: bool = True,
        consistency_threshold: float = 1.5,
        global_max_corners: int = 1000,
        global_ransac_threshold: float = 2.0,
    ) -> None:
        if not 0 <= refiner_weight <= 1:
            raise ValueError("refiner_weight must be in [0, 1]")
        if consistency_threshold < 0:
            raise ValueError("consistency_threshold must be non-negative")
        self.base = base if base is not None else FarnebackFlow()
        self.refiner = refiner
        self.refiner_weight = float(refiner_weight)
        self.compensate_global = bool(compensate_global)
        self.reject_inconsistent = bool(reject_inconsistent)
        self.consistency_threshold = float(consistency_threshold)
        self.global_max_corners = int(global_max_corners)
        self.global_ransac_threshold = float(global_ransac_threshold)

    def reset(self) -> None:
        self.base.reset()
        if self.refiner is not None:
            self.refiner.reset()

    def estimate(
        self,
        previous_frame: np.ndarray,
        next_frame: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> FlowResult:
        previous, following = validate_frame_pair(previous_frame, next_frame)
        include = normalize_mask(mask, previous.shape[:2])
        base_forward = self.base.estimate(previous, following, mask=include)
        combined = base_forward.flow.copy()
        valid = base_forward.valid.copy()
        confidence = (
            np.ones(valid.shape, dtype=np.float32)
            if base_forward.confidence is None
            else base_forward.confidence.copy()
        )

        consistency_mean = None
        if self.reject_inconsistent:
            base_backward = self.base.estimate(following, previous, mask=include)
            check = forward_backward_consistency(
                base_forward, base_backward, threshold=self.consistency_threshold
            )
            valid &= check.consistent
            confidence *= np.exp(
                -np.nan_to_num(check.error, nan=np.inf) /
                max(self.consistency_threshold, np.finfo(np.float32).eps)
            ).astype(np.float32)
            consistency_mean = check.mean_error

        refiner_name = None
        if self.refiner is not None:
            refined = self.refiner.estimate(previous, following, mask=include)
            refiner_name = self.refiner.name
            both = valid & refined.valid
            only_refiner = (~valid) & refined.valid
            weight = self.refiner_weight
            combined[both] = (1.0 - weight) * combined[both] + weight * refined.flow[both]
            combined[only_refiner] = refined.flow[only_refiner]
            if refined.confidence is not None:
                confidence[both] = (1.0 - weight) * confidence[both] + weight * refined.confidence[both]
                confidence[only_refiner] = refined.confidence[only_refiner]
            else:
                confidence[only_refiner] = 1.0
            valid |= refined.valid

        global_motion = None
        if self.compensate_global:
            global_motion = estimate_global_motion(
                previous,
                following,
                include,
                max_corners=self.global_max_corners,
                ransac_threshold=self.global_ransac_threshold,
            )
            combined -= global_motion.flow

        valid &= include & np.isfinite(combined).all(axis=-1)
        combined[~valid] = 0.0
        confidence[~valid] = 0.0
        metadata: dict[str, object] = {
            "algorithm": self.name,
            "base": self.base.name,
            "refiner": refiner_name,
            "refiner_weight": self.refiner_weight,
            "camera_compensated": self.compensate_global,
            "consistency_threshold": self.consistency_threshold,
            "forward_backward_mae": consistency_mean,
            "valid_fraction": float(valid.mean()),
        }
        if global_motion is not None:
            metadata.update(
                {
                    "global_affine": global_motion.matrix.tolist(),
                    "global_inlier_fraction": global_motion.inlier_fraction,
                    "global_points_used": global_motion.points_used,
                }
            )
        return FlowResult(combined, valid, confidence, metadata)
