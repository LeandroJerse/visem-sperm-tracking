"""Hybrid SORT variant with flow prior and ambiguity-aware distance gates."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ..assignment import (
    match_cost_matrix,
    pairwise_center_distance,
    pairwise_iou,
)
from ..base import FlowInput
from ..classical.sort import SortTracker
from ..flow import sample_flow
from ..types import TrackDetection, TrackResult


class AdaptiveFlowSortTracker(SortTracker):
    """SORT hybrid adapted for small, erratically moving microscopy objects.

    The Kalman prediction is shifted by optional local optical flow. Association
    combines normalized center distance and IoU.  Its distance gate expands for
    a fast track but is capped by local detection spacing in dense scenes to
    reduce identity swaps.  The separate class keeps the pure SORT baseline
    scientifically comparable.
    """

    name = "adaptive_flow_sort"

    def __init__(
        self,
        *,
        base_distance: float = 18.0,
        min_distance: float = 4.0,
        velocity_scale: float = 1.5,
        density_fraction: float = 0.75,
        flow_weight: float = 1.0,
        flow_window_scale: float = 1.5,
        distance_weight: float = 0.7,
        iou_weight: float = 0.3,
        minimum_iou_override: float = 0.1,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if base_distance <= 0 or min_distance <= 0 or min_distance > base_distance:
            raise ValueError("Require 0 < min_distance <= base_distance")
        if velocity_scale < 0 or density_fraction <= 0:
            raise ValueError("velocity_scale must be >= 0 and density_fraction > 0")
        if flow_weight < 0 or flow_window_scale <= 0:
            raise ValueError("flow_weight must be >= 0 and flow_window_scale > 0")
        if distance_weight < 0 or iou_weight < 0 or distance_weight + iou_weight <= 0:
            raise ValueError("Association weights must be non-negative and not both zero")
        if not 0.0 <= minimum_iou_override <= 1.0:
            raise ValueError("minimum_iou_override must be in [0, 1]")
        weight_sum = distance_weight + iou_weight
        self.base_distance = float(base_distance)
        self.min_distance = float(min_distance)
        self.velocity_scale = float(velocity_scale)
        self.density_fraction = float(density_fraction)
        self.flow_weight = float(flow_weight)
        self.flow_window_scale = float(flow_window_scale)
        self.distance_weight = float(distance_weight / weight_sum)
        self.iou_weight = float(iou_weight / weight_sum)
        self.minimum_iou_override = float(minimum_iou_override)

    def _predict_tracks(self, flow: FlowInput = None) -> None:
        for track in self._tracks:
            predicted = track.predict()
            if flow is not None and self.flow_weight > 0:
                u, v = sample_flow(
                    flow, predicted, window_scale=self.flow_window_scale
                )
                track.kf.add_position_offset(
                    self.flow_weight * u, self.flow_weight * v
                )

    @staticmethod
    def _typical_detection_spacing(detection_boxes: np.ndarray) -> float | None:
        if len(detection_boxes) < 2:
            return None
        distances = pairwise_center_distance(detection_boxes, detection_boxes)
        np.fill_diagonal(distances, np.inf)
        nearest = np.min(distances, axis=1)
        finite = nearest[np.isfinite(nearest)]
        return float(np.median(finite)) if finite.size else None

    def _associate_adaptive(
        self, observations: list[TrackDetection]
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        if not self._tracks or not observations:
            return [], list(range(len(self._tracks))), list(range(len(observations)))
        track_boxes = np.asarray([track.kf.bbox for track in self._tracks], dtype=float)
        detection_boxes = np.asarray(
            [[det.cx, det.cy, det.w, det.h] for det in observations], dtype=float
        )
        distances = pairwise_center_distance(track_boxes, detection_boxes)
        ious = pairwise_iou(track_boxes, detection_boxes)
        spacing = self._typical_detection_spacing(detection_boxes)

        gates = np.asarray(
            [
                self.base_distance
                + self.velocity_scale * np.linalg.norm(track.kf.velocity[:2])
                for track in self._tracks
            ],
            dtype=float,
        )
        if spacing is not None:
            density_cap = max(self.min_distance, self.density_fraction * spacing)
            gates = np.minimum(gates, density_cap)
        gates = np.maximum(gates, self.min_distance)

        normalized_distance = distances / gates[:, None]
        cost = (
            self.distance_weight * normalized_distance
            + self.iou_weight * (1.0 - ious)
        )
        valid = (distances <= gates[:, None]) | (ious >= self.minimum_iou_override)
        cost[~valid] = np.inf
        if self.class_aware:
            for track_index, track in enumerate(self._tracks):
                for detection_index, detection in enumerate(observations):
                    if track.class_id != detection.class_id:
                        cost[track_index, detection_index] = np.inf
        return match_cost_matrix(cost)

    def update(
        self,
        detections: Sequence[TrackDetection | Any],
        *,
        frame_index: int | None = None,
        flow: FlowInput = None,
    ) -> list[TrackResult]:
        observations = self._coerce_detections(detections)
        frame = self._begin_frame(frame_index)
        self._predict_tracks(flow)
        matches, _, unmatched_detections = self._associate_adaptive(observations)
        self._update_matches(matches, observations)
        for detection_index in unmatched_detections:
            self._spawn(observations[detection_index])
        return self._finish_frame(frame)
