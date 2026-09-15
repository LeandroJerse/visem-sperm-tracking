"""Independent audit of a completed training-only individual GT preparation.

Read only exported JSON/CSV below data/derived/prediction/ground_truth_individuals.
Never import src/script or open source labels, MP4, cache arrays or YAML. Derive
segments offline by grouping consecutive eligible indices independently for each
original ID; do not use the producer's active-track state machine. Reconstruct
every observation/segment/window and summary, retaining exact binary floats.
An explicit complete run and exclusive new report are required. --self-test
uses only synthetic objects in memory, without reading experiment artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
from itertools import groupby
import json
import math
from pathlib import Path
import platform
import re
import sys
import time
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data/derived/prediction/ground_truth_individuals"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
COUNTS = {v: 1440 if v == "35" else 1500 if v == "82" else 1470 for v in TRAIN}
GAPS = {"23": list(range(823, 973)) + list(range(1084, 1108))}
START_REASONS = ("video_start", "annotation_absent", "class_1", "id_absent")
END_REASONS = ("video_end", "annotation_absent", "class_1", "id_absent")
FLOAT_FIELDS = ("cx", "cy", "w", "h", "x", "y")
FIELDS = {
    "ground_truth_raw": "video_id frame source object_id class_id class_name cx cy w h x y score".split(),
    "observations": "video_id frame_index annotated track_id segment_id class_id cx cy w h x y".split(),
    "segments": "video_id track_id segment_id split start_frame end_frame observation_count start_reason end_reason end_boundary_frame".split(),
    "windows": "window_id video_id track_id segment_id split history_start origin_frame future_end history_length forecast_horizon".split(),
    "frame_status": "video_id frame_index annotated raw_count individual_count cluster_count".split(),
}
TOTAL_FIELDS = ("frames_total", "frames_annotated", "frames_unannotated", "raw_observations",
    "individual_observations", "cluster_observations", "segments_total", "segments_with_windows",
    "segments_without_windows", "origins_with_complete_history", "windows_total", "origins_excluded_incomplete_future")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(value not in (None, "") and not isinstance(value, bool), f"Invalid number: {value!r}")
    result = float(value)
    require(math.isfinite(result), f"Nonfinite number: {value!r}")
    return result


def integer(value):
    result = number(value)
    require(result.is_integer(), f"Noninteger count/index: {value!r}")
    return int(result)


def boolean(value):
    require(type(value) is bool or value in ("True", "False"), f"Invalid boolean: {value!r}")
    return value is True or value == "True"


def json_digest(value, *, ascii=True):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=ascii, allow_nan=False).encode("utf-8")).hexdigest()


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid SHA256")
    return value


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def lexical_path(value):
    """Compare recorded paths without dereferencing a source or metadata file."""
    require(isinstance(value, str) and value, "Invalid recorded path")
    if not Path(value).is_absolute():
        value = str(ROOT / value)
    return value.replace("/", "\\").rstrip("\\").casefold()


def timestamp(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Timestamp lacks timezone")
    return result


class Audit:
    def __init__(self):
        self.files = {}
        self.comparisons = 0

    def path(self, value):
        path = Path(value)
        path = (path if path.is_absolute() else ROOT / path).resolve()
        require(path.is_relative_to(OUTPUT_ROOT) and path.suffix.lower() in (".json", ".csv"),
                f"Only exported CSV/JSON in the individual-reference output root may be read: {path}")
        return path

    def hash(self, value, expected=None):
        path = self.path(value)
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Artifact changed while hashing")
        actual = digest.hexdigest()
        if expected is not None:
            require(actual == sha(expected), f"Hash mismatch: {path}")
        old = self.files.get(str(path))
        require(old is None or old["sha256"] == actual, "Artifact changed after an earlier read")
        self.files[str(path)] = {"path": str(path), "sha256": actual, "bytes": after.st_size,
            "mtime_ns": after.st_mtime_ns, "expected_hash_verified": expected is not None or bool(old and old["expected_hash_verified"])}
        return path

    def reference(self, ref):
        require(set(ref) == {"path", "sha256", "bytes"}, "Unexpected artifact reference schema")
        path = self.hash(ref["path"], ref["sha256"])
        self.equal(self.files[str(path)]["bytes"], integer(ref["bytes"]), "artifact byte count")
        return path

    def read(self, value, reader):
        path = self.path(value)
        if str(path) not in self.files:
            self.hash(path)
        before = path.stat()
        old = self.files[str(path)]
        require((before.st_size, before.st_mtime_ns) == (old["bytes"], old["mtime_ns"]), "Artifact changed before parsing")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            result = reader(stream)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Artifact changed while parsing")
        return result

    def json(self, value):
        return self.read(value, lambda stream: json.load(stream, object_pairs_hook=strict_object, parse_constant=bad_constant))

    def csv(self, value, kind):
        def read(stream):
            reader = csv.DictReader(stream)
            require(reader.fieldnames == FIELDS[kind], f"CSV schema differs: {kind}")
            rows = list(reader)
            require(all(None not in row and all(v is not None for v in row.values()) for row in rows), f"Malformed CSV: {kind}")
            return rows
        return self.read(value, read)

    def equal(self, observed, expected, label):
        self.comparisons += 1
        if isinstance(expected, dict):
            require(isinstance(observed, dict) and set(observed) == set(expected), f"{label}: mapping keys differ")
            for key, value in expected.items():
                self.equal(observed[key], value, f"{label}.{key}")
        elif isinstance(expected, (tuple, list)):
            require(isinstance(observed, (tuple, list)) and len(observed) == len(expected), f"{label}: sequence length differs")
            for i, value in enumerate(expected):
                self.equal(observed[i], value, f"{label}[{i}]")
        elif type(expected) is bool:
            require(boolean(observed) == expected, f"{label}: boolean differs")
        elif isinstance(expected, int):
            require(integer(observed) == expected, f"{label}: count/index differs ({observed!r} != {expected!r})")
        elif isinstance(expected, float):
            require(number(observed).hex() == expected.hex(), f"{label}: float is not preserved exactly")
        else:
            require(observed == expected, f"{label}: value differs ({observed!r} != {expected!r})")


def expected_plan():
    return {
        "plan_id": "individual_trajectories_v1_20260908", "method": "ground_truth_individuals",
        "configuration_id": "individual_trajectories_v1", "purpose": "training_reference_preparation_without_model_evaluation",
        "protocol": {"splits_config": "configs/protocol/splits.yaml",
            "splits_sha256": "f147f748c58d46d39868b2717df2369f2e46efa4af3ebfef93c7821002aad101",
            "inventory": "data/manifests/visem_tracking.csv",
            "inventory_sha256": "d28e4f543f45d6b41add122789126eda1377a973f72f600a3bde75d6c2d8f03b",
            "annotation_gaps": "data/manifests/annotation_gaps.csv", "train_ids": list(map(int, TRAIN)), "statistical_unit": "video"},
        "input": {"root": "data/sources/visem_tracking/dataset/Train", "width": 640, "height": 480,
            "expected_frames": COUNTS, "missing_label_ranges": {"23": [[823, 972], [1084, 1107]]},
            "read_mode": "label_contents_and_mp4_hash_metadata_without_pixel_decoding"},
        "eligibility": {"individual_classes": [0, 2], "cluster_class": 1, "preserve_original_track_ids": True,
            "break_on": ["annotation_absent", "class_1", "id_absent"], "keep_individuals_inside_cluster_boxes": True,
            "interpolate": False, "spatial_or_speed_filter": False},
        "windows": {"history_length": 20, "forecast_horizon": 10, "stride": 1, "output": "indices_only",
            "future_reference_use": "offline_eligibility_and_targets_only", "report_origins_excluded_incomplete_future": True},
        "run": {"stage": "preparation", "split": "train", "seed": 42, "order": "registered_train_id_order", "randomness": "none"},
        "output": {"root": "data/derived", "overwrite": False},
        "budget": {"soft_wall_seconds": 1200, "max_sampled_rss_mb": 2048, "max_artifact_mb": 2048,
                   "on_failure": "preserve_partial_run_without_completion"},
    }


def recorded_provenance(audit, manifest, manifest_path):
    require(manifest.get("status") == "complete" and manifest.get("git_dirty") is False
            and manifest.get("method") == "ground_truth_individuals" and manifest.get("module") == "prediction"
            and manifest.get("stage") == "preparation" and manifest.get("seed") == 42,
            "Preparation must be complete with the registered identity and a clean recorded Git snapshot")
    require(json_digest(manifest["config"]) == json_digest(expected_plan()), "Embedded prospective plan changed")
    require(manifest["config_hash"] == json_digest(manifest["config"])[:12], "Resolved configuration hash differs")
    capture = manifest["provenance_capture"]
    require(capture["mode"] == "shared_batch" and capture["per_candidate_recheck"] is False
            and capture["recheck_policy"] == "batch_end_before_ranking"
            and audit.path(capture["origin_batch_manifest"]) == manifest_path, "Recorded capture policy/origin differs")
    snapshot = json_digest({"repo_root": str(ROOT), "captured_at": capture["captured_at"],
        "process_id": capture["process_id"], "git_sha": manifest["git_sha"], "git_dirty": manifest["git_dirty"],
        "source_hash": manifest["source_hash"], "environment": manifest["environment"]})
    require(snapshot == capture["snapshot_sha256"] and integer(capture["process_id"]) > 0, "Snapshot payload hash differs")
    end = manifest["repository_recheck"]
    require(end["status"] == "verified" and end["snapshot_sha256"] == snapshot
            and end["scope"] == "preparation_end_before_completion"
            and end["checks"] == ["git_sha", "git_dirty", "source_hash", "environment"], "Missing final recorded snapshot verification")
    require(timestamp(capture["captured_at"]) <= timestamp(manifest["started_at"])
            <= timestamp(end["checked_at"]) <= timestamp(manifest["finished_at"]), "Snapshot chronology differs")
    references = manifest["metadata"]
    expected_paths = ["configs/protocol/individual_trajectories_v1.yaml", "configs/protocol/splits.yaml",
                      "data/manifests/visem_tracking.csv", "data/manifests/annotation_gaps.csv"]
    require([lexical_path(item["path"]) for item in references] == [lexical_path(p) for p in expected_paths],
            "Recorded prerequisite metadata paths differ")
    for item in references:
        sha(item["sha256"])
        require(integer(item["bytes"]) > 0, "Invalid recorded prerequisite byte count")
    require(references[1]["sha256"] == manifest["config"]["protocol"]["splits_sha256"]
            and references[2]["sha256"] == manifest["config"]["protocol"]["inventory_sha256"], "Recorded split/inventory hash differs")
    return snapshot


def source_contract(audit, record, video, frame_rows, raw_by_frame, recheck, manifest):
    """Check exported source metadata and row counts, never source bytes."""
    count, missing = COUNTS[video], GAPS.get(video, [])
    require(record["schema_version"] == 1 and record["contract"] == "full_video_input_v1"
            and record["video_id"] == video and record["expected_frame_count"] == count
            and record["expected_width"] == 640 and record["expected_height"] == 480, "Wrong source contract identity")
    require(record["input_hash"] == json_digest({k: v for k, v in record.items() if k != "input_hash"}, ascii=False),
            "Exported input contract hash differs")
    base = ROOT / "data/sources/visem_tracking/dataset/Train" / video
    require(lexical_path(record["source_video"]["path"]) == lexical_path(str(base / f"{video}.mp4")),
            "Recorded source path is not canonical")
    sha(record["source_video"]["sha256"])
    require(integer(record["source_video"]["bytes"]) > 0, "Invalid recorded source size")
    md = record["video_metadata"]
    require(md["width"] == 640 and md["height"] == 480 and md["frame_count"] == count and number(md["fps"]) > 0,
            "Recorded source dimensions/time base differ")
    gt = record["ground_truth"]
    require(lexical_path(gt["directory"]) == lexical_path(str(base / "labels_ftid"))
            and gt["layout"] == "track_id class cx cy w h", "Recorded GT origin/layout differs")
    audit.equal(gt["unannotated_indices"], missing, "contract annotation gaps")
    audit.equal(gt["annotated_frames"], count - len(missing), "contract annotated count")
    audit.equal(gt["unannotated_frames"], len(missing), "contract unannotated count")
    expected_indices = [i for i in range(count) if i not in set(missing)]
    audit.equal([r["frame"] for r in gt["files"]], expected_indices, "recorded label indices")
    inv = record["inventory"]
    require(inv["sha256"] == json_digest(inv["entries"], ascii=False), "Recorded directory inventory hash differs")
    entries = dict(inv["entries"])
    require(len(entries) == len(inv["entries"]), "Duplicate recorded source entry")
    for item in gt["files"]:
        frame = integer(item["frame"])
        match = re.fullmatch(rf"{video}_frame_([0-9]+)_with_ftid\.txt", item["name"])
        require(match is not None and int(match.group(1)) == frame and entries.get(item["name"]) == "file",
                "Recorded label filename/frame does not align")
        require(lexical_path(item["path"]) == lexical_path(str(base / "labels_ftid" / item["name"])), "Recorded label belongs to another input")
        sha(item["sha256"])
        require(integer(item["bytes"]) >= 0, "Invalid label byte count")
        audit.equal(item["rows"], len(raw_by_frame[frame]), "raw GT rows per recorded label")
    require({name for name in entries if name.lower().endswith(".txt")} == {item["name"] for item in gt["files"]},
            "Recorded label inventory contains unaccounted TXT files")
    audit.equal(gt["annotated_empty_frames"], sum(boolean(row["annotated"]) and not raw_by_frame[i]
                for i, row in enumerate(frame_rows)), "recorded empty frames")
    require(recheck["status"] == "verified" and recheck["input_hash"] == record["input_hash"]
            and recheck["files_verified"] == 1 + count - len(missing)
            and recheck["checks"] == ["canonical_paths", "mp4_sha256", "label_sha256", "directory_inventory"],
            "Missing recorded source recheck")
    require(timestamp(manifest["started_at"]) <= timestamp(recheck["checked_at"])
            <= timestamp(manifest["repository_recheck"]["checked_at"]), "Source recheck chronology differs")


def decode_raw(audit, rows, video, frame_rows):
    count = len(frame_rows)
    by_frame = [dict() for _ in range(count)]
    previous = -1
    for row in rows:
        frame = integer(row["frame"])
        require(row["video_id"] == video and row["source"] == "manual" and 0 <= frame < count and frame >= previous,
                "Raw export contains another source/video or reordered/foreign frame")
        previous = frame
        require(boolean(frame_rows[frame]["annotated"]), "Raw GT exists in an explicitly unannotated frame")
        identity = row["object_id"]
        require(isinstance(identity, str) and identity and identity != "-1" and identity.isprintable()
                and not any(c.isspace() for c in identity) and identity not in by_frame[frame],
                "Missing, invalid or duplicated original track ID")
        cls = integer(row["class_id"])
        require(cls in (0, 1, 2) and row["class_name"] == {0: "normal", 1: "cluster", 2: "pinhead"}[cls]
                and number(row["score"]) == 1, "Invalid GT class/name/confidence")
        obj = {"track_id": identity, "class_id": cls, **{k: number(row[k]) for k in FLOAT_FIELDS}}
        require(obj["w"] > 0 and obj["h"] > 0 and 0 <= obj["cx"] <= 640 and 0 <= obj["cy"] <= 480,
                "Invalid recorded normalized geometry")
        audit.equal(obj["x"], obj["cx"] - obj["w"] / 2, "raw x definition")
        audit.equal(obj["y"], obj["cy"] - obj["h"] / 2, "raw y definition")
        require(obj["x"] >= -1e-9 and obj["y"] >= -1e-9
                and obj["x"] + obj["w"] <= 640 + 1e-9 and obj["y"] + obj["h"] <= 480 + 1e-9,
                "Raw GT box lies outside recorded image bounds")
        by_frame[frame][identity] = obj
    for frame, row in enumerate(frame_rows):
        objects = by_frame[frame]
        individuals = sum(obj["class_id"] in (0, 2) for obj in objects.values())
        audit.equal(row, {"video_id": video, "frame_index": frame, "annotated": boolean(row["annotated"]),
            "raw_count": len(objects), "individual_count": individuals, "cluster_count": len(objects)-individuals},
            "frame status rebuilt from raw GT")
    return by_frame


def offline_reconstruction(video, frame_rows, by_frame):
    """Group each ID's eligible time indices; inspect only the two boundaries."""
    eligible = defaultdict(list)
    for frame, objects in enumerate(by_frame):
        for identity, obj in objects.items():
            if obj["class_id"] in (0, 2):
                eligible[identity].append(frame)
    segments, membership, windows = [], {}, []
    for identity, indices in sorted(eligible.items()):
        for _, contiguous in groupby(enumerate(indices), key=lambda pair: pair[1] - pair[0]):
            interval = [frame for _, frame in contiguous]
            start, end = interval[0], interval[-1]
            segment_id = f"{video}/{quote(identity, safe='')}/{start}"
            def boundary_reason(frame, at_start):
                if frame < 0 or frame >= len(frame_rows):
                    return "video_start" if at_start else "video_end"
                if not boolean(frame_rows[frame]["annotated"]):
                    return "annotation_absent"
                adjacent = by_frame[frame].get(identity)
                if adjacent is not None and adjacent["class_id"] == 1:
                    return "class_1"
                require(adjacent is None, "Consecutive eligible indices were split incorrectly")
                return "id_absent"
            segment = {"video_id": video, "track_id": identity, "segment_id": segment_id, "split": "train",
                "start_frame": start, "end_frame": end, "observation_count": len(interval),
                "start_reason": boundary_reason(start - 1, True), "end_reason": boundary_reason(end + 1, False),
                "end_boundary_frame": end + 1}
            require(len(interval) == end - start + 1, "Offline interval is not consecutive")
            segments.append(segment)
            for frame in interval:
                membership[frame, identity] = segment_id
            # Enumerate eligible origin positions, rather than advancing an active tracker.
            for origin in interval:
                if origin - start < 19 or end - origin < 10:
                    continue
                windows.append({"window_id": f"{segment_id}/{origin}/h20_f10", "video_id": video,
                    "track_id": identity, "segment_id": segment_id, "split": "train", "history_start": origin - 19,
                    "origin_frame": origin, "future_end": origin + 10, "history_length": 20, "forecast_horizon": 10})
    observations = [{"video_id": video, "frame_index": frame, "annotated": True,
                     **obj, "segment_id": membership[frame, identity]}
                    for frame, objects in enumerate(by_frame) for identity, obj in sorted(objects.items())
                    if obj["class_id"] in (0, 2)]
    segments.sort(key=lambda row: (row["start_frame"], row["track_id"]))
    windows.sort(key=lambda row: (row["origin_frame"], row["track_id"], row["segment_id"]))
    classes = Counter(obj["class_id"] for objects in by_frame for obj in objects.values())
    raw_ids = {identity for objects in by_frame for identity in objects}
    history_origins = sum(max(s["observation_count"] - 19, 0) for s in segments)
    future_exclusions = {reason: sum(max(s["observation_count"] - 19, 0) - max(s["observation_count"] - 29, 0)
                                   for s in segments if s["end_reason"] == reason) for reason in END_REASONS}
    with_windows = sum(s["observation_count"] >= 30 for s in segments)
    summary = {"schema_version": 1, "video_id": video, "split": "train", "expected_frame_count": len(frame_rows),
        "frames_total": len(frame_rows), "frames_annotated": sum(boolean(row["annotated"]) for row in frame_rows),
        "frames_unannotated": sum(not boolean(row["annotated"]) for row in frame_rows),
        "frames_annotated_empty": sum(boolean(row["annotated"]) and not by_frame[i] for i, row in enumerate(frame_rows)),
        "frames_with_individuals": sum(any(obj["class_id"] in (0, 2) for obj in objects.values()) for objects in by_frame),
        "frames_with_clusters": sum(any(obj["class_id"] == 1 for obj in objects.values()) for objects in by_frame),
        "frames_cluster_only": sum(bool(objects) and all(obj["class_id"] == 1 for obj in objects.values()) for objects in by_frame),
        "raw_observations": sum(classes.values()), "individual_observations": len(observations),
        "cluster_observations": classes[1], "class_observations": {str(k): classes[k] for k in (0, 1, 2)},
        "unique_raw_track_ids": len(raw_ids), "unique_individual_track_ids": len(eligible),
        "segments_total": len(segments), "segments_with_windows": with_windows,
        "segments_without_windows": len(segments) - with_windows,
        "segment_start_reasons": {r: sum(s["start_reason"] == r for s in segments) for r in START_REASONS},
        "segment_end_reasons": {r: sum(s["end_reason"] == r for s in segments) for r in END_REASONS},
        "history_length": 20, "forecast_horizon": 10, "stride": 1,
        "origins_with_complete_history": history_origins, "windows_total": len(windows),
        "origins_excluded_incomplete_future": history_origins - len(windows), "excluded_origins_by_end_reason": future_exclusions}
    retained_short = sum(s["observation_count"] for s in segments if s["observation_count"] < 30)
    retention = {"all_individual_observations_retained": len(observations) == classes[0] + classes[2],
        "original_track_ids_preserved": True, "all_segments_retained": True,
        "individual_observations": len(observations), "observations_in_segments_without_windows": retained_short,
        "segments_shorter_than_history": sum(s["observation_count"] < 20 for s in segments),
        "segments_history_without_complete_future": sum(20 <= s["observation_count"] < 30 for s in segments),
        "candidate_origins": len(observations), "origins_excluded_incomplete_history": sum(min(s["observation_count"], 19) for s in segments),
        "origins_excluded_incomplete_future": history_origins - len(windows), "accepted_origins": len(windows)}
    require(sum(s["observation_count"] for s in segments) == len(observations)
            and retention["candidate_origins"] == retention["origins_excluded_incomplete_history"]
                + retention["origins_excluded_incomplete_future"] + retention["accepted_origins"]
            and sum(future_exclusions.values()) == history_origins - len(windows), "Rebuilt retention/origin accounting failed")
    return observations, segments, windows, summary, retention


