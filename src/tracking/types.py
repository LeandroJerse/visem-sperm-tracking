"""Public data types used by every tracker.

The tracking package deliberately has its own small detection type.  This keeps
the trackers independent from a particular detector while
``TrackDetection.from_detection`` still accepts the project's detection
objects (or any object exposing the same attributes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


TrackState = Literal["tentative", "confirmed", "lost"]


def _validate_box(cx: float, cy: float, w: float, h: float) -> None:
    values = np.asarray([cx, cy, w, h], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("Bounding-box coordinates must be finite")
    if w <= 0 or h <= 0:
        raise ValueError("Bounding-box width and height must be positive")


@dataclass(frozen=True)
class TrackDetection:
    """One detector observation in pixel coordinates.

    ``object_id`` is optional metadata.  Trackers never use a ground-truth ID
    for association; it exists only so the same type can be used by evaluation
    helpers.
    """

    cx: float
    cy: float
    w: float
    h: float
    score: float = 1.0
    class_id: int = 0
    object_id: int | str | None = None

    def __post_init__(self) -> None:
        _validate_box(self.cx, self.cy, self.w, self.h)
        if not np.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("Detection score must be finite and in [0, 1]")

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (
            self.cx - self.w / 2.0,
            self.cy - self.h / 2.0,
            self.cx + self.w / 2.0,
            self.cy + self.h / 2.0,
        )

    @property
    def xywh(self) -> tuple[float, float, float, float]:
        """Return top-left x/y plus width/height (MOTChallenge convention)."""
        x1, y1, _, _ = self.xyxy
        return (x1, y1, self.w, self.h)

    @classmethod
    def from_detection(cls, detection: Any) -> "TrackDetection":
        """Convert a detector object exposing ``cx``, ``cy``, ``w`` and ``h``."""
        if isinstance(detection, cls):
            return detection
        try:
            return cls(
                cx=float(detection.cx),
                cy=float(detection.cy),
                w=float(detection.w),
                h=float(detection.h),
                score=float(getattr(detection, "score", 1.0)),
                class_id=int(getattr(detection, "class_id", 0)),
                object_id=getattr(detection, "object_id", None),
            )
        except AttributeError as exc:
            raise TypeError(
                "A tracking detection must expose cx, cy, w and h attributes"
            ) from exc


@dataclass(frozen=True)
class TrackResult:
    """Immutable state emitted for one track in one frame."""

    frame_index: int
    track_id: int
    cx: float
    cy: float
    w: float
    h: float
    score: float
    class_id: int
    age: int
    hits: int
    time_since_update: int
    state: TrackState
    predicted: bool = False

    def __post_init__(self) -> None:
        _validate_box(self.cx, self.cy, self.w, self.h)
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if self.track_id < 1:
            raise ValueError("track_id must be positive")
        if not np.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("Track score must be finite and in [0, 1]")
        if self.age < 1 or self.hits < 1 or self.time_since_update < 0:
            raise ValueError("Invalid track lifecycle counters")
        if self.state not in {"tentative", "confirmed", "lost"}:
            raise ValueError(f"Invalid track state: {self.state}")

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (
            self.cx - self.w / 2.0,
            self.cy - self.h / 2.0,
            self.cx + self.w / 2.0,
            self.cy + self.h / 2.0,
        )

    @property
    def xywh(self) -> tuple[float, float, float, float]:
        x1, y1, _, _ = self.xyxy
        return (x1, y1, self.w, self.h)

    def as_detection(self) -> TrackDetection:
        return TrackDetection(
            cx=self.cx,
            cy=self.cy,
            w=self.w,
            h=self.h,
            score=self.score,
            class_id=self.class_id,
            object_id=self.track_id,
        )
