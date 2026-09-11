"""Authenticated, independent YOLO copies; no training or test-set traversal.

``inspect_metadata`` opens manifests only, never JPEGs or annotation contents.
``materialize_dataset`` requires a clean RunSnapshot before content reads and
creates an immutable RunContext. Consumers must clone this sealed derivation
into their own run before a library is allowed to create caches or repair JPEGs.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import Any

import yaml

from src.core.artifacts import sha256_file, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import config_hash
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot, configuration_directory


TRAIN_IDS = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
VAL_IDS = ("14", "19", "36", "52")
CLASS_NAMES = ("sperm", "cluster", "small_or_pinhead")
DEFAULT_PLAN = "configs/detection/yolo/dataset_v1.yaml"
MIB = 1024**2
METADATA_ENVELOPE_BYTES = 64*MIB


class DatasetError(ValueError):
    """A closed-universe or provenance requirement did not hold."""


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader: _UniqueLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise DatasetError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _keys(value: Any, expected: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise DatasetError(f"Unexpected/missing keys in {name}; expected {sorted(expected)}")
    return value


def _relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise DatasetError("Paths must be canonical repository-relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise DatasetError("Absolute paths and path traversal are forbidden")
    return path.as_posix()


def _safe(root: Path, relative: str, *, file: bool = False) -> Path:
    current = root
    for part in PurePosixPath(_relative(relative)).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
                raise DatasetError(f"Symlink/junction/reparse point forbidden: {current}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise DatasetError("Path escaped its root")
    if file:
        info = current.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise DatasetError(f"Expected independent regular file: {current}")
    return current


@dataclass(frozen=True)
class DatasetPlan:
    """Resolved specification; direct construction is useful for synthetic tests."""

    root: Path
    config: dict[str, Any]
    plan_path: str
    plan_sha256: str
    videos: tuple[dict[str, Any], ...]
    gaps: dict[str, tuple[int, ...]]


def _bound_manifests(root: Path, config: dict) -> dict[str, Path]:
    bindings = _keys(config["manifests"], {"splits", "inventory", "gaps"}, "manifests")
    result = {}
    for name, binding in bindings.items():
        _keys(binding, {"path", "sha256"}, f"manifests.{name}")
        expected_path = {"splits": "configs/protocol/splits.yaml",
                         "inventory": "data/manifests/visem_tracking.csv",
                         "gaps": "data/manifests/annotation_gaps.csv"}[name]
        if binding["path"] != expected_path:
            raise DatasetError("Unexpected manifest path")
        if not re.fullmatch(r"[0-9a-f]{64}", str(binding["sha256"])):
            raise DatasetError("Expected a full lowercase SHA256")
        path = _safe(root, binding["path"], file=True)
        if sha256_file(path) != binding["sha256"]:
            raise DatasetError(f"Manifest hash mismatch: {name}")
        result[name] = path
    return result


def load_dataset_plan(path: str | Path = DEFAULT_PLAN, *, root: Path = REPOSITORY_ROOT) -> DatasetPlan:
    root = Path(root).resolve()
    relative = _relative(str(path))
    source = _safe(root, relative, file=True)
    config = yaml.load(source.read_text(encoding="utf-8"), Loader=_UniqueLoader)
    _keys(config, {"kind", "configuration_id", "source_root", "output_root", "manifests",
                   "split_ids", "expected_counts", "classes", "image", "labels",
                   "legacy_sidecars", "resources", "seed"}, "plan")
    if config["kind"] != "yolo_dataset_materialization_v1":
        raise DatasetError("Unsupported dataset plan kind")
    if config["source_root"] != "data/sources/visem_tracking/dataset/Train":
        raise DatasetError("Only the official source root is permitted")
    if config["output_root"] != "data/datasets":
        raise DatasetError("Dataset output must remain under data/datasets")
    _keys(config["split_ids"], {"train", "val"}, "split_ids")
    if (config["split_ids"]["train"] != list(TRAIN_IDS)
            or config["split_ids"]["val"] != list(VAL_IDS)):
        raise DatasetError("The exact official 12/4 IDs and order are required; test is forbidden")
    if config["classes"] != list(CLASS_NAMES):
        raise DatasetError("YOLO must retain the three original classes")
    if config["expected_counts"] != {"train": 17466, "val": 5850, "unlabeled": 174}:
        raise DatasetError("Unexpected annotated/unlabeled counts")
    if config["image"] != {"width": 640, "height": 480, "extension": ".jpg", "max_bytes": 16*MIB}:
        raise DatasetError("Unexpected image contract")
    if config["labels"] != {"fields": 5, "max_bytes": MIB, "bounds_tolerance": 1e-9,
                             "reference_fields": 6, "reference_tolerance": 1e-9}:
        raise DatasetError("Unexpected label contract")
    if config["legacy_sidecars"] != {"extension": ".npy", "policy": "inventory_metadata_only_exclude"}:
        raise DatasetError("Unexpected legacy sidecar policy")
    if config["resources"] != {"artifact_limit_mib": 2048, "rss_limit_mib": 1024,
                                "free_reserve_mib": 512, "chunk_bytes": MIB}:
        raise DatasetError("Unexpected prospective resource limits")
    if type(config["seed"]) is not int or config["seed"] != 42:
        raise DatasetError("Expected seed 42")
    if not re.fullmatch(r"[a-z0-9_]+", str(config["configuration_id"])):
        raise DatasetError("Invalid configuration identifier")
    bound = _bound_manifests(root, config)
    split = yaml.load(bound["splits"].read_text(encoding="utf-8"), Loader=_UniqueLoader)
    for name, expected in (("train", TRAIN_IDS), ("val", VAL_IDS)):
        if tuple(map(str, split["fixed_split"][name])) != expected:
            raise DatasetError("Split manifest disagrees with the permitted IDs")
    with bound["inventory"].open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len({r["video_id"] for r in rows}) != len(rows):
        raise DatasetError("Duplicate video in inventory")
    selected = {r["video_id"]: r for r in rows if r["video_id"] in TRAIN_IDS+VAL_IDS}
    if set(selected) != set(TRAIN_IDS+VAL_IDS):
        raise DatasetError("Incomplete permitted video inventory")
    gaps: dict[str, set[int]] = {vid: set() for vid in TRAIN_IDS+VAL_IDS}
    with bound["gaps"].open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            vid = row["video_id"]
            if vid not in gaps or row["policy"] != "exclude" or row["reason"] != "missing_label_file":
                raise DatasetError("Unexpected annotation gap")
            values = set(range(int(row["start_frame"]), int(row["end_frame"])+1))
            if len(values) != int(row["frame_count"]) or values & gaps[vid]:
                raise DatasetError("Invalid or overlapping annotation gaps")
            gaps[vid].update(values)
    videos = []
    for split_name, ids in (("train", TRAIN_IDS), ("val", VAL_IDS)):
        for vid in ids:
            row = selected[vid]
            total, annotated = int(row["total_frames"]), int(row["annotated_frames"])
            if (row["split"] != split_name or not gaps[vid] <= set(range(total))
                    or annotated != total-len(gaps[vid])):
                raise DatasetError("Video manifest/gap mismatch")
            videos.append({"video_id": vid, "split": split_name, "total_frames": total,
                           "annotated_frames": annotated})
    for name in ("train", "val"):
        if sum(v["annotated_frames"] for v in videos if v["split"] == name) != config["expected_counts"][name]:
            raise DatasetError("Annotated count mismatch")
    if sum(map(len, gaps.values())) != 174:
        raise DatasetError("Unexpected unlabeled count")
    return DatasetPlan(root, config, relative, sha256_file(source), tuple(videos),
                       {k: tuple(sorted(v)) for k, v in gaps.items()})


def _file_metadata(root: Path, relative: str) -> dict[str, Any]:
    path = _safe(root, relative, file=True)
    info = path.stat()
    return {"path": relative, "bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


def inspect_metadata(plan: DatasetPlan) -> dict[str, Any]:
    """Read closed directory universes and stat only; never open source contents."""
    records, sidecars = [], []
    source_root = _safe(plan.root, plan.config["source_root"])
    for video in plan.videos:
        vid, split = video["video_id"], video["split"]
        if split not in {"train", "val"} or not re.fullmatch(r"[0-9]+", vid):
            raise DatasetError("Invalid permitted video identity")
        expected_images = {f"{vid}_frame_{i}.jpg" for i in range(video["total_frames"])}
        expected_labels = {f"{vid}_frame_{i}.txt" for i in range(video["total_frames"])
                           if i not in plan.gaps[vid]}
        image_dir = _safe(source_root, f"{vid}/images")
        label_dir = _safe(source_root, f"{vid}/labels")
        reference_dir = _safe(source_root, f"{vid}/labels_ftid")
        image_names = {p.name for p in image_dir.iterdir()}
        label_names = {p.name for p in label_dir.iterdir()}
        reference_names = {p.name for p in reference_dir.iterdir()}
        npy_names = {name for name in image_names if name.endswith(".npy")}
        if image_names-npy_names != expected_images or label_names != expected_labels:
            raise DatasetError(f"Unexpected/missing image or label files for video {vid}")
        if reference_names != {name[:-4]+"_with_ftid.txt" for name in expected_labels}:
            raise DatasetError(f"Unexpected/missing labels_ftid files for video {vid}")
        if any(name[:-4]+".jpg" not in expected_images for name in npy_names):
            raise DatasetError("Legacy NPY sidecar does not match a known JPEG")
        for name in sorted(npy_names):
            sidecars.append(_file_metadata(plan.root, f"{plan.config['source_root']}/{vid}/images/{name}"))
        for frame in range(video["total_frames"]):
            stem = f"{vid}_frame_{frame}"
            image = _file_metadata(plan.root, f"{plan.config['source_root']}/{vid}/images/{stem}.jpg")
            if image["bytes"] <= 0 or image["bytes"] > plan.config["image"]["max_bytes"]:
                raise DatasetError("Image byte-size guard exceeded")
            if frame in plan.gaps[vid]:
                continue
            label = _file_metadata(plan.root, f"{plan.config['source_root']}/{vid}/labels/{stem}.txt")
            reference = _file_metadata(plan.root, f"{plan.config['source_root']}/{vid}/labels_ftid/{stem}_with_ftid.txt")
            if max(label["bytes"], reference["bytes"]) > plan.config["labels"]["max_bytes"]:
                raise DatasetError("Label byte-size guard exceeded")
            records.append({"split": split, "video_id": vid, "frame": frame,
                            "image": image, "label": label, "reference": reference})
    counts = {name: sum(r["split"] == name for r in records) for name in ("train", "val")}
    counts["unlabeled"] = sum(map(len, plan.gaps.values()))
    if counts != plan.config["expected_counts"]:
        raise DatasetError("Closed dataset counts do not match the plan")
    payload = {"records": records, "excluded_legacy_sidecars": sidecars, "counts": counts,
               "copy_bytes": sum(r[k]["bytes"] for r in records for k in ("image", "label")),
               "source_content_read": False, "legacy_sidecars_content_read": False}
    payload["metadata_sha256"] = config_hash(payload, 64)
    return payload


def parse_yolo_labels(text: str, *, tolerance: float = 1e-9) -> list[tuple[int, float, float, float, float]]:
    """Validate every original annotation without repairing, filtering or sorting."""
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1e-9:
        raise DatasetError("Invalid numerical bounds tolerance")
    rows, seen = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5 or fields[0] not in {"0", "1", "2"}:
            raise DatasetError(f"Expected class 0/1/2 and five fields at line {number}")
        try:
            x, y, width, height = map(float, fields[1:])
        except ValueError as exc:
            raise DatasetError(f"Nonnumeric annotation at line {number}") from exc
        if not all(map(math.isfinite, (x, y, width, height))) or min(width, height) <= 0:
            raise DatasetError(f"Nonfinite or nonpositive box at line {number}")
        if min(x-width/2, y-height/2) < -tolerance or max(x+width/2, y+height/2) > 1+tolerance:
            raise DatasetError(f"Box outside normalized image bounds at line {number}")
        row = (int(fields[0]), x, y, width, height)
        if row in seen:
            raise DatasetError(f"Duplicate annotation at line {number}")
        seen.add(row)
        rows.append(row)
    return rows


def compare_ftid_reference(rows: list[tuple], text: str, *, tolerance: float = 1e-9) -> dict:
    """Compare annotation multisets one-to-one, ignoring only original IDs."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1e-9:
        raise DatasetError("Invalid reference tolerance")
    ids, stripped = set(), []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 6 or fields[0] == "-1" or fields[0] in ids:
            raise DatasetError("Expected six FTID fields and unique original IDs")
        ids.add(fields[0])
        stripped.append(" ".join(fields[1:]))
    reference = parse_yolo_labels("\n".join(stripped), tolerance=tolerance)
    if Counter(row[0] for row in rows) != Counter(row[0] for row in reference):
        raise DatasetError("YOLO/FTID annotation counts or classes differ")
    if Counter(rows) == Counter(reference):
        return {"annotations": len(rows), "exact_multiset": True, "maximum_difference": 0.0}
    maximum = 0.0
    for class_id in range(3):
        a = np.asarray([row[1:] for row in rows if row[0] == class_id], dtype=np.float64)
        b = np.asarray([row[1:] for row in reference if row[0] == class_id], dtype=np.float64)
        if not len(a):
            continue
        distance = np.max(np.abs(a[:, None, :]-b[None, :, :]), axis=2)
        left, right = linear_sum_assignment((distance > tolerance).astype(np.int8))
        if np.any(distance[left, right] > tolerance):
            raise DatasetError("YOLO/FTID boxes differ beyond the registered tolerance")
        maximum = max(maximum, float(np.max(distance[left, right])))
    return {"annotations": len(rows), "exact_multiset": False, "maximum_difference": maximum}


