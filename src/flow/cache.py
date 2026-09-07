"""Content-addressed flow cache and trajectory-level flow feature sampling."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np

from .base import FlowResult
from .metrics import sample_field


def make_cache_key(*parts: object, config: Mapping[str, Any] | None = None) -> str:
    """Build a stable SHA-256 key from frame identifiers and resolved config."""

    payload = {"parts": [str(part) for part in parts], "config": dict(config or {})}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FlowCache:
    """Immutable ``.npz`` cache; an existing key is never silently replaced."""

    def __init__(self, root: str | Path, *, compressed: bool = True) -> None:
        self.root = Path(root)
        self.compressed = bool(compressed)

    def path_for(self, key: str) -> Path:
        if not key or any(character not in "0123456789abcdef-_" for character in key.lower()):
            raise ValueError("cache key must contain only hexadecimal, '-' or '_'")
        return self.root / key[:2] / f"{key}.npz"

    def exists(self, key: str) -> bool:
        return self.path_for(key).is_file()

    def save(self, key: str, result: FlowResult, *, overwrite: bool = False) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            return path
        metadata = json.dumps(result.metadata, sort_keys=True, default=str)
        writer = np.savez_compressed if self.compressed else np.savez
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{key}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                payload: dict[str, np.ndarray] = {
                    "flow": result.flow,
                    "valid": result.valid.astype(np.uint8),
                    "metadata": np.asarray(metadata),
                }
                if result.confidence is not None:
                    payload["confidence"] = result.confidence
                writer(temporary, **payload)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return path

    def load(self, key: str) -> FlowResult | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        return load_flow_file(path)


def load_flow_file(path: str | Path) -> FlowResult:
    """Load one trusted flow ``.npz`` artifact without inferring its cache root."""

    artifact = Path(path)
    if not artifact.is_file():
        raise FileNotFoundError(f"flow cache artifact not found: {artifact}")
    try:
        archive_context = np.load(artifact, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid flow cache artifact: {artifact}") from exc
    with archive_context as archive:
        required = {"flow", "valid", "metadata"}
        missing = required - set(archive.files)
        if missing:
            raise ValueError(
                f"flow cache artifact missing arrays {sorted(missing)}: {artifact}"
            )
        try:
            metadata = json.loads(str(archive["metadata"].item()))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid flow metadata in {artifact}") from exc
        confidence = archive["confidence"] if "confidence" in archive.files else None
        return FlowResult(
            archive["flow"],
            archive["valid"].astype(bool),
            confidence,
            metadata,
        )


@dataclass(frozen=True)
class SampledFlow:
    vectors: np.ndarray
    valid: np.ndarray
    confidence: np.ndarray | None

    @property
    def features(self) -> np.ndarray:
        """Return ``u, v, magnitude, direction`` for prediction models."""

        magnitude = np.linalg.norm(self.vectors, axis=-1)
        direction = np.arctan2(self.vectors[..., 1], self.vectors[..., 0])
        return np.concatenate(
            (self.vectors, magnitude[..., None], direction[..., None]), axis=-1
        ).astype(np.float32)


def sample_flow(result: FlowResult, points_xy: np.ndarray) -> SampledFlow:
    """Bilinearly sample flow at trajectory positions."""

    vectors, inside = sample_field(result.flow, points_xy)
    validity, _ = sample_field(
        result.valid.astype(np.float32), points_xy, outside_value=0.0
    )
    valid = inside & (validity >= 0.999) & np.isfinite(vectors).all(axis=-1)
    vectors = np.where(valid[..., None], vectors, np.nan).astype(np.float32)
    confidence = None
    if result.confidence is not None:
        confidence, _ = sample_field(result.confidence, points_xy, outside_value=0.0)
        confidence = np.where(valid, confidence, 0.0).astype(np.float32)
    return SampledFlow(vectors, valid, confidence)


def sample_background_flow(
    result: FlowResult,
    points_xy: np.ndarray,
    *,
    radius: int = 7,
    inner_radius: int = 2,
    min_samples: int = 8,
) -> SampledFlow:
    """Robustly sample masked background flow around object centers.

    A sperm center is normally invalid after masking the object itself.  This
    helper takes the component-wise median in a circular annulus around each
    point, avoiding the scientifically incorrect fallback of replacing missing
    flow by ``(0, 0)``.  The strict :func:`sample_flow` remains available when
    the field is valid at the requested position.
    """

    if radius <= 0 or inner_radius < 0 or inner_radius >= radius:
        raise ValueError("require radius > inner_radius >= 0")
    if min_samples <= 0:
        raise ValueError("min_samples must be positive")
    points = np.asarray(points_xy, dtype=np.float32)
    if points.ndim < 1 or points.shape[-1] != 2:
        raise ValueError("points_xy must have final dimension 2")
    original_shape = points.shape[:-1]
    flat = points.reshape(-1, 2)
    vectors = np.full((len(flat), 2), np.nan, dtype=np.float32)
    valid = np.zeros(len(flat), dtype=bool)
    confidence = (
        np.zeros(len(flat), dtype=np.float32)
        if result.confidence is not None
        else None
    )
    height, width = result.flow.shape[:2]
    outer_squared = radius * radius
    inner_squared = inner_radius * inner_radius

    for index, point in enumerate(flat):
        if not np.isfinite(point).all():
            continue
        center_x, center_y = float(point[0]), float(point[1])
        x0 = max(0, int(np.floor(center_x - radius)))
        x1 = min(width, int(np.ceil(center_x + radius)) + 1)
        y0 = max(0, int(np.floor(center_y - radius)))
        y1 = min(height, int(np.ceil(center_y + radius)) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        distance_squared = (xx - center_x) ** 2 + (yy - center_y) ** 2
        candidates = (
            result.valid[y0:y1, x0:x1]
            & (distance_squared <= outer_squared)
            & (distance_squared >= inner_squared)
        )
        if int(candidates.sum()) < min_samples:
            continue
        neighborhood = result.flow[y0:y1, x0:x1][candidates]
        vectors[index] = np.median(neighborhood, axis=0)
        valid[index] = True
        if result.confidence is not None:
            assert confidence is not None
            confidence[index] = float(
                np.median(result.confidence[y0:y1, x0:x1][candidates])
            )
    return SampledFlow(
        vectors.reshape(original_shape + (2,)),
        valid.reshape(original_shape),
        None if confidence is None else confidence.reshape(original_shape),
    )


def sample_trajectory_features(
    flow_by_frame: Mapping[int, FlowResult],
    frame_ids: Sequence[int],
    positions_xy: np.ndarray,
    *,
    background_radius: int | None = None,
    background_inner_radius: int = 2,
    min_background_samples: int = 8,
) -> SampledFlow:
    """Sample the ``frame -> frame+1`` field at each trajectory position.

    Set ``background_radius`` when objects were masked from the flow.  Sampling
    then uses a robust annular neighborhood rather than a zero-flow fallback.
    """

    frames = np.asarray(frame_ids, dtype=int)
    positions = np.asarray(positions_xy, dtype=np.float32)
    if positions.shape != (len(frames), 2):
        raise ValueError("positions_xy must have shape (len(frame_ids), 2)")
    vectors = np.full((len(frames), 2), np.nan, dtype=np.float32)
    valid = np.zeros(len(frames), dtype=bool)
    confidences = np.zeros(len(frames), dtype=np.float32)
    has_confidence = False
    for index, (frame_id, position) in enumerate(zip(frames, positions)):
        result = flow_by_frame.get(int(frame_id))
        if result is None:
            continue
        sampled = (
            sample_flow(result, position[None, :])
            if background_radius is None
            else sample_background_flow(
                result,
                position[None, :],
                radius=background_radius,
                inner_radius=background_inner_radius,
                min_samples=min_background_samples,
            )
        )
        vectors[index] = sampled.vectors[0]
        valid[index] = bool(sampled.valid[0])
        if sampled.confidence is not None:
            has_confidence = True
            confidences[index] = sampled.confidence[0]
    return SampledFlow(vectors, valid, confidences if has_confidence else None)
