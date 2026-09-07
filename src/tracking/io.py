"""Stable CSV and MOTChallenge exports for tracking outputs."""
from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from .types import TrackResult


TRACK_CSV_FIELDS = (
    "video_id",
    "frame_index",
    "annotated",
    "track_id",
    "cx",
    "cy",
    "w",
    "h",
    "x",
    "y",
    "score",
    "class_id",
    "age",
    "hits",
    "time_since_update",
    "state",
    "predicted",
)


def track_result_to_row(
    video_id: str,
    result: TrackResult,
    *,
    annotated: bool | None = None,
) -> dict[str, object]:
    """Convert one result while preserving its frame annotation state.

    ``annotated`` is deliberately tri-state.  ``1`` and ``0`` mean that a
    frame-status source explicitly classified the frame; an empty value means
    that no authoritative status was available.  Unknown is never serialized
    as ``0``, because that would turn missing labels into negative ground
    truth.
    """

    x, y, _, _ = result.xywh
    return {
        "video_id": video_id,
        "frame_index": result.frame_index,
        "annotated": "" if annotated is None else int(annotated),
        "track_id": result.track_id,
        "cx": result.cx,
        "cy": result.cy,
        "w": result.w,
        "h": result.h,
        "x": x,
        "y": y,
        "score": result.score,
        "class_id": result.class_id,
        "age": result.age,
        "hits": result.hits,
        "time_since_update": result.time_since_update,
        "state": result.state,
        "predicted": int(result.predicted),
    }


def export_tracks_csv(
    results: Iterable[TrackResult],
    path: str | Path,
    *,
    video_id: str,
    annotated_by_frame: Mapping[int, bool | None] | None = None,
    overwrite: bool = False,
) -> Path:
    """Write the full lifecycle schema without silently overwriting a run.

    The optional mapping comes from the tracking frame universe.  Missing
    mapping entries remain unknown (empty CSV value), rather than being
    interpreted as unannotated.
    """

    rows = [
        track_result_to_row(
            video_id,
            result,
            annotated=(
                annotated_by_frame.get(result.frame_index)
                if annotated_by_frame is not None
                else None
            ),
        )
        for result in results
    ]
    target = Path(path)
    return _atomic_csv_write(target, TRACK_CSV_FIELDS, rows, overwrite=overwrite)


def export_motchallenge(
    results: Iterable[TrackResult],
    path: str | Path,
    *,
    overwrite: bool = False,
    include_predictions: bool = True,
    frame_offset: int = 1,
) -> Path:
    """Export MOTChallenge's ten-column tracker format for external metrics."""
    if frame_offset < 0:
        raise ValueError("frame_offset must be non-negative")
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            for result in sorted(results, key=lambda item: (item.frame_index, item.track_id)):
                if result.predicted and not include_predictions:
                    continue
                x, y, w, h = result.xywh
                writer.writerow(
                    [
                        result.frame_index + frame_offset,
                        result.track_id,
                        f"{x:.6f}",
                        f"{y:.6f}",
                        f"{w:.6f}",
                        f"{h:.6f}",
                        f"{result.score:.6f}",
                        -1,
                        -1,
                        -1,
                    ]
                )
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return target


def _atomic_csv_write(
    target: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, object]],
    *,
    overwrite: bool,
) -> Path:
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return target