def _copy_independent(source: Path, destination: Path, chunk: int, expected_bytes: int,
                      source_audit: list[dict] | None = None) -> str:
    before = sha256_file(source)
    if source_audit is not None:
        source_audit.append({"path": str(source), "sha256_before": before})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        copied = 0
        while block := incoming.read(chunk):
            copied += len(block)
            if copied > expected_bytes:
                raise DatasetError("Source grew beyond its preflight size")
            outgoing.write(block)
    if copied != expected_bytes:
        raise DatasetError("Source size changed since preflight")
    if destination.stat().st_nlink != 1 or os.path.samefile(source, destination):
        raise DatasetError("Copy shares source storage identity")
    if sha256_file(source) != before or sha256_file(destination) != before:
        raise DatasetError("Source/copy hash changed during copying")
    return before


def _validate_jpeg_copy(path: Path, width: int, height: int) -> None:
    import cv2
    import numpy as np

    raw = path.read_bytes()
    if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9"):
        raise DatasetError(f"JPEG framing invalid; no repair permitted: {path.name}")
    decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.shape != (height, width, 3) or decoded.dtype != np.uint8:
        raise DatasetError(f"JPEG decoding/dimensions invalid: {path.name}")


def _resource_guard(monitor: ResourceMonitor, config: dict, *, bytes_written: int) -> dict:
    measured = monitor.summary()
    rss = measured["ram_rss_peak_mb"]
    if rss is None or rss > config["resources"]["rss_limit_mib"]:
        raise DatasetError("RSS unavailable or prospective RAM limit exceeded")
    if bytes_written > config["resources"]["artifact_limit_mib"]*MIB:
        raise DatasetError("Prospective artifact limit exceeded")
    return measured


