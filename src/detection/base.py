"""Core abstractions shared by every detector in this module.

A ``Detection`` is a single bounding box in **pixel** coordinates, with the box
center (``cx``, ``cy``) as the primary representation. Top-left corner (``x``,
``y``) is derived. Every concrete detector returns a list of ``Detection`` per
frame through the ``Detector`` interface, so they are interchangeable in the CLI
(``--method``) and in :func:`src.detection.runner.run_on_video`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    """A bounding box in pixel coordinates (center-based)."""

    cx: float
    cy: float
    w: float
    h: float
    class_id: int = 0
    score: float = 1.0
    # track id (ground truth; string in labels_ftid) or per-frame index (detection)
    object_id: int | str = -1

    @property
    def x(self) -> float:
        """Top-left x of the box."""
        return self.cx - self.w / 2.0

    @property
    def y(self) -> float:
        """Top-left y of the box."""
        return self.cy - self.h / 2.0

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class Detector(ABC):
    """Base class for all detectors.

    Subclasses implement :meth:`detect`. Stateful detectors (e.g. background
    subtraction) override :meth:`reset` so the runner can clear state between
    videos.
    """

    name: str = "base"

    @abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        """Return the detections found in a single BGR frame."""
        raise NotImplementedError

    def reset(self) -> None:
        """Reset any per-video internal state. No-op by default."""
        return None