def verify(value, audit):
    require(not any(name == "src" or name.startswith("src.") or name == "script" or name.startswith("script.")
                    for name in sys.modules), "Scientific project implementation imported")
    manifest_path = audit.hash(value)
    manifest = audit.json(manifest_path)
    snapshot = recorded_provenance(audit, manifest, manifest_path)
    expected_files = {f"by_video/{v}/{name}.{ext}" for v in TRAIN
                      for name, ext in [(k, "csv") for k in FIELDS] + [("summary", "json"), ("input_contract", "json")]}
    expected_files.add("summary.json")
    artifacts = {}
    for ref in manifest["artifacts"]:
        path = audit.reference(ref)
        require(path.is_relative_to(manifest_path.parent), "Artifact is outside its own run")
        rel = path.relative_to(manifest_path.parent).as_posix()
        require(rel in expected_files and rel not in artifacts, "Unknown or duplicate artifact")
        artifacts[rel] = path
    require(set(artifacts) == expected_files and len(artifacts) == 85, "The complete 12-video artifact set is missing")
    found = {p.relative_to(manifest_path.parent).as_posix() for p in manifest_path.parent.rglob("*") if p.is_file()}
    require(found == expected_files | {"manifest.json"}, "Run contains undeclared artifacts")
    require(len(manifest["input_rechecks"]) == 12, "Wrong source recheck cohort")
    summaries, retention_rows, input_hashes = [], [], {}
    for number_, video in enumerate(TRAIN, 1):
        folder = f"by_video/{video}/"
        frames = audit.csv(artifacts[folder + "frame_status.csv"], "frame_status")
        require(len(frames) == COUNTS[video] and [integer(r["frame_index"]) for r in frames] == list(range(COUNTS[video])),
                f"Frame universe differs for {video}")
        require(all(row["video_id"] == video for row in frames), "Frame status includes another video")
        missing = [i for i, row in enumerate(frames) if not boolean(row["annotated"])]
        audit.equal(missing, GAPS.get(video, []), "registered annotation gaps")
        by_frame = decode_raw(audit, audit.csv(artifacts[folder + "ground_truth_raw.csv"], "ground_truth_raw"), video, frames)
        contract = audit.json(artifacts[folder + "input_contract.json"])
        source_contract(audit, contract, video, frames, by_frame, manifest["input_rechecks"][number_-1], manifest)
        input_hashes[video] = contract["input_hash"]
        observations, segments, windows, summary, retention = offline_reconstruction(video, frames, by_frame)
        for name, expected in (("observations", observations), ("segments", segments), ("windows", windows)):
            audit.equal(audit.csv(artifacts[folder + name + ".csv"], name), expected, f"all {video} {name}")
        audit.equal(audit.json(artifacts[folder + "summary.json"]), summary, f"all {video} summary fields")
        summaries.append(summary)
        retention_rows.append({"video_id": video, **retention})
        print(json.dumps({"verified_videos": number_, "total_videos": 12,
                          "individual_observations": summary["individual_observations"],
                          "segments": summary["segments_total"], "windows": summary["windows_total"]}), flush=True)
    totals = {key: sum(s[key] for s in summaries) for key in TOTAL_FIELDS}
    require(totals["frames_total"] == 17640 and totals["frames_annotated"] == 17466 and totals["frames_unannotated"] == 174,
            "Cohort frame counts differ from the registered 17640/17466/174 universe")
    expected_summary = {"status": "prepared_training_reference_not_prediction_evaluation", "video_ids": list(TRAIN),
        "totals": totals, "videos": summaries, "statistical_unit": "video", "future_reference_conditioned_eligibility": True,
        "model_evaluated": False, "validation_sources_read": False, "test_sources_read": False, "pixels_decoded": False}
    audit.equal(audit.json(artifacts["summary.json"]), expected_summary, "global summary")
    audit.equal(manifest["summary"], expected_summary, "manifest summary")
    resources = manifest["resources"]
    require(number(resources["ram_rss_peak_mb"]) <= 2048
            and integer(resources["artifact_bytes_before_final_manifest"]) <= 2048 * 1024**2,
            "Completed preparation records exceeded their resource limit")
    declared_bytes = sum(audit.files[str(p)]["bytes"] for p in artifacts.values())
    return {"status": "passed", "run_manifest": str(manifest_path),
        "run_manifest_sha256": audit.files[str(manifest_path)]["sha256"], "plan_hash": json_digest(manifest["config"]),
        "git_sha_of_verified_run": manifest["git_sha"], "source_hash_of_verified_run": manifest["source_hash"],
        "shared_snapshot_sha256": snapshot, "input_hashes_recorded": input_hashes,
        "video_ids": list(TRAIN), "expected_frames_per_video": COUNTS, "totals_rebuilt": totals,
        "video_summaries_rebuilt": summaries, "retention_rebuilt": retention_rows,
        "class_observations_rebuilt": {str(k): sum(s["class_observations"][str(k)] for s in summaries) for k in (0, 1, 2)},
        "segment_start_reasons_rebuilt": {k: sum(s["segment_start_reasons"][k] for s in summaries) for k in START_REASONS},
        "segment_end_reasons_rebuilt": {k: sum(s["segment_end_reasons"][k] for s in summaries) for k in END_REASONS},
        "declared_artifact_bytes": declared_bytes,
        "algorithm": "Offline per-ID grouping of consecutive eligible frame indices, followed by independent boundary inspection and full window enumeration.",
        "all_observations_segments_windows_compared": True, "coordinates_compared_as_exact_binary_floats": True,
        "limits": ["Only exported CSV/JSON inside the individual-reference output root were read; no YAML/source labels/MP4/cache arrays.",
            "Source identity/dimensions/hashes and source rechecks are recorded producer evidence; original bytes and video headers were not revalidated.",
            "Every segment, window, observation and summary was rebuilt from exported raw GT and frame status; raw GT accuracy against original annotations was not independently assessed.",
            "Future labels establish offline target eligibility only; this audit does not certify causal predictor/flow inputs.",
            "Segments are continuity intervals retaining original IDs, not new biological identities or independent statistical samples.",
            "No HOTA policy, prediction performance or benefit of optical flow is established by this preparation."]}


