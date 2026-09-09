"""Strict sampling and authenticated, causal optical-flow pairs.

The archive describes ``frame_from -> frame_to`` for one named video. A
consumer with information available through ``origin_frame`` may only load
pairs ending at or before that origin. Diagnostics describe apparent image
motion; none estimates physical fluid velocity or error against unknown truth.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from .base import FlowResult


_IDENTITY_KEYS = {
    "video_id", "frame_from", "frame_to", "source_sha256", "estimator_hash",
    "width", "height",
}
_RECORD_KEYS = _IDENTITY_KEYS | {"path", "sha256"}
_METADATA_KEYS = _IDENTITY_KEYS | {"schema_version"}
_ARRAY_KEYS = {"metadata", "forward", "backward", "forward_valid", "backward_valid"}


def strict_sample(
    field: np.ndarray, valid: np.ndarray, points_xy: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Bilinear sampling in float64, without clipping or validity imputation.

    Coordinates have shape ``(N, 2)`` in ``(x, y)`` order. Every corner with
    strictly positive interpolation weight must be valid and finite in every
    channel. Zero-weight corners do not invalidate exact pixel/border samples.
    An invalid sample is NaN in every channel and has ``good=False``.
    """
    values = np.asarray(field)
    mask = np.asarray(valid)
    points = np.asarray(points_xy)
    if values.ndim not in (2, 3) or min(values.shape[:2]) <= 0:
        raise ValueError("field must be nonempty (H,W) or (H,W,C)")
    if values.ndim == 3 and values.shape[2] == 0:
        raise ValueError("field must have at least one channel")
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
        raise ValueError("field must contain real numeric values")
    if mask.dtype != np.dtype(bool) or mask.shape != values.shape[:2]:
        raise ValueError("valid must be a boolean (H,W) array")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points_xy must have shape (N,2)")
    if not np.issubdtype(points.dtype, np.number) or np.iscomplexobj(points):
        raise ValueError("points_xy must contain real numeric values")
    points = points.astype(np.float64, copy=False)
    height, width = values.shape[:2]
    channels = 1 if values.ndim == 2 else values.shape[2]
    output = np.full((len(points), channels), np.nan, dtype=np.float64)
    good = (
        np.isfinite(points).all(axis=1)
        & (points[:, 0] >= 0) & (points[:, 0] <= width - 1)
        & (points[:, 1] >= 0) & (points[:, 1] <= height - 1)
    )
    selected = np.flatnonzero(good)
    if len(selected):
        p = points[selected]
        x0, y0 = np.floor(p).astype(np.int64).T
        x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
        wx, wy = (p - np.column_stack((x0, y0))).T
        total = np.zeros((len(selected), channels), dtype=np.float64)
        available = np.ones(len(selected), dtype=bool)
        for x, y, weight in (
            (x0, y0, (1 - wx) * (1 - wy)),
            (x1, y0, wx * (1 - wy)),
            (x0, y1, (1 - wx) * wy),
            (x1, y1, wx * wy),
        ):
            corner = values[y, x].reshape(len(selected), channels).astype(np.float64)
            active = weight > 0
            finite_valid = mask[y, x] & np.isfinite(corner).all(axis=1)
            available &= ~active | finite_valid
            # Mask before multiplication: NaN * 0 must never poison an exact
            # sample whose unused corner is invalid.
            contribution = np.where((active & finite_valid)[:, None], corner, 0.0)
            total += contribution * weight[:, None]
        available &= np.isfinite(total).all(axis=1)
        good[selected] = available
        output[selected[available]] = total[available]
    return (output[:, 0] if values.ndim == 2 else output), good


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA256 digest")
    return value


