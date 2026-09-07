"""Sequence-level helpers built on the frame-by-frame tracker API."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from .base import FlowInput, Tracker
from .types import TrackDetection, TrackResult


def track_sequence(
    tracker: Tracker,
    detections_by_frame: Iterable[Sequence[TrackDetection | Any]],
    *,
    start_frame: int = 0,
    flows: Iterable[FlowInput] | None = None,
    reset: bool = True,
) -> list[TrackResult]:
    """Track a sequence and return a flat, frame-indexed result list.

    Empty frames must appear as empty sequences.  If ``flows`` is supplied, it
    must contain exactly one item per frame; use ``None`` for a frame without a
    flow estimate.
    """
    if start_frame < 0:
        raise ValueError("start_frame must be non-negative")
    if reset:
        tracker.reset()
    flow_iterator = iter(flows) if flows is not None else None
    sentinel = object()
    results: list[TrackResult] = []
    for offset, detections in enumerate(detections_by_frame):
        if flow_iterator is None:
            flow: FlowInput = None
        else:
            flow = next(flow_iterator, sentinel)  # type: ignore[assignment]
            if flow is sentinel:
                raise ValueError("flows ended before detections_by_frame")
        results.extend(
            tracker.update(
                detections,
                frame_index=start_frame + offset,
                flow=flow,
            )
        )
    if flow_iterator is not None and next(flow_iterator, sentinel) is not sentinel:
        raise ValueError("flows contains more items than detections_by_frame")
    return results


def group_results_by_frame(
    results: Iterable[TrackResult],
) -> dict[int, list[TrackResult]]:
    """Group and deterministically sort flat tracking results."""
    grouped: dict[int, list[TrackResult]] = {}
    for result in results:
        grouped.setdefault(result.frame_index, []).append(result)
    for frame_results in grouped.values():
        frame_results.sort(key=lambda result: result.track_id)
    return dict(sorted(grouped.items()))
