"""Deduplicate causal sampling requests without reading future coordinates.

One sample belongs to a named video, original ID, uninterrupted segment and
source frame. Overlapping windows share that sample; they remain distinct
evaluation windows. All functions are pure and operate on detached histories.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any

import numpy as np

from src.prediction.reference import HistoryBatch


_WINDOW_FIELDS = (
    "window_id", "video_id", "track_id", "segment_id", "split", "history_start",
    "origin_frame", "future_end", "history_length", "forecast_horizon",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _token(value: Any, name: str) -> str:
    _require(isinstance(value, str) and bool(value) and value.isprintable()
             and not any(character.isspace() for character in value)
             and value != "-1", f"Invalid {name}")
    return value


def _integer(value: Any, name: str) -> int:
    _require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")
    return value


def _row(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class CompactRequests:
    """Immutable rows; links contain 19 ordered ``sample_ids`` per window."""

    video_id: str
    windows: tuple[Mapping[str, Any], ...]
    samples: tuple[Mapping[str, Any], ...]
    links: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class SampleValue:
    """An invalid vector has two NaNs and a reason; valid zero stays zero."""

    u: float
    v: float
    valid: bool
    reason: str


@dataclass(frozen=True)
class CompactFeatures:
    """Sample rows augmented with values and coverage for every window.

    Invalid numeric values remain NaN internally. CSV exporters must write
    empty u/v cells plus ``valid=False`` and the explicit reason.
    """

    samples: tuple[Mapping[str, Any], ...]
    coverage: tuple[Mapping[str, Any], ...]


def build_compact_requests(
    batches: Iterable[HistoryBatch], *, video_id: str,
) -> CompactRequests:
    """Union source samples across audited 20-position training histories.

    Output order is deterministic: windows by origin/ID/segment/window ID,
    samples by source frame/ID/segment. ``sample_id`` is the full SHA256 of
    compact ASCII JSON ``[video_id, track_id, segment_id, frame_from]``.
    The final historical position is checked for consistency but is never
    requested as a source sample for that same window (it would end at t+1).
    Empty batches contribute nothing; no replacement origin is selected.
    """
    _token(video_id, "video_id")
    windows: dict[str, dict] = {}
    signatures: set[tuple] = set()
    positions: dict[tuple, tuple[float, float]] = {}
    samples: dict[tuple, dict] = {}
    segment_tracks: dict[str, str] = {}
    identities: dict[str, tuple] = {}
    links: dict[str, tuple[str, ...]] = {}
    for batch in batches:
        _require(isinstance(batch, HistoryBatch), "Expected HistoryBatch without targets")
        histories = batch.histories
        _require(isinstance(histories, np.ndarray) and histories.dtype == np.dtype(np.float64)
                 and histories.shape == (len(batch.window_rows), 20, 2),
                 "Histories must have float64 shape (N,20,2)")
        _require(np.isfinite(histories).all(), "Histories must contain finite positions")
        for history, supplied in zip(histories, batch.window_rows):
            _require(isinstance(supplied, Mapping) and set(supplied) == set(_WINDOW_FIELDS),
                     "Unexpected historical window schema")
            row = {name: supplied[name] for name in _WINDOW_FIELDS}
            for name in ("window_id", "video_id", "track_id", "segment_id"):
                _token(row[name], name)
            _require(row["video_id"] == video_id, "Cross-video history")
            _require(row["split"] == "train", "Only training histories are accepted")
            for name in ("history_start", "origin_frame", "future_end", "history_length", "forecast_horizon"):
                _integer(row[name], name)
            _require(row["history_length"] == 20 and row["forecast_horizon"] == 10
                     and row["origin_frame"] == row["history_start"] + 19
                     and row["future_end"] == row["origin_frame"] + 10,
                     "Window must have 20 consecutive history positions and ten future targets")
            _require(row["window_id"] not in windows, "Duplicate window_id")
            signature = (row["track_id"], row["segment_id"], row["origin_frame"])
            _require(signature not in signatures, "Duplicate window under another name")
            signatures.add(signature)
            segment = row["segment_id"]
            _require(segment not in segment_tracks or segment_tracks[segment] == row["track_id"],
                     "Segment belongs to conflicting original IDs")
            segment_tracks[segment] = row["track_id"]
            ids = []
            for offset, point in enumerate(history):
                frame = row["history_start"] + offset
                key = (video_id, row["track_id"], segment, frame)
                xy = (float(point[0]), float(point[1]))
                _require(key not in positions or positions[key] == xy,
                         "Conflicting source coordinates across overlapping histories")
                positions[key] = xy
                if offset == 19:
                    continue
                sample_id = hashlib.sha256(json.dumps(
                    list(key), ensure_ascii=True, separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")).hexdigest()
                _require(sample_id not in identities or identities[sample_id] == key,
                         "Sample identifier collision")
                identities[sample_id] = key
                samples[key] = {
                    "sample_id": sample_id, "video_id": video_id,
                    "track_id": row["track_id"], "segment_id": segment,
                    "frame_from": frame, "frame_to": frame + 1,
                    "cx": xy[0], "cy": xy[1],
                }
                ids.append(sample_id)
            windows[row["window_id"]] = row
            links[row["window_id"]] = tuple(ids)
    ordered_windows = sorted(windows.values(), key=lambda row: (
        row["origin_frame"], row["track_id"], row["segment_id"], row["window_id"],
    ))
    ordered_samples = sorted(samples.values(), key=lambda row: (
        row["frame_from"], row["track_id"], row["segment_id"],
    ))
    return CompactRequests(
        video_id, tuple(_row(row) for row in ordered_windows),
        tuple(_row(row) for row in ordered_samples),
        tuple(_row({"window_id": row["window_id"], "sample_ids": links[row["window_id"]]})
              for row in ordered_windows),
    )


def attach_samples(
    requests: CompactRequests, sampled: Mapping[str, SampleValue],
) -> CompactFeatures:
    """Attach every requested vector and compute coverage without dropping rows.

    Eligibility of the planned last-five-flow predictor uses precisely source
    frames t-5..t-1. Missing older samples are still reported but do not exclude
    that predictor. This is availability, never a numerical quality threshold.
    """
    _require(isinstance(requests, CompactRequests), "Expected CompactRequests")
    _require(isinstance(sampled, Mapping), "sampled must map sample_id to SampleValue")
    expected = {row["sample_id"] for row in requests.samples}
    _require(len(expected) == len(requests.samples), "Duplicate sample requests")
    _require(set(sampled) == expected, "Sample coverage has missing or extra sample_ids")
    attached = {}
    for row in requests.samples:
        value = sampled[row["sample_id"]]
        _require(isinstance(value, SampleValue), "Expected SampleValue")
        _require(type(value.valid) is bool, "Sample validity must be bool")
        _require(isinstance(value.reason, str), "Sample reason must be a string")
        _require(all(isinstance(number, (int, float, np.integer, np.floating))
                     and not isinstance(number, (bool, np.bool_)) for number in (value.u, value.v)),
                 "Sample vector must contain real numeric values")
        u, v = float(value.u), float(value.v)
        if value.valid:
            _require(math.isfinite(u) and math.isfinite(v) and value.reason == "",
                     "Valid sample needs finite coordinates and empty reason")
        else:
            _require(math.isnan(u) and math.isnan(v) and bool(value.reason)
                     and value.reason.isprintable(),
                     "Invalid sample needs two NaNs and an explicit printable reason")
        attached[row["sample_id"]] = _row({**row, "u": u, "v": v,
                                            "valid": value.valid, "reason": value.reason})
    _require(len(requests.links) == len(requests.windows), "Window linkage count differs")
    coverage = []
    for row, link in zip(requests.windows, requests.links):
        _require(row["window_id"] == link["window_id"], "Window linkage order differs")
        ids = link["sample_ids"]
        _require(len(ids) == 19 and len(set(ids)) == 19 and set(ids) <= expected,
                 "Window must link 19 distinct available sample IDs")
        values = [attached[sample_id] for sample_id in ids]
        _require(all(value["video_id"] == row["video_id"]
                     and value["track_id"] == row["track_id"]
                     and value["segment_id"] == row["segment_id"]
                     and value["frame_from"] == row["history_start"] + index
                     and value["frame_to"] == row["history_start"] + index + 1
                     for index, value in enumerate(values)),
                 "Window samples must preserve video, ID, segment and consecutive causal pairs")
        valid_history = sum(value["valid"] for value in values)
        valid_last = sum(value["valid"] for value in values[-5:])
        coverage.append(_row({
            "window_id": row["window_id"], "video_id": row["video_id"],
            "track_id": row["track_id"], "segment_id": row["segment_id"],
            "origin_frame": row["origin_frame"], "sample_count": 19,
            "valid_history19": valid_history, "valid_last5": valid_last,
            "eligible_last5": valid_last == 5,
            "invalid_reasons_history19": tuple(sorted(Counter(
                value["reason"] for value in values if not value["valid"]
            ).items())),
            "invalid_reasons_last5": tuple(sorted(Counter(
                value["reason"] for value in values[-5:] if not value["valid"]
            ).items())),
        }))
    return CompactFeatures(tuple(attached[row["sample_id"]] for row in requests.samples), tuple(coverage))


def sampling_witness(
    field: np.ndarray, valid: np.ndarray, points: np.ndarray,
) -> dict[str, np.ndarray]:
    """Copy the four bilinear neighbours without computing weights or samples.

    Corners are ordered 00,10,01,11, with the upper neighbours clipped only at
    the last integer image boundary, as in the causal sampler. Outside points
    have corner coordinates -1, vectors NaN, flags false. Interior invalid or
    nonfinite corner values remain visible for independent audit, including
    unused zero-weight corners. No field or point input is mutated.
    """
    _require(isinstance(field, np.ndarray) and field.dtype == np.dtype(np.float32)
             and field.ndim == 3 and field.shape[2] == 2 and min(field.shape[:2]) > 0,
             "Witness field must have nonempty float32 shape (H,W,2)")
    _require(isinstance(valid, np.ndarray) and valid.dtype == np.dtype(bool)
             and valid.shape == field.shape[:2], "Witness valid must be bool (H,W)")
    _require(isinstance(points, np.ndarray) and points.dtype == np.dtype(np.float64)
             and points.ndim == 2 and points.shape[1] == 2,
             "Witness points must be float64 (N,2)")
    height, width = field.shape[:2]
    inside = (np.isfinite(points).all(axis=1) & (points[:, 0] >= 0)
              & (points[:, 0] <= width - 1) & (points[:, 1] >= 0)
              & (points[:, 1] <= height - 1))
    corners_xy = np.full((len(points), 4, 2), -1, dtype=np.int64)
    corner_uv = np.full((len(points), 4, 2), np.nan, dtype=np.float32)
    corner_valid = np.zeros((len(points), 4), dtype=bool)
    selected = np.flatnonzero(inside)
    if len(selected):
        x0, y0 = np.floor(points[selected]).astype(np.int64).T
        x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
        for index, (x, y) in enumerate(((x0, y0), (x1, y0), (x0, y1), (x1, y1))):
            corners_xy[selected, index] = np.column_stack((x, y))
            corner_uv[selected, index] = field[y, x]
            corner_valid[selected, index] = valid[y, x]
    return {"corners_xy": corners_xy, "corner_uv": corner_uv,
            "corner_valid": corner_valid, "inside": inside}