def preflight_resources(plan: DatasetPlan, inventory: dict) -> dict:
    estimated = inventory["copy_bytes"]+METADATA_ENVELOPE_BYTES
    reserve = plan.config["resources"]["free_reserve_mib"]*MIB
    available = shutil.disk_usage(plan.root).free
    if estimated > plan.config["resources"]["artifact_limit_mib"]*MIB:
        raise DatasetError("Copy estimate plus metadata envelope exceeds artifact budget")
    if available < estimated+reserve:
        raise DatasetError("Insufficient free space plus metadata envelope and reserve")
    return {"copy_bytes": inventory["copy_bytes"], "metadata_envelope_bytes": METADATA_ENVELOPE_BYTES,
            "estimated_run_bytes": estimated, "free_reserve_bytes": reserve,
            "minimum_free_bytes": estimated+reserve, "available_free_bytes": available}


def copy_dataset(plan: DatasetPlan, inventory: dict, destination: Path, *,
                 monitor: ResourceMonitor | None = None, source_audit: list[dict] | None = None) -> dict:
    """Materialize into a new directory; caller supplies scientific provenance.

    This lower-level function is independently testable on synthetic fixtures.
    Real entry points use ``materialize_dataset`` and its clean-Git gate.
    """
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite dataset: {destination}")
    _safe(plan.root, destination.absolute().relative_to(plan.root).as_posix())
    source_root = _safe(plan.root, plan.config["source_root"])
    if destination.resolve().is_relative_to(source_root.resolve()):
        raise DatasetError("Destination cannot be inside immutable sources")
    if inspect_metadata(plan) != inventory:
        raise DatasetError("Source metadata changed after preflight")
    reserve = plan.config["resources"]["free_reserve_mib"]*MIB
    resource_plan = preflight_resources(plan, inventory)
    destination.mkdir(parents=True, exist_ok=False)
    monitor = monitor or ResourceMonitor()
    rows, bytes_written = [], 0
    class_counts = {str(i): 0 for i in range(3)}
    lists: dict[str, list[str]] = {"train": [], "val": []}
    for record in inventory["records"]:
        row = {key: record[key] for key in ("split", "video_id", "frame")}
        stem = f"{record['video_id']}_frame_{record['frame']}"
        for kind, folder, suffix in (("image", "images", ".jpg"), ("label", "labels", ".txt")):
            original = _safe(plan.root, record[kind]["path"], file=True)
            relative = f"{folder}/{record['split']}/{record['video_id']}/{stem}{suffix}"
            target = destination / relative
            digest = _copy_independent(original, target, plan.config["resources"]["chunk_bytes"],
                                       record[kind]["bytes"], source_audit)
            bytes_written += target.stat().st_size
            row[kind] = {"source": record[kind]["path"], "path": relative,
                         "sha256": digest, "bytes": target.stat().st_size}
        parsed = parse_yolo_labels((destination/row["label"]["path"]).read_text(encoding="utf-8"),
                                   tolerance=plan.config["labels"]["bounds_tolerance"])
        original_reference = _safe(plan.root, record["reference"]["path"], file=True)
        reference_bytes = original_reference.read_bytes()
        if len(reference_bytes) != record["reference"]["bytes"]:
            raise DatasetError("FTID byte size changed since preflight")
        row["reference"] = {"source": record["reference"]["path"],
                            "sha256": hashlib.sha256(reference_bytes).hexdigest(), "bytes": len(reference_bytes)}
        if source_audit is not None:
            source_audit.append({"path": str(original_reference), "sha256_before": row["reference"]["sha256"]})
        row["reference_parity"] = compare_ftid_reference(parsed, reference_bytes.decode("utf-8-sig"),
                                                        tolerance=plan.config["labels"]["reference_tolerance"])
        for annotation in parsed:
            class_counts[str(annotation[0])] += 1
        row["annotation_count"] = len(parsed)
        _validate_jpeg_copy(destination/row["image"]["path"], plan.config["image"]["width"], plan.config["image"]["height"])
        lists[record["split"]].append((destination/row["image"]["path"]).resolve().as_posix())
        rows.append(row)
        _resource_guard(monitor, plan.config, bytes_written=bytes_written)
    # Verify originals and copies after all validation; no source image/label is repaired.
    for row in rows:
        for kind in ("image", "label"):
            entry = row[kind]
            if (sha256_file(_safe(plan.root, entry["source"], file=True)) != entry["sha256"]
                    or sha256_file(_safe(destination, entry["path"], file=True)) != entry["sha256"]):
                raise DatasetError("Final original/copy authentication failed")
        if sha256_file(_safe(plan.root, row["reference"]["source"], file=True)) != row["reference"]["sha256"]:
            raise DatasetError("Final FTID source authentication failed")
        _resource_guard(monitor, plan.config, bytes_written=bytes_written)
    if inspect_metadata(plan) != inventory:
        raise DatasetError("Source universe/metadata changed during materialization")
    for split, paths in lists.items():
        with (destination/f"{split}.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(paths)+"\n")
    descriptor = {"path": destination.resolve().as_posix(), "train": "train.txt", "val": "val.txt",
                  "nc": 3, "names": dict(enumerate(CLASS_NAMES))}
    with (destination/"visem.yaml").open("x", encoding="utf-8") as stream:
        yaml.safe_dump(descriptor, stream, sort_keys=False, allow_unicode=True)
    definition = {name: {"sha256": sha256_file(destination/name), "bytes": (destination/name).stat().st_size}
                  for name in ("train.txt", "val.txt", "visem.yaml")}
    expected_files = {r[k]["path"] for r in rows for k in ("image", "label")} | set(definition)
    found_files = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if found_files != expected_files:
        raise DatasetError("Unexpected/missing files in the materialized dataset")
    actual = sum(_safe(destination, relative, file=True).stat().st_size for relative in expected_files)
    resources = _resource_guard(monitor, plan.config, bytes_written=actual)
    if shutil.disk_usage(destination).free < reserve:
        raise DatasetError("Free-space reserve no longer available")
    return {"files": rows, "definition": definition, "class_counts": class_counts,
            "counts": inventory["counts"], "copied_bytes": bytes_written,
            "dataset_bytes": actual, "resources": resources, "resource_preflight": resource_plan,
            "consumer_policy": "clone_to_new_consumer_run_before_library_access",
            "originals_rehashed_after": True, "sources_modified": False,
            "test_traversed": False, "labels_ftid_read": True, "labels_ftid_copied": False,
            "trained": False}


def materialize_dataset(plan: DatasetPlan) -> Path:
    resolved_config = {**plan.config, "plan_sha256": plan.plan_sha256}
    prefix = f"{plan.config['output_root']}/yolo/materialized/{configuration_directory('materialized', resolved_config)}/preparation"
    _safe(plan.root, prefix)
    snapshot = RunSnapshot.capture(plan.root)
    context = RunContext.create(module="yolo", method="dataset", algorithm="materialized",
                                stage="preparation", seed=plan.config["seed"],
                                config=resolved_config,
                                repo_root=plan.root, output_root=plan.config["output_root"],
                                provenance_snapshot=snapshot)
    inventory = None
    source_audit: list[dict] = []
    try:
        inventory = inspect_metadata(plan)
        inventory_path = write_json_exclusive(context.path/"source_metadata.json", inventory)
        result = copy_dataset(plan, inventory, context.path/"dataset", source_audit=source_audit)
        _bound_manifests(plan.root, plan.config)
        if sha256_file(_safe(plan.root, plan.plan_path, file=True)) != plan.plan_sha256:
            raise DatasetError("Plan changed during materialization")
        proof = snapshot.verify_current()
        result_path = write_json_exclusive(context.path/"dataset_manifest.json", result)
        total = sum(p.stat().st_size for p in context.path.rglob("*") if p.is_file())
        # Reserve a small, explicit envelope for the completed RunContext manifest.
        if total+MIB > plan.config["resources"]["artifact_limit_mib"]*MIB:
            raise DatasetError("Run artifacts plus manifest envelope exceed budget")
        if shutil.disk_usage(context.path).free < (plan.config["resources"]["free_reserve_mib"]+1)*MIB:
            raise DatasetError("Final free-space reserve plus manifest envelope unavailable")
        context.complete(summary={k: result[k] for k in ("counts", "class_counts", "dataset_bytes", "resources")},
                         artifacts={"source_metadata": {"path": str(inventory_path), "sha256": sha256_file(inventory_path)},
                                    "dataset_manifest": {"path": str(result_path), "sha256": sha256_file(result_path)}},
                         descriptor=str(context.path/"dataset/visem.yaml"),
                         provenance_verification=proof, run_bytes_before_final_manifest=total,
                         training_allowed=False, consumer_clone_required=True)
    except BaseException as exc:
        # Recheck every source already opened even on failure. No restoration,
        # cleanup or repair is attempted; external changes remain explicit.
        checks = []
        for entry in source_audit:
            check = dict(entry)
            try:
                relative = Path(entry["path"]).relative_to(plan.root).as_posix()
                check["sha256_after"] = sha256_file(_safe(plan.root, relative, file=True))
                check["unchanged"] = check["sha256_after"] == entry["sha256_before"]
            except (OSError, ValueError) as audit_error:
                check.update(unchanged=False, error=str(audit_error))
            checks.append(check)
        audit_path = write_json_exclusive(context.path/"source_authentication_failure.json",
                                          {"scope": "sources_opened_before_failure", "files": checks,
                                           "checked_file_count": len(checks),
                                           "all_checked_unchanged": all(c["unchanged"] for c in checks)})
        context.fail(exc, source_metadata_sha256=inventory.get("metadata_sha256") if inventory else None,
                     source_authentication_failure={"path": str(audit_path), "sha256": sha256_file(audit_path)},
                     partial_outputs_preserved=True, training_allowed=False)
        raise
    return context.path/"manifest.json"


def main(argv: list[str] | None = None) -> Path | None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--mode", choices=("plan", "materialize"), default="plan")
    args = parser.parse_args(argv)
    plan = load_dataset_plan(args.plan)
    if args.mode == "materialize":
        result = materialize_dataset(plan)
        print(result)
        return result
    monitor = ResourceMonitor()
    inventory = inspect_metadata(plan)
    resources = _resource_guard(monitor, plan.config, bytes_written=0)
    print(json.dumps({**{key: value for key, value in inventory.items()
                        if key not in {"records", "excluded_legacy_sidecars"}},
                      "excluded_sidecar_count": len(inventory["excluded_legacy_sidecars"]),
                      "resource_preflight": preflight_resources(plan, inventory),
                      "metadata_phase_resources": resources},
                     ensure_ascii=False, indent=2))
    return None


if __name__ == "__main__":
    main()