def _identity(
    *, video_id: str, frame_from: int, frame_to: int,
    source_sha256: str, estimator_hash: str, width: int, height: int,
) -> dict[str, Any]:
    if not isinstance(video_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", video_id) is None:
        raise ValueError("video_id must be a nonempty explicit identifier")
    _integer(frame_from, "frame_from")
    _integer(frame_to, "frame_to")
    if frame_to != frame_from + 1:
        raise ValueError("flow pair must contain consecutive frames")
    return {
        "video_id": video_id, "frame_from": frame_from, "frame_to": frame_to,
        "source_sha256": _digest(source_sha256, "source_sha256"),
        "estimator_hash": _digest(estimator_hash, "estimator_hash"),
        "width": _integer(width, "width", minimum=1),
        "height": _integer(height, "height", minimum=1),
    }


def _validate_flow(result: FlowResult, name: str) -> tuple[int, int]:
    if not isinstance(result, FlowResult):
        raise ValueError(f"{name} must be a FlowResult")
    field, valid = result.flow, result.valid
    if (
        not isinstance(field, np.ndarray) or field.dtype != np.dtype(np.float32)
        or field.ndim != 3 or field.shape[2] != 2 or min(field.shape[:2]) <= 0
    ):
        raise ValueError(f"{name} must have nonempty float32 flow (H,W,2)")
    if (
        not isinstance(valid, np.ndarray) or valid.dtype != np.dtype(bool)
        or valid.shape != field.shape[:2]
    ):
        raise ValueError(f"{name} must have boolean valid (H,W)")
    if not np.isfinite(field[valid]).all():
        raise ValueError(f"{name} contains nonfinite vectors declared valid")
    return field.shape[:2]


def _basename(value: Any) -> str:
    # Both Windows and POSIX separators are rejected, independent of host OS.
    if (
        not isinstance(value, str) or value in {"", ".", ".."}
        or any(character in value for character in ("/", "\\", ":", "\x00"))
        or not value.endswith(".npz")
    ):
        raise ValueError("pair path must be an explicit .npz basename")
    return value


def write_pair(
    path: str | Path, *, video_id: str, frame_from: int, frame_to: int,
    source_sha256: str, estimator_hash: str,
    forward: FlowResult, backward: FlowResult,
) -> dict[str, Any]:
    """Write a new immutable pair archive and return its authenticated index.

    Parent directories must already exist. Exclusive creation refuses every
    existing destination. A failed write may leave an incomplete file, which
    is never returned as a usable indexed pair. Confidence and estimator-local
    metadata are not serialized; the resolved estimator hash binds this cache.
    """
    path = Path(path)
    _basename(path.name)
    height, width = _validate_flow(forward, "forward")
    if _validate_flow(backward, "backward") != (height, width):
        raise ValueError("forward and backward shapes differ")
    identity = _identity(
        video_id=video_id, frame_from=frame_from, frame_to=frame_to,
        source_sha256=source_sha256, estimator_hash=estimator_hash,
        width=width, height=height,
    )
    metadata = json.dumps({"schema_version": 1, **identity}, sort_keys=True, allow_nan=False)
    with path.open("xb") as stream:
        np.savez_compressed(
            stream, metadata=np.asarray(metadata), forward=forward.flow,
            backward=backward.flow, forward_valid=forward.valid,
            backward_valid=backward.valid,
        )
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **identity}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate metadata key: {key}")
        output[key] = value
    return output


