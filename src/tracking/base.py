"""Unified stateful tracker interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import numpy as np

from .types import TrackDetection, TrackResult


FlowInput = (
    tuple[float, float]
    | np.ndarray
    | Any  # a callable ``flow(cx, cy) -> (u, v)`` is validated when sampled
    | None
)


class Tracker(ABC):
    """Base class implemented by all online trackers.

    ``update`` must be called exactly once per consecutive video frame,
    including frames with no detections.  Enforcing this rule avoids silently
    changing ``max_age`` semantics when callers skip empty frames.
    """

    name = "base"

    def __init__(self, *, start_id: int = 1) -> None:
        if start_id < 1:
            raise ValueError("start_id must be positive")
        self.start_id = int(start_id)
        self._next_id = self.start_id
        self._frame_index: int | None = None

    @abstractmethod
    def update(
        self,
        detections: Sequence[TrackDetection | Any],
        *,
        frame_index: int | None = None,
        flow: FlowInput = None,
    ) -> list[TrackResult]:
        """Consume one frame and return the visible/predicted track states."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear all video-specific state and restart deterministic IDs."""
        self._next_id = self.start_id
        self._frame_index = None
        self._reset_tracks()

    @abstractmethod
    def _reset_tracks(self) -> None:
        raise NotImplementedError

    def _begin_frame(self, frame_index: int | None) -> int:
        if frame_index is None:
            resolved = 0 if self._frame_index is None else self._frame_index + 1
        else:
            resolved = int(frame_index)
            if resolved < 0:
                raise ValueError("frame_index must be non-negative")
        if self._frame_index is not None and resolved != self._frame_index + 1:
            raise ValueError(
                "Tracker updates must use consecutive frame indices; pass an "
                "empty detection list for frames without observations"
            )
        self._frame_index = resolved
        return resolved

    def _new_id(self) -> int:
        track_id = self._next_id
        self._next_id += 1
        return track_id

    @staticmethod
    def _coerce_detections(
        detections: Sequence[TrackDetection | Any],
    ) -> list[TrackDetection]:
        return [TrackDetection.from_detection(item) for item in detections]

    @property
    @abstractmethod
    def active_track_ids(self) -> tuple[int, ...]:
        """IDs still retained by the tracker, including temporarily lost tracks."""
        raise NotImplementedError
