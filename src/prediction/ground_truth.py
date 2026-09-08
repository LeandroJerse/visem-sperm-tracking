"""Pure, class-aware eligibility of original-ID ground-truth trajectories.

Inputs must describe every frame of one video, including explicitly unannotated
frames. This module never reads files, interpolates positions, runs a tracker or
uses optical flow. Future observations only determine offline target eligibility;
the exported windows are indices, not predictor features. Overlapping windows
remain dependent observations from their source video.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Any, Iterable
from urllib.parse import quote

from src.detection.base import Detection
from src.detection.io import GroundTruthFrame


START_REASONS = ("video_start", "annotation_absent", "class_1", "id_absent")
END_REASONS = ("video_end", "annotation_absent", "class_1", "id_absent")


@dataclass(frozen=True)
class IndividualGroundTruth:
    """Detached, JSON-exportable records; ``track_id`` always remains original.

    Segment IDs identify continuous observation intervals, not new biological
    identities. Dictionaries may be serialized directly and share no mutable
    state with input Detection objects.
    """

    observations: tuple[dict[str, Any], ...]
    segments: tuple[dict[str, Any], ...]
    windows: tuple[dict[str, Any], ...]
    frame_status: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _token(value: Any, name: str) -> str:
    if (not isinstance(value, str) or not value or not value.isprintable()
            or any(character.isspace() for character in value)):
        raise ValueError(f"{name} must be a nonempty printable string without whitespace")
    return value


def _identity(value: Any) -> str:
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(_integer(value, "track_id"))
    identity = _token(value, "track_id")
    if identity == "-1":
        raise ValueError("track_id cannot be the missing-identity sentinel -1")
    return identity


def _coordinate(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _detection_record(detection: Detection) -> dict[str, Any]:
    if not isinstance(detection, Detection):
        raise ValueError("GT detections must be Detection instances")
    identity = _identity(detection.object_id)
    class_id = _integer(detection.class_id, "class_id")
    if class_id not in (0, 1, 2):
        raise ValueError("GT class_id must be 0, 1 or 2")
    cx, cy, width, height = (
        _coordinate(getattr(detection, name), name) for name in ("cx", "cy", "w", "h")
    )
    x, y = cx - width / 2.0, cy - height / 2.0
    if min(width, height) <= 0 or min(cx, cy) < 0 or min(x, y) < -1e-9:
        raise ValueError("GT boxes require positive dimensions and nonnegative pixel bounds")
    # Upper image bounds are certified by the upstream strict parser: this pure
    # interface deliberately has no image dimensions or video dependency.
    return {"track_id": identity, "class_id": class_id,
            "cx": cx, "cy": cy, "w": width, "h": height, "x": x, "y": y}


def build_individual_ground_truth(
    frames: Iterable[GroundTruthFrame],
    *,
    video_id: str,
    split: str,
    expected_frame_count: int,
    history_length: int = 20,
    forecast_horizon: int = 10,
    stride: int = 1,
) -> IndividualGroundTruth:
    """Segment eligible classes 0/2, preserving IDs and the complete frame axis.

    Input indices must be exactly ``0..expected_frame_count-1`` in order. An
    absent label must be an explicit ``annotated=False`` frame with no rows;
    a missing frame record is an invalid input, never a negative observation.
    Class 0 <-> 2 stays continuous. Class 1, ID absence or annotation absence
    ends a segment, regardless of the geometry of other clusters in the frame.

    ``end_boundary_frame`` is the first frame that terminates a segment (N for
    the video boundary). ``id_absent`` as a start reason only describes absence
    in the preceding annotated frame, not the birth of a biological object.
    Origins are sampled with ``stride`` anchored at each segment's first valid
    history. All segments survive, including those too short for any window.
    """
    video_id = _token(video_id, "video_id")
    if "/" in video_id or "\\" in video_id:
        raise ValueError("video_id cannot contain path separators")
    split = _token(split, "split")
    expected_frame_count = _integer(expected_frame_count, "expected_frame_count", minimum=1)
    history_length = _integer(history_length, "history_length", minimum=2)
    forecast_horizon = _integer(forecast_horizon, "forecast_horizon", minimum=1)
    stride = _integer(stride, "stride", minimum=1)

    observations: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    frame_status: list[dict[str, Any]] = []
    active: dict[str, dict[str, Any]] = {}
    raw_ids: set[str] = set()
    individual_ids: set[str] = set()
    classes: Counter[int] = Counter()
    previous_annotated = False
    previous_classes: dict[str, int] = {}

    def close_segment(identity: str, reason: str, boundary: int) -> None:
        segment = active.pop(identity)
        segment["end_reason"] = reason
        segment["end_boundary_frame"] = boundary
        segments.append(segment)

    for expected_index, frame in enumerate(frames):
        if not isinstance(frame, GroundTruthFrame):
            raise ValueError("frames must contain GroundTruthFrame instances")
        frame_index = _integer(frame.frame_idx, "frame_idx")
        if expected_index >= expected_frame_count or frame_index != expected_index:
            raise ValueError("GT frame indices must be exactly the expected ordered universe")
        if type(frame.annotated) is not bool:
            raise ValueError("annotated must be an explicit bool")
        if not isinstance(frame.detections, (tuple, list)):
            raise ValueError("frame detections must be a tuple or list")
        if not frame.annotated and frame.detections:
            raise ValueError("An unannotated frame cannot contain GT rows")
        by_id: dict[str, dict[str, Any]] = {}
        for detection in frame.detections:
            try:
                row = _detection_record(detection)
            except ValueError as exc:
                raise ValueError(f"Invalid GT at frame {frame_index}: {exc}") from exc
            identity = row["track_id"]
            if identity in by_id:
                raise ValueError(f"Duplicate GT track_id {identity!r} at frame {frame_index}")
            by_id[identity] = row

        for identity in sorted(active):
            if not frame.annotated:
                close_segment(identity, "annotation_absent", frame_index)
            elif identity not in by_id:
                close_segment(identity, "id_absent", frame_index)
            elif by_id[identity]["class_id"] == 1:
                close_segment(identity, "class_1", frame_index)

        individual_count = sum(row["class_id"] != 1 for row in by_id.values())
        frame_status.append({"video_id": video_id, "frame_index": frame_index,
                             "annotated": frame.annotated, "raw_count": len(by_id),
                             "individual_count": individual_count,
                             "cluster_count": len(by_id) - individual_count})
        for identity in sorted(by_id):
            row = by_id[identity]
            classes[row["class_id"]] += 1
            raw_ids.add(identity)
            if row["class_id"] == 1:
                continue
            individual_ids.add(identity)
            if identity not in active:
                start_reason = (
                    "video_start" if frame_index == 0
                    else "annotation_absent" if not previous_annotated
                    else "class_1" if previous_classes.get(identity) == 1
                    else "id_absent"
                )
                active[identity] = {
                    "video_id": video_id, "track_id": identity,
                    "segment_id": f"{video_id}/{quote(identity, safe='')}/{frame_index}",
                    "split": split, "start_frame": frame_index, "end_frame": frame_index,
                    "observation_count": 0, "start_reason": start_reason,
                }
            segment = active[identity]
            segment["end_frame"] = frame_index
            segment["observation_count"] += 1
            observations.append({"video_id": video_id, "frame_index": frame_index,
                                 "annotated": True, **row, "segment_id": segment["segment_id"]})
        previous_annotated = frame.annotated
        previous_classes = {identity: row["class_id"] for identity, row in by_id.items()}

    if len(frame_status) != expected_frame_count:
        raise ValueError("GT frame indices must cover the complete expected universe")
    for identity in sorted(active):
        close_segment(identity, "video_end", expected_frame_count)
    segments.sort(key=lambda row: (row["start_frame"], row["track_id"]))

    windows: list[dict[str, Any]] = []
    origins_with_history = 0
    segments_with_windows = 0
    exclusions = {reason: 0 for reason in END_REASONS}
    for segment in segments:
        first_origin = segment["start_frame"] + history_length - 1
        history_count = max(0, (segment["end_frame"] - first_origin) // stride + 1)
        window_count = max(0, (segment["end_frame"] - forecast_horizon - first_origin) // stride + 1)
        origins_with_history += history_count
        segments_with_windows += window_count > 0
        exclusions[segment["end_reason"]] += history_count - window_count
        for origin_frame in range(first_origin, segment["end_frame"] - forecast_horizon + 1, stride):
            windows.append({
                "window_id": f"{segment['segment_id']}/{origin_frame}/h{history_length}_f{forecast_horizon}",
                "video_id": video_id, "track_id": segment["track_id"],
                "segment_id": segment["segment_id"], "split": split,
                "history_start": origin_frame - history_length + 1,
                "origin_frame": origin_frame, "future_end": origin_frame + forecast_horizon,
                "history_length": history_length, "forecast_horizon": forecast_horizon,
            })
    windows.sort(key=lambda row: (row["origin_frame"], row["track_id"], row["segment_id"]))
    summary = {
        "schema_version": 1, "video_id": video_id, "split": split,
        "expected_frame_count": expected_frame_count, "frames_total": len(frame_status),
        "frames_annotated": sum(row["annotated"] for row in frame_status),
        "frames_unannotated": sum(not row["annotated"] for row in frame_status),
        "frames_annotated_empty": sum(row["annotated"] and row["raw_count"] == 0 for row in frame_status),
        "frames_with_individuals": sum(row["individual_count"] > 0 for row in frame_status),
        "frames_with_clusters": sum(row["cluster_count"] > 0 for row in frame_status),
        "frames_cluster_only": sum(row["cluster_count"] > 0 and row["individual_count"] == 0
                                   for row in frame_status),
        "raw_observations": sum(classes.values()), "individual_observations": len(observations),
        "cluster_observations": classes[1], "class_observations": {str(key): classes[key] for key in (0, 1, 2)},
        "unique_raw_track_ids": len(raw_ids), "unique_individual_track_ids": len(individual_ids),
        "segments_total": len(segments), "segments_with_windows": segments_with_windows,
        "segments_without_windows": len(segments) - segments_with_windows,
        "segment_start_reasons": {reason: sum(row["start_reason"] == reason for row in segments)
                                  for reason in START_REASONS},
        "segment_end_reasons": {reason: sum(row["end_reason"] == reason for row in segments)
                                for reason in END_REASONS},
        "history_length": history_length, "forecast_horizon": forecast_horizon, "stride": stride,
        "origins_with_complete_history": origins_with_history, "windows_total": len(windows),
        "origins_excluded_incomplete_future": origins_with_history - len(windows),
        "excluded_origins_by_end_reason": exclusions,
    }
    return IndividualGroundTruth(tuple(observations), tuple(segments), tuple(windows),
                                 tuple(frame_status), summary)
