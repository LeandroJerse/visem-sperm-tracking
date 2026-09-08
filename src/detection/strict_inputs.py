"""Immutable input contract for complete annotated videos, without pixel decoding.

Preparation reads only the requested canonical MP4 and its labels. Dimensions
and frame count are expectations supplied before evaluation, not values inferred
from detector metrics. Missing label files remain explicitly unannotated.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from src.core.artifacts import sha256_file
from .base import Detection
from .io import GroundTruthFrame, parse_gt_text


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _canonical_paths(video_path: str | Path, gt_dir: str | Path, video_id: str) -> tuple[Path, Path]:
    video = Path(video_path).resolve(strict=True)
    labels = Path(gt_dir).resolve(strict=True)
    if (not video.is_file() or video.name != f"{video_id}.mp4"
            or video.parent.name != video_id):
        raise ValueError("Canonical video path must be <video_id>/<video_id>.mp4")
    if not labels.is_dir() or labels != video.parent / "labels_ftid":
        raise ValueError("GT directory must be the same video's canonical labels_ftid folder")
    return video, labels


def _inventory(folder: Path) -> tuple[tuple[str, str], ...]:
    entries = []
    for path in sorted(folder.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            raise ValueError(f"GT inventory does not accept symbolic links: {path}")
        kind = "file" if path.is_file() else "directory" if path.is_dir() else "other"
        if path.suffix.lower() == ".txt" and kind != "file":
            raise ValueError(f"Label entry is not a regular file: {path}")
        entries.append((path.name, kind))
    return tuple(entries)


def _file_hash(path: Path) -> tuple[str, int]:
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError(f"Input changed while hashing: {path}")
    return digest, after.st_size


def _video_metadata(video: Path, width: int, height: int, frames: int) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open video metadata: {video}")
        result = {
            "width": float(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": float(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "frame_count": float(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        }
        for name, expected in (("width", width), ("height", height), ("frame_count", frames)):
            if not math.isfinite(result[name]) or result[name] != expected:
                raise ValueError(f"Video metadata {name}={result[name]} differs from expected {expected}")
            result[name] = expected
        if not math.isfinite(result["fps"]) or result["fps"] <= 0:
            raise ValueError("Video FPS must be finite and positive")
        result["backend"] = capture.getBackendName() if hasattr(capture, "getBackendName") else None
        return result
    finally:
        capture.release()


@dataclass(frozen=True)
class FullVideoInput:
    """Prepared source identity and immutable GT values for one full video.

    Obtain instances from ``prepare_full_video_input``. ``gt_frame`` creates
    fresh Detection objects, so a consumer cannot mutate the prepared GT.
    ``reference`` is JSON serializable and returns a detached copy.
    """

    video_path: Path
    gt_dir: Path
    video_id: str
    expected_width: int
    expected_height: int
    expected_frame_count: int
    _records: tuple[tuple[tuple[float, float, float, float, int, str], ...] | None, ...]
    _label_names: tuple[str | None, ...]
    _reference_json: str

    @property
    def input_hash(self) -> str:
        return self.reference()["input_hash"]

    def reference(self) -> dict[str, Any]:
        return json.loads(self._reference_json)

    def metadata(self) -> dict[str, Any]:
        return self.reference()

    def gt_frame(self, frame_idx: int) -> GroundTruthFrame:
        if isinstance(frame_idx, bool) or not isinstance(frame_idx, int) or not 0 <= frame_idx < self.expected_frame_count:
            raise IndexError(f"Frame {frame_idx!r} is outside the prepared video")
        records = self._records[frame_idx]
        return GroundTruthFrame(
            frame_idx, records is not None,
            tuple(Detection(cx, cy, w, h, class_id=cls, object_id=identity)
                  for cx, cy, w, h, cls, identity in records) if records is not None else (),
            self.gt_dir / self._label_names[frame_idx] if records is not None else None,
        )

    @property
    def gt_frames(self) -> tuple[GroundTruthFrame, ...]:
        return tuple(self.gt_frame(index) for index in range(self.expected_frame_count))

    def assert_matches(self, video_path: str | Path, gt_dir: str | Path | None, video_id: str | None) -> None:
        if gt_dir is None:
            raise ValueError("Full-video execution requires its prepared GT directory")
        video, labels = _canonical_paths(video_path, gt_dir, self.video_id)
        if video != self.video_path or labels != self.gt_dir or str(video_id) != self.video_id:
            raise ValueError("Video, GT directory and video_id must exactly match the full-video input")

    def verify_current(self) -> dict[str, Any]:
        """Recheck every label hash, MP4 hash and directory inventory; no pixels."""
        self.assert_matches(self.video_path, self.gt_dir, self.video_id)
        reference = self.reference()
        observed_inventory = [list(entry) for entry in _inventory(self.gt_dir)]
        if observed_inventory != reference["inventory"]["entries"]:
            raise ValueError("GT directory inventory changed after preparation")
        for record in [reference["source_video"], *reference["ground_truth"]["files"]]:
            digest, size = _file_hash(Path(record["path"]))
            if digest != record["sha256"] or size != record["bytes"]:
                raise ValueError(f"Prepared input content changed: {record['path']}")
        return {"status": "verified", "input_hash": reference["input_hash"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "checks": ["canonical_paths", "mp4_sha256", "label_sha256", "directory_inventory"],
                "files_verified": 1 + len(reference["ground_truth"]["files"])}


def prepare_full_video_input(
    video_path: str | Path, gt_dir: str | Path, *, video_id: str | int,
    expected_width: int = 640, expected_height: int = 480,
    expected_frame_count: int = 1470,
) -> FullVideoInput:
    """Validate a canonical video and all tracked labels without decoding frames.

    ``expected_frame_count`` is per video (for example, a shorter registered
    video must supply its own expectation). Header agreement is only preflight;
    the strict runner subsequently verifies the entire decoded frame universe.
    """
    if isinstance(video_id, bool) or not re.fullmatch(r"[1-9][0-9]*", str(video_id)):
        raise ValueError("video_id must be a canonical positive integer identifier")
    identity = str(video_id)
    width = _positive_integer(expected_width, "expected_width")
    height = _positive_integer(expected_height, "expected_height")
    count = _positive_integer(expected_frame_count, "expected_frame_count")
    video, labels = _canonical_paths(video_path, gt_dir, identity)
    video_sha, video_bytes = _file_hash(video)
    metadata = _video_metadata(video, width, height, count)
    inventory = _inventory(labels)
    pattern = re.compile(rf"{re.escape(identity)}_frame_(?P<frame>[0-9]+)_with_ftid\.txt")
    names: list[str | None] = [None] * count
    records: list[tuple | None] = [None] * count
    label_files = []
    for name, _kind in inventory:
        if Path(name).suffix.lower() != ".txt":
            continue
        match = pattern.fullmatch(name)
        if match is None:
            raise ValueError(f"Noncanonical label filename or wrong video prefix: {name}")
        index = int(match.group("frame"))
        if index >= count:
            raise ValueError(f"Label frame {index} is outside expected range 0..{count - 1}")
        if names[index] is not None:
            raise ValueError(f"Duplicate label index {index}: {names[index]} and {name}")
        path = labels / name
        content = path.read_bytes()
        detections = parse_gt_text(content.decode("utf-8-sig"), width, height,
                                   strict_ftid=True, label_path=path)
        names[index] = name
        records[index] = tuple((float(item.cx), float(item.cy), float(item.w), float(item.h),
                                item.class_id, str(item.object_id)) for item in detections)
        label_files.append({"path": str(path), "name": name, "frame": index,
                            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                            "rows": len(detections)})
    if not label_files:
        raise ValueError("Complete annotated-video input requires at least one label file")
    label_files.sort(key=lambda record: record["frame"])
    missing = [index for index, item in enumerate(records) if item is None]
    reference = {
        "schema_version": 1, "contract": "full_video_input_v1", "video_id": identity,
        "expected_width": width, "expected_height": height, "expected_frame_count": count,
        "source_video": {"path": str(video), "sha256": video_sha, "bytes": video_bytes},
        "video_metadata": metadata,
        "ground_truth": {"directory": str(labels), "layout": "track_id class cx cy w h",
                         "files": label_files, "annotated_frames": len(label_files),
                         "unannotated_frames": len(missing), "unannotated_indices": missing,
                         "annotated_empty_frames": sum(item == () for item in records)},
        "inventory": {"entries": inventory, "sha256": _json_hash(inventory)},
    }
    reference["input_hash"] = _json_hash(reference)
    result = FullVideoInput(video, labels, identity, width, height, count, tuple(records), tuple(names),
                            json.dumps(reference, sort_keys=True, ensure_ascii=False, allow_nan=False))
    result.verify_current()
    return result
