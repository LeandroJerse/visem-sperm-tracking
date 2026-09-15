r"""Independent QA of a future sealed YOLO dataset; imports no producer modules.

Usage: .venv\Scripts\python.exe tmp/tcc_report/verify_yolo_dataset_v1.py
       --manifest <run/manifest.json> --output <preparation/verification_unique.json>
Run only after the coordinator supplies an actual completed manifest.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time

import cv2
import numpy as np
import psutil
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
import yaml


ROOT = Path(__file__).resolve().parents[2]
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
VAL = ("14", "19", "36", "52")
COUNTS = {"train": 17466, "val": 5850, "unlabeled": 174}
NAMES = {0: "sperm", 1: "cluster", 2: "small_or_pinhead"}
SOURCE = "data/sources/visem_tracking/dataset/Train"
MIB = 1024**2


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.numeric_comparisons = 0
        self.files = {}
        self.decoded_copies = 0
        self.annotation_rows = 0
        self.exact_reference_frames = 0
        self.tolerant_reference_frames = 0
        self.max_reference_difference = 0.0
        self.peak_rss = 0
        self.process = psutil.Process()

    def check(self, condition, message):
        self.comparisons += 1
        if not condition:
            raise AssertionError(message)

    def equal(self, actual, expected, message):
        self.check(actual == expected, f"{message}: {actual!r} != {expected!r}")

    def resource(self):
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
        self.check(self.peak_rss <= 1024*MIB, "QA RSS exceeded 1 GiB")

    def regular(self, path):
        path = Path(path)
        relative = path.absolute().relative_to(ROOT)
        current = ROOT
        for part in relative.parts:
            current = current/part
            info = current.lstat()
            self.check(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 1024,
                       f"Link/reparse point forbidden: {current}")
        info = path.stat()
        self.check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, f"Not an independent regular file: {path}")
        return info

    def digest(self, path, expected=None):
        path = Path(path)
        info = self.regular(path)
        value = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(MIB):
                value.update(block)
        result = value.hexdigest()
        self.files[str(path.relative_to(ROOT))] = {"sha256": result, "bytes": info.st_size}
        if expected is not None:
            self.equal(result, expected, f"SHA256 {path}")
        return result


def strict_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise AssertionError(f"Duplicate JSON key {key}")
            out[key] = value
        return out
    def constant(value):
        raise AssertionError(f"Nonfinite JSON constant {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise AssertionError(f"Noncanonical relative path {value!r}")
    if PurePosixPath(value).is_absolute() or any(x in ("", ".", "..") for x in value.split("/")):
        raise AssertionError(f"Path traversal {value!r}")
    return Path(value)


def source_hash():
    files = []
    for folder in ("src", "configs", "script"):
        files.extend(p for p in (ROOT/folder).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix.lower() in {".py", ".yaml", ".yml"})
    files.extend(ROOT/name for name in ("pyproject.toml", "requirements.txt", "requirements-core.lock")
                 if (ROOT/name).is_file())
    value = hashlib.sha256()
    for path in sorted(set(files), key=lambda p: p.as_posix().lower()):
        encoded = path.relative_to(ROOT).as_posix().encode("utf-8")
        value.update(len(encoded).to_bytes(4, "big"))
        value.update(encoded)
        value.update(path.read_bytes())
    return value.hexdigest()


def annotation_rows(path, *, ftid, audit):
    result, identities, seen = [], set(), set()
    text = Path(path).read_text(encoding="utf-8-sig" if ftid else "utf-8")
    for number, line in enumerate(text.splitlines(), 1):
        f = line.split()
        if not f:
            continue
        audit.equal(len(f), 6 if ftid else 5, f"Annotation field count {path}:{number}")
        if ftid:
            audit.check(f[0] != "-1" and f[0] not in identities, f"Duplicate/invalid FTID {path}:{number}")
            identities.add(f[0])
            f = f[1:]
        audit.check(f[0] in {"0", "1", "2"}, "Unexpected annotation class")
        values = tuple(map(float, f[1:]))
        audit.check(all(math.isfinite(x) for x in values), "Nonfinite annotation")
        x, y, w, h = values
        audit.check(w > 0 and h > 0, "Nonpositive annotation size")
        audit.check(min(x-w/2, y-h/2) >= -1e-9 and max(x+w/2, y+h/2) <= 1+1e-9,
                    "Annotation outside normalized image bounds")
        row = (int(f[0]), *values)
        audit.check(row not in seen, "Duplicate numerical annotation")
        seen.add(row)
        result.append(row)
    return result


def parity(yolo, reference, audit):
    audit.equal(Counter(row[0] for row in yolo), Counter(row[0] for row in reference), "FTID class/count parity")
    if Counter(yolo) == Counter(reference):
        audit.exact_reference_frames += 1
        audit.numeric_comparisons += len(yolo)*4
        return {"annotations": len(yolo), "exact_multiset": True, "maximum_difference": 0.0}
    audit.tolerant_reference_frames += 1
    maximum = 0.0
    for category in NAMES:
        first = np.array([r[1:] for r in yolo if r[0] == category])
        second = np.array([r[1:] for r in reference if r[0] == category])
        if not len(first):
            continue
        distances = cdist(first, second, metric="chebyshev")
        a, b = linear_sum_assignment(np.where(distances <= 1e-9, 0, 1))
        audit.check(np.all(distances[a, b] <= 1e-9), "YOLO/FTID geometric multiset mismatch")
        maximum = max(maximum, float(distances[a, b].max()))
        audit.numeric_comparisons += len(a)*4
    audit.max_reference_difference = max(audit.max_reference_difference, maximum)
    return {"annotations": len(yolo), "exact_multiset": False, "maximum_difference": maximum}


def verify(manifest_path, audit):
    import csv

    audit.digest(manifest_path)
    manifest = strict_json(manifest_path)
    run = manifest_path.parent
    dataset_dir = run/"dataset"
    for key, expected in {"status": "complete", "module": "yolo", "method": "dataset",
                          "algorithm": "materialized", "stage": "preparation", "seed": 42,
                          "git_dirty": False, "training_allowed": False,
                          "consumer_clone_required": True}.items():
        audit.equal(manifest[key], expected, f"Manifest {key}")
    audit.check(run.is_relative_to(ROOT/"data/datasets/yolo/materialized"), "Unexpected run location")
    audit.equal(run.name, manifest["run_id"], "Run identifier")
    audit.equal(manifest["provenance_verification"]["status"], "verified", "End-of-run provenance")
    audit.equal(manifest["provenance_verification"]["snapshot_sha256"],
                manifest["provenance_capture"]["snapshot_sha256"], "Provenance snapshot identity")
    audit.equal(source_hash(), manifest["source_hash"], "Current executable source hash; keep source stable until QA")
    commit = subprocess.run(["git", "rev-parse", "--verify", manifest["git_sha"]+"^{commit}"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    audit.check(commit.startswith(manifest["git_sha"]), "Commit does not resolve")
    cfg = manifest["config"]
    audit.equal(hashlib.sha256(canonical(cfg)).hexdigest()[:12], manifest["config_hash"], "Resolved configuration hash")
    scientific = {k: v for k, v in cfg.items() if k != "configuration_id"}
    audit.equal(hashlib.sha256(canonical(scientific)).hexdigest()[:12], manifest["configuration_hash"], "Scientific configuration hash")
    audit.equal(cfg["kind"], "yolo_dataset_materialization_v1", "Plan kind")
    audit.equal(cfg["source_root"], SOURCE, "Source root")
    audit.equal(cfg["output_root"], "data/datasets", "Output root")
    audit.equal(cfg["split_ids"], {"train": list(TRAIN), "val": list(VAL)}, "Allowed splits; no test")
    audit.equal(cfg["expected_counts"], COUNTS, "Expected counts")
    audit.equal(cfg["classes"], list(NAMES.values()), "Original classes")
    plan_path = ROOT/"configs/detection/yolo/dataset_v1.yaml"
    audit.digest(plan_path, cfg["plan_sha256"])
    audit.equal(yaml.safe_load(plan_path.read_text()), {k: v for k, v in cfg.items() if k != "plan_sha256"}, "Prospective YAML equality")
    audit.equal(cfg["labels"], {"fields": 5, "max_bytes": MIB, "bounds_tolerance": 1e-9,
                              "reference_fields": 6, "reference_tolerance": 1e-9}, "Annotation tolerances")
    audit.equal(cfg["resources"], {"artifact_limit_mib": 2048, "rss_limit_mib": 1024,
                                 "free_reserve_mib": 512, "chunk_bytes": MIB}, "Resource ceilings")
    bound = {}
    for name, entry in cfg["manifests"].items():
        path = ROOT/relative_path(entry["path"])
        audit.digest(path, entry["sha256"])
        bound[name] = path
    split = yaml.safe_load(bound["splits"].read_text())
    for name, values in (("train", TRAIN), ("val", VAL)):
        audit.equal(tuple(map(str, split["fixed_split"][name])), values, f"Official {name}")
    with bound["inventory"].open(newline="", encoding="utf-8") as stream:
        inventory_rows = list(csv.DictReader(stream))
    audit.equal(len({r["video_id"] for r in inventory_rows}), len(inventory_rows), "No duplicate video inventory")
    videos = {r["video_id"]: r for r in inventory_rows if r["video_id"] in TRAIN+VAL}
    audit.equal(set(videos), set(TRAIN+VAL), "Permitted metadata videos")
    gaps = {vid: set() for vid in TRAIN+VAL}
    with bound["gaps"].open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            audit.check(row["video_id"] in gaps, "Unexpected gap video")
            indices = set(range(int(row["start_frame"]), int(row["end_frame"])+1))
            audit.equal(len(indices), int(row["frame_count"]), "Gap count")
            audit.check(not indices & gaps[row["video_id"]], "Overlapping gap")
            gaps[row["video_id"]].update(indices)
    audit.equal(sum(map(len, gaps.values())), 174, "Unlabeled gap total")
    artifacts = manifest["artifacts"]
    audit.equal(set(artifacts), {"source_metadata", "dataset_manifest"}, "Run artifact contract")
    for name in artifacts:
        expected = run/(name+".json")
        audit.equal(Path(artifacts[name]["path"]), expected, f"Artifact path {name}")
        audit.digest(expected, artifacts[name]["sha256"])
    metadata = strict_json(run/"source_metadata.json")
    result = strict_json(run/"dataset_manifest.json")
    audit.equal(hashlib.sha256(canonical({k: v for k, v in metadata.items() if k != "metadata_sha256"})).hexdigest(),
                metadata["metadata_sha256"], "Metadata canonical hash")
    audit.equal(metadata["source_content_read"], False, "Metadata-only source inventory")
    audit.equal(metadata["legacy_sidecars_content_read"], False, "Legacy caches never opened")
    audit.equal(metadata["counts"], COUNTS, "Metadata counts")
    audit.equal(result["counts"], COUNTS, "Dataset counts")
    expected_rows = []
    expected_sidecars = set()
    for split_name, ids in (("train", TRAIN), ("val", VAL)):
        for vid in ids:
            base = ROOT/SOURCE/vid
            n = int(videos[vid]["total_frames"])
            audit.equal(videos[vid]["split"], split_name, "Video split")
            expected_images = {f"{vid}_frame_{f}.jpg" for f in range(n)}
            allowed = set(range(n))-gaps[vid]
            expected_labels = {f"{vid}_frame_{f}.txt" for f in allowed}
            image_names = {p.name for p in (base/"images").iterdir()}
            sidecar_names = {name for name in image_names if name.endswith(".npy")}
            audit.equal(image_names-sidecar_names, expected_images, f"Source JPEG universe {vid}")
            audit.check(all(name[:-4]+".jpg" in expected_images for name in sidecar_names), "Unknown NPY sidecar")
            audit.equal({p.name for p in (base/"labels").iterdir()}, expected_labels, f"Source YOLO labels {vid}")
            audit.equal({p.name for p in (base/"labels_ftid").iterdir()},
                        {name[:-4]+"_with_ftid.txt" for name in expected_labels}, f"Source FTID universe {vid}")
            expected_sidecars.update(f"{SOURCE}/{vid}/images/{name}" for name in sidecar_names)
            audit.equal(len(allowed), int(videos[vid]["annotated_frames"]), "Per-video annotated count")
            expected_rows.extend((split_name, vid, f) for f in sorted(allowed))
    audit.equal(len(expected_rows), 23316, "Expected annotated frames")
    audit.equal([(r["split"], r["video_id"], r["frame"]) for r in metadata["records"]], expected_rows, "Metadata ordered universe")
    audit.equal([(r["split"], r["video_id"], r["frame"]) for r in result["files"]], expected_rows, "Copied ordered universe")
    audit.equal({r["path"] for r in metadata["excluded_legacy_sidecars"]}, expected_sidecars, "Excluded legacy sidecars")
    audit.equal(len(metadata["excluded_legacy_sidecars"]), len(expected_sidecars), "No duplicate sidecars")
    for entry in metadata["excluded_legacy_sidecars"]:
        info = audit.regular(ROOT/relative_path(entry["path"]))
        audit.equal((info.st_size, info.st_mtime_ns), (entry["bytes"], entry["mtime_ns"]), "Excluded cache metadata preserved")
    expected_files = {"visem.yaml", "train.txt", "val.txt"}
    lists = {"train": [], "val": []}
    copied_bytes = 0
    class_counts = Counter()
    for index, (row, meta, identity) in enumerate(zip(result["files"], metadata["records"], expected_rows)):
        split_name, vid, frame = identity
        audit.equal(set(row), {"split", "video_id", "frame", "image", "label", "reference", "reference_parity", "annotation_count"}, "Per-frame schema")
        stem = f"{vid}_frame_{frame}"
        for kind, folder, suffix in (("image", "images", ".jpg"), ("label", "labels", ".txt")):
            entry = row[kind]
            expected_relative = f"{folder}/{split_name}/{vid}/{stem}{suffix}"
            expected_source = f"{SOURCE}/{vid}/{folder}/{stem}{suffix}"
            audit.equal(set(entry), {"source", "path", "sha256", "bytes"}, "Per-file schema")
            audit.equal(entry["path"], expected_relative, "Derived file identity")
            audit.equal(entry["source"], expected_source, "Source file identity")
            original, copy = ROOT/relative_path(expected_source), dataset_dir/relative_path(expected_relative)
            audit.digest(original, entry["sha256"])
            audit.digest(copy, entry["sha256"])
            audit.check(not os.path.samefile(original, copy), "Source and destination share identity")
            source_info = original.stat()
            audit.equal((source_info.st_size, source_info.st_mtime_ns),
                        (meta[kind]["bytes"], meta[kind]["mtime_ns"]), "Original metadata preserved")
            audit.equal(meta[kind]["path"], expected_source, "Metadata source identity")
            audit.equal(copy.stat().st_size, entry["bytes"], "Copied bytes")
            audit.equal(source_info.st_size, entry["bytes"], "Source bytes")
            copied_bytes += entry["bytes"]
            expected_files.add(expected_relative)
        reference = row["reference"]
        expected_reference = f"{SOURCE}/{vid}/labels_ftid/{stem}_with_ftid.txt"
        audit.equal(set(reference), {"source", "sha256", "bytes"}, "Reference schema")
        audit.equal(reference["source"], expected_reference, "Reference FTID identity")
        reference_path = ROOT/relative_path(expected_reference)
        audit.digest(reference_path, reference["sha256"])
        audit.equal(meta["reference"]["path"], expected_reference, "Metadata FTID identity")
        reference_info = reference_path.stat()
        audit.equal((reference_info.st_size, reference_info.st_mtime_ns),
                    (meta["reference"]["bytes"], meta["reference"]["mtime_ns"]), "FTID metadata preserved")
        audit.equal(reference_info.st_size, reference["bytes"], "FTID bytes")
        yolo = annotation_rows(dataset_dir/row["label"]["path"], ftid=False, audit=audit)
        ftid = annotation_rows(reference_path, ftid=True, audit=audit)
        observed_parity = parity(yolo, ftid, audit)
        audit.equal(row["reference_parity"]["annotations"], observed_parity["annotations"], "Parity annotation count")
        audit.equal(row["reference_parity"]["exact_multiset"], observed_parity["exact_multiset"], "Parity exactness")
        audit.check(abs(row["reference_parity"]["maximum_difference"]-observed_parity["maximum_difference"]) <= 1e-12,
                    "Reference parity maximum difference")
        audit.equal(row["annotation_count"], len(yolo), "Annotation count")
        class_counts.update(str(r[0]) for r in yolo)
        audit.annotation_rows += len(yolo)
        image_path = dataset_dir/row["image"]["path"]
        raw = image_path.read_bytes()
        audit.check(raw.startswith(b"\xff\xd8") and raw.endswith(b"\xff\xd9"), "JPEG framing")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        audit.check(image is not None and image.shape == (480, 640, 3) and image.dtype == np.uint8,
                    "Copied JPEG decode/shape/type")
        audit.decoded_copies += 1
        lists[split_name].append(image_path.resolve().as_posix())
        audit.resource()
        if (index+1) % 1500 == 0:
            print(f"Verified {index+1}/23316 frames", flush=True)
    audit.equal(copied_bytes, result["copied_bytes"], "Copied data byte total")
    audit.equal(copied_bytes, metadata["copy_bytes"], "Metadata copy byte estimate")
    audit.equal(dict(class_counts), result["class_counts"], "Class observation counts")
    audit.equal(dict(class_counts), {"0": 458327, "1": 13026, "2": 20376}, "Preflight annotation counts")
    for split_name, paths in lists.items():
        audit.equal((dataset_dir/f"{split_name}.txt").read_text().splitlines(), paths, f"Descriptor list {split_name}")
    descriptor = yaml.safe_load((dataset_dir/"visem.yaml").read_text())
    audit.equal(descriptor, {"path": dataset_dir.resolve().as_posix(), "train": "train.txt", "val": "val.txt", "nc": 3, "names": NAMES},
                "No test or external paths in descriptor")
    audit.equal(set(result["definition"]), {"visem.yaml", "train.txt", "val.txt"}, "Definition file universe")
    for name, entry in result["definition"].items():
        audit.digest(dataset_dir/name, entry["sha256"])
        audit.equal((dataset_dir/name).stat().st_size, entry["bytes"], "Definition bytes")
    actual_files = set()
    for path in dataset_dir.rglob("*"):
        info = path.lstat()
        audit.check(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 1024,
                    "Derived directory tree contains links")
        if path.is_file():
            actual_files.add(path.relative_to(dataset_dir).as_posix())
    audit.equal(actual_files, expected_files, "Closed derived file universe")
    audit.equal(len(actual_files), 46635, "23316 image-label pairs plus three descriptors")
    size = sum((dataset_dir/relative).stat().st_size for relative in actual_files)
    audit.equal(size, result["dataset_bytes"], "Dataset actual bytes")
    audit.equal({p.name for p in run.iterdir()}, {"manifest.json", "source_metadata.json", "dataset_manifest.json", "dataset"}, "Completed run top-level universe")
    run_bytes = sum(p.stat().st_size for p in run.rglob("*") if p.is_file())
    audit.check(run_bytes <= 2048*MIB, "Run exceeds artifact limit")
    for key, expected in {"consumer_policy": "clone_to_new_consumer_run_before_library_access",
                          "originals_rehashed_after": True, "sources_modified": False,
                          "test_traversed": False, "labels_ftid_read": True,
                          "labels_ftid_copied": False, "trained": False}.items():
        audit.equal(result[key], expected, f"Dataset policy {key}")
    for key in ("counts", "class_counts", "dataset_bytes", "resources"):
        audit.equal(manifest["summary"][key], result[key], f"Run/dataset summary {key}")
    resources = result["resources"]
    audit.check(resources["ram_rss_peak_mb"] is not None and 0 < resources["ram_rss_peak_mb"] <= 1024, "Recorded RAM")
    audit.check(resources["resource_samples"] >= 23316, "Sampled resource completeness")
    audit.check(math.isfinite(manifest["elapsed_seconds"]) and manifest["elapsed_seconds"] >= 0, "Run duration")
    preflight = result["resource_preflight"]
    audit.equal(preflight["copy_bytes"], copied_bytes, "Resource copy estimate")
    audit.equal(preflight["metadata_envelope_bytes"], 64*MIB, "Metadata envelope")
    audit.equal(preflight["free_reserve_bytes"], 512*MIB, "Free-space reserve")
    audit.equal(preflight["estimated_run_bytes"], copied_bytes+64*MIB, "Estimated run size")
    audit.equal(preflight["minimum_free_bytes"], copied_bytes+576*MIB, "Minimum free space")
    audit.check(preflight["available_free_bytes"] >= preflight["minimum_free_bytes"], "Prospective disk capacity")
    audit.equal(Path(manifest["descriptor"]), dataset_dir/"visem.yaml", "Run descriptor identity")
    audit.equal(source_hash(), manifest["source_hash"], "Executable sources stable through QA")
    return {"run_bytes": run_bytes, "dataset_bytes": size, "counts": COUNTS,
            "class_counts": dict(class_counts), "source_commit": commit,
            "descriptor_files": 3, "copied_file_count": 46632,
            "source_pixels_decoded": False, "copied_jpegs_decoded": audit.decoded_copies,
            "legacy_cache_contents_opened": False, "test_sources_traversed": False,
            "scope": "independent_dataset_integrity_and_annotation_parity_not_training_quality"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve(strict=True)
    output = Path(args.output).absolute()
    if output.parent != manifest.parent.parent or output.name == "manifest.json":
        raise ValueError("QA output must be a uniquely named sibling of the run directory")
    if output.exists():
        raise FileExistsError(output)
    started = time.perf_counter()
    audit = Audit()
    payload = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
               "manifest": str(manifest), "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "versions": {"opencv": cv2.__version__, "numpy": np.__version__}}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
    error = None
    try:
        payload["summary"] = verify(manifest, audit)
        payload["status"] = "passed"
    except BaseException as exc:
        payload.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        error = exc
    finally:
        payload.update(elapsed_seconds=time.perf_counter()-started,
                       files_checked=len(audit.files), comparisons=audit.comparisons,
                       numeric_comparisons=audit.numeric_comparisons,
                       annotation_rows=audit.annotation_rows,
                       exact_reference_frames=audit.exact_reference_frames,
                       tolerant_reference_frames=audit.tolerant_reference_frames,
                       maximum_reference_difference=audit.max_reference_difference,
                       qa_peak_rss_mib=audit.peak_rss/MIB, files=audit.files)
        temporary = output.with_name(output.name+".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, output)
    print(json.dumps({k: v for k, v in payload.items() if k not in {"files"}}, indent=2, ensure_ascii=False), flush=True)
    if error:
        raise error


if __name__ == "__main__":
    main()
