"""Rastreador moderno leve com associação em dois estágios ByteTrack-style."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..base import FlowInput
from ..classical.sort import SortTracker
from ..types import TrackDetection, TrackResult


class ByteTrackStyleTracker(SortTracker):
    """SORT motion with ByteTrack's high-score/low-score association idea.

    This is intentionally named ``ByteTrackStyleTracker``: it implements the
    central two-pass association rule, but does not claim to reproduce every
    track-pool heuristic in the official ByteTrack codebase.  Low-confidence
    detections may recover an existing track but never start a new one.
    """

    name = "bytetrack_style"

    def __init__(
        self,
        *,
        high_threshold: float = 0.6,
        low_threshold: float = 0.1,
        new_track_threshold: float | None = None,
        second_iou_threshold: float = 0.05,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if not 0.0 <= low_threshold < high_threshold <= 1.0:
            raise ValueError("Require 0 <= low_threshold < high_threshold <= 1")
        if not 0.0 <= second_iou_threshold <= 1.0:
            raise ValueError("second_iou_threshold must be in [0, 1]")
        selected_new_threshold = (
            high_threshold if new_track_threshold is None else new_track_threshold
        )
        if not high_threshold <= selected_new_threshold <= 1.0:
            raise ValueError("new_track_threshold must be >= high_threshold and <= 1")
        self.high_threshold = float(high_threshold)
        self.low_threshold = float(low_threshold)
        self.new_track_threshold = float(selected_new_threshold)
        self.second_iou_threshold = float(second_iou_threshold)

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

        high_indices = [
            index
            for index, detection in enumerate(observations)
            if detection.score >= self.high_threshold
        ]
        low_indices = [
            index
            for index, detection in enumerate(observations)
            if self.low_threshold <= detection.score < self.high_threshold
        ]

        first_matches, unmatched_tracks, unmatched_high = self._associate_iou(
            observations,
            list(range(len(self._tracks))),
            high_indices,
        )
        second_matches, _, _ = self._associate_iou(
            observations,
            unmatched_tracks,
            low_indices,
            threshold=self.second_iou_threshold,
        )
        self._update_matches(first_matches + second_matches, observations)

        for detection_index in unmatched_high:
            if observations[detection_index].score >= self.new_track_threshold:
                self._spawn(observations[detection_index])
        return self._finish_frame(frame)
