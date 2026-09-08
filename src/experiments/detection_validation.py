"""Resolve the two immutable training finalists and select on complete validation.

Only metadata is read here. Video decoding, strict label parsing and certification
of the exact frame identities belong to the executor, never to this resolver.
Validation selection is neither an independent test nor a frozen configuration.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import re
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from src.core.paths import REPOSITORY_ROOT
from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID
from .config import canonical_json, config_hash
from .detection_refinement import _Inputs, _csv_equals, _require, load_refinement_candidates
from .detection_search import (
    _MACRO_METRICS, _PREFIXES, _QUALITY_COUNTS, _RAW_COUNTS, _SCORED_COUNTS,
    _SUFFIXES, _count, _equal, _evaluation, _finite, _frame_plan, _id,
    _unique_ids, _validate_video, rank_candidates, summarize_candidate,
)

VALIDATION_IDS = ("14", "19", "36", "52")
VALIDATION_EXPECTED_FRAMES = {"14": 1470, "19": 1470, "36": 1470, "52": 1440}
VALIDATION_INTERPRETATION = "validation_selection_not_independent_test_not_frozen"
_FINALISTS = ("t219_o0_c2", "t218_o0_c2")
_TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
_TEST = ("24", "38", "47", "54")
_TIES = ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"]


class _StrictYaml(yaml.SafeLoader):
    pass


def _yaml_mapping(loader: _StrictYaml, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        _require(key not in result, f"duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


class _MetadataInputs(_Inputs):
    @staticmethod
    def path(value: str | Path, base: Path | None = None) -> Path:
        path = Path(value)
        root = REPOSITORY_ROOT.resolve()
        path = (path if path.is_absolute() else (base or root) / path).resolve()
        _require(path.is_relative_to(root), "validation metadata must be inside the repository")
        _require(not path.is_relative_to(root / "data/sources"), "source access is forbidden")
        _require(path.suffix.lower() in {".json", ".csv", ".yaml", ".yml"},
                 "validation resolver reads only metadata JSON/CSV/YAML")
        return path

    def read(self, value: str | Path) -> Any:
        path = self.path(value)
        if str(path) not in self.records:
            self.verify(path)
        record, before = self.records[str(path)], path.stat()
        _require((before.st_size, before.st_mtime_ns) == (record["bytes"], record["mtime_ns"]),
                 f"input changed before read: {path}")
        text = path.read_text(encoding="utf-8-sig")
        after = path.stat()
        _require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                 f"input changed during read: {path}")
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.load(text, Loader=_StrictYaml)
        return json.loads(text) if path.suffix.lower() == ".json" else list(csv.DictReader(io.StringIO(text)))


def _exact(value: Any, expected: Any, label: str) -> None:
    _require(canonical_json(value) == canonical_json(expected), f"invalid registered {label}")


def _hash(value: Any, label: str) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             f"invalid SHA256: {label}")
    return value


def _rules(plan: dict) -> dict[str, int]:
    _require(isinstance(plan, dict), "validation plan must be a mapping")
    _require(set(plan) == {"plan_id", "method", "stage", "purpose", "refinement", "protocol",
                          "input", "evaluation", "selection", "run", "budget"}, "unexpected validation plan fields")
    for section in ("refinement", "protocol", "input", "evaluation", "selection", "run", "budget"):
        _require(isinstance(plan[section], dict), f"validation {section} must be a mapping")
    for key, expected in {
        "plan_id": "threshold_validation_v3_20260908", "method": "threshold", "stage": "validation",
        "purpose": "select_between_two_training_finalists_on_complete_validation_videos",
    }.items():
        _exact(plan.get(key), expected, key)
    protocol = plan["protocol"]
    _require(set(protocol) == {"splits_config", "splits_sha256", "inventory", "inventory_sha256",
                              "validation_ids", "test_ids_blocked"}, "unexpected protocol fields")
    _exact(protocol["splits_config"], "configs/protocol/splits.yaml", "splits path")
    _exact(protocol["inventory"], "data/manifests/visem_tracking.csv", "inventory path")
    _exact(protocol["validation_ids"], [14, 19, 36, 52], "validation IDs")
    _exact(protocol["test_ids_blocked"], [24, 38, 47, 54], "blocked test IDs")
    _hash(protocol["splits_sha256"], "splits"); _hash(protocol["inventory_sha256"], "inventory")
    expected_frames = _frame_plan(plan["input"].get("expected_frames"), VALIDATION_IDS)
    _exact(expected_frames, VALIDATION_EXPECTED_FRAMES, "full-video frame counts")
    expected_input = {
        "root": "data/sources/visem_tracking/dataset/Train", "label_format": "tracked_yolo",
        "width": 640, "height": 480, "expected_frames": plan["input"]["expected_frames"],
        "expected_annotation_coverage": "complete_per_versioned_inventory",
        "read_mode": "sequential_full_video_with_extra_eof_check",
        "on_missing_or_malformed_label": "fail_without_selection", "resize": False,
        "ground_truth_available_to_detector": False,
    }
    _exact(plan["input"], expected_input, "input rules")
    _exact(plan["evaluation"], {"protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID,
           "class_policy": "individuals_ignore_clusters", "center_gate_px": 10,
           "sensitivity_gates_px": [15, 20]}, "evaluation")
    _exact(plan["selection"], {
        "primary": "macro_video_f1_individuals_center_10px", "tie_breakers": _TIES,
        "video_weighting": "equal_after_within_video_aggregation",
        "require_all_candidates_and_full_videos": True, "timing_used_for_ranking": False,
        "sensitivity_used_for_ranking": False, "interpretation": VALIDATION_INTERPRETATION,
        "hypothesis_tests": False, "confidence_intervals": False,
    }, "selection")
    _exact(plan["run"], {"split": "val", "seed": 42, "opencv_threads": 1, "save_video": False,
           "order": "seeded_shuffle_of_eight_candidate_video_pairs", "reset_detector_per_video": True}, "run")
    _exact(plan["budget"], {"batch_soft_wall_seconds": 1800, "max_rss_mb": 2048,
           "max_batch_artifact_mb": 2048, "max_predictions_per_frame": 2000,
           "on_failure": "preserve_partial_runs_without_selection"}, "budget")
    refinement = plan["refinement"]
    _require(set(refinement) == {"manifest", "manifest_sha256", "finalists_sha256", "verification",
                               "verification_sha256", "candidate_ids", "parameter_hashes"}, "unexpected refinement fields")
    _exact(refinement["candidate_ids"], list(_FINALISTS), "two training finalists")
    _require(set(refinement["parameter_hashes"]) == set(_FINALISTS), "parameter hashes must cover both finalists")
    for key in ("manifest_sha256", "finalists_sha256", "verification_sha256"):
        _hash(refinement[key], key)
    for ident in _FINALISTS:
        params = {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
                  "min_area": 3, "max_area": 300, "threshold_value": int(ident[1:4]),
                  "morph_iterations": 0, "close_iterations": 2}
        _exact(refinement["parameter_hashes"][ident], config_hash(params, 64), "finalist parameters")
    return expected_frames


def _video_csv(rows: list[dict[str, str]]) -> list[dict]:
    """Parse only the fields consumed by the shared arithmetic validator."""
    result = []
    for row in rows:
        typed = {key: row[key] for key in ("video_id", "configuration_id", "evaluation_protocol_id", "class_policy")}
        typed["center_gate_px"] = float(row["center_gate_px"])
        typed["sensitivity_gates_px"] = json.loads(row["sensitivity_gates_px"])
        for key in (*_RAW_COUNTS, "frames_total", "frames_annotated", "frames_unannotated"):
            typed[key] = int(row[key])
        for suffix in _SUFFIXES:
            for key in _SCORED_COUNTS:
                typed[key + suffix] = int(row[key + suffix])
            for prefix in _PREFIXES:
                for metric in (*_MACRO_METRICS, *_QUALITY_COUNTS):
                    key = f"{prefix}{metric}{suffix}"
                    typed[key] = int(row[key]) if metric in {"tp", "fp", "fn", "count_evaluated_frames"} else float(row[key])
        value = row.get("detection_ms_mean")
        typed["detection_ms_mean"] = float(value) if value else None
        result.append(typed)
    return result


def _snapshot(manifest: dict, batch: dict, batch_path: Path, inputs: _MetadataInputs) -> None:
    _require(manifest.get("status") == "complete" and manifest.get("git_dirty") is False,
             "refinement run must be complete with a clean execution snapshot")
    _require(manifest.get("git_sha") == batch.get("git_sha") and manifest.get("source_hash") == batch.get("source_hash")
             and manifest.get("environment") == batch.get("environment"), "refinement snapshots differ")
    capture = manifest.get("provenance_capture", {})
    expected = batch.get("provenance_capture", {})
    _require(capture.get("mode") == "shared_batch" and capture.get("per_candidate_recheck") is False
             and capture.get("snapshot_sha256") == expected.get("snapshot_sha256")
             and capture.get("captured_at") == expected.get("captured_at")
             and capture.get("process_id") == expected.get("process_id")
             and inputs.path(capture["origin_batch_manifest"]) == batch_path,
             "refinement lacks the original shared batch snapshot")
    snapshot_hash = config_hash({"repo_root": str(REPOSITORY_ROOT.resolve()), "captured_at": capture["captured_at"],
                                "process_id": capture["process_id"], "git_sha": manifest["git_sha"],
                                "git_dirty": False, "source_hash": manifest["source_hash"],
                                "environment": manifest["environment"]}, 64)
    _require(capture["snapshot_sha256"] == snapshot_hash, "shared snapshot hash differs from captured metadata")
    _require(manifest.get("config_hash") == config_hash(manifest["config"]), "refinement config hash mismatch")


def load_validation_plan(path: Path) -> tuple[dict, list[dict], dict]:
    """Verify prospective rules and reconstruct both finalists from all 117 runs.

    No source path is dereferenced. The 5,850-frame plan is an expectation from
    the versioned inventory, not proof that a future decoding run is complete.
    """
    inputs = _MetadataInputs()
    plan_path = inputs.verify(path)
    plan = inputs.read(plan_path)
    frames = _rules(plan)
    protocol, refinement = plan["protocol"], plan["refinement"]
    split_path = inputs.verify(protocol["splits_config"], protocol["splits_sha256"])
    inventory_path = inputs.verify(protocol["inventory"], protocol["inventory_sha256"])
    split, inventory = inputs.read(split_path), inputs.read(inventory_path)
    _exact(split["fixed_split"], {"train": list(map(int, _TRAIN)), "val": list(map(int, VALIDATION_IDS)),
                                 "test": list(map(int, _TEST))}, "split membership")
    _require(len({str(row["video_id"]) for row in inventory}) == len(inventory), "duplicate inventory video ID")
    inventory_by_id = {str(row["video_id"]): row for row in inventory}
    for video_id in VALIDATION_IDS:
        row = inventory_by_id.get(video_id, {})
        _require(row.get("split") == "val" and row.get("annotation_status") == "complete"
                 and row.get("total_frames") == row.get("annotated_frames") == str(frames[video_id]),
                 f"inventory does not certify the expected annotated coverage for {video_id}")
    batch_path = inputs.verify(refinement["manifest"], refinement["manifest_sha256"])
    qa_path = inputs.verify(refinement["verification"], refinement["verification_sha256"])
    batch, qa = inputs.read(batch_path), inputs.read(qa_path)
    _snapshot(batch, batch, batch_path, inputs)
    end = batch.get("provenance_verification", {})
    _require(end.get("status") == "verified" and end.get("scope") == "batch_end_before_ranking"
             and end.get("snapshot_sha256") == batch["provenance_capture"]["snapshot_sha256"],
             "refinement was not revalidated before ranking")
    summary = batch["summary"]
    _require(summary.get("mode") == "refine" and summary.get("complete") is True
             and summary.get("selection_allowed") is True and summary.get("completed_candidates") == 117
             and summary.get("frames_per_candidate") == 576 and summary.get("frame_evaluations") == 67392,
             "a complete 117-candidate refinement is required")
    _require(qa.get("status") == "passed" and qa.get("ranking_complete_match") is True
             and qa.get("batch_manifest_sha256") == refinement["manifest_sha256"]
             and inputs.path(qa["batch_manifest"]) == batch_path
             and qa.get("git_sha_of_verified_runs") == batch["git_sha"]
             and qa.get("source_hash_of_verified_runs") == batch["source_hash"], "QA does not certify this refinement")
    _require(qa.get("candidates") == 117 and qa.get("frames_per_video") == 48
             and qa.get("frames_per_candidate") == 576 and qa.get("frame_evaluations") == 67392
             and tuple(map(str, qa.get("videos", []))) == _TRAIN
             and qa.get("candidate_expansion_matches_registered_rule") is True,
             "QA does not cover the full registered refinement universe")
    refs = batch["config"]["refinement_provenance"]
    for key in ("coarse_manifest", "derived_plan", "coarse_verification", "sample_manifest"):
        inputs.verify(refs[key]["path"], refs[key]["sha256"])
    original_plan = batch["config"]["plan"]
    registered, parents_provenance = load_refinement_candidates(
        inputs.path(refs["coarse_manifest"]["path"]), inputs.path(refs["derived_plan"]["path"]), original_plan)
    registered_by_id = {row["configuration_id"]: row for row in registered}
    _require(len(registered_by_id) == len(registered) == 117, "registered refinement universe differs")
    sample = inputs.read(refs["sample_manifest"]["path"])
    sample_path = inputs.path(refs["sample_manifest"]["path"])
    _require(tuple(map(str, sample["video_ids"])) == _TRAIN, "refinement sample is not training-only")
    _require(summary["plan_hash"] == config_hash(original_plan, 64) == qa["plan_hash"]
             and summary["sample_hash"] == sample["sample_hash"] == qa["sample_hash"]
             and summary["refinement_execution_hash"] == qa["refinement_execution_hash"], "refinement identity differs")
    expected_pairs = [[video_id, frame] for video_id in _TRAIN for frame in sample["selections"][video_id]["master"]]
    _require(len(expected_pairs) == len({tuple(pair) for pair in expected_pairs}) == 576,
             "refinement master frame plan is incomplete or duplicated")
    artifacts = inputs.artifacts(batch, batch_path)
    _require({"planned_candidates.json", "planned_frames.json", "candidate_metrics.csv", "ranking.csv", "finalists.json"}
             <= set(artifacts), "refinement lacks hashed selection artifacts")
    inputs.verify(artifacts["finalists.json"], refinement["finalists_sha256"])
    planned = inputs.read(artifacts["planned_candidates.json"])
    _require(len(planned) == 117 and {r["configuration_id"]: r for r in planned} == registered_by_id,
             "refinement candidate plan differs from its registered expansion")
    _exact(inputs.read(artifacts["planned_frames.json"]), expected_pairs, "refinement frame plan")
    children = batch.get("candidate_manifests", [])
    _require(len(children) == 117 and len({r["path"] for r in children}) == 117, "missing or duplicate refinement runs")
    summaries, child_refs, child_configs = [], {}, {}
    for number, reference in enumerate(children, 1):
        child_path = inputs.verify(reference["path"], reference["sha256"])
        child = inputs.read(child_path)
        _snapshot(child, batch, batch_path, inputs)
        config = child["config"]
        ident = config["configuration_id"]
        _require(ident in registered_by_id and ident not in child_refs, "unexpected or duplicate refinement candidate")
        expected = registered_by_id[ident]
        _require(config["params"] == expected["params"] and config["evaluation"] == expected["evaluation"] == plan["evaluation"]
                 and config["run"]["split"] == "train", "refinement candidate parameters/evaluation differ")
        provenance = config["provenance"]
        _require(provenance.get("batch_id") == batch["run_id"] and provenance.get("sample_mode") == "master"
                 and provenance.get("sample_hash") == sample["sample_hash"]
                 and provenance.get("search_plan_hash") == summary["plan_hash"]
                 and provenance.get("sample_manifest_sha256") == inputs.reference(sample_path)["sha256"],
                 "refinement candidate provenance differs")
        child_files = inputs.artifacts(child, child_path)
        _require({"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"} <= set(child_files),
                 "refinement child lacks complete hashed artifacts")
        child_summary = inputs.read(child_files["summary.json"])
        _require(child_summary == child["summary"] == inputs.read(artifacts[f"candidate_{number:03d}.json"]),
                 "refinement summary copies differ")
        rows = inputs.read(child_files["frame_metrics.csv"])
        _exact([[r["video_id"], int(r["frame"])] for r in rows], expected_pairs, "refinement frame identities")
        _require(all(r["annotated"] == "True" and r["configuration_id"] == ident
                     and r["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
                     and r["sample_hash"] == sample["sample_hash"] for r in rows), "refinement frame metadata differs")
        rebuilt = summarize_candidate(_video_csv(inputs.read(child_files["video_summary.csv"])), _TRAIN, 48)
        _require(all(child_summary.get(k) == v for k, v in rebuilt.items()), "refinement video aggregates differ from candidate summary")
        _require(child_summary.get("configuration_id") == ident and child_summary.get("mode") == "refine"
                 and child_summary.get("plan_hash") == summary["plan_hash"]
                 and child_summary.get("sample_hash") == sample["sample_hash"]
                 and child_summary.get("run_id") == child.get("run_id")
                 and inputs.path(child_summary["manifest_path"]) == child_path,
                 "refinement summary identity differs")
        summaries.append(child_summary)
        child_refs[ident], child_configs[ident] = inputs.reference(child_path), config
    ranked = rank_candidates(summaries, list(registered_by_id))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    _csv_equals(inputs.read(artifacts["candidate_metrics.csv"]), summaries, "refinement candidate metrics")
    _csv_equals(inputs.read(artifacts["ranking.csv"]), ranked, "refinement ranking")
    _require(inputs.read(artifacts["finalists.json"]) == ranked[:2], "finalists are not the complete refinement top two")
    _exact([row["configuration_id"] for row in ranked[:2]], list(_FINALISTS), "refinement top two")
    _exact(qa.get("independent_top2"), list(_FINALISTS), "QA top two")
    candidates = []
    for ident in _FINALISTS:
        config = child_configs[ident]
        _exact(config_hash(config["params"], 64), refinement["parameter_hashes"][ident], "selected parameter hash")
        candidates.append({"configuration_id": ident, "method": "threshold", "params": copy.deepcopy(config["params"]),
                           "evaluation": copy.deepcopy(plan["evaluation"]), "provenance": {
                               "training_finalist_manifest": child_refs[ident], "validation_plan_hash": config_hash(plan, 64),
                               "candidate_parameters_hash": refinement["parameter_hashes"][ident]}})
    provenance = {
        "plan": inputs.reference(plan_path), "splits": inputs.reference(split_path), "inventory": inputs.reference(inventory_path),
        "refinement_manifest": inputs.reference(batch_path), "finalists": inputs.reference(artifacts["finalists.json"]),
        "refinement_verification": inputs.reference(qa_path), "sample_manifest": inputs.reference(sample_path),
        "plan_hash": config_hash(plan, 64), "candidate_parameters_hashes": copy.deepcopy(refinement["parameter_hashes"]),
        "expected_frames_per_video": frames, "exact_frame_plan": [[v, i] for v in VALIDATION_IDS for i in range(frames[v])],
        "training_finalist_manifests": {ident: child_refs[ident] for ident in _FINALISTS},
        "refinement_parent_provenance": parents_provenance,
        "validated_inputs": [inputs.reference(Path(p)) for p in sorted(inputs.records)],
        "interpretation": VALIDATION_INTERPRETATION,
    }
    return plan, candidates, provenance


def summarize_validation_candidate(
    video_summaries: Sequence[Mapping[str, Any]], expected_frames_per_video: Mapping[Any, int],
) -> dict[str, Any]:
    """Require all four complete validation videos, then assign equal video weight."""
    frame_plan = _frame_plan(expected_frames_per_video, VALIDATION_IDS)
    rows = list(video_summaries)
    _require(all(isinstance(row, Mapping) for row in rows), "video summaries must be mappings")
    ids = _unique_ids([r.get("video_id") for r in rows], "validation video summaries", count=4)
    _require(set(ids) == set(VALIDATION_IDS), "validation summaries must cover exactly 14/19/36/52")
    identifiers = {_id(r.get("configuration_id"), "configuration_id") for r in rows}
    _require(len(identifiers) == 1, "validation summaries must belong to one candidate")
    by_video = dict(zip(ids, rows))
    ordered = [by_video[v] for v in VALIDATION_IDS]
    for video_id, row in zip(VALIDATION_IDS, ordered):
        _require(row.get("split") == "val" and row.get("status") == "complete"
                 and row.get("frame_coverage_verified") is True,
                 "validation video requires split=val, complete status and certified frame coverage")
        _validate_video(row, frame_plan[video_id])
    frames = sum(frame_plan.values())
    result = {"configuration_id": next(iter(identifiers)), "complete": True, "split": "val", "frame_coverage_verified": True,
              "evaluation_protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID, "class_policy": "individuals_ignore_clusters",
              "center_gate_px": 10, "sensitivity_gates_px": [15, 20], "interpretation": VALIDATION_INTERPRETATION,
              "video_ids": list(VALIDATION_IDS), "n_videos": 4, "expected_frames_per_video": frame_plan,
              "frames_total": frames, "frames_annotated": frames, "frames_unannotated": 0}
    for key in _RAW_COUNTS:
        result[key] = sum(r[key] for r in ordered)
    for suffix in _SUFFIXES:
        for key in _SCORED_COUNTS:
            result[key + suffix] = sum(r[key + suffix] for r in ordered)
        for prefix in _PREFIXES:
            for metric in _MACRO_METRICS:
                key = f"{prefix}{metric}{suffix}"
                result[f"macro_video_{key}"] = statistics.fmean(r[key] for r in ordered)
            for metric in _QUALITY_COUNTS:
                key = f"{prefix}{metric}{suffix}"
                result[key] = sum(r[key] for r in ordered)
    result["macro_video_f1_individuals_center_10px"] = result["macro_video_f1"]
    times = [r.get("detection_ms_mean") for r in ordered]
    result["macro_video_detection_ms_mean"] = (
        statistics.fmean(_finite(v, "detection_ms_mean", minimum=0) for v in times)
        if all(v is not None for v in times) else None)
    return result


def rank_validation_candidates(summaries: Sequence[Mapping[str, Any]], expected_candidate_ids: Sequence[Any]) -> list[dict]:
    """Return both finalists in the predeclared order; never select from a subset."""
    expected = _unique_ids(expected_candidate_ids, "expected validation candidates", count=2)
    rows = list(summaries)
    _require(all(isinstance(row, Mapping) for row in rows), "candidate summaries must be mappings")
    actual = _unique_ids([r.get("configuration_id") for r in rows], "validation candidates", count=2)
    _require(set(actual) == set(expected), "both expected validation candidates are required")
    common_plan = None
    for row in rows:
        _require(row.get("complete") is True and row.get("n_videos") == 4 and row.get("split") == "val"
                 and row.get("frame_coverage_verified") is True
                 and row.get("status", "complete") == "complete" and row.get("interpretation") == VALIDATION_INTERPRETATION,
                 "ranking requires complete validation summaries without test/frozen interpretation")
        _evaluation({"protocol_id": row.get("evaluation_protocol_id"), "class_policy": row.get("class_policy"),
                     "center_gate_px": row.get("center_gate_px"), "sensitivity_gates_px": row.get("sensitivity_gates_px")})
        ids = _unique_ids(row.get("video_ids", []), "validation video IDs", count=4)
        _require(set(ids) == set(VALIDATION_IDS), "validation video universe differs")
        frame_plan = _frame_plan(row.get("expected_frames_per_video"), VALIDATION_IDS)
        signature = tuple(frame_plan.items())
        _require(common_plan is None or signature == common_plan, "validation candidates require identical frame universes")
        common_plan = signature
        frames = sum(frame_plan.values())
        _require(_count(row, "frames_total") == _count(row, "frames_annotated") == frames
                 and _count(row, "frames_unannotated") == 0, "validation frame coverage is incomplete")
        raw, gt, individuals, clusters = (_count(row, k) for k in _RAW_COUNTS)
        _require(gt == individuals + clusters, "inconsistent validation GT counts")
        for suffix in _SUFFIXES:
            scored, ignored, target = (_count(row, k + suffix) for k in _SCORED_COUNTS)
            _require(scored + ignored == raw and target == individuals, "inconsistent validation prediction counts")
            for prefix in _PREFIXES:
                n = lambda metric: f"{prefix}{metric}{suffix}"
                predictions, targets = (raw, gt) if prefix else (scored, target)
                tp, fp, fn = (_count(row, n(k)) for k in ("tp", "fp", "fn"))
                _require(tp + fp == predictions and tp + fn == targets, "inconsistent validation TP/FP/FN")
                _require(_count(row, n("count_evaluated_frames")) == frames, "incomplete validation metric coverage")
                error = _finite(row.get(n("count_error")), n("count_error"))
                absolute = _finite(row.get(n("count_abs_error")), n("count_abs_error"), minimum=0)
                _equal(error, fp - fn, n("count_error"))
                _require(absolute.is_integer() and abs(error) <= absolute <= predictions + targets
                         and (absolute - error) % 2 == 0, "inconsistent validation absolute count error")
                metrics = {k: _finite(row.get(f"macro_video_{n(k)}"), n(k)) for k in _MACRO_METRICS}
                _require(all(0 <= metrics[k] <= 1 for k in ("precision", "recall", "f1")), "validation macro scores out of range")
                _require(metrics["count_mae"] >= abs(metrics["count_bias"]), "validation macro MAE below absolute bias")
        _equal(_finite(row.get("macro_video_f1_individuals_center_10px"), "primary F1 alias"), row["macro_video_f1"], "primary F1 alias")
    return [copy.deepcopy(dict(row)) for row in sorted(rows, key=lambda r: (
        -r["macro_video_f1"], -r["macro_video_recall"], r["macro_video_count_mae"], str(r["configuration_id"])))]