def self_test():
    audit = Audit()
    n, video = 45, "synthetic"
    raw_by_frame = [dict() for _ in range(n)]
    special = "00/a%é"
    def obj(identity, cls=0, cx=10.004, width=2.0):
        return {"track_id": identity, "class_id": cls, "cx": cx, "cy": 10.0,
                "w": width, "h": width, "x": cx-width/2, "y": 10.0-width/2}
    for f in range(n):
        if f == 11:
            continue
        raw_by_frame[f][special] = obj(special, cls=2 if f % 2 else 0)
        raw_by_frame[f]["surrounding_cluster"] = obj("surrounding_cluster", cls=1, width=18)
        if f < 10 or 15 <= f < 20:
            raw_by_frame[f]["switch"] = obj("switch")
        elif 10 <= f < 15:
            raw_by_frame[f]["switch"] = obj("switch", cls=1)
    raw_by_frame[2]["singleton"] = obj("singleton")
    frame_rows = [{"video_id": video, "frame_index": f, "annotated": f != 11,
                   "raw_count": len(objects), "individual_count": sum(o["class_id"] != 1 for o in objects.values()),
                   "cluster_count": sum(o["class_id"] == 1 for o in objects.values())} for f, objects in enumerate(raw_by_frame)]
    observations, segments, windows, summary, retention = offline_reconstruction(video, frame_rows, raw_by_frame)
    chosen = [s for s in segments if s["track_id"] == special]
    require([(s["start_frame"], s["end_frame"]) for s in chosen] == [(0, 10), (12, 44)], "Annotation gap was bridged")
    require(chosen[1]["segment_id"] == f"synthetic/{quote(special, safe='')}/12"
            and chosen[1]["start_reason"] == "annotation_absent" and chosen[1]["end_reason"] == "video_end", "ID/reason encoding differs")
    switch = [s for s in segments if s["track_id"] == "switch"]
    require(switch[0]["end_reason"] == "class_1" and switch[1]["start_reason"] == "class_1"
            and switch[1]["end_reason"] == "id_absent", "Class/absence boundaries differ")
    require(len(windows) == 4 and [r["origin_frame"] for r in windows] == [31, 32, 33, 34], "20+10/stride1 enumeration differs")
    require(any(s["track_id"] == "singleton" and s["observation_count"] == 1 for s in segments), "Short segment was lost")
    require(len([o for o in observations if o["track_id"] == special]) == 44, "Individual inside another cluster was discarded")
    require(retention["origins_excluded_incomplete_future"] == 10 and summary["windows_total"] == 4,
            "Retention/future exclusion counts differ")
    audit.equal(observations[0]["cx"], 10.004, "exact float preserved")
    try:
        audit.equal(10.00, 10.004, "rounding corruption")
    except ValueError:
        pass
    else:
        raise ValueError("Float corruption was accepted")
    for length in range(101):
        accepted = sum(i >= 19 and i + 10 < length for i in range(length))
        require(accepted == max(length-29, 0)
                and length == min(length, 19) + max(length-19, 0)-accepted + accepted, "Origin accounting differs")
    for forbidden in (ROOT / "data/sources/forbidden.json", ROOT / "configs/protocol/individual_trajectories_v1.yaml"):
        try:
            audit.path(forbidden)
        except ValueError:
            pass
        else:
            raise ValueError("Forbidden source/metadata path was accepted")
    require(not any(name == "src" or name.startswith("src.") or name == "script" or name.startswith("script.")
                    for name in sys.modules), "Project implementation was imported")
    return {"status": "passed", "mode": "synthetic_self_test", "experiment_artifacts_read": False,
            "checks": ["offline segmentation", "class0/2 continuity", "class1/absent/annotation boundaries",
                       "original quoted ID", "individual inside cluster retained", "singleton retained",
                       "all 20+10 stride1 origins", "future exclusions", "exact float and rounding rejection",
                       "lengths0..100", "source/YAML access guards"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest")
    parser.add_argument("--output", help="Exclusive new JSON report outside the immutable run")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        require(args.run_manifest is None and args.output is None, "Synthetic self-test accepts no experiment paths")
        print(json.dumps(self_test()), flush=True)
        return 0
    require(args.run_manifest is not None and args.output is not None, "Explicit run manifest and new report path are required")
    output, requested = Path(args.output).resolve(), Path(args.run_manifest).resolve()
    require(output.is_relative_to(OUTPUT_ROOT) and output.suffix.lower() == ".json"
            and not output.is_relative_to(requested.parent) and output.parent.is_dir(),
            "Report must be a new JSON in the output root, outside the immutable run, with an existing parent")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        started, audit = time.perf_counter(), Audit()
        try:
            report = verify(args.run_manifest, audit)
            code = 0
        except Exception as error:
            report = {"status": "failed", "error_type": type(error).__name__, "error": str(error),
                      "requested_run_manifest": args.run_manifest}
            code = 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-started,
            comparisons=audit.comparisons, files_verified=len(audit.files), input_files=list(audit.files.values()),
            verifier_path=str(Path(__file__).resolve()), verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            runtime={"python": sys.version, "platform": platform.platform()},
            comparison_rules={"counts_and_ids": "exact", "floats": "exact binary64 via float.hex, no rounding tolerance"},
            project_implementation_imported=False, original_sources_opened=False, seed=None)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
