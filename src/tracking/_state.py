"""Internal mutable track states shared by tracker implementations."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import TrackDetection, TrackResult, TrackState


@dataclass
class SimpleTrackState:
    track_id: int
    bbox: np.ndarray
    score: float
    class_id: int
    age: int = 1
    hits: int = 1
    time_since_update: int = 0

    @classmethod
    def create(cls, track_id: int, detection: TrackDetection) -> "SimpleTrackState":
        return cls(
            track_id=track_id,
            bbox=np.asarray(
                [detection.cx, detection.cy, detection.w, detection.h], dtype=float
            ),
            score=detection.score,
            class_id=detection.class_id,
        )

    def advance(self) -> None:
        self.age += 1
        self.time_since_update += 1

    def update(self, detection: TrackDetection) -> None:
        self.bbox[:] = [detection.cx, detection.cy, detection.w, detection.h]
        self.score = detection.score
        self.class_id = detection.class_id
        self.hits += 1
        self.time_since_update = 0

    def result(self, frame_index: int, min_hits: int) -> TrackResult:
        if self.time_since_update > 0:
            state: TrackState = "lost"
        elif self.hits >= min_hits:
            state = "confirmed"
        else:
            state = "tentative"
        return TrackResult(
            frame_index=frame_index,
            track_id=self.track_id,
            cx=float(self.bbox[0]),
            cy=float(self.bbox[1]),
            w=float(self.bbox[2]),
            h=float(self.bbox[3]),
            score=float(self.score),
            class_id=int(self.class_id),
            age=self.age,
            hits=self.hits,
            time_since_update=self.time_since_update,
            state=state,
            predicted=self.time_since_update > 0,
        )
