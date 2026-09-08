"""Immutable, training-only sample of canonical decoded detection frames.

``prepare_sample`` writes one lossless uint8 BGR NPY per video and full-precision
GT. ``load_sample`` verifies the plan, audit, sources and cached bytes before
returning a TrainingSample. Its ``frames(mode, video_id=None)`` iterator yields
``(video_id, original_frame_index, readonly_bgr_view, tuple[Detection, ...])``.
Views retain their mmap owner; consumers must not accumulate frame views or
modify them. Only one video's array is opened by the iterator at a time.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

from src.core.paths import REPOSITORY_ROOT
from src.detection.base import Detection
from src.detection.io import CSV_FIELDS, detection_to_row, write_detections_csv
from .config import canonical_json, load_config
from .dataset import load_split_spec
from .resources import ResourceMonitor
from .runs import _git_dirty, _git_sha, _source_hash, environment_snapshot
from .sampling import evenly_spaced_indices


TRAIN_IDS = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
_WIDTH, _HEIGHT = 640, 480
_COUNTS = {"master": 48, "coarse": 12, "benchmark": 1}
_SOURCES = Path("data/sources/visem_tracking/dataset/Train")
_PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_sha(value: Any) -> str:
    return _sha(canonical_json(value).encode("utf-8"))


def _read_bytes(path: Path) -> bytes:
    before = path.stat()
    value = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Input changed during read: {path}")
    return value


def _digest(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Input changed during hash: {path}")
    return digest.hexdigest()


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline="")))


def _write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def _validate_plan(plan: dict, root: Path) -> dict:
    """Check exact train identity before accessing audit/cache/source files."""
    protocol, sampling, run = plan["protocol"], plan["sampling"], plan["run"]
    ids = tuple(str(value) for value in protocol["train_ids"])
    if ids != TRAIN_IDS:
        raise ValueError("Plan must contain the exact 12 authorized training IDs in order")
    if Path(protocol["splits_config"]).as_posix() != "configs/protocol/splits.yaml":
        raise ValueError("Use the current canonical configs/protocol/splits.yaml")
    spec_path = root / protocol["splits_config"]
    spec = load_split_spec(spec_path)
    if spec.train != TRAIN_IDS:
        raise ValueError("Current split differs from the exact authorized training IDs")
    if run.get("split") != "train" or run.get("seed") != 42 or run.get("opencv_threads") != 1:
        raise ValueError("Sample requires run.split=train, seed=42 and opencv_threads=1")
    for mode, count in _COUNTS.items():
        if sampling.get(f"{mode}_frames_per_video") != count:
            raise ValueError(f"Sample requires {count} {mode} frames per video")
    if sampling.get("benchmark_rule") != "upper_middle_of_coarse_sample":
        raise ValueError("sampling.benchmark_rule must be upper_middle_of_coarse_sample")
    expected = {
        "rule": "evenly_spaced_annotated_indices_nested",
        "image_source": "sequential_decode_canonical_mp4",
        "cache_format": "numpy_uint8_bgr_lossless", "width": _WIDTH, "height": _HEIGHT,
    }
    if any(sampling.get(key) != value for key, value in expected.items()):
        raise ValueError("Sampling rule, dimensions or cache format differs from the registered contract")
    evaluation = plan["evaluation"]
    if (evaluation.get("protocol_id") != _PROTOCOL
            or evaluation.get("class_policy") != "individuals_ignore_clusters"
            or evaluation.get("center_gate_px") != 10
            or sorted(evaluation.get("sensitivity_gates_px", [])) != [15, 20]):
        raise ValueError("Sample plan must use the approved V3 evaluation")
    limits = {key: float(plan["budget"][key]) for key in ("max_cache_mb", "max_rss_mb")}
    if any(not math.isfinite(value) or value <= 0 for value in limits.values()):
        raise ValueError("Cache and RAM budgets must be finite and positive")
    if len(TRAIN_IDS) * _COUNTS["master"] * _HEIGHT * _WIDTH * 3 / 1024**2 > limits["max_cache_mb"]:
        raise ValueError("Planned pixel arrays exceed max_cache_mb before any source access")
    return {"path": str(protocol["splits_config"]), "sha256": _digest(spec_path)}


def _strict_gt(content: bytes, record: dict, path: Path) -> tuple[Detection, ...]:
    detections: list[Detection] = []
    identities: set[str] = set()
    for line_number, line in enumerate(content.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 6 or fields[1] not in {"0", "1", "2"}:
            raise ValueError(f"Invalid six-field tracked label at {path}:{line_number}")
        if fields[0] in identities:
            raise ValueError(f"Duplicate GT identity at {path}:{line_number}")
        identities.add(fields[0])
        coords = tuple(float(value) for value in fields[2:])
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in coords) or min(coords[2:]) <= 0:
            raise ValueError(f"Invalid normalized coordinates at {path}:{line_number}")
        cx, cy, width, height = (value * scale for value, scale in zip(coords, (_WIDTH, _HEIGHT, _WIDTH, _HEIGHT)))
        detection = Detection(cx, cy, width, height, class_id=int(fields[1]), object_id=fields[0])
        if (min(detection.x, detection.y) < -1e-9
                or detection.x + width > _WIDTH + 1e-9 or detection.y + height > _HEIGHT + 1e-9):
            raise ValueError(f"GT box outside canonical image at {path}:{line_number}")
        detections.append(detection)
    expected = int(record["raw_rows"])
    if (len(detections) != expected or int(record["valid_rows"]) != expected
            or int(record["invalid_rows"]) != 0):
        raise ValueError(f"GT count/validity differs from geometry audit: {path}")
    if (record["annotation_state"] == "annotated_empty") != (expected == 0):
        raise ValueError(f"GT empty/nonempty state differs from geometry audit: {path}")
    for class_id in (0, 1, 2):
        count = sum(item.class_id == class_id for item in detections)
        if count != int(record[f"raw_class{class_id}"]) or count != int(record[f"valid_class{class_id}"]):
            raise ValueError(f"GT class counts differ from geometry audit: {path}")
    return tuple(detections)


def _audit_and_labels(plan: dict, root: Path) -> tuple[dict, dict, dict]:
    """Select only by annotation presence/index, then validate chosen labels."""
    audit_path = root / plan["protocol"]["geometry_audit"]
    manifest_bytes = _read_bytes(audit_path / "manifest.json")
    audit = json.loads(manifest_bytes)
    if tuple(str(value) for value in audit["configuration"]["video_ids"]) != TRAIN_IDS:
        raise ValueError("Geometry audit must contain only the exact training IDs")
    files = {}
    hashes = {"manifest.json": _sha(manifest_bytes)}
    for name in ("per_frame_counts.csv", "input_files.csv"):
        content = _read_bytes(audit_path / name)
        hashes[name] = _sha(content)
        if hashes[name] != audit["outputs"][name]["sha256"]:
            raise ValueError(f"Geometry audit artifact hash mismatch: {name}")
        files[name] = _csv_rows(content)
    frame_records: dict[str, dict[int, dict]] = {video: {} for video in TRAIN_IDS}
    for row in files["per_frame_counts.csv"]:
        video, index = row["video_id"], int(row["frame"])
        if video not in frame_records or index < 0 or index in frame_records[video]:
            raise ValueError("Geometry audit contains foreign, duplicate or invalid frame IDs")
        if row["annotation_state"] not in {"annotated", "annotated_empty", "unlabeled"}:
            raise ValueError("Geometry audit contains an unknown annotation state")
        frame_records[video][index] = row
    input_records = {}
    for row in files["input_files.csv"]:
        if row["role"] != "labels_ftid":
            continue
        key = (row["video_id"], int(row["frame"]))
        if key[0] not in TRAIN_IDS or key in input_records:
            raise ValueError("Geometry audit contains foreign or duplicate tracked label identity")
        input_records[key] = row
    selections, labels = {}, {}
    for video in TRAIN_IDS:
        eligible = [index for index, row in frame_records[video].items()
                    if row["annotation_state"] in {"annotated", "annotated_empty"}]
        master = evenly_spaced_indices(eligible, _COUNTS["master"])
        if len(master) != _COUNTS["master"]:
            raise ValueError(f"Training video {video} has fewer than 48 eligible annotated frames")
        coarse = evenly_spaced_indices(master, _COUNTS["coarse"])
        selections[video] = {"master": list(master), "coarse": list(coarse),
                             "benchmark": list(evenly_spaced_indices(coarse, _COUNTS["benchmark"]))}
        folder = root / _SOURCES / video / "labels_ftid"
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing tracked label directory: {folder}")
        actual_labels: dict[int, Path] = {}
        for path in folder.glob(f"{video}_frame_*_with_ftid.txt"):
            if not path.is_file():
                continue
            token = path.name.removeprefix(f"{video}_frame_").removesuffix("_with_ftid.txt")
            if not token.isdigit():
                raise ValueError(f"Invalid tracked label filename: {path}")
            index = int(token)
            if index in actual_labels:
                raise ValueError(f"Duplicate tracked label frame: {path}")
            actual_labels[index] = path
        if set(actual_labels) != set(eligible):
            raise ValueError(
                f"Tracked label index differs from audit for video {video}: "
                f"missing={sorted(set(eligible) - set(actual_labels))}, "
                f"extra={sorted(set(actual_labels) - set(eligible))}"
            )
        for index in master:
            key, record = (video, index), frame_records[video][index]
            if record["labels_ftid_present"] != "True" or index not in actual_labels:
                raise ValueError(f"Selected GT is missing; never infer an empty frame: {video}/{index}")
            if (int(record["image_width"]), int(record["image_height"])) != (_WIDTH, _HEIGHT):
                raise ValueError(f"Audit image dimensions differ for {video}/{index}")
            path = actual_labels[index]
            relative = path.relative_to(root).as_posix()
            prior = input_records[key]
            if prior["path"] != relative:
                raise ValueError(f"Selected GT path differs from audit: {path}")
            content = _read_bytes(path)
            if _sha(content) != prior["sha256"] or len(content) != int(prior["bytes"]):
                raise ValueError(f"Selected GT hash mismatch: {path}")
            ground_truth = _strict_gt(content, record, path)
            labels[key] = {"path": relative, "sha256": _sha(content), "bytes": len(content),
                           "nonempty_lines": len(ground_truth), "ground_truth": ground_truth}
    return {"path": str(plan["protocol"]["geometry_audit"]), "hashes": hashes}, selections, labels


def _check_resources(monitor: ResourceMonitor, plan: dict) -> None:
    monitor.sample()
    peak = monitor.summary()["ram_rss_peak_mb"]
    if peak is not None and peak > float(plan["budget"]["max_rss_mb"]):
        raise RuntimeError("Sample preparation exceeded max_rss_mb")


def _identity(manifest: dict) -> dict:
    return {key: manifest[key] for key in (
        "schema_version", "plan_sha256", "split", "audit", "video_ids", "sampling",
        "selections", "videos", "ground_truth", "frames",
    )}


def prepare_sample(plan: dict, output_dir: Path, repo_root: Path = REPOSITORY_ROOT) -> dict:
    """Create a new cache; errors stop and preserve any partial output as failed."""
    root, output = Path(repo_root).resolve(), Path(output_dir).resolve()
    split = _validate_plan(plan, root)
    if output.exists():
        raise FileExistsError(f"Sample output already exists; never overwrite: {output}")
    if output.is_relative_to((root / "data/sources").resolve()):
        raise ValueError("A derived sample cannot be written inside immutable sources")
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    monitor = ResourceMonitor()
    audit, selections, labels = _audit_and_labels(plan, root)
    timings = {"input_validation_seconds": time.perf_counter() - started,
               "source_hash_seconds": 0.0, "array_hash_seconds": 0.0,
               "decode_seconds": 0.0, "array_write_seconds": 0.0}
    provenance = {"git_sha": _git_sha(root), "git_dirty": _git_dirty(root),
                  "source_hash": _source_hash(root), "environment": environment_snapshot(),
                  "generator_sha256": _digest(Path(__file__)), "seed": 42}
    plan_source = root / "configs/detection/threshold/search_v3.yaml"
    if plan_source.is_file() and load_config(plan_source) == plan:
        provenance["plan_source"] = {"path": plan_source.relative_to(root).as_posix(), "sha256": _digest(plan_source)}
    output.mkdir(parents=True, exist_ok=False)
    (output / "frames").mkdir()
    manifest: dict = {
        "schema_version": 1, "kind": "canonical_training_detection_sample", "status": "running",
        "started_at": started_at, "plan_sha256": _json_sha(plan), "plan_id": plan.get("plan_id"),
        "split": split, "audit": audit, "video_ids": list(TRAIN_IDS),
        "sampling": dict(plan["sampling"]), "selections": selections,
        "provenance": provenance, "videos": {}, "frames": [],
        "pixel_definition": "Exact uint8 BGR pixels decoded from canonical MP4; no lossy re-encoding, resize or GT mask",
    }
    _write_json(output / "preparation.json", manifest)
    cv2.setNumThreads(1)
    try:
        ground_truth_rows = []
        for video in TRAIN_IDS:
            video_path = root / _SOURCES / video / f"{video}.mp4"
            phase_started = time.perf_counter()
            source_sha = _digest(video_path)
            timings["source_hash_seconds"] += time.perf_counter() - phase_started
            relative_array = f"frames/video_{video}.npy"
            array = np.lib.format.open_memmap(
                output / relative_array, mode="w+", dtype=np.uint8,
                shape=(_COUNTS["master"], _HEIGHT, _WIDTH, 3),
            )
            cap = cv2.VideoCapture(str(video_path))
            master = selections[video]["master"]
            position = 0
            try:
                if not cap.isOpened():
                    raise ValueError(f"Cannot decode canonical video: {video_path}")
                backend = cap.getBackendName()
                for index in range(master[-1] + 1):
                    phase_started = time.perf_counter()
                    ok, frame = cap.read()
                    timings["decode_seconds"] += time.perf_counter() - phase_started
                    if not ok:
                        raise ValueError(f"Incomplete canonical decode at video {video}, frame {index}")
                    if cap.get(cv2.CAP_PROP_POS_FRAMES) != index + 1:
                        raise ValueError(f"Canonical decoder position mismatch at {video}/{index}")
                    if frame.dtype != np.uint8 or frame.shape != (_HEIGHT, _WIDTH, 3):
                        raise ValueError(f"Canonical uint8 BGR dimensions mismatch at {video}/{index}")
                    if index == master[position]:
                        phase_started = time.perf_counter()
                        array[position] = frame
                        timings["array_write_seconds"] += time.perf_counter() - phase_started
                        label = labels[(video, index)]
                        ground_truth_rows.extend(detection_to_row(video, index, "manual", item) for item in label["ground_truth"])
                        manifest["frames"].append({"video_id": video, "frame": index, "array_index": position,
                                                   "pixel_sha256": _sha(frame.tobytes(order="C")),
                                                   "label": {key: value for key, value in label.items() if key != "ground_truth"}})
                        position += 1
                    _check_resources(monitor, plan)
                if position != _COUNTS["master"]:
                    raise ValueError(f"Incomplete selected frame universe for video {video}")
            finally:
                cap.release()
                phase_started = time.perf_counter()
                array.flush()
                timings["array_write_seconds"] += time.perf_counter() - phase_started
                del array
            phase_started = time.perf_counter()
            if _digest(video_path) != source_sha:
                raise ValueError(f"Canonical video changed during decoding: {video_path}")
            timings["source_hash_seconds"] += time.perf_counter() - phase_started
            phase_started = time.perf_counter()
            array_sha = _digest(output / relative_array)
            timings["array_hash_seconds"] += time.perf_counter() - phase_started
            manifest["videos"][video] = {
                "source_path": video_path.relative_to(root).as_posix(), "source_sha256": source_sha,
                "source_bytes": video_path.stat().st_size, "array_path": relative_array,
                "array_sha256": array_sha, "array_bytes": (output / relative_array).stat().st_size,
                "shape": [_COUNTS["master"], _HEIGHT, _WIDTH, 3], "dtype": "uint8", "decoder_backend": backend,
                "decoded_frames": master[-1] + 1,
            }
            print(json.dumps({
                "event": "sample_video_cached", "video_id": video,
                "completed_videos": len(manifest["videos"]), "planned_videos": len(TRAIN_IDS),
                "master_frames": len(master), "array_bytes": manifest["videos"][video]["array_bytes"],
                "elapsed_seconds": time.perf_counter() - started,
            }), flush=True)
        ground_truth_path = write_detections_csv(ground_truth_rows, output / "ground_truth.csv")
        manifest["ground_truth"] = {"path": "ground_truth.csv", "sha256": _digest(ground_truth_path),
                                    "rows": len(ground_truth_rows), "bytes": ground_truth_path.stat().st_size}
        for label in labels.values():
            if _digest(root / label["path"]) != label["sha256"]:
                raise ValueError(f"Selected GT changed during preparation: {label['path']}")
        if _digest(root / split["path"]) != split["sha256"]:
            raise ValueError("Current split changed during sample preparation")
        for name, digest in audit["hashes"].items():
            if _digest(root / audit["path"] / name) != digest:
                raise ValueError(f"Geometry audit changed during preparation: {name}")
        cache_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat(),
                        elapsed_seconds=time.perf_counter() - started, timings=timings,
                        resources=monitor.summary(), cache_bytes=cache_bytes)
        manifest["sample_hash"] = _json_sha(_identity(manifest))
        # Account for the manifest itself, including the size of this field.
        while True:
            total_bytes = cache_bytes + len(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
            if total_bytes == manifest["cache_bytes"]:
                break
            manifest["cache_bytes"] = total_bytes
        if total_bytes / 1024**2 > float(plan["budget"]["max_cache_mb"]):
            raise RuntimeError("Sample cache exceeded max_cache_mb")
        _write_json(output / "manifest.json", manifest)
        return manifest
    except BaseException as error:
        manifest.update(status="failed", error=str(error), elapsed_seconds=time.perf_counter() - started,
                        timings=timings, resources=monitor.summary())
        _write_json(output / "manifest.json", manifest)
        raise


@dataclass(frozen=True)
class TrainingSample:
    cache_dir: Path
    manifest: dict
    _ground_truth: dict[tuple[str, int], tuple[Detection, ...]]

    @property
    def sample_hash(self) -> str:
        return self.manifest["sample_hash"]

    @property
    def video_ids(self) -> tuple[str, ...]:
        return tuple(self.manifest["video_ids"])

    def indices(self, mode: str, video_id: str) -> tuple[int, ...]:
        if mode not in _COUNTS or str(video_id) not in self.video_ids:
            raise ValueError("Unknown sample mode or non-training video ID")
        return tuple(self.manifest["selections"][str(video_id)][mode])

    def frames(self, mode: str = "master", video_id: str | None = None) -> Iterator[tuple[str, int, np.ndarray, tuple[Detection, ...]]]:
        videos = self.video_ids if video_id is None else (str(video_id),)
        for video in videos:
            selected = self.indices(mode, video)
            positions = {index: position for position, index in enumerate(self.indices("master", video))}
            array = np.load(self.cache_dir / self.manifest["videos"][video]["array_path"], mmap_mode="r", allow_pickle=False)
            try:
                for index in selected:
                    # Detection is mutable; isolate each candidate from changes
                    # made by a previous consumer without copying pixel arrays.
                    ground_truth = tuple(replace(item) for item in self._ground_truth[(video, index)])
                    yield video, index, array[positions[index]], ground_truth
            finally:
                del array


def load_sample(cache_dir: Path, plan: dict, repo_root: Path = REPOSITORY_ROOT) -> TrainingSample:
    """Verify all cache and selected source content before yielding readonly frames."""
    root, cache = Path(repo_root).resolve(), Path(cache_dir).resolve()
    split = _validate_plan(plan, root)
    manifest = json.loads(_read_bytes(cache / "manifest.json"))
    if manifest.get("status") != "complete" or manifest.get("schema_version") != 1:
        raise ValueError("Only complete supported sample caches may be loaded")
    if manifest["plan_sha256"] != _json_sha(plan) or manifest["split"] != split:
        raise ValueError("Sample plan or current split hash differs from the manifest")
    if manifest["sample_hash"] != _json_sha(_identity(manifest)):
        raise ValueError("Sample identity hash mismatch")
    audit, selections, labels = _audit_and_labels(plan, root)
    if (manifest["audit"] != audit or manifest["selections"] != selections
            or manifest["video_ids"] != list(TRAIN_IDS) or set(manifest["videos"]) != set(TRAIN_IDS)):
        raise ValueError("Cached sample universe differs from the authorized audit and selection")
    expected_keys = [(video, index) for video in TRAIN_IDS for index in selections[video]["master"]]
    observed_keys = [(row["video_id"], row["frame"]) for row in manifest["frames"]]
    if observed_keys != expected_keys:
        raise ValueError("Cached frame identities are incomplete, reordered or duplicated")
    for video in TRAIN_IDS:
        record = manifest["videos"][video]
        expected_path = (_SOURCES / video / f"{video}.mp4").as_posix()
        if record["source_path"] != expected_path or record["array_path"] != f"frames/video_{video}.npy":
            raise ValueError("Noncanonical video or cache path")
        if _digest(root / expected_path) != record["source_sha256"]:
            raise ValueError(f"Canonical video hash mismatch: {video}")
        array_path = cache / record["array_path"]
        if _digest(array_path) != record["array_sha256"]:
            raise ValueError(f"Cached array hash mismatch: {video}")
        array = np.load(array_path, mmap_mode="r", allow_pickle=False)
        try:
            if (array.dtype != np.uint8 or array.shape != (_COUNTS["master"], _HEIGHT, _WIDTH, 3)
                    or array.flags.writeable or not array.flags.c_contiguous):
                raise ValueError(f"Cached array dimensions/dtype/readonly mismatch: {video}")
            for position, index in enumerate(selections[video]["master"]):
                row = manifest["frames"][expected_keys.index((video, index))]
                label = labels[(video, index)]
                if (row["array_index"] != position or row["pixel_sha256"] != _sha(array[position].tobytes(order="C"))
                        or row["label"] != {key: value for key, value in label.items() if key != "ground_truth"}):
                    raise ValueError(f"Cached frame/GT identity mismatch: {video}/{index}")
        finally:
            del array
    if manifest["ground_truth"]["path"] != "ground_truth.csv":
        raise ValueError("Noncanonical ground truth cache path")
    gt_bytes = _read_bytes(cache / "ground_truth.csv")
    if _sha(gt_bytes) != manifest["ground_truth"]["sha256"]:
        raise ValueError("Cached ground truth hash mismatch")
    rows = _csv_rows(gt_bytes)
    expected_rows = [detection_to_row(video, index, "manual", detection)
                     for video, index in expected_keys for detection in labels[(video, index)]["ground_truth"]]
    expected_text = io.StringIO(newline="")
    writer = csv.DictWriter(expected_text, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(expected_rows)
    if rows != _csv_rows(expected_text.getvalue().encode("utf-8")) or len(rows) != manifest["ground_truth"]["rows"]:
        raise ValueError("Cached ground truth differs from complete original IDs/classes/precision")
    return TrainingSample(cache, manifest, {key: label["ground_truth"] for key, label in labels.items()})
