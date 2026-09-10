"""Read the audited training reference without exposing targets to predictors.

Only exported metadata/tables are read. Raw-GT bytes are hashed, never parsed;
the distinction between ``class_1`` and ``id_absent`` boundary reasons remains
producer evidence certified by the pinned independent audit. All frame axes,
individual observations, segment intervals and window indices are checked here.
This is a development reference conditioned on complete future targets, not an
evaluation of detected/tracked trajectories or independent test performance.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any
from urllib.parse import quote

import numpy as np

from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import config_hash


TRAIN_IDS = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
EXPECTED_FRAMES = {video: 1440 if video == "35" else 1500 if video == "82" else 1470 for video in TRAIN_IDS}
HISTORY_LENGTH, FORECAST_HORIZON = 20, 10
_GAPS = {"23": ((823, 972), (1084, 1107))}
_START = ("video_start", "annotation_absent", "class_1", "id_absent")
_END = ("video_end", "annotation_absent", "class_1", "id_absent")
_FIELDS = {
    "observations": "video_id frame_index annotated track_id segment_id class_id cx cy w h x y".split(),
    "segments": "video_id track_id segment_id split start_frame end_frame observation_count start_reason end_reason end_boundary_frame".split(),
    "windows": "window_id video_id track_id segment_id split history_start origin_frame future_end history_length forecast_horizon".split(),
    "frame_status": "video_id frame_index annotated raw_count individual_count cluster_count".split(),
}
_ARTIFACT_NAMES = (*[f"{name}.csv" for name in _FIELDS], "ground_truth_raw.csv", "summary.json", "input_contract.json")
_METADATA_PATHS = ("configs/protocol/individual_trajectories_v1.yaml", "configs/protocol/splits.yaml",
                   "data/manifests/visem_tracking.csv", "data/manifests/annotation_gaps.csv")
_TOTALS = ("frames_total", "frames_annotated", "frames_unannotated", "raw_observations",
           "individual_observations", "cluster_observations", "segments_total", "segments_with_windows",
           "segments_without_windows", "origins_with_complete_history", "windows_total",
           "origins_excluded_incomplete_future")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mapping(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(content: bytes) -> Any:
    return json.loads(content.decode("utf-8-sig"), object_pairs_hook=_mapping,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON: {token}")))


def _integer(value: Any, name: str) -> int:
    _require(not isinstance(value, bool) and (isinstance(value, int)
             or isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value) is not None),
             f"{name} must be a nonnegative integer")
    result = int(value)
    _require(result >= 0, f"{name} must be nonnegative")
    return result


def _boolean(value: str) -> bool:
    _require(value in ("True", "False"), "CSV annotation flag must be True or False")
    return value == "True"


def _token(value: Any, name: str) -> str:
    _require(isinstance(value, str) and bool(value) and value.isprintable()
             and not any(c.isspace() for c in value) and value != "-1", f"Invalid {name}")
    return value


def _number(value: Any, name: str) -> float:
    _require(not isinstance(value, bool), f"Invalid numeric {name}")
    result = float(value)
    _require(math.isfinite(result), f"Nonfinite {name}")
    return result


def _same(value: Any, expected: Any, name: str) -> None:
    _require(config_hash(value, 64) == config_hash(expected, 64), f"Inconsistent {name}")


def _readonly(value: np.ndarray) -> np.ndarray:
    # Immutable bytes, rather than only a reversible WRITEABLE flag. Every
    # public batch owns detached bytes and cannot change the loaded reference.
    return np.frombuffer(value.tobytes(order="C"), dtype=np.float64).reshape(value.shape)


@dataclass(frozen=True)
class WindowBatch:
    histories: np.ndarray
    targets: np.ndarray
    window_rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class HistoryBatch:
    """Detached historical inputs at one origin, without future coordinates."""

    histories: np.ndarray
    window_rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class VideoReference:
    video_id: str
    fps: float
    _summary_json: str = field(repr=False)
    _positions: Mapping[str, np.ndarray] = field(repr=False)
    _starts: Mapping[str, int] = field(repr=False)
    _windows: tuple[tuple[Any, ...], ...] = field(repr=False)

    @property
    def summary(self) -> dict:
        return json.loads(self._summary_json)

    @property
    def n_windows(self) -> int:
        return len(self._windows)

    @property
    def track_ids_with_windows(self) -> tuple[str, ...]:
        return tuple(sorted({row[2] for row in self._windows}))

    @property
    def window_keys_sha256(self) -> str:
        """Fingerprint every audited key in order, independent of batch size."""
        digest = hashlib.sha256()
        for row in self._windows:
            digest.update(json.dumps(list(row[:8]), ensure_ascii=True, separators=(",", ":")).encode("utf-8") + b"\n")
        return digest.hexdigest()

    def iter_batches(self, batch_size: int = 512) -> Iterator[WindowBatch]:
        _require(type(batch_size) is int and batch_size > 0, "batch_size must be a positive integer")
        for start in range(0, self.n_windows, batch_size):
            specs = self._windows[start:start + batch_size]
            histories = np.empty((len(specs), HISTORY_LENGTH, 2), dtype=np.float64)
            targets = np.empty((len(specs), FORECAST_HORIZON, 2), dtype=np.float64)
            rows = []
            for index, spec in enumerate(specs):
                row = dict(zip(_FIELDS["windows"], spec))
                segment = row["segment_id"]
                offset = row["history_start"] - self._starts[segment]
                positions = self._positions[segment]
                histories[index] = positions[offset:offset + HISTORY_LENGTH]
                targets[index] = positions[offset + HISTORY_LENGTH:offset + HISTORY_LENGTH + FORECAST_HORIZON]
                rows.append(MappingProxyType(row))
            yield WindowBatch(_readonly(histories), _readonly(targets), tuple(rows))

    def history_batch_at_origin(self, origin_frame: int) -> HistoryBatch:
        """Return only histories of audited windows at a specified origin.

        Eligibility still comes from the parent's complete-future rule, but
        future coordinates are neither sliced nor returned by this interface.
        An empty batch never requests an alternative origin automatically.
        """
        _require(type(origin_frame) is int and origin_frame >= 0,
                 "origin_frame must be a nonnegative integer")
        specs = [spec for spec in self._windows if spec[6] == origin_frame]
        histories = np.empty((len(specs), HISTORY_LENGTH, 2), dtype=np.float64)
        rows = []
        for index, spec in enumerate(specs):
            row = dict(zip(_FIELDS["windows"], spec))
            segment = row["segment_id"]
            offset = row["history_start"] - self._starts[segment]
            histories[index] = self._positions[segment][offset:offset + HISTORY_LENGTH]
            rows.append(MappingProxyType(row))
        return HistoryBatch(_readonly(histories), tuple(rows))

    def iter_history_batches(self, *, first_origin: int, last_origin: int,
                             batch_size: int = 128) -> Iterator[HistoryBatch]:
        """Scan window metadata once and expose only bounded historical slices.

        This is the streaming counterpart of ``history_batch_at_origin``.
        Complete-future eligibility is inherited from the audited reference;
        target coordinates are never sliced or returned. Empty origin ranges
        yield no batches and are not replaced with another cohort.
        """
        _require(type(first_origin) is int and first_origin >= HISTORY_LENGTH - 1,
                 "first_origin must be an integer >= 19")
        _require(type(last_origin) is int and last_origin >= first_origin,
                 "last_origin must be an integer >= first_origin")
        _require(type(batch_size) is int and batch_size > 0,
                 "batch_size must be a positive integer")
        pending = []
        for spec in self._windows:
            if first_origin <= spec[6] <= last_origin:
                pending.append(spec)
                if len(pending) == batch_size:
                    yield self._history_batch(pending)
                    pending = []
        if pending:
            yield self._history_batch(pending)

    def _history_batch(self, specs: list[tuple[Any, ...]]) -> HistoryBatch:
        histories = np.empty((len(specs), HISTORY_LENGTH, 2), dtype=np.float64)
        rows = []
        for index, spec in enumerate(specs):
            row = dict(zip(_FIELDS["windows"], spec))
            segment = row["segment_id"]
            offset = row["history_start"] - self._starts[segment]
            histories[index] = self._positions[segment][offset:offset + HISTORY_LENGTH]
            rows.append(MappingProxyType(row))
        return HistoryBatch(_readonly(histories), tuple(rows))


@dataclass(frozen=True)
class _File:
    path: Path
    sha256: str
    size: int

    def read(self) -> bytes:
        content = self.path.read_bytes()
        _require(len(content) == self.size and hashlib.sha256(content).hexdigest() == self.sha256,
                 f"Reference file changed: {self.path}")
        return content

    def reference(self) -> dict:
        return {"path": str(self.path), "sha256": self.sha256, "bytes": self.size}


class _Inputs:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.records: dict[Path, _File] = {}

    def path(self, value: str | Path) -> Path:
        value = Path(value)
        path = (value if value.is_absolute() else self.root / value).resolve()
        _require(path.is_relative_to(self.root) and not path.is_relative_to(self.root / "data/sources"),
                 "Reference reader cannot access original sources or paths outside the repository")
        _require(path.suffix.lower() in (".json", ".csv", ".yaml", ".yml"), "Reference inputs must be exported metadata")
        return path

    def register(self, path: str | Path, sha256: str, size: int | None = None) -> _File:
        path = self.path(path)
        _require(isinstance(sha256, str) and re.fullmatch(r"[0-9a-f]{64}", sha256) is not None, "Invalid reference SHA256")
        if size is None:
            size = path.stat().st_size
        record = _File(path, sha256, _integer(size, "reference bytes"))
        if path in self.records:
            _require(self.records[path] == record, f"Conflicting reference: {path}")
        record.read()
        self.records[path] = record
        return record


def _csv(record: _File, table: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(record.read().decode("utf-8-sig")))
    _require(reader.fieldnames == _FIELDS[table], f"Unexpected {table} CSV schema")
    rows = list(reader)
    _require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
             f"Malformed {table} CSV row")
    return rows


def _video(video: str, tables: dict[str, list[dict]], summary: dict, contract: dict) -> VideoReference:
    count = EXPECTED_FRAMES[video]
    missing = {index for left, right in _GAPS.get(video, ()) for index in range(left, right + 1)}
    status = tables["frame_status"]
    _require(len(status) == count, "Frame status does not cover the complete video")
    for index, row in enumerate(status):
        _require(row["video_id"] == video and _integer(row["frame_index"], "frame_index") == index,
                 "Frame status must contain the exact ordered video/frame universe")
        row["annotated"] = _boolean(row["annotated"])
        _require(row["annotated"] == (index not in missing), "Annotation coverage differs from the registered gaps")
        for key in ("raw_count", "individual_count", "cluster_count"):
            row[key] = _integer(row[key], key)
        _require(row["raw_count"] == row["individual_count"] + row["cluster_count"], "Invalid raw/individual/cluster counts")
        _require(row["annotated"] or row["raw_count"] == 0, "Unannotated frames cannot contain observations")

    observations = tables["observations"]
    by_segment: dict[str, list[dict]] = {}
    observed_keys, ordered_keys, class_counts = set(), [], Counter()
    individual_counts = Counter()
    for row in observations:
        frame = _integer(row["frame_index"], "observation frame")
        identity = _token(row["track_id"], "track_id")
        segment = _token(row["segment_id"], "segment_id")
        cls = _integer(row["class_id"], "class_id")
        _require(row["video_id"] == video and frame < count and status[frame]["annotated"]
                 and _boolean(row["annotated"]) and cls in (0, 2), "Invalid individual observation cohort/class/frame")
        key = (frame, identity)
        _require(key not in observed_keys, "Duplicate individual ID within a frame")
        observed_keys.add(key)
        ordered_keys.append(key)
        row["frame_index"], row["class_id"] = frame, cls
        for key in ("cx", "cy", "w", "h", "x", "y"):
            row[key] = _number(row[key], key)
        _require(row["w"] > 0 and row["h"] > 0 and row["x"] >= -1e-9 and row["y"] >= -1e-9
                 and row["x"] + row["w"] <= 640 + 1e-9 and row["y"] + row["h"] <= 480 + 1e-9
                 and abs(row["x"] - (row["cx"] - row["w"] / 2)) <= 1e-9
                 and abs(row["y"] - (row["cy"] - row["h"] / 2)) <= 1e-9, "Invalid individual pixel geometry")
        by_segment.setdefault(segment, []).append(row)
        class_counts[str(cls)] += 1
        individual_counts[frame] += 1
    _require(ordered_keys == sorted(ordered_keys), "Observation order is not deterministic frame/ID order")
    _require(all(individual_counts[index] == row["individual_count"] for index, row in enumerate(status)),
             "Frame counts do not match individual observations")

    segments, seen_segments, positions, starts = tables["segments"], set(), {}, {}
    intervals: dict[str, list[tuple[int, int]]] = {}
    expected_windows = []
    origins, segments_with_windows = 0, 0
    exclusions = Counter()
    segment_order = []
    for row in segments:
        identity, segment = _token(row["track_id"], "track_id"), _token(row["segment_id"], "segment_id")
        start, end, boundary, length = (_integer(row[key], key) for key in
                                       ("start_frame", "end_frame", "end_boundary_frame", "observation_count"))
        _require(row["video_id"] == video and row["split"] == "train" and 0 <= start <= end < count,
                 "Invalid segment video/split/interval")
        _require(segment == f"{video}/{quote(identity, safe='')}/{start}" and segment not in seen_segments,
                 "Invalid or duplicate segment ID")
        seen_segments.add(segment)
        segment_order.append((start, identity))
        _require(boundary == end + 1 and length == end - start + 1, "Invalid segment boundary/count")
        rows = by_segment.get(segment, [])
        _require(len(rows) == length and [r["frame_index"] for r in rows] == list(range(start, end + 1))
                 and all(r["track_id"] == identity for r in rows), "Segment does not have complete consecutive observations of one ID")
        start_reason, end_reason = row["start_reason"], row["end_reason"]
        expected_start = "video_start" if start == 0 else "annotation_absent" if not status[start - 1]["annotated"] else None
        expected_end = "video_end" if end == count - 1 else "annotation_absent" if not status[end + 1]["annotated"] else None
        _require(start_reason == expected_start if expected_start else start_reason in ("class_1", "id_absent"),
                 "Segment start reason disagrees with frame coverage")
        _require(end_reason == expected_end if expected_end else end_reason in ("class_1", "id_absent"),
                 "Segment end reason disagrees with frame coverage")
        _require((start - 1, identity) not in observed_keys and (end + 1, identity) not in observed_keys,
                 "A segment may not split consecutive individual observations")
        intervals.setdefault(identity, []).append((start, end))
        positions[segment] = _readonly(np.array([(r["cx"], r["cy"]) for r in rows], dtype=np.float64))
        starts[segment] = start
        history_origins = max(0, length - HISTORY_LENGTH + 1)
        window_count = max(0, length - HISTORY_LENGTH - FORECAST_HORIZON + 1)
        origins += history_origins
        segments_with_windows += window_count > 0
        exclusions[end_reason] += history_origins - window_count
        for origin in range(start + HISTORY_LENGTH - 1, end - FORECAST_HORIZON + 1):
            expected_windows.append((f"{segment}/{origin}/h20_f10", video, identity, segment, "train",
                                     origin - HISTORY_LENGTH + 1, origin, origin + FORECAST_HORIZON,
                                     HISTORY_LENGTH, FORECAST_HORIZON))
    _require(segment_order == sorted(segment_order), "Segments are not in deterministic order")
    _require(seen_segments == set(by_segment), "Unknown or empty declared segment")
    for values in intervals.values():
        ordered = sorted(values)
        _require(all(right[0] > left[1] + 1 for left, right in zip(ordered, ordered[1:])), "Overlapping/adjacent segments of one ID")
    expected_windows.sort(key=lambda row: (row[6], row[2], row[3]))
    windows = []
    for row in tables["windows"]:
        for key in _FIELDS["windows"][5:]:
            row[key] = _integer(row[key], key)
        windows.append(tuple(row[key] for key in _FIELDS["windows"]))
    _require(windows == expected_windows, "Window IDs/indices must exactly equal all registered history20/future10 windows")

    expected_summary = {
        "schema_version": 1, "video_id": video, "split": "train", "expected_frame_count": count,
        "frames_total": count, "frames_annotated": count - len(missing), "frames_unannotated": len(missing),
        "frames_annotated_empty": sum(row["annotated"] and row["raw_count"] == 0 for row in status),
        "frames_with_individuals": sum(row["individual_count"] > 0 for row in status),
        "frames_with_clusters": sum(row["cluster_count"] > 0 for row in status),
        "frames_cluster_only": sum(row["cluster_count"] > 0 and row["individual_count"] == 0 for row in status),
        "raw_observations": sum(row["raw_count"] for row in status), "individual_observations": len(observations),
        "cluster_observations": sum(row["cluster_count"] for row in status),
        "class_observations": {"0": class_counts["0"], "1": sum(row["cluster_count"] for row in status), "2": class_counts["2"]},
        "unique_individual_track_ids": len(intervals), "segments_total": len(segments),
        "segments_with_windows": segments_with_windows, "segments_without_windows": len(segments) - segments_with_windows,
        "segment_start_reasons": {reason: sum(row["start_reason"] == reason for row in segments) for reason in _START},
        "segment_end_reasons": {reason: sum(row["end_reason"] == reason for row in segments) for reason in _END},
        "history_length": HISTORY_LENGTH, "forecast_horizon": FORECAST_HORIZON, "stride": 1,
        "origins_with_complete_history": origins, "windows_total": len(windows),
        "origins_excluded_incomplete_future": origins - len(windows),
        "excluded_origins_by_end_reason": {reason: exclusions[reason] for reason in _END},
    }
    for key, value in expected_summary.items():
        _same(summary.get(key), value, f"video {video} summary.{key}")
    raw_ids = _integer(summary.get("unique_raw_track_ids"), "unique_raw_track_ids")
    _require(len(intervals) <= raw_ids <= expected_summary["raw_observations"], "Invalid inherited raw ID count")
    _require(contract.get("contract") == "full_video_input_v1" and contract.get("video_id") == video
             and contract.get("expected_frame_count") == count and contract.get("expected_width") == 640
             and contract.get("expected_height") == 480, "Invalid exported input contract")
    metadata = contract.get("video_metadata", {})
    _require(metadata.get("frame_count") == count and metadata.get("width") == 640 and metadata.get("height") == 480,
             "Input metadata dimensions/frame count mismatch")
    fps = _number(metadata.get("fps"), "FPS")
    _require(fps > 0, "FPS must be positive")
    _same(contract.get("ground_truth", {}).get("unannotated_indices"), sorted(missing), "input-contract gaps")
    _require(contract["ground_truth"].get("annotated_frames") == count - len(missing)
             and contract["ground_truth"].get("unannotated_frames") == len(missing), "Input-contract annotation counts mismatch")
    return VideoReference(video, fps, json.dumps(summary), MappingProxyType(positions), MappingProxyType(starts), tuple(windows))


@dataclass(frozen=True)
class PredictionReference:
    _inputs: _Inputs = field(repr=False)
    _manifest: _File = field(repr=False)
    _qa: _File = field(repr=False)
    _summary_json: str = field(repr=False)
    _input_hashes: Mapping[str, str] = field(repr=False)

    @property
    def video_ids(self) -> tuple[str, ...]:
        return TRAIN_IDS

    @property
    def summary(self) -> dict:
        return json.loads(self._summary_json)

    @property
    def provenance(self) -> dict:
        return {"parent_manifest": self._manifest.reference(), "verification": self._qa.reference(),
                "validated_inputs": [record.reference() for record in self._inputs.records.values()],
                "boundary_reason_policy": "class_1_vs_id_absent_inherited_from_hashed_audited_reference",
                "original_sources_read": False, "scope": "individual_reference_v1_training_only"}

    def load_video(self, video_id: str) -> VideoReference:
        _require(video_id in TRAIN_IDS, "Reference allows only registered training video IDs")
        folder = self._manifest.path.parent / "by_video" / video_id
        records = self._inputs.records
        tables = {table: _csv(records[folder / f"{table}.csv"], table) for table in _FIELDS}
        summary = _json(records[folder / "summary.json"].read())
        declared = next(row for row in self.summary["videos"] if row["video_id"] == video_id)
        _same(summary, declared, "per-video and parent summaries")
        contract = _json(records[folder / "input_contract.json"].read())
        _require(contract.get("input_hash") == self._input_hashes[video_id], "Input contract hash identity differs from QA")
        return _video(video_id, tables, summary, contract)

    def verify_current(self) -> dict:
        for record in self._inputs.records.values():
            record.read()
        return {"status": "verified", "files_verified": len(self._inputs.records),
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "scope": "exported_reference_end_of_batch_no_original_source_recheck"}


def load_prediction_reference(
    manifest_path: str | Path, *, expected_manifest_sha256: str,
    verification_path: str | Path, expected_verification_sha256: str,
    repo_root: str | Path = REPOSITORY_ROOT,
) -> PredictionReference:
    """Load the parent pinned by the prospective plan; inspect no original data.

    Production callers supply the fixed parent/QA digests from their plan.
    This interface has no split/cohort/window-length override. Tables are
    checked per video before batches are returned; call ``verify_current``
    again before completing the consuming experiment.
    """
    inputs = _Inputs(Path(repo_root))
    parent_path, qa_path = inputs.path(manifest_path), inputs.path(verification_path)
    _require(parent_path.is_relative_to(inputs.root / "data/derived")
             and qa_path.is_relative_to(inputs.root / "data/derived"), "Parent and QA must be derived metadata")
    parent = inputs.register(parent_path, expected_manifest_sha256)
    qa_record = inputs.register(qa_path, expected_verification_sha256)
    manifest, qa = _json(parent.read()), _json(qa_record.read())
    _require(manifest.get("status") == "complete" and qa.get("status") == "passed", "Parent/QA must be complete/passed")
    _require(qa.get("run_manifest_sha256") == parent.sha256 and inputs.path(qa.get("run_manifest", "")) == parent.path,
             "QA does not identify the pinned parent")
    _require(manifest.get("module") == "prediction" and manifest.get("method") == "ground_truth_individuals"
             and manifest.get("stage") == "preparation" and manifest.get("git_dirty") is False, "Invalid parent preparation identity")
    config, summary = manifest["config"], manifest["summary"]
    _require(config.get("plan_id") == "individual_trajectories_v1_20260908"
             and config.get("purpose") == "training_reference_preparation_without_model_evaluation"
             and config.get("configuration_id") == "individual_trajectories_v1"
             and config.get("method") == "ground_truth_individuals", "Invalid individual reference plan")
    _same(config["protocol"]["train_ids"], [int(video) for video in TRAIN_IDS], "training cohort")
    _same(config["input"]["expected_frames"], EXPECTED_FRAMES, "expected frame universe")
    _same(config["input"].get("missing_label_ranges"), {"23": [[823, 972], [1084, 1107]]}, "registered annotation gaps")
    _require(config["input"].get("root") == "data/sources/visem_tracking/dataset/Train"
             and config["input"].get("read_mode") == "label_contents_and_mp4_hash_metadata_without_pixel_decoding"
             and config["protocol"].get("statistical_unit") == "video", "Invalid source-reference/statistical-unit contract")
    _require(config["input"].get("width") == 640 and config["input"].get("height") == 480, "Reference must retain 640x480 pixels")
    _same(config["eligibility"], {"individual_classes": [0, 2], "cluster_class": 1,
          "preserve_original_track_ids": True, "break_on": ["annotation_absent", "class_1", "id_absent"],
          "keep_individuals_inside_cluster_boxes": True, "interpolate": False, "spatial_or_speed_filter": False}, "eligibility")
    _same(config["windows"], {"history_length": 20, "forecast_horizon": 10, "stride": 1,
          "output": "indices_only", "future_reference_use": "offline_eligibility_and_targets_only",
          "report_origins_excluded_incomplete_future": True}, "window contract")
    _require(config["run"].get("split") == "train" and config["run"].get("stage") == "preparation", "Parent split must be train")
    _require(config_hash(config, 64) == qa.get("plan_hash") and manifest.get("config_hash") == config_hash(config), "Parent plan hash mismatch")
    _require(manifest.get("git_sha") == qa.get("git_sha_of_verified_run")
             and manifest.get("source_hash") == qa.get("source_hash_of_verified_run"), "QA code provenance mismatch")
    snapshot_hash = manifest.get("provenance_capture", {}).get("snapshot_sha256")
    _require(snapshot_hash == qa.get("shared_snapshot_sha256") and snapshot_hash is not None
             and manifest.get("repository_recheck", {}).get("status") == "verified"
             and manifest["repository_recheck"].get("snapshot_sha256") == snapshot_hash, "Parent snapshot was not rechecked")
    _same(summary.get("video_ids"), list(TRAIN_IDS), "parent video IDs")
    _same(qa.get("video_ids"), list(TRAIN_IDS), "QA video IDs")
    _same(qa.get("expected_frames_per_video"), EXPECTED_FRAMES, "QA frame counts")
    _require(summary.get("status") == "prepared_training_reference_not_prediction_evaluation"
             and summary.get("model_evaluated") is False and summary.get("validation_sources_read") is False
             and summary.get("test_sources_read") is False and summary.get("pixels_decoded") is False
             and summary.get("statistical_unit") == "video" and summary.get("future_reference_conditioned_eligibility") is True,
             "Reference is not the registered training-only preparation")
    _require(qa.get("all_observations_segments_windows_compared") is True
             and qa.get("coordinates_compared_as_exact_binary_floats") is True
             and qa.get("original_sources_opened") is False and qa.get("project_implementation_imported") is False,
             "Independent exported-reference QA is incomplete")
    _same(qa.get("totals_rebuilt"), summary["totals"], "QA totals")
    _same(qa.get("video_summaries_rebuilt"), summary["videos"], "QA video summaries")
    _require([row.get("video_id") for row in summary["videos"]] == list(TRAIN_IDS), "Missing/duplicate video summary")
    for key in _TOTALS:
        _require(_integer(summary["totals"].get(key), key) == sum(_integer(row.get(key), key) for row in summary["videos"]),
                 f"Parent total {key} disagrees with video summaries")

    expected_paths = {parent.path.parent / "summary.json"}
    expected_paths.update(parent.path.parent / "by_video" / video / name for video in TRAIN_IDS for name in _ARTIFACT_NAMES)
    artifact_refs = manifest.get("artifacts", [])
    paths = [inputs.path(ref["path"]) for ref in artifact_refs]
    _require(len(paths) == 85 and len(set(paths)) == 85 and set(paths) == expected_paths, "Parent must hash the exact 85 reference artifacts")
    for ref in artifact_refs:
        inputs.register(ref["path"], ref["sha256"], ref["bytes"])
    exported_summary = _json(inputs.records[parent.path.parent / "summary.json"].read())
    _same(exported_summary, summary, "parent and exported summaries")
    metadata_refs = manifest.get("metadata", [])
    _require([inputs.path(ref["path"]) for ref in metadata_refs] == [inputs.root / name for name in _METADATA_PATHS],
             "Reference metadata identity differs from the registered protocol")
    for ref in metadata_refs:
        inputs.register(ref["path"], ref["sha256"], ref["bytes"])
    _require(config["protocol"].get("splits_config") == _METADATA_PATHS[1]
             and config["protocol"].get("splits_sha256") == metadata_refs[1]["sha256"]
             and config["protocol"].get("inventory") == _METADATA_PATHS[2]
             and config["protocol"].get("inventory_sha256") == metadata_refs[2]["sha256"]
             and config["protocol"].get("annotation_gaps") == _METADATA_PATHS[3], "Protocol metadata references disagree with parent config")
    qa_refs = qa.get("input_files", [])
    qa_paths = [inputs.path(ref["path"]) for ref in qa_refs]
    _require(len(qa_paths) == 86 and len(set(qa_paths)) == 86 and set(qa_paths) == expected_paths | {parent.path}
             and qa.get("files_verified") == 86, "QA did not verify exactly the parent and all artifacts")
    for ref in qa_refs:
        record = inputs.records[inputs.path(ref["path"])]
        _require(record.sha256 == ref["sha256"] and record.size == ref["bytes"], "QA artifact identity mismatch")
    input_hashes = qa.get("input_hashes_recorded", {})
    _require(set(input_hashes) == set(TRAIN_IDS) and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
             for value in input_hashes.values()), "QA input identity cohort mismatch")
    rechecks = manifest.get("input_rechecks", [])
    _require(len(rechecks) == 12 and [row.get("input_hash") for row in rechecks] == [input_hashes[video] for video in TRAIN_IDS]
             and all(row.get("status") == "verified" for row in rechecks), "Parent input identities were not all rechecked")
    return PredictionReference(inputs, parent, qa_record, json.dumps(summary), MappingProxyType(dict(input_hashes)))
