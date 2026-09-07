"""Classical SORT: constant-velocity Kalman prediction plus IoU/Hungarian."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..assignment import match_cost_matrix, pairwise_iou
from ..base import FlowInput, Tracker
from ..kalman import BoundingBoxKalmanFilter
from ..types import TrackDetection, TrackResult, TrackState


@dataclass
class _KalmanTrackState:
    track_id: int
    kf: BoundingBoxKalmanFilter
    score: float
    class_id: int
    age: int = 1
    hits: int = 1
    hit_streak: int = 1
    time_since_update: int = 0

    def predict(self) -> np.ndarray:
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.age += 1
        self.time_since_update += 1
        return self.kf.predict()

    def update(self, detection: TrackDetection) -> None:
        self.kf.update(
            np.asarray([detection.cx, detection.cy, detection.w, detection.h], dtype=float)
        )
        self.score = detection.score
        self.class_id = detection.class_id
        self.hits += 1
        self.hit_streak += 1
        self.time_since_update = 0

    def result(self, frame_index: int, min_hits: int) -> TrackResult:
        bbox = self.kf.bbox
        if self.time_since_update > 0:
            state: TrackState = "lost"
        elif self.hits >= min_hits:
            state = "confirmed"
        else:
            state = "tentative"
        return TrackResult(
            frame_index=frame_index,
            track_id=self.track_id,
            cx=float(bbox[0]),
            cy=float(bbox[1]),
            w=float(bbox[2]),
            h=float(bbox[3]),
            score=float(self.score),
            class_id=int(self.class_id),
            age=self.age,
            hits=self.hits,
            time_since_update=self.time_since_update,
            state=state,
            predicted=self.time_since_update > 0,
        )


class SortTracker(Tracker):
    """A transparent SORT baseline without appearance features.

    Association is exactly Hungarian assignment on ``1 - IoU`` after a
    constant-velocity Kalman prediction.  Tiny microscopy boxes can require a
    lower ``iou_threshold`` than pedestrian-tracking defaults.
    """

    name = "sort"

    def __init__(
        self,
        *,
        iou_threshold: float = 0.1,
        max_age: int = 3,
        min_hits: int = 1,
        process_noise: float = 1.0,
        measurement_noise: float = 4.0,
        class_aware: bool = False,
        emit_predictions: bool = False,
        emit_tentative: bool = False,
        start_id: int = 1,
    ) -> None:
        super().__init__(start_id=start_id)
        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be in [0, 1]")
        if max_age < 0:
            raise ValueError("max_age must be non-negative")
        if min_hits < 1:
            raise ValueError("min_hits must be at least 1")
        if process_noise <= 0 or measurement_noise <= 0:
            raise ValueError("Kalman noise values must be positive")
        self.iou_threshold = float(iou_threshold)
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.process_noise = float(process_noise)
        self.measurement_noise = float(measurement_noise)
        self.class_aware = bool(class_aware)
        self.emit_predictions = bool(emit_predictions)
        self.emit_tentative = bool(emit_tentative)
        self._tracks: list[_KalmanTrackState] = []

    def _reset_tracks(self) -> None:
        self._tracks.clear()

    @property
    def active_track_ids(self) -> tuple[int, ...]:
        return tuple(sorted(track.track_id for track in self._tracks))

    def _predict_tracks(self, flow: FlowInput = None) -> None:
        del flow  # the classical baseline deliberately ignores external flow
        for track in self._tracks:
            track.predict()

    def _associate_iou(
        self,
        observations: list[TrackDetection],
        track_indices: list[int],
        detection_indices: list[int],
        *,
        threshold: float | None = None,
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        if not track_indices or not detection_indices:
            return [], track_indices.copy(), detection_indices.copy()
        track_boxes = np.asarray(
            [self._tracks[index].kf.bbox for index in track_indices], dtype=float
        )
        detection_boxes = np.asarray(
            [
                [observations[index].cx, observations[index].cy,
                 observations[index].w, observations[index].h]
                for index in detection_indices
            ],
            dtype=float,
        )
        ious = pairwise_iou(track_boxes, detection_boxes)
        cost = 1.0 - ious
        selected_threshold = self.iou_threshold if threshold is None else threshold
        cost[ious < selected_threshold] = np.inf
        if self.class_aware:
            for local_track, track_index in enumerate(track_indices):
                for local_detection, detection_index in enumerate(detection_indices):
                    if (
                        self._tracks[track_index].class_id
                        != observations[detection_index].class_id
                    ):
                        cost[local_track, local_detection] = np.inf
        local_matches, local_unmatched_tracks, local_unmatched_detections = (
            match_cost_matrix(cost)
        )
        return (
            [
                (track_indices[track], detection_indices[detection])
                for track, detection in local_matches
            ],
            [track_indices[index] for index in local_unmatched_tracks],
            [detection_indices[index] for index in local_unmatched_detections],
        )

    def _spawn(self, detection: TrackDetection) -> None:
        bbox = np.asarray(
            [detection.cx, detection.cy, detection.w, detection.h], dtype=float
        )
        self._tracks.append(
            _KalmanTrackState(
                track_id=self._new_id(),
                kf=BoundingBoxKalmanFilter(
                    bbox,
                    process_noise=self.process_noise,
                    measurement_noise=self.measurement_noise,
                ),
                score=detection.score,
                class_id=detection.class_id,
            )
        )

    def _update_matches(
        self,
        matches: list[tuple[int, int]],
        observations: list[TrackDetection],
    ) -> None:
        for track_index, detection_index in matches:
            self._tracks[track_index].update(observations[detection_index])

    def _finish_frame(self, frame: int) -> list[TrackResult]:
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
        matches, _, unmatched_detections = self._associate_iou(
            observations,
            list(range(len(self._tracks))),
            list(range(len(observations))),
        )
        self._update_matches(matches, observations)
        for detection_index in unmatched_detections:
            self._spawn(observations[detection_index])
        return self._finish_frame(frame)
