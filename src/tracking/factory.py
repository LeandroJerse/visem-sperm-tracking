"""Tracker registry and factory."""
from __future__ import annotations

from typing import Any

from .base import Tracker
from .classical import CentroidGreedyTracker, HungarianTracker, SortTracker
from .hybrid import AdaptiveFlowSortTracker
from .modern import ByteTrackStyleTracker


TRACKERS: dict[str, type[Tracker]] = {
    CentroidGreedyTracker.name: CentroidGreedyTracker,
    HungarianTracker.name: HungarianTracker,
    SortTracker.name: SortTracker,
    ByteTrackStyleTracker.name: ByteTrackStyleTracker,
    AdaptiveFlowSortTracker.name: AdaptiveFlowSortTracker,
}


def register_tracker(
    name: str, tracker_class: type[Tracker], *, overwrite: bool = False
) -> None:
    """Register an extension without changing the built-in factory."""
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Tracker name cannot be empty")
    if not isinstance(tracker_class, type) or not issubclass(tracker_class, Tracker):
        raise TypeError("tracker_class must be a Tracker subclass")
    if normalized in TRACKERS and not overwrite:
        raise KeyError(f"Tracker already registered: {normalized}")
    TRACKERS[normalized] = tracker_class


def create_tracker(name: str, **kwargs: Any) -> Tracker:
    """Instantiate a tracker by its stable experiment name."""
    normalized = name.strip().lower()
    try:
        tracker_class = TRACKERS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(TRACKERS))
        raise ValueError(f"Unknown tracker '{name}'. Available: {available}") from exc
    return tracker_class(**kwargs)