def load_pair(
    path: str | Path, record: dict[str, Any], *, video_id: str,
    frame_from: int, frame_to: int, origin_frame: int,
    source_sha256: str, estimator_hash: str,
) -> tuple[FlowResult, FlowResult]:
    """Load the exact indexed video/pair, only if available at the origin.

    Read and hash one byte snapshot before parsing its pickle-free NPZ. Neither
    a matching filename nor a valid NPZ alone is sufficient provenance. The
    caller must separately authenticate the containing index/manifest.
    """
    path = Path(path)
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
        raise ValueError("pair record has unexpected schema")
    if _basename(record["path"]) != path.name:
        raise ValueError("pair path does not match its record")
    _digest(record["sha256"], "sha256")
    recorded_identity = _identity(**{key: record[key] for key in _IDENTITY_KEYS})
    expected = _identity(
        video_id=video_id, frame_from=frame_from, frame_to=frame_to,
        source_sha256=source_sha256, estimator_hash=estimator_hash,
        width=record["width"], height=record["height"],
    )
    if recorded_identity != expected:
        raise ValueError("pair video, frame or provenance does not match request")
    _integer(origin_frame, "origin_frame")
    if frame_to > origin_frame:
        raise ValueError("future flow is unavailable at origin_frame")
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != record["sha256"]:
        raise ValueError("pair archive SHA256 mismatch")
    try:
        with np.load(io.BytesIO(blob), allow_pickle=False) as archive:
            if len(archive.files) != len(_ARRAY_KEYS) or set(archive.files) != _ARRAY_KEYS:
                raise ValueError("pair archive has unexpected array schema")
            raw_metadata = archive["metadata"]
            if raw_metadata.ndim != 0 or raw_metadata.dtype.kind != "U":
                raise ValueError("metadata must be a Unicode scalar")
            metadata = json.loads(str(raw_metadata.item()), object_pairs_hook=_unique_object)
            if not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
                raise ValueError("pair metadata has unexpected schema")
            if type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1:
                raise ValueError("unsupported pair schema_version")
            actual_identity = _identity(**{key: metadata[key] for key in _IDENTITY_KEYS})
            if actual_identity != expected:
                raise ValueError("pair metadata does not match authenticated index")
            fields = [archive["forward"], archive["backward"]]
            masks = [archive["forward_valid"], archive["backward_valid"]]
    except (OSError, EOFError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid pair archive") from exc
    results = []
    for direction, field, valid in zip(("forward", "backward"), fields, masks):
        # Check raw dtypes/validity BEFORE FlowResult can cast or normalize them.
        if field.dtype != np.dtype(np.float32) or field.shape != (expected["height"], expected["width"], 2):
            raise ValueError(f"{direction} array must have exact float32 shape")
        if valid.dtype != np.dtype(bool) or valid.shape != field.shape[:2]:
            raise ValueError(f"{direction}_valid array must have exact boolean shape")
        if not np.isfinite(field[valid]).all():
            raise ValueError(f"{direction} contains nonfinite vectors declared valid")
        results.append(FlowResult(field, valid, metadata={**metadata, "direction": direction}))
    return results[0], results[1]


def _advected_points(flow: FlowResult) -> np.ndarray:
    y, x = np.indices(flow.flow.shape[:2], dtype=np.float64)
    return np.column_stack((x.ravel(), y.ravel())) + flow.flow.reshape(-1, 2).astype(np.float64)


def pair_diagnostics(
    previous_gray_u8: np.ndarray, next_gray_u8: np.ndarray,
    forward: FlowResult, backward: FlowResult, threshold: float = 1.5,
) -> dict[str, float | int | None]:
    """Photometry and round-trip consistency with explicit finite support.

    Warped and zero-motion MAE use the SAME forward-valid, in-bounds warped
    support and intensities divided by 255. FB consistency is diagnostic only;
    its threshold never alters the estimator's valid mask. Pixel fractions use
    H*W as denominator; consistent_fraction uses only valid round trips.
    """
    shape = _validate_flow(forward, "forward")
    if _validate_flow(backward, "backward") != shape:
        raise ValueError("forward and backward shapes differ")
    previous, following = np.asarray(previous_gray_u8), np.asarray(next_gray_u8)
    if (
        previous.dtype != np.dtype(np.uint8) or following.dtype != np.dtype(np.uint8)
        or previous.shape != shape or following.shape != shape
    ):
        raise ValueError("diagnostic images must be uint8 grayscale matching flow")
    if isinstance(threshold, bool) or not np.isfinite(threshold) or threshold < 0:
        raise ValueError("consistency threshold must be finite and nonnegative")
    points = _advected_points(forward)
    count = int(np.prod(shape))
    forward_valid = forward.valid.ravel()
    warped, warped_good = strict_sample(following, np.ones(shape, dtype=bool), points)
    photo_good = forward_valid & warped_good
    photo_count = int(photo_good.sum())
    previous64, following64 = previous.ravel().astype(np.float64), following.ravel().astype(np.float64)
    backward_at_next, backward_good = strict_sample(backward.flow, backward.valid, points)
    roundtrip_good = forward_valid & backward_good
    roundtrip_count = int(roundtrip_good.sum())
    residual = np.linalg.norm(
        forward.flow.reshape(-1, 2)[roundtrip_good].astype(np.float64)
        + backward_at_next[roundtrip_good], axis=1,
    )
    return {
        "photometric_warp_mae": float(np.abs(previous64[photo_good] - warped[photo_good]).mean() / 255.0) if photo_count else None,
        "photometric_zero_mae": float(np.abs(previous64[photo_good] - following64[photo_good]).mean() / 255.0) if photo_count else None,
        "photometric_valid_pixels": photo_count,
        "photometric_valid_fraction": photo_count / count,
        "forward_backward_mae": float(residual.mean()) if roundtrip_count else None,
        "consistent_fraction": float((residual <= threshold).mean()) if roundtrip_count else None,
        "forward_backward_valid_pixels": roundtrip_count,
        "forward_backward_valid_fraction": roundtrip_count / count,
        "flow_finite_valid_fraction": int(forward_valid.sum()) / count,
    }


def temporal_diagnostics(first: FlowResult, following: FlowResult) -> dict[str, float | int | None]:
    """Describe F_next(p+F_first(p))-F_first(p), not error against truth.

    The caller must bind these fields to consecutive, causal pair records.
    Advection samples the next field on the first field's transported grid.
    Positive-weight validity is strict; no missing vector becomes zero.
    """
    shape = _validate_flow(first, "first")
    if _validate_flow(following, "following") != shape:
        raise ValueError("temporal fields must have identical shapes")
    sampled, good = strict_sample(following.flow, following.valid, _advected_points(first))
    good &= first.valid.ravel()
    count = int(good.sum())
    difference = np.linalg.norm(sampled[good] - first.flow.reshape(-1, 2)[good].astype(np.float64), axis=1)
    return {
        "advected_temporal_mean_change": float(difference.mean()) if count else None,
        "advected_temporal_p95_change": float(np.percentile(difference, 95)) if count else None,
        "advected_temporal_valid_pixels": count,
        "advected_temporal_valid_fraction": count / int(np.prod(shape)),
    }
