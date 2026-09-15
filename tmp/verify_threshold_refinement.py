"""Independent, read-only verification of a completed threshold refinement batch.

No project implementation is imported. Read only run CSV/JSON artifacts,
registered configuration YAML and sample/parent manifests (metadata only).
Never open source labels,
videos, cached pixels, detectors or the scientific evaluator. Output is a new
exclusive JSON record, including failures, never a replacement of any run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
import yaml
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
MATCH_CANDIDATES = {"t193_o0_c2", "t209_o0_c1", "t200_o1_c2"}
CONTRACT_READY = True  # Final contract agreed; only an explicit complete batch is accepted.


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
        require(path.suffix.lower() in {".json", ".csv"}
                or (path.is_relative_to(ROOT / "configs") and path.suffix.lower() in {".yaml", ".yml"}),
                f"Only JSON/CSV artifacts or registered configuration YAML may be read: {path}")
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

    def yaml(self, path):
        require(self.path(path).is_relative_to(ROOT / "configs"), "YAML input must be a registered configuration")
        return self._stable_read(path, yaml.safe_load)

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


def expand_registered_parents(parent_ids, params_by_id, offsets):
    """Canonical candidate order; each candidate retains original ranked parents."""
    records = {}
    for parent_id in parent_ids:
        params = params_by_id[parent_id]
        for offset in offsets:
            resolved = {**params, "threshold_value": max(0, min(255, params["threshold_value"] + offset))}
            t, o, c = (resolved[key] for key in ("threshold_value", "morph_iterations", "close_iterations"))
            key = f"t{t:03d}_o{o}_c{c}"
            require(key not in records or records[key]["params"] == resolved, "Configuration ID collision")
            record = records.setdefault(key, {"configuration_id": key, "method": "threshold", "params": resolved, "parents": []})
            if parent_id not in record["parents"]:
                record["parents"].append(parent_id)
    return [records[key] for key in sorted(records)]


def validate_refinement_contract(audit, batch, batch_path, plan, plan_hash):
    """Reconstruct parameters from the registered parent rule, not run rankings.

    Read only parent result metadata and the derived JSON, never original
    annotations or pixels. Parent metrics are already recorded; this check
    verifies their selection links and independently instantiates the rule.
    """
    execution = batch["config"]["refinement_execution"]
    provenance = batch["config"]["refinement_provenance"]
    recorded = batch["config"]["provenance"]
    execution_path = audit.hash(recorded["refinement_execution_path"], recorded["refinement_execution_sha256"])
    require(audit.yaml(execution_path) == execution, "Embedded execution differs from its registered YAML")
    execution_hash = digest_json(execution)
    require(batch["summary"]["refinement_execution_hash"] == execution_hash,
            "Operational execution hash mismatch")
    require(execution["kind"] == "execution_of_registered_refinement" and execution["method"] == "threshold"
            and execution["base_plan_hash"] == plan_hash
            and audit.yaml(audit.hash(execution["base_plan"])) == plan,
            "Operational execution does not bind the original plan")
    expected = {
        "sampling": {"benchmark_mode": "benchmark", "refinement_mode": "master",
                     "benchmark_frames_per_video": 1, "refinement_frames_per_video": 48},
        "selection": {"finalists": 2, "inherit_ranking_rule_from_base_plan": True,
                      "interpretation": "training_finalists_for_later_full_validation_not_promoted"},
        "benchmark": {"candidate_policy": "all_refinement_candidates", "selection_allowed": False,
                      "projection_safety_factor": 2,
                      "projection_formula": "cache_validation_seconds + parent_validation_seconds + 2 * 48 * candidate_loop_seconds",
                      "interpretation": "operational_projection_not_temporal_worst_case_bound"},
        "budget": {"benchmark_soft_wall_seconds": 600, "refine_soft_wall_seconds": 7200,
                   "allow_refine_if_projection_seconds_at_most": 4800,
                   "inherit_resource_limits_from_base_plan": True},
    }
    require(all(execution.get(key) == value for key, value in expected.items()),
            "Registered operational sampling, selection or budget has changed")
    coarse_path = audit.hash(execution["coarse_manifest"], execution["coarse_manifest_sha256"])
    derived_path = audit.hash(execution["derived_plan"], execution["derived_plan_sha256"])
    coarse, derived = audit.json(coarse_path), audit.json(derived_path)
    require(coarse.get("status") == "complete" and coarse["summary"].get("mode") == "coarse"
            and coarse["summary"].get("selection_allowed") is True
            and coarse["summary"]["plan_hash"] == plan_hash
            and coarse["summary"]["sample_hash"] == batch["summary"]["sample_hash"],
            "Coarse parent is incomplete or belongs to another original plan/sample")
    verify_batch_snapshot(audit, coarse, coarse_path)
    require(derived.get("kind") == "deterministic_instantiation_of_registered_refinement"
            and derived.get("status") == "planned_not_executed"
            and audit.path(derived["coarse_manifest"]) == coarse_path
            and derived["coarse_manifest_sha256"] == execution["coarse_manifest_sha256"]
            and derived["plan_hash"] == plan_hash
            and derived["sample_hash"] == batch["summary"]["sample_hash"]
            and derived["rule"] == plan["refinement_plan"], "Derived plan provenance differs")
    require(tuple(map(str, derived["videos"])) == TRAIN and derived["frames_per_video"] == 48
            and derived["candidate_count"] == 117 and derived["frame_evaluations"] == 67392,
            "Derived plan describes another comparison universe")
    rule = plan["refinement_plan"]
    require(rule["threshold_offsets"] == list(range(-15, 16)) and rule["clamp_threshold_to"] == [0, 255]
            and rule["inherit_parent_morphology"] is True and rule["deduplicate_resolved_parameters"] is True
            and rule["fixed_min_area"] == 3 and rule["fixed_max_area"] == 300
            and rule["maximum_candidates"] == 155 and rule["frames_per_video"] == 48,
            "Registered refinement rule has changed")
    parent_files = audit.artifacts(coarse, coarse_path)
    parents = audit.json(parent_files["shortlist.json"])
    ranking = audit.csv(parent_files["ranking.csv"])
    parent_ids = [row["configuration_id"] for row in parents]
    require(len(parents) == len(set(parent_ids)) == 5
            and parent_ids == [row["configuration_id"] for row in ranking[:5]],
            "Parent shortlist differs from the recorded complete coarse ranking")
    require(len(ranking) == len({row["configuration_id"] for row in ranking}) == 171
            and [integer(row["rank"]) for row in ranking] == list(range(1, 172)),
            "Incomplete coarse parent ranking")
    references = coarse["candidate_manifests"]
    require(len(references) == len({row["path"] for row in references}) == 171,
            "Coarse batch does not bind all candidate manifests")
    references_by_path = {audit.path(row["path"]): row for row in references}
    parent_params, parent_runs = {}, {}
    for parent in parents:
        child_path = audit.path(parent["manifest_path"])
        require(child_path in references_by_path, "Selected parent was not part of the coarse batch")
        child = audit.json(audit.hash(child_path, references_by_path[child_path]["sha256"]))
        verify_child_snapshot(audit, child, coarse, coarse_path)
        require(child["status"] == "complete" and child["config"]["configuration_id"] == parent["configuration_id"]
                and child["config"]["evaluation"] == plan["evaluation"] and child["summary"] == {key: value for key, value in parent.items() if key != "rank"},
                "Selected parent payload differs from the complete coarse child")
        params = child["config"]["params"]
        require(all(params[key] == value for key, value in plan["params"].items()), "Parent fixed parameters drifted")
        parent_params[parent["configuration_id"]] = params
        parent_runs[parent["configuration_id"]] = {"manifest_path": str(child_path),
                                                   "artifacts": audit.artifacts(child, child_path)}
    reconstructed = expand_registered_parents(parent_ids, parent_params, rule["threshold_offsets"])
    expected_params = {row["configuration_id"]: row["params"] for row in reconstructed}
    require(len(expected_params) == 117, "Independent registered expansion must produce exactly 117 parameters")
    records = derived["candidates"]
    observed = {row["configuration_id"]: row for row in records}
    require(len(records) == len(observed) == len(expected_params) and set(observed) == set(expected_params),
            "Derived candidate universe differs from the independent expansion")
    require([row["configuration_id"] for row in records] == sorted(expected_params), "Derived candidates are not in canonical ID order")
    require(digest_json(records) == digest_json(reconstructed),
            "Derived parameters or parent membership/order differs from the ranked parents")
    validate_refinement_provenance(audit, provenance, execution, derived, parent_ids, records,
                                   coarse, coarse_path, derived_path, parent_files, plan)
    expected_candidates = [{"configuration_id": row["configuration_id"], "method": "threshold", "params": row["params"],
                            "evaluation": plan["evaluation"], "run": {"split": "train", "seed": 42, "save_video": False},
                            "provenance": {"search_plan_id": plan["plan_id"], "refinement_parent_ids": row["parents"],
                                           "derived_plan_sha256": execution["derived_plan_sha256"],
                                           "coarse_manifest_sha256": execution["coarse_manifest_sha256"]}}
                           for row in reconstructed]
    random.Random(42).shuffle(expected_candidates)
    return {"expected_params": expected_params, "execution_hash": execution_hash,
            "expected_candidates_in_seed42_order": expected_candidates,
            "parent_runs": parent_runs,
            "execution_path": str(execution_path), "derived_path": str(derived_path),
            "derived_sha256": execution["derived_plan_sha256"], "parent_ids": parent_ids,
            "provenance": provenance}


def validate_refinement_provenance(audit, provenance, execution, derived, parent_ids, records,
                                   coarse, coarse_path, derived_path, parent_files, plan):
    """Check final reference schema, parent-order hash and complete input-hash set.

    Rehash the coarse inputs recorded by the loader without reusing its code.
    This does not repeat coarse frame metric arithmetic or inspect its pixels.
    """
    sample_ref = coarse["config"]["input"]
    sample_path = audit.hash(sample_ref["sample_manifest_path"], sample_ref["sample_manifest_sha256"])
    sample = audit.json(sample_path)
    require(sample["sample_hash"] == derived["sample_hash"] and sample["plan_sha256"] == derived["plan_hash"],
            "Parent sample identity differs")
    recorded_refs = {
        "coarse_manifest": {"path": str(coarse_path), "sha256": execution["coarse_manifest_sha256"]},
        "derived_plan": {"path": str(derived_path), "sha256": execution["derived_plan_sha256"]},
        "sample_manifest": {"path": str(sample_path), "sha256": sample_ref["sample_manifest_sha256"]},
    }
    input_paths = {coarse_path, derived_path, sample_path, *parent_files.values()}
    child_summaries = {}
    for reference in coarse["candidate_manifests"]:
        child_path = audit.hash(reference["path"], reference["sha256"])
        child = audit.json(child_path)
        require(child.get("status") == "complete", "Incomplete coarse child provenance")
        verify_child_snapshot(audit, child, coarse, coarse_path)
        config_id = child["config"]["configuration_id"]
        require(config_id not in child_summaries, "Duplicate coarse child identity")
        child_summaries[config_id] = child["summary"]
        child_files = audit.artifacts(child, child_path)
        input_paths.update({child_path, *child_files.values()})
    require(len(child_summaries) == 171, "Complete coarse input set must contain 171 candidates")
    independently_ranked = sorted(child_summaries, key=lambda key: (
        -number(child_summaries[key]["macro_video_f1"]), -number(child_summaries[key]["macro_video_recall"]),
        number(child_summaries[key]["macro_video_count_mae"]), key))
    require(parent_ids == independently_ranked[:5], "Original ranked parent order differs from its complete summaries")
    verification_paths = []
    for path in sorted(derived_path.parent.glob("verification*.json")):
        path = audit.hash(path)
        input_paths.add(path)
        if audit.files[str(path)]["sha256"] == derived["verification_sha256"]:
            verification_paths.append(path)
    require(len(verification_paths) == 1, "Derived plan must bind one existing coarse verification by SHA256")
    verification_path = audit.hash(verification_paths[0], derived["verification_sha256"])
    verification = audit.json(verification_path)
    require(verification.get("status") == "passed" and verification.get("ranking_complete_match") is True
            and verification["batch_manifest_sha256"] == execution["coarse_manifest_sha256"]
            and audit.path(verification["batch_manifest"]) == coarse_path
            and verification["plan_hash"] == derived["plan_hash"] and verification["sample_hash"] == derived["sample_hash"]
            and verification["independent_top5"] == parent_ids,
            "Bound coarse verification does not approve these original ranked parents")
    recorded_refs["coarse_verification"] = {"path": str(verification_path), "sha256": derived["verification_sha256"]}
    expected = {**recorded_refs, "plan_hash": derived["plan_hash"], "sample_hash": derived["sample_hash"],
                "search_plan_id": plan["plan_id"], "parent_candidate_ids": parent_ids,
                "candidate_count": len(records), "frames_per_video": 48, "frame_evaluations": 67392,
                "candidate_expansion_sha256": digest_json(records), "validated_input_count": len(input_paths),
                "validated_input_hashes_sha256": digest_json(sorted((str(path), audit.files[str(path)]["sha256"]) for path in input_paths)),
                "interpretation": "training_refinement_not_generalization_estimate",
                "requires_new_cost_projection_before_execution": True}
    require(digest_json(provenance) == digest_json(expected), "Final refinement provenance fields, parent order or input-hash set differ")


def verify_parent_overlap(audit, config_id, parent_run, sample, frame_rows, raw_rows):
    """Compare the old twelve-frame results within the new 48-frame universe.

    Raw detections/GT must preserve all complete serialized rows, including
    object IDs and duplicate multiplicity. Row order carries no scientific
    meaning here. Only detection_ms is excluded from frame-metric equality;
    the candidate/protocol/sample metadata must remain identical too.
    """
    old_frames = audit.csv(parent_run["artifacts"]["frame_metrics.csv"])
    old_raw = audit.csv(parent_run["artifacts"]["detections.csv"])
    expected = {(vid, frame) for vid in TRAIN for frame in sample["selections"][vid]["coarse"]}
    old_by_pair = {(str(row["video_id"]), integer(row["frame"])): row for row in old_frames}
    new_by_pair = {(str(row["video_id"]), integer(row["frame"])): row for row in frame_rows}
    require(len(old_frames) == len(old_by_pair) == 144 and set(old_by_pair) == expected
            and expected <= set(new_by_pair), "Parent re-evaluation does not share all original 144 coarse frames")
    old_objects, new_objects = defaultdict(list), defaultdict(list)
    for rows, target in ((old_raw, old_objects), (raw_rows, new_objects)):
        for row in rows:
            key = (str(row["video_id"]), integer(row["frame"]))
            if key in expected:
                target[key].append(row)
    normalized = []
    for key in sorted(expected):
        old_frame, new_frame = old_by_pair[key], new_by_pair[key]
        require(set(old_frame) == set(new_frame), "Frame-metric columns changed between coarse and refinement")
        for name in set(old_frame) - {"detection_ms"}:
            audit.equal(new_frame[name], old_frame[name], f"coarse/master overlap {config_id}/{key}/{name}")
        encode = lambda rows: sorted(digest_json(row) for row in rows)
        old_digest, new_digest = encode(old_objects[key]), encode(new_objects[key])
        require(old_digest == new_digest, f"Raw GT/detection rows differ on shared frame {config_id}/{key}")
        normalized.append({"video_id": key[0], "frame": key[1], "raw_rows": len(old_digest), "row_multiset_sha256": digest_json(old_digest)})
    return {"configuration_id": config_id, "coarse_manifest": parent_run["manifest_path"],
            "shared_frames": len(expected), "frames_per_video": 12, "video_ids": list(TRAIN),
            "raw_rows_compared": sum(row["raw_rows"] for row in normalized),
            "raw_row_multisets_equal": True, "frame_metrics_equal": True,
            "frame_metrics_excluded_fields": ["detection_ms"],
            "comparison": "complete serialized raw-row multisets and exact metric cells on original coarse frames",
            "shared_frame_records_sha256": digest_json(normalized)}


def verify(batch_path, audit):
    require(CONTRACT_READY, "Refinement contract is not finalized; no run artifacts were opened")
    batch_path = audit.hash(batch_path)
    batch = audit.json(batch_path)
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False, "Batch must be complete with clean Git")
    batch_capture = verify_batch_snapshot(audit, batch, batch_path)
    require(batch["summary"].get("mode") == "refine", "This verifier only accepts completed refinement searches, not benchmarks")
    require(batch["summary"].get("selection_allowed") is True, "Complete refinement batch must allow its training finalists")
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
    require(plan["sampling"]["master_frames_per_video"] == 48
            and plan["sampling"]["benchmark_frames_per_video"] == 1
            and plan["refinement_plan"]["finalists_for_later_full_validation"] == 2,
            "Refinement sampling or finalist rule differs from the registered plan")
    plan_hash = digest_json(plan)
    require(batch["summary"]["plan_hash"] == plan_hash, "Plan fingerprint mismatch")
    require(batch["config_hash"] == digest_json(batch["config"])[:12], "Batch configuration hash mismatch")
    contract = validate_refinement_contract(audit, batch, batch_path, plan, plan_hash)
    expected_params = contract["expected_params"]
    benchmark_ref = batch["config"]["provenance"]["benchmark"]
    benchmark_path = audit.hash(benchmark_ref["path"], benchmark_ref["sha256"])
    benchmark = audit.json(benchmark_path)
    require(benchmark["status"] == "complete" and benchmark["summary"]["mode"] == "refinement_benchmark"
            and benchmark["source_hash"] == batch["source_hash"]
            and benchmark["git_sha"] == batch["git_sha"]
            and benchmark["summary"]["plan_hash"] == plan_hash
            and benchmark["summary"]["sample_hash"] == batch["summary"]["sample_hash"], "Benchmark reference differs from the refinement code/plan/sample")
    require(benchmark["summary"].get("selection_allowed") is False
            and benchmark["summary"]["refinement_execution_hash"] == contract["execution_hash"]
            and benchmark["config"]["refinement_execution"] == batch["config"]["refinement_execution"]
            and benchmark["config"]["refinement_provenance"] == contract["provenance"]
            and benchmark["config_hash"] == digest_json(benchmark["config"])[:12],
            "Benchmark operational contract or provenance differs")
    audit.fields(benchmark["summary"], dict(completed_candidates=117, frames_per_candidate=12,
                                           frame_evaluations=1404), "benchmark completeness")
    projected = (number(benchmark["summary"]["cache_validation_seconds"])
                 + number(benchmark["summary"]["parent_validation_seconds"])
                 + 2 * 48 * number(benchmark["summary"]["candidate_loop_seconds"]))
    audit.equal(benchmark["summary"]["projected_refinement_seconds"], projected, "benchmark projection")
    require(0 <= projected <= 4800, "Benchmark did not satisfy the registered refinement projection ceiling")
    audit.equal(benchmark_ref["projected_refinement_seconds"], projected, "bound benchmark projection")
    benchmark_capture = verify_batch_snapshot(audit, benchmark, benchmark_path)
    benchmark_artifacts = audit.artifacts(benchmark, benchmark_path)
    require("ranking.csv" not in benchmark_artifacts and "finalists.json" not in benchmark_artifacts,
            "A cost-only benchmark must not publish a ranking or finalists")
    benchmark_planned = audit.json(benchmark_artifacts["planned_candidates.json"])
    require(len(benchmark_planned) == 117
            and {row["configuration_id"]: row["params"] for row in benchmark_planned} == expected_params,
            "Benchmark did not cover the exact derived parameter universe")
    require(digest_json(benchmark_planned) == digest_json(contract["expected_candidates_in_seed42_order"]),
            "Benchmark candidate order or per-candidate parent provenance differs from seed42 expansion")
    benchmark_children = benchmark["candidate_manifests"]
    require(len(benchmark_children) == 117 and len({item["path"] for item in benchmark_children}) == 117,
            "Benchmark must link to all 117 candidate captures")
    benchmark_ids = []
    for reference in benchmark_children:
        child_path = audit.hash(reference["path"], reference["sha256"])
        child = audit.json(child_path)
        require(child.get("status") == "complete", "Incomplete benchmark child")
        verify_child_snapshot(audit, child, benchmark, benchmark_path)
        child_id = child["config"]["configuration_id"]
        benchmark_ids.append(child_id)
        require(child_id in expected_params and child["config"]["params"] == expected_params[child_id]
                and child["config"]["evaluation"] == plan["evaluation"]
                and child["summary"]["mode"] == "refinement_benchmark"
                and child["summary"]["frames_total"] == 12
                and child["config"]["provenance"]["sample_mode"] == "benchmark"
                and child["config"]["provenance"]["refinement_execution_hash"] == contract["execution_hash"]
                and child["config"]["provenance"]["refinement_provenance"] == contract["provenance"],
                "Benchmark candidate identity or refinement provenance differs")
        audit.artifacts(child, child_path)
    require(len(benchmark_ids) == len(set(benchmark_ids)) == 117 and set(benchmark_ids) == set(expected_params),
            "Benchmark candidate identities are incomplete or duplicated")
    artifacts = audit.artifacts(batch, batch_path)
    required = {"planned_candidates.json", "planned_frames.json", "candidate_metrics.csv", "ranking.csv", "finalists.json"}
    required.update(f"candidate_{i:03d}.json" for i in range(1, 118))
    require(required <= set(artifacts), "Batch lacks complete artifact hashes")
    candidates = audit.json(artifacts["planned_candidates.json"])
    require(digest_json(candidates) == digest_json(contract["expected_candidates_in_seed42_order"]),
            "Refinement candidate order or per-candidate parent provenance differs from seed42 expansion")
    candidate_by_id = {item["configuration_id"]: item for item in candidates}
    require(len(candidates) == len(candidate_by_id) == len(expected_params) == 117
            and set(candidate_by_id) == set(expected_params), "Candidate universe differs from the 117 derived configurations")
    require(MATCH_CANDIDATES <= set(candidate_by_id), "Predetermined matching candidates must exist")
    for key, item in candidate_by_id.items():
        require(item["method"] == "threshold" and item["params"] == expected_params[key]
                and item["evaluation"] == plan["evaluation"]
                and item["run"] == {"split": "train", "seed": 42, "save_video": False},
                "Resolved candidate differs from the derived plan")
    pairs = [(str(vid), integer(frame)) for vid, frame in audit.json(artifacts["planned_frames.json"])]
    require(len(pairs) == len(set(pairs)) == 576, "Expected 576 unique planned frames")
    frames_by_video = {vid: sorted(frame for video, frame in pairs if video == vid) for vid in TRAIN}
    require(all(len(frames) == 48 for frames in frames_by_video.values()), "Expected exactly 48 frames for each training video")
    require({vid for vid, _ in pairs} == set(TRAIN), "Unexpected video in planned frame universe")
    expected_pairs = set(pairs)
    sample_ref = batch["config"]["input"]
    sample_path = audit.hash(sample_ref["sample_manifest_path"], sample_ref["sample_manifest_sha256"])
    sample = audit.json(sample_path)
    require(sample["sample_hash"] == batch["summary"]["sample_hash"] == sample_ref["sample_hash"], "Sample identity mismatch")
    require(sample["plan_sha256"] == plan_hash and tuple(sample["video_ids"]) == TRAIN, "Sample plan/split mismatch")
    require(all(frames_by_video[vid] == sample["selections"][vid]["master"] for vid in TRAIN), "Planned frames differ from sample manifest")
    for vid in TRAIN:
        selection = sample["selections"][vid]
        coarse = selection["coarse"]
        require(len(coarse) == len(set(coarse)) == 12 and coarse == sorted(coarse)
                and set(coarse) <= set(frames_by_video[vid])
                and selection["benchmark"] == [coarse[len(coarse) // 2]],
                "Cache must preserve master/coarse/upper-middle benchmark nesting")
    benchmark_pairs = [(str(vid), integer(frame)) for vid, frame in audit.json(benchmark_artifacts["planned_frames.json"])]
    require(len(benchmark_pairs) == len(set(benchmark_pairs)) == 12
            and set(benchmark_pairs) == {(vid, frame) for vid in TRAIN for frame in sample["selections"][vid]["benchmark"]},
            "Refinement benchmark must reuse exactly the twelve original cached benchmark frames")
    require(benchmark["config"]["input"] == sample_ref, "Refinement and benchmark bind different sample manifests")
    match_pairs = {(vid, frame) for vid in ("11", "12", "23")
                   for frame in (frames_by_video[vid][0], frames_by_video[vid][len(frames_by_video[vid]) // 2], frames_by_video[vid][-1])}
    reference_gt = {}
    rebuilt = {}
    overlap_checks = []
    manifests = batch["candidate_manifests"]
    require(len(manifests) == 117 and len({item["path"] for item in manifests}) == 117, "Expected 117 distinct child manifests")
    for index, reference in enumerate(manifests, 1):
        child_path = audit.hash(reference["path"], reference["sha256"])
        child = audit.json(child_path)
        require(child["status"] == "complete" and child["git_dirty"] is False, "Incomplete/dirty candidate")
        verify_child_snapshot(audit, child, batch, batch_path)
        require(child["source_hash"] == batch["source_hash"] and child["git_sha"] == batch["git_sha"], "Candidate code differs from batch")
        require(child["stage"] == "refinement" and child["seed"] == 42
                and child["config"]["run"] == {"split": "train", "seed": 42, "save_video": False, "stage": "refinement"},
                "Candidate run split/stage/seed drifted")
        require(child["config_hash"] == digest_json(child["config"])[:12], "Candidate configuration hash mismatch")
        config_id = child["config"]["configuration_id"]
        require(config_id in expected_params and config_id not in rebuilt, "Unexpected or duplicate candidate")
        require(child["config"]["params"] == expected_params[config_id] and child["config"]["evaluation"] == plan["evaluation"], "Candidate contract or parameters drifted")
        provenance = child["config"]["provenance"]
        planned_provenance = candidate_by_id[config_id]["provenance"]
        require(all(provenance.get(key) == value for key, value in planned_provenance.items()),
                "Candidate provenance changed parent IDs/order or registered parent hashes")
        require(provenance["search_plan_hash"] == plan_hash and provenance["sample_hash"] == sample["sample_hash"]
                and provenance["sample_manifest_sha256"] == sample_ref["sample_manifest_sha256"]
                and provenance["batch_id"] == batch["run_id"] and provenance["sample_mode"] == "master", "Candidate provenance differs")
        require(provenance["refinement_execution_hash"] == contract["execution_hash"]
                and provenance["refinement_provenance"] == contract["provenance"]
                and child["summary"]["refinement_execution_hash"] == contract["execution_hash"]
                and child["summary"]["mode"] == "refine", "Candidate refinement provenance differs")
        child_files = audit.artifacts(child, child_path)
        require({"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"} <= set(child_files), "Incomplete candidate artifacts")
        frame_rows = audit.csv(child_files["frame_metrics.csv"])
        observed = [(str(row["video_id"]), integer(row["frame"])) for row in frame_rows]
        require(len(observed) == len(set(observed)) == 576 and set(observed) == expected_pairs, "Candidate has missing/extra/duplicate frames")
        by_pair = dict(zip(observed, frame_rows))
        raw_by_pair = defaultdict(lambda: {"detection": [], "manual": []})
        raw_rows = audit.csv(child_files["detections.csv"])
        for row in raw_rows:
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
        if config_id in contract["parent_runs"]:
            overlap_checks.append(verify_parent_overlap(audit, config_id, contract["parent_runs"][config_id], sample, frame_rows, raw_rows))
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
            print(json.dumps({"verified_candidates": index, "planned": 117}), flush=True)
    require(set(rebuilt) == set(expected_params), "Incomplete reconstructed candidate universe")
    for filename in ("candidate_metrics.csv", "ranking.csv"):
        records = audit.csv(artifacts[filename])
        ids = [row["configuration_id"] for row in records]
        require(len(ids) == len(set(ids)) == 117 and set(ids) == set(rebuilt), f"Incomplete {filename}")
        for row in records:
            audit.fields(row, rebuilt[row["configuration_id"]], filename)
    independently_ranked = sorted(rebuilt, key=lambda key: (-rebuilt[key]["macro_video_f1"], -rebuilt[key]["macro_video_recall"],
                                                            rebuilt[key]["macro_video_count_mae"], key))
    ranking = audit.csv(artifacts["ranking.csv"])
    require([row["configuration_id"] for row in ranking] == independently_ranked, "Ranking order differs from independent video-macro/tie-break calculation")
    require([integer(row["rank"]) for row in ranking] == list(range(1, 118)), "Rank positions are not consecutive")
    finalists = audit.json(artifacts["finalists.json"])
    require([row["configuration_id"] for row in finalists] == independently_ranked[:2], "Top two differs from independent ranking")
    for index, row in enumerate(finalists, 1):
        audit.fields(row, rebuilt[row["configuration_id"]], "finalist metrics")
        require(integer(row["rank"]) == index, "Finalist rank mismatch")
    require(len(audit.match_checks) == 162, "Expected 27 predetermined candidate/frame combinations × 3 gates × 2 policies")
    require(len(overlap_checks) == 5 and {row["configuration_id"] for row in overlap_checks} == set(contract["parent_ids"]),
            "All five coarse parents must be rechecked on their original shared frames")
    audit.fields(batch["summary"], dict(completed_candidates=117, frames_per_candidate=576, frame_evaluations=67392), "batch completeness")
    return {"status": "passed", "batch_manifest": str(batch_path), "batch_manifest_sha256": audit.files[str(batch_path)]["sha256"],
            "git_sha_of_verified_runs": batch["git_sha"], "source_hash_of_verified_runs": batch["source_hash"],
            "plan_hash": plan_hash, "sample_hash": sample["sample_hash"], "candidates": 117, "videos": list(TRAIN),
            "refinement_execution_hash": contract["execution_hash"],
            "derived_plan": {"path": contract["derived_path"], "sha256": contract["derived_sha256"]},
            "parent_candidate_ids": contract["parent_ids"],
            "candidate_expansion_matches_registered_rule": True,
            "frames_per_video": 48, "frames_per_candidate": 576, "frame_evaluations": 67392,
            "independent_top2": independently_ranked[:2], "ranking_complete_match": True,
            "predetermined_matching_frames": sorted([list(key) for key in match_pairs]),
            "predetermined_matching_candidates": sorted(MATCH_CANDIDATES),
            "predetermined_master_rank_indices_zero_based": [0, 24, 47],
            "matching_checks": audit.match_checks,
            "coarse_parent_re_evaluation": sorted(overlap_checks, key=lambda row: contract["parent_ids"].index(row["configuration_id"])),
            "coarse_overlap_candidate_frame_comparisons": sum(row["shared_frames"] for row in overlap_checks),
            "coarse_overlap_distinct_physical_frames": 144,
            "shared_provenance": {
                "refinement_snapshot_sha256": batch_capture["snapshot_sha256"],
                "benchmark_snapshot_sha256": benchmark_capture["snapshot_sha256"],
                "refinement_candidate_links_verified": 117, "benchmark_candidate_links_verified": 117,
                "both_batch_end_verifications_verified": True,
                "scope": "Recorded snapshot payloads, hashes, parent links and chronology; no live-source/environment recheck.",
            },
            "limits": ["training refinement, not generalization or scientific promotion",
                       "all frame arithmetic and macro aggregation checked; SciPy matching checked only on the 27 predetermined candidate/frame combinations",
                       "GT comes only from run CSVs; original labels, videos and cached pixel arrays were not opened",
                       "parent selection references and deterministic expansion checked; coarse parent metrics not reaggregated in this refinement verification",
                       "sample and benchmark artifact hashes checked; original-source hashes, cached-pixel bytes and benchmark metric arithmetic not independently revalidated"]}


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
                      runtime={"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "pyyaml": yaml.__version__, "platform": platform.platform()},
                      tolerances={"scalar_absolute": 1e-12, "spatial_absolute_px": 1e-9},
                      project_implementation_imported=False, seed=None)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
