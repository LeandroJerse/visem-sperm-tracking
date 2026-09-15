"""Independent, read-only verification of a completed coarse threshold batch.

No project implementation is imported. Read only run CSV/JSON artifacts and
the referenced sample manifest (metadata only). Never open source labels,
videos, cached pixels, detectors or the scientific evaluator. Output is a new
exclusive JSON record, including failures, never a replacement of any run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
THRESHOLDS = (0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 190, 192, 200, 208, 224, 240, 255)
PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"
GATES = ((10, ""), (15, "_at_15px"), (20, "_at_20px"))
PREFIXES = ("", "secondary_all_objects_")
METRICS = ("precision", "recall", "f1", "count_mae", "count_bias")
COUNT_METRICS = ("tp", "fp", "fn", "count_error", "count_abs_error", "count_evaluated_frames")
RAW = ("n_predictions_raw", "n_ground_truth_raw", "n_gt_individuals", "n_gt_clusters")
SCORED = ("n_predictions_scored", "n_predictions_ignored", "n_ground_truth_scored")
MATCH_CANDIDATES = {"t000_o0_c0", "t200_o1_c2", "t255_o2_c2"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(value is not None and value != "" and not isinstance(value, bool), f"Invalid number: {value!r}")
    result = float(value)
    require(math.isfinite(result), f"Nonfinite number: {value!r}")
    return result


def integer(value):
    result = number(value)
    require(result.is_integer(), f"Noninteger count/index: {value!r}")
    return int(result)


def boolean(value):
    require(value in (True, False, "True", "False", "true", "false"), f"Invalid boolean: {value!r}")
    return value is True or value in ("True", "true")


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return dict(precision=precision, recall=recall, f1=f1)


def digest_json(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Audit:
    def __init__(self):
        self.files = {}
        self.comparisons = 0
        self.match_checks = []

    def path(self, value, base=None):
        path = Path(value)
        if not path.is_absolute():
            path = (base or ROOT) / path
        path = path.resolve()
        require(path.is_relative_to(ROOT), f"Path outside repository: {path}")
        require(not path.is_relative_to(ROOT / "data/sources"), f"Source access forbidden: {path}")
        require(path.suffix.lower() in {".json", ".csv"}, f"Only JSON/CSV artifact reads allowed: {path}")
        return path

    def hash(self, value, expected=None, base=None):
        path = self.path(value, base)
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"File changed during hash: {path}")
        actual = digest.hexdigest()
        if expected is not None:
            require(actual == expected, f"SHA256 mismatch: {path}")
        old = self.files.get(str(path))
        require(old is None or old["sha256"] == actual, f"Input changed since previous read: {path}")
        self.files[str(path)] = {"path": str(path), "sha256": actual, "bytes": after.st_size,
                                 "mtime_ns": after.st_mtime_ns, "expected_hash_verified": expected is not None or bool(old and old["expected_hash_verified"])}
        return path

    def _stable_read(self, path, reader):
        path = self.path(path)
        if str(path) not in self.files:
            self.hash(path)
        expected = self.files[str(path)]
        before = path.stat()
        require((before.st_size, before.st_mtime_ns) == (expected["bytes"], expected["mtime_ns"]), f"Input changed before read: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            result = reader(stream)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"Input changed during read: {path}")
        return result

    def json(self, path):
        return self._stable_read(path, json.load)

    def csv(self, path):
        return self._stable_read(path, lambda stream: list(csv.DictReader(stream)))

    def equal(self, observed, expected, label, *, spatial=False):
        self.comparisons += 1
        if expected is None:
            require(observed is None or observed == "", f"{label}: expected undefined, got {observed!r}")
        elif isinstance(expected, bool):
            require(boolean(observed) == expected, f"{label}: boolean mismatch")
        elif isinstance(expected, (float, int)):
            require(math.isclose(number(observed), expected, rel_tol=0, abs_tol=1e-9 if spatial else 1e-12),
                    f"{label}: {observed!r} != {expected!r}")
        else:
            require(observed == expected, f"{label}: {observed!r} != {expected!r}")

    def fields(self, observed, expected, label):
        for key, value in expected.items():
            require(key in observed, f"Missing {label}.{key}")
            self.equal(observed[key], value, f"{label}.{key}", spatial="center_error" in key)

    def artifacts(self, manifest, manifest_path):
        hashes = manifest.get("artifact_hashes")
        require(isinstance(hashes, dict) and hashes, f"Missing artifact hashes: {manifest_path}")
        declared = manifest.get("artifacts", {})
        require(set(declared) <= set(hashes), f"Artifact without declared hash: {manifest_path}")
        result = {}
        for key, expected in hashes.items():
            path = self.hash(declared.get(key, key), expected, manifest_path.parent)
            require(path.parent == manifest_path.parent, f"Artifact outside own run directory: {path}")
            require(path.name not in result, f"Duplicate artifact file: {path}")
            result[path.name] = path
        return result


def frame_counts(audit, frame):
    """Check arithmetic independent of matching; undefined primary PRF is explicit."""
    require(boolean(frame["annotated"]), "Unannotated frame entered screening")
    raw_pred, raw_gt, individuals, clusters = (integer(frame[key]) for key in RAW)
    require(min(raw_pred, raw_gt, individuals, clusters) >= 0, "Negative object count")
    require(raw_gt == individuals + clusters, "Raw GT partition mismatch")
    audit.equal(frame["count_error_raw"], raw_pred - raw_gt, "raw count error")
    for gate, suffix in GATES:
        scored, ignored, scored_gt = (integer(frame[key + suffix]) for key in SCORED)
        require(scored + ignored == raw_pred and scored_gt == individuals, "Raw/scored/ignored partition mismatch")
        evaluable = not (clusters > 0 and scored_gt == 0 and scored == 0)
        audit.equal(frame["primary_evaluable" + suffix], evaluable, "primary evaluability")
        for prefix in PREFIXES:
            tp, fp, fn = (integer(frame[f"{prefix}{key}{suffix}"]) for key in ("tp", "fp", "fn"))
            pred_count, gt_count = (raw_pred, raw_gt) if prefix else (scored, scored_gt)
            require(min(tp, fp, fn) >= 0 and tp + fp == pred_count and tp + fn == gt_count, "TP/FP/FN partition mismatch")
            values = prf(tp, fp, fn) if prefix or evaluable else dict(precision=None, recall=None, f1=None)
            values.update(count_error=fp-fn, count_abs_error=abs(fp-fn), count_bias=fp-fn, count_mae=abs(fp-fn))
            distances = number(frame[f"{prefix}center_error_sum_px{suffix}"])
            require(0 <= distances <= tp * gate + 1e-9, "Impossible center-error sum")
            values["center_error_mean_px"] = distances / tp if tp else None
            audit.fields(frame, {f"{prefix}{key}{suffix}": value for key, value in values.items()}, "frame arithmetic")


def aggregate_video(audit, frames):
    """Sum counts within a video, then calculate PRF and frame count errors."""
    result = {"frames_total": len(frames), "frames_annotated": len(frames), "frames_unannotated": 0}
    result.update({key: sum(integer(row[key]) for row in frames) for key in RAW})
    for _, suffix in GATES:
        result.update({key + suffix: sum(integer(row[key + suffix]) for row in frames) for key in SCORED})
        for prefix in PREFIXES:
            tp, fp, fn = (sum(integer(row[f"{prefix}{key}{suffix}"]) for row in frames) for key in ("tp", "fp", "fn"))
            effective = bool(prefix) or any(boolean(row["primary_evaluable" + suffix]) for row in frames) or tp+fp+fn > 0
            values = prf(tp, fp, fn) if effective else dict(precision=None, recall=None, f1=None)
            errors = [integer(row[f"{prefix}count_error{suffix}"]) for row in frames]
            total_distance = math.fsum(number(row[f"{prefix}center_error_sum_px{suffix}"]) for row in frames)
            values.update(tp=tp, fp=fp, fn=fn, count_error=sum(errors), count_abs_error=sum(map(abs, errors)),
                          count_evaluated_frames=len(frames), count_bias=statistics.fmean(errors),
                          count_mae=statistics.fmean(map(abs, errors)), center_error_sum_px=total_distance,
                          center_error_mean_px=total_distance/tp if tp else None)
            result.update({f"{prefix}{key}{suffix}": value for key, value in values.items()})
    return result


def aggregate_candidate(videos):
    """Equal video weight, never pooling F1 or averaging frame F1."""
    result = {"frames_total": sum(row["frames_total"] for row in videos),
              "frames_annotated": sum(row["frames_annotated"] for row in videos), "frames_unannotated": 0, "n_videos": 12}
    result.update({key: sum(row[key] for row in videos) for key in RAW})
    for _, suffix in GATES:
        result.update({key + suffix: sum(row[key + suffix] for row in videos) for key in SCORED})
        for prefix in PREFIXES:
            for metric in METRICS:
                name = f"{prefix}{metric}{suffix}"
                require(all(row[name] is not None for row in videos), f"Undefined video metric: {name}")
                result[f"macro_video_{name}"] = statistics.fmean(row[name] for row in videos)
            for metric in COUNT_METRICS:
                name = f"{prefix}{metric}{suffix}"
                result[name] = sum(row[name] for row in videos)
    result["macro_video_f1_individuals_center_10px"] = result["macro_video_f1"]
    return result


def independent_match(predictions, ground_truth, gate, *, individuals):
    """SciPy assignment: maximum gated cardinality, then minimum total distance."""
    target = [item for item in ground_truth if not individuals or item["class_id"] in (0, 2)]
    clusters = [item for item in ground_truth if item["class_id"] == 1]
    # math.hypot preserves the same input float coordinates without invoking
    # the project's matching implementation or its Hungarian routine.
    distance = np.asarray([[math.hypot(p["cx"]-g["cx"], p["cy"]-g["cy"]) for g in target]
                           for p in predictions], dtype=np.float64).reshape(len(predictions), len(target))
    accepted = []
    if predictions and target:
        penalty = (min(len(predictions), len(target)) + 1) * (gate + 1.0)
        left, right = linear_sum_assignment(np.where(distance <= gate, distance, penalty))
        accepted = [(int(i), int(j), float(distance[i, j])) for i, j in zip(left, right) if distance[i, j] <= gate]
    paired_predictions = {i for i, _, _ in accepted}
    ignored = []
    if individuals:
        for i, item in enumerate(predictions):
            if i in paired_predictions or (len(target) and bool(np.any(distance[i] <= gate))):
                continue
            if any(box["cx"]-box["w"]/2 <= item["cx"] <= box["cx"]+box["w"]/2
                   and box["cy"]-box["h"]/2 <= item["cy"] <= box["cy"]+box["h"]/2 for box in clusters):
                ignored.append(i)
    tp, fp, fn = len(accepted), len(predictions)-len(accepted)-len(ignored), len(target)-len(accepted)
    total_distance = math.fsum(value for _, _, value in accepted)
    evaluable = not (individuals and clusters and not target and len(predictions) == len(ignored))
    result = prf(tp, fp, fn) if evaluable else dict(precision=None, recall=None, f1=None)
    result.update(tp=tp, fp=fp, fn=fn, center_error_sum_px=total_distance,
                  center_error_mean_px=total_distance/tp if tp else None,
                  count_error=fp-fn, count_abs_error=abs(fp-fn), count_bias=fp-fn, count_mae=abs(fp-fn))
    if individuals:
        result.update(n_predictions_scored=len(predictions)-len(ignored), n_predictions_ignored=len(ignored),
                      n_ground_truth_scored=len(target), primary_evaluable=evaluable)
    return result


def compare_matching(audit, config_id, key, pred, gt, frame):
    for gate, suffix in GATES:
        for prefix in PREFIXES:
            expected = independent_match(pred, gt, gate, individuals=not bool(prefix))
            audit.fields(frame, {f"{prefix}{name}{suffix}": value for name, value in expected.items()},
                         f"SciPy {config_id}/{key}/{gate}/{prefix or 'individuals'}")
            audit.match_checks.append({"configuration_id": config_id, "video_id": key[0], "frame": key[1],
                                       "gate_px": gate, "policy": "binary_all_objects" if prefix else "individuals_ignore_clusters",
                                       "tp": expected["tp"], "fp": expected["fp"], "fn": expected["fn"],
                                       "ignored": expected.get("n_predictions_ignored", 0),
                                       "center_error_sum_px": expected["center_error_sum_px"]})


def recorded_time(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Provenance timestamps must include a timezone")
    return result


def verify_batch_snapshot(audit, manifest, manifest_path):
    """Check the recorded capture and final verification, not current machine state."""
    capture = manifest.get("provenance_capture", {})
    require(capture.get("mode") == "shared_batch" and capture.get("per_candidate_recheck") is False
            and capture.get("recheck_policy") == "batch_end_before_ranking", "Missing shared-batch provenance policy")
    require(audit.path(capture["origin_batch_manifest"]) == manifest_path, "Batch snapshot origin does not point to itself")
    require(integer(capture["process_id"]) > 0, "Invalid snapshot process identity")
    require(manifest.get("git_dirty") is False, "Shared snapshot must record clean Git")
    expected_hash = digest_json({
        "repo_root": str(ROOT), "captured_at": capture["captured_at"],
        "process_id": capture["process_id"], "git_sha": manifest["git_sha"],
        "git_dirty": manifest["git_dirty"], "source_hash": manifest["source_hash"],
        "environment": manifest["environment"],
    })
    require(capture.get("snapshot_sha256") == expected_hash, "Snapshot hash does not reproduce its recorded capture")
    verification = manifest.get("provenance_verification", {})
    require(verification.get("status") == "verified"
            and verification.get("snapshot_sha256") == expected_hash
            and verification.get("scope") == "batch_end_before_ranking"
            and verification.get("checks") == ["git_sha", "git_dirty", "source_hash", "environment"],
            "Batch lacks a verified final check of the same shared snapshot")
    require(recorded_time(capture["captured_at"]) <= recorded_time(manifest["started_at"])
            <= recorded_time(verification["checked_at"]) <= recorded_time(manifest["finished_at"]),
            "Batch capture/final-verification chronology is inconsistent")
    return capture


def verify_child_snapshot(audit, child, parent, parent_path):
    capture = child.get("provenance_capture", {})
    require(capture == parent["provenance_capture"], "Candidate does not share its batch's exact capture")
    require(audit.path(capture["origin_batch_manifest"]) == parent_path, "Candidate snapshot links to another batch")
    require(all(child.get(key) == parent.get(key) for key in ("git_sha", "git_dirty", "source_hash", "environment")),
            "Candidate snapshot payload differs from its batch")
    require(recorded_time(capture["captured_at"]) <= recorded_time(child["started_at"])
            <= recorded_time(child["finished_at"]) <= recorded_time(parent["provenance_verification"]["checked_at"]),
            "Candidate did not finish before its batch's final provenance verification")
    config_provenance = child["config"]["provenance"]
    require(config_provenance["batch_id"] == parent["run_id"]
            and audit.path(config_provenance["batch_manifest_path"]) == parent_path,
            "Candidate configuration provenance points to another batch")


def verify(batch_path, audit):
    batch_path = audit.hash(batch_path)
    batch = audit.json(batch_path)
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False, "Batch must be complete with clean Git")
    batch_capture = verify_batch_snapshot(audit, batch, batch_path)
    require(batch["summary"].get("mode") == "coarse", "This verifier only accepts coarse searches, not benchmarks")
    require(batch["summary"].get("selection_allowed") is True, "Complete coarse batch must allow its training shortlist")
    plan = batch["config"]["plan"]
    require(plan["method"] == "threshold" and plan["params"] == {
        "adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
        "min_area": 3, "max_area": 300}, "Unexpected fixed threshold parameters")
    require(tuple(map(str, plan["protocol"]["train_ids"])) == TRAIN, "Unexpected training split")
    require(tuple(plan["search_space"]["threshold_value"]) == THRESHOLDS, "Unexpected threshold grid")
    require(plan["search_space"]["morph_iterations"] == [0, 1, 2] and plan["search_space"]["close_iterations"] == [0, 1, 2], "Unexpected morphology grid")
    require(plan["sampling"]["coarse_frames_per_video"] == 12, "Expected 12 coarse frames per video")
    require(plan["selection"]["primary"] == "macro_video_f1_individuals_center_10px"
            and plan["selection"]["tie_breakers"] == ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"]
            and plan["selection"]["timing_used_for_ranking"] is False
            and plan["selection"]["comparisons_require_all_candidates_and_all_planned_frames"] is True
            and plan["selection"]["coarse_shortlist_size"] == 5, "Unexpected selection semantics")
    require(plan["evaluation"] == {"protocol_id": PROTOCOL, "center_gate_px": 10, "sensitivity_gates_px": [15, 20],
                                   "class_policy": "individuals_ignore_clusters"}, "Unexpected evaluation contract")
    plan_hash = digest_json(plan)
    require(batch["summary"]["plan_hash"] == plan_hash, "Plan fingerprint mismatch")
    require(batch["config_hash"] == digest_json(batch["config"])[:12], "Batch configuration hash mismatch")
    benchmark_ref = batch["config"]["provenance"]["benchmark"]
    benchmark_path = audit.hash(benchmark_ref["path"], benchmark_ref["sha256"])
    benchmark = audit.json(benchmark_path)
    require(benchmark["status"] == "complete" and benchmark["summary"]["mode"] == "benchmark"
            and benchmark["source_hash"] == batch["source_hash"]
            and benchmark["summary"]["plan_hash"] == plan_hash
            and benchmark["summary"]["sample_hash"] == batch["summary"]["sample_hash"], "Benchmark reference differs from the coarse code/plan/sample")
    benchmark_capture = verify_batch_snapshot(audit, benchmark, benchmark_path)
    benchmark_children = benchmark["candidate_manifests"]
    require(len(benchmark_children) == 171 and len({item["path"] for item in benchmark_children}) == 171,
            "Benchmark must link to all 171 candidate captures")
    for reference in benchmark_children:
        child = audit.json(audit.hash(reference["path"], reference["sha256"]))
        require(child.get("status") == "complete", "Incomplete benchmark child")
        verify_child_snapshot(audit, child, benchmark, benchmark_path)
    artifacts = audit.artifacts(batch, batch_path)
    required = {"planned_candidates.json", "planned_frames.json", "candidate_metrics.csv", "ranking.csv", "shortlist.json"}
    required.update(f"candidate_{i:03d}.json" for i in range(1, 172))
    require(required <= set(artifacts), "Batch lacks complete artifact hashes")
    candidates = audit.json(artifacts["planned_candidates.json"])
    expected_params = {f"t{t:03d}_o{o}_c{c}": {**plan["params"], "threshold_value": t, "morph_iterations": o, "close_iterations": c}
                       for t, o, c in itertools.product(THRESHOLDS, range(3), range(3))}
    candidate_by_id = {item["configuration_id"]: item for item in candidates}
    require(len(candidates) == len(candidate_by_id) == 171 and set(candidate_by_id) == set(expected_params), "Candidate universe must contain 171 unique planned configurations")
    for key, item in candidate_by_id.items():
        require(item["method"] == "threshold" and item["params"] == expected_params[key]
                and item["evaluation"] == plan["evaluation"] and item["run"] == {"split": "train", "seed": 42, "save_video": False}, "Resolved candidate differs from plan")
    pairs = [(str(vid), integer(frame)) for vid, frame in audit.json(artifacts["planned_frames.json"])]
    require(len(pairs) == len(set(pairs)) == 144, "Expected 144 unique planned frames")
    frames_by_video = {vid: sorted(frame for video, frame in pairs if video == vid) for vid in TRAIN}
    require(all(len(frames) == 12 for frames in frames_by_video.values()), "Expected exactly 12 frames for each training video")
    require({vid for vid, _ in pairs} == set(TRAIN), "Unexpected video in planned frame universe")
    expected_pairs = set(pairs)
    sample_ref = batch["config"]["input"]
    sample_path = audit.hash(sample_ref["sample_manifest_path"], sample_ref["sample_manifest_sha256"])
    sample = audit.json(sample_path)
    require(sample["sample_hash"] == batch["summary"]["sample_hash"] == sample_ref["sample_hash"], "Sample identity mismatch")
    require(sample["plan_sha256"] == plan_hash and tuple(sample["video_ids"]) == TRAIN, "Sample plan/split mismatch")
    require(all(frames_by_video[vid] == sample["selections"][vid]["coarse"] for vid in TRAIN), "Planned frames differ from sample manifest")
    match_pairs = {(vid, frame) for vid in ("11", "12") for frame in (frames_by_video[vid][0], frames_by_video[vid][-1])}
    reference_gt = {}
    rebuilt = {}
    manifests = batch["candidate_manifests"]
    require(len(manifests) == 171 and len({item["path"] for item in manifests}) == 171, "Expected 171 distinct child manifests")
    for index, reference in enumerate(manifests, 1):
        child_path = audit.hash(reference["path"], reference["sha256"])
        child = audit.json(child_path)
        require(child["status"] == "complete" and child["git_dirty"] is False, "Incomplete/dirty candidate")
        verify_child_snapshot(audit, child, batch, batch_path)
        require(child["source_hash"] == batch["source_hash"] and child["git_sha"] == batch["git_sha"], "Candidate code differs from batch")
        require(child["stage"] == "search" and child["seed"] == 42
                and child["config"]["run"] == {"split": "train", "seed": 42, "save_video": False, "stage": "search"},
                "Candidate run split/stage/seed drifted")
        require(child["config_hash"] == digest_json(child["config"])[:12], "Candidate configuration hash mismatch")
        config_id = child["config"]["configuration_id"]
        require(config_id in expected_params and config_id not in rebuilt, "Unexpected or duplicate candidate")
        require(child["config"]["params"] == expected_params[config_id] and child["config"]["evaluation"] == plan["evaluation"], "Candidate contract or parameters drifted")
        provenance = child["config"]["provenance"]
        require(provenance["search_plan_hash"] == plan_hash and provenance["sample_hash"] == sample["sample_hash"]
                and provenance["sample_manifest_sha256"] == sample_ref["sample_manifest_sha256"]
                and provenance["batch_id"] == batch["run_id"] and provenance["sample_mode"] == "coarse", "Candidate provenance differs")
        child_files = audit.artifacts(child, child_path)
        require({"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"} <= set(child_files), "Incomplete candidate artifacts")
        frame_rows = audit.csv(child_files["frame_metrics.csv"])
        observed = [(str(row["video_id"]), integer(row["frame"])) for row in frame_rows]
        require(len(observed) == len(set(observed)) == 144 and set(observed) == expected_pairs, "Candidate has missing/extra/duplicate frames")
        by_pair = dict(zip(observed, frame_rows))
        raw_by_pair = defaultdict(lambda: {"detection": [], "manual": []})
        for row in audit.csv(child_files["detections.csv"]):
            key = (str(row["video_id"]), integer(row["frame"]))
            require(key in expected_pairs and row["source"] in {"detection", "manual"}, "Unexpected raw object frame/source")
            item = {key_: number(row[key_]) for key_ in ("cx", "cy", "w", "h")}
            item.update(class_id=integer(row["class_id"]), object_id=row["object_id"])
            require(item["class_id"] in (0, 1, 2) and item["w"] > 0 and item["h"] > 0, "Invalid raw object geometry/class")
            raw_by_pair[key][row["source"]].append(item)
        for key, frame in by_pair.items():
            require(frame["configuration_id"] == config_id and frame["evaluation_protocol_id"] == PROTOCOL
                    and frame["class_policy"] == "individuals_ignore_clusters"
                    and number(frame["center_gate_px"]) == 10 and frame["sample_hash"] == sample["sample_hash"], "Frame metadata drift")
            pred, gt = raw_by_pair[key]["detection"], raw_by_pair[key]["manual"]
            audit.fields(frame, dict(n_predictions_raw=len(pred), n_ground_truth_raw=len(gt),
                                     n_gt_individuals=sum(item["class_id"] in (0, 2) for item in gt),
                                     n_gt_clusters=sum(item["class_id"] == 1 for item in gt)), "Raw CSV counts")
            fingerprint = digest_json(sorted(gt, key=lambda item: (item["object_id"], item["class_id"], item["cx"], item["cy"])))
            if key not in reference_gt:
                reference_gt[key] = fingerprint
            require(reference_gt[key] == fingerprint, "GT differs between candidates")
            frame_counts(audit, frame)
            if config_id in MATCH_CANDIDATES and key in match_pairs:
                compare_matching(audit, config_id, key, pred, gt, frame)
        saved_videos = audit.csv(child_files["video_summary.csv"])
        saved_by_video = {str(row["video_id"]): row for row in saved_videos}
        require(len(saved_videos) == len(saved_by_video) == 12 and set(saved_by_video) == set(TRAIN), "Video summary universe mismatch")
        video_metrics = []
        for vid in TRAIN:
            aggregate = aggregate_video(audit, [by_pair[(vid, frame)] for frame in frames_by_video[vid]])
            audit.fields(saved_by_video[vid], aggregate, f"video summary {config_id}/{vid}")
            video_metrics.append(aggregate)
        total = aggregate_candidate(video_metrics)
        saved_summary = audit.json(child_files["summary.json"])
        audit.fields(saved_summary, total, f"candidate summary {config_id}")
        audit.fields(child["summary"], total, f"manifest summary {config_id}")
        require(saved_summary == child["summary"], "Summary JSON differs from child manifest")
        checkpoint = audit.json(artifacts[f"candidate_{index:03d}.json"])
        require(checkpoint == saved_summary, "Batch candidate checkpoint differs from immutable run summary")
        total["configuration_id"] = config_id
        rebuilt[config_id] = total
        if index % 20 == 0:
            print(json.dumps({"verified_candidates": index, "planned": 171}), flush=True)
    require(set(rebuilt) == set(expected_params), "Incomplete reconstructed candidate universe")
    for filename in ("candidate_metrics.csv", "ranking.csv"):
        records = audit.csv(artifacts[filename])
        ids = [row["configuration_id"] for row in records]
        require(len(ids) == len(set(ids)) == 171 and set(ids) == set(rebuilt), f"Incomplete {filename}")
        for row in records:
            audit.fields(row, rebuilt[row["configuration_id"]], filename)
    independently_ranked = sorted(rebuilt, key=lambda key: (-rebuilt[key]["macro_video_f1"], -rebuilt[key]["macro_video_recall"],
                                                            rebuilt[key]["macro_video_count_mae"], key))
    ranking = audit.csv(artifacts["ranking.csv"])
    require([row["configuration_id"] for row in ranking] == independently_ranked, "Ranking order differs from independent video-macro/tie-break calculation")
    require([integer(row["rank"]) for row in ranking] == list(range(1, 172)), "Rank positions are not consecutive")
    shortlist = audit.json(artifacts["shortlist.json"])
    require([row["configuration_id"] for row in shortlist] == independently_ranked[:5], "Top five differs from independent ranking")
    for index, row in enumerate(shortlist, 1):
        audit.fields(row, rebuilt[row["configuration_id"]], "shortlist metrics")
        require(integer(row["rank"]) == index, "Shortlist rank mismatch")
    require(len(audit.match_checks) == 72, "Expected 12 predetermined frames × 3 gates × 2 policies")
    audit.fields(batch["summary"], dict(completed_candidates=171, frames_per_candidate=144, frame_evaluations=24624), "batch completeness")
    return {"status": "passed", "batch_manifest": str(batch_path), "batch_manifest_sha256": audit.files[str(batch_path)]["sha256"],
            "git_sha_of_verified_runs": batch["git_sha"], "source_hash_of_verified_runs": batch["source_hash"],
            "plan_hash": plan_hash, "sample_hash": sample["sample_hash"], "candidates": 171, "videos": list(TRAIN),
            "frames_per_video": 12, "frames_per_candidate": 144, "frame_evaluations": 24624,
            "independent_top5": independently_ranked[:5], "ranking_complete_match": True,
            "predetermined_matching_frames": sorted([list(key) for key in match_pairs]),
            "matching_checks": audit.match_checks,
            "shared_provenance": {
                "coarse_snapshot_sha256": batch_capture["snapshot_sha256"],
                "benchmark_snapshot_sha256": benchmark_capture["snapshot_sha256"],
                "coarse_candidate_links_verified": 171, "benchmark_candidate_links_verified": 171,
                "both_batch_end_verifications_verified": True,
                "scope": "Recorded snapshot payloads, hashes, parent links and chronology; no live-source/environment recheck.",
            },
            "limits": ["training screening, not generalization or scientific promotion",
                       "all frame arithmetic and macro aggregation checked; SciPy matching checked only on the 12 predetermined candidate/frame combinations",
                       "GT comes only from run CSVs; original labels, videos and cached pixel arrays were not opened",
                       "sample and benchmark manifest reference hashes checked; original-source hashes, cached-pixel bytes and benchmark child artifacts not independently revalidated"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest", required=True)
    parser.add_argument("--output", required=True, help="New JSON report path; existing files are refused")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    require(output.is_relative_to(ROOT) and output.suffix.lower() == ".json", "Output must be a new JSON file inside the repository")
    require(not output.is_relative_to(ROOT / "data/sources"), "Cannot write inside immutable sources")
    require(output.parent.is_dir(), "Output parent must already exist")
    # Reserve exclusively before reading any run; no existing record is touched.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        started = time.perf_counter()
        audit = Audit()
        try:
            report = verify(args.batch_manifest, audit)
            code = 0
        except Exception as error:
            report = {"status": "failed", "error_type": type(error).__name__, "error": str(error),
                      "batch_manifest_requested": args.batch_manifest}
            code = 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-started,
                      numeric_comparisons=audit.comparisons, files_verified=len(audit.files),
                      input_files=list(audit.files.values()),
                      verifier_script=str(Path(__file__).resolve()),
                      verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      runtime={"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()},
                      tolerances={"scalar_absolute": 1e-12, "spatial_absolute_px": 1e-9},
                      project_implementation_imported=False, seed=None)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
