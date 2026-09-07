"""Greedy nearest-centroid tracking baseline."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .._state import SimpleTrackState
from ..assignment import pairwise_center_distance
from ..base import FlowInput, Tracker
from ..types import TrackDetection, TrackResult


class _DistanceTracker(Tracker):
    """Shared lifecycle for centroid-distance baselines."""

    def __init__(
        self,
        *,
        max_distance: float = 20.0,
        max_age: int = 2,
        min_hits: int = 1,
        class_aware: bool = False,
        emit_predictions: bool = False,
        emit_tentative: bool = True,
        start_id: int = 1,
    ) -> None:
        super().__init__(start_id=start_id)
        if max_distance <= 0:
            raise ValueError("max_distance must be positive")
        if max_age < 0:
            raise ValueError("max_age must be non-negative")
        if min_hits < 1:
            raise ValueError("min_hits must be at least 1")
        self.max_distance = float(max_distance)
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.class_aware = bool(class_aware)
        self.emit_predictions = bool(emit_predictions)
        self.emit_tentative = bool(emit_tentative)
        self._tracks: list[SimpleTrackState] = []

    def _reset_tracks(self) -> None:
        self._tracks.clear()

    @property
    def active_track_ids(self) -> tuple[int, ...]:
        return tuple(sorted(track.track_id for track in self._tracks))

    def _associate(
        self, cost: np.ndarray
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Greedily take the globally closest still-available pair."""
        n_tracks, n_detections = cost.shape
        remaining = cost.copy()
        matches: list[tuple[int, int]] = []
        while remaining.size:
            flat_index = int(np.argmin(remaining))
            value = float(remaining.flat[flat_index])
            if not np.isfinite(value) or value > self.max_distance:
                break
            track_index, detection_index = np.unravel_index(flat_index, remaining.shape)
            matches.append((int(track_index), int(detection_index)))
            remaining[track_index, :] = np.inf
            remaining[:, detection_index] = np.inf
        matched_tracks = {track for track, _ in matches}
        matched_detections = {detection for _, detection in matches}
        return (
            matches,
            [idx for idx in range(n_tracks) if idx not in matched_tracks],
            [idx for idx in range(n_detections) if idx not in matched_detections],
        )

    def update(
        self,
        detections: Sequence[TrackDetection | Any],
        *,
        frame_index: int | None = None,
        flow: FlowInput = None,
    ) -> list[TrackResult]:
        del flow  # baseline intentionally does not use optical-flow information
        observations = self._coerce_detections(detections)
        frame = self._begin_frame(frame_index)
        for track in self._tracks:
            track.advance()

        track_boxes = np.asarray([track.bbox for track in self._tracks], dtype=float).reshape(-1, 4)
        detection_boxes = np.asarray(
            [[det.cx, det.cy, det.w, det.h] for det in observations], dtype=float
        ).reshape(-1, 4)
        cost = pairwise_center_distance(track_boxes, detection_boxes)
        if self.class_aware and cost.size:
            for track_index, track in enumerate(self._tracks):
                for detection_index, detection in enumerate(observations):
                    if track.class_id != detection.class_id:
                        cost[track_index, detection_index] = np.inf

        matches, _, unmatched_detections = self._associate(cost)
        for track_index, detection_index in matches:
            self._tracks[track_index].update(observations[detection_index])
        for detection_index in unmatched_detections:
            self._tracks.append(
                SimpleTrackState.create(self._new_id(), observations[detection_index])
            )

        self._tracks = [
            track for track in self._tracks if track.time_since_update <= self.max_age
        ]
        results: list[TrackResult] = []
        for track in sorted(self._tracks, key=lambda item: item.track_id):
            visible = track.time_since_update == 0 or self.emit_predictions
            confirmed_or_requested = track.hits >= self.min_hits or self.emit_tentative
            if visible and confirmed_or_requested:
                results.append(track.result(frame, self.min_hits))
        return results


class CentroidGreedyTracker(_DistanceTracker):
    """Fast baseline using greedy global nearest-centroid association."""

    name = "centroid_greedy"
