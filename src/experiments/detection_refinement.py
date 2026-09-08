"""Validate immutable coarse artifacts and resolve the registered refinement.

This loader reads only JSON/CSV artifacts. It neither opens source labels or
pixels nor runs a detector. Refinement remains training screening; promotion,
cost approval and execution belong to the orchestrator.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import canonical_json, config_hash
from src.experiments.detection_search import expand_coarse_candidates, rank_candidates


_TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
_PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class _Inputs:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    @staticmethod
    def path(value: str | Path, base: Path | None = None) -> Path:
        path = Path(value)
        path = (path if path.is_absolute() else (base or Path.cwd()) / path).resolve()
        _require(path.suffix.lower() in {".json", ".csv"}, "refinement reads only JSON/CSV artifacts")
        _require(not path.is_relative_to(REPOSITORY_ROOT / "data/sources"), "source access is forbidden")
        return path

    def verify(self, value: str | Path, expected: str | None = None) -> Path:
        path = self.path(value)
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        after = path.stat()
        _require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"input changed: {path}")
        observed = digest.hexdigest()
        _require(expected is None or observed == expected, f"artifact SHA256 mismatch: {path}")
        previous = self.records.get(str(path))
        _require(previous is None or previous["sha256"] == observed, f"input changed between reads: {path}")
        self.records[str(path)] = {"path": str(path), "sha256": observed, "bytes": after.st_size,
                                  "mtime_ns": after.st_mtime_ns}
        return path

    def read(self, value: str | Path) -> Any:
        path = self.path(value)
        if str(path) not in self.records:
            self.verify(path)
        record = self.records[str(path)]
        before = path.stat()
        _require((before.st_size, before.st_mtime_ns) == (record["bytes"], record["mtime_ns"]), f"input changed before read: {path}")
        text = path.read_text(encoding="utf-8-sig")
        after = path.stat()
        _require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"input changed during read: {path}")
        return json.loads(text) if path.suffix.lower() == ".json" else list(csv.DictReader(io.StringIO(text)))

    def reference(self, path: Path) -> dict[str, str]:
        return {key: self.records[str(path)][key] for key in ("path", "sha256")}

    def artifacts(self, manifest: dict, manifest_path: Path) -> dict[str, Path]:
        artifacts, hashes = manifest.get("artifacts"), manifest.get("artifact_hashes")
        _require(isinstance(artifacts, dict) and isinstance(hashes, dict) and artifacts
                 and set(artifacts) == set(hashes), "every declared artifact must have a SHA256")
        paths: dict[str, Path] = {}
        for key, value in artifacts.items():
            path = self.path(value, manifest_path.parent)
            _require(path.parent == manifest_path.parent and path.name != "manifest.json", "artifact is outside its run directory")
            _require(path.name not in paths, "duplicate artifact path")
            paths[path.name] = self.verify(path, hashes[key])
        return paths


def _csv_equals(rows: list[dict[str, str]], expected: list[dict[str, Any]], label: str) -> None:
    _require(len(rows) == len(expected), f"incomplete {label}")
    for actual, reference in zip(rows, expected):
        serialized = {key: "" if value is None else str(value) for key, value in reference.items()}
        _require(actual == serialized, f"{label} differs from the complete candidate summaries")


def _rule(plan: dict) -> dict:
    rule = plan.get("refinement_plan")
    _require(isinstance(rule, dict), "missing registered refinement rule")
    _require(rule.get("parent_candidates") == "top_5_from_complete_coarse_search"
             and plan["selection"].get("coarse_shortlist_size") == 5, "refinement requires the complete coarse top five")
    _require(canonical_json(rule.get("threshold_offsets")) == canonical_json(list(range(-15, 16)))
             and rule.get("clamp_threshold_to") == [0, 255], "refinement requires all integer offsets -15..15, clamped to [0,255]")
    _require(rule.get("inherit_parent_morphology") is True and rule.get("deduplicate_resolved_parameters") is True,
             "refinement must inherit morphology and deduplicate resolved parameters")
    _require(rule.get("fixed_min_area") == plan["params"]["min_area"]
             and rule.get("fixed_max_area") == plan["params"]["max_area"], "refinement must retain the registered fixed area limits")
    _require(rule.get("frames_per_video") == 48 and rule.get("finalists_for_later_full_validation") == 2,
             "refinement requires 48 frames/video and two later validation finalists")
    _require(rule.get("requires_new_cost_projection_before_execution") is True, "refinement requires a new cost projection")
    _require(type(rule.get("maximum_candidates")) is int and rule["maximum_candidates"] > 0
             and type(rule.get("maximum_frame_evaluations")) is int and rule["maximum_frame_evaluations"] > 0,
             "refinement must declare positive integer candidate/frame budgets")
    return rule


def _expand(parents: list[str], coarse: dict[str, dict], rule: dict) -> list[dict]:
    resolved: dict[str, dict] = {}
    for parent_id in parents:
        parent_params = coarse[parent_id]["params"]
        for offset in rule["threshold_offsets"]:
            params = copy.deepcopy(parent_params)
            params["threshold_value"] = min(255, max(0, parent_params["threshold_value"] + offset))
            configuration_id = f"t{params['threshold_value']:03d}_o{params['morph_iterations']}_c{params['close_iterations']}"
            if configuration_id not in resolved:
                resolved[configuration_id] = {"configuration_id": configuration_id, "method": "threshold", "params": params, "parents": []}
            _require(resolved[configuration_id]["params"] == params, "configuration ID collision after parameter resolution")
            if parent_id not in resolved[configuration_id]["parents"]:
                resolved[configuration_id]["parents"].append(parent_id)
    result = [resolved[key] for key in sorted(resolved)]
    _require(0 < len(result) <= rule["maximum_candidates"], "refinement exceeds the registered candidate budget")
    _require(len(result) * 12 * rule["frames_per_video"] <= rule["maximum_frame_evaluations"],
             "refinement exceeds the registered frame-evaluation budget")
    return result


def load_refinement_candidates(
    coarse_manifest: Path, derived_plan_path: Path, plan: dict,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate a completed coarse selection and resolve its exact registered refinement.

    Original plan, manifests and artifacts remain immutable. The derived plan
    must equal the deterministic reconstruction: candidates sorted by ID and
    parent IDs retained in their original coarse-ranking order.
    Its independent verification is located by SHA256 among ``verification*.json``
    files beside the derived plan; no source or pixel file is opened.
    """
    coarse_candidates = expand_coarse_candidates(plan)
    coarse_by_id = {candidate["configuration_id"]: candidate for candidate in coarse_candidates}
    _require(len(coarse_candidates) >= 5, "coarse search must contain at least five candidates")
    _require(tuple(map(str, plan["protocol"]["train_ids"])) == _TRAIN, "refinement requires the registered 12 training videos")
    _require(plan["sampling"]["coarse_frames_per_video"] == 12 and plan["sampling"]["master_frames_per_video"] == 48,
             "refinement requires the registered nested 12/48-frame sample")
    rule = _rule(plan)
    inputs = _Inputs()
    coarse_path = inputs.verify(coarse_manifest)
    derived_path = inputs.verify(derived_plan_path)
    coarse, derived = inputs.read(coarse_path), inputs.read(derived_path)
    _require(isinstance(coarse, dict) and isinstance(derived, dict), "manifests/plans must be JSON mappings")
    plan_hash = config_hash(plan, 64)
    summary = coarse.get("summary", {})
    _require(coarse.get("status") == "complete" and coarse.get("git_dirty") is False
             and summary.get("mode") == "coarse" and summary.get("complete") is True
             and summary.get("selection_allowed") is True, "refinement requires a complete coarse batch, not a benchmark or partial run")
    _require(coarse.get("config", {}).get("plan") == plan and summary.get("plan_hash") == plan_hash,
             "coarse batch belongs to another original plan")
    _require(coarse.get("config_hash") == config_hash(coarse["config"]), "coarse resolved-config hash mismatch")
    capture, verification = coarse.get("provenance_capture", {}), coarse.get("provenance_verification", {})
    _require(capture.get("mode") == "shared_batch" and verification.get("status") == "verified"
             and verification.get("scope") == "batch_end_before_ranking"
             and verification.get("snapshot_sha256") == capture.get("snapshot_sha256"), "coarse provenance lacks a verified shared snapshot")
    _require(derived.get("coarse_manifest_sha256") == inputs.reference(coarse_path)["sha256"]
             and inputs.path(derived["coarse_manifest"]) == coarse_path, "derived plan points to a different or changed coarse manifest")
    sample_hash = summary.get("sample_hash")
    _require(isinstance(sample_hash, str) and len(sample_hash) == 64, "invalid sample identity")
    sample_ref = coarse["config"]["input"]
    sample_path = inputs.verify(sample_ref["sample_manifest_path"], sample_ref["sample_manifest_sha256"])
    sample = inputs.read(sample_path)
    _require(sample_ref["sample_hash"] == sample_hash == sample["sample_hash"] and sample["plan_sha256"] == plan_hash,
             "coarse sample or plan identity differs")
    _require(tuple(map(str, sample["video_ids"])) == _TRAIN, "sample video universe differs")
    planned_pairs = []
    for video in _TRAIN:
        selection = sample["selections"][video]
        for mode, count in (("coarse", 12), ("master", 48)):
            indices = selection[mode]
            _require(isinstance(indices, list) and len(indices) == len(set(indices)) == count
                     and all(type(index) is int and index >= 0 for index in indices)
                     and indices == sorted(indices), "sample indices are missing, repeated or unordered")
        _require(set(selection["coarse"]) <= set(selection["master"]), "coarse frames must be nested within master sample")
        planned_pairs.extend([[video, index] for index in selection["coarse"]])
    files = inputs.artifacts(coarse, coarse_path)
    needed = {"planned_candidates.json", "planned_frames.json", "ranking.csv", "shortlist.json", "candidate_metrics.csv"}
    needed.update(f"candidate_{index:03d}.json" for index in range(1, len(coarse_candidates) + 1))
    _require(needed <= set(files), "coarse batch lacks hashed selection artifacts")
    planned = inputs.read(files["planned_candidates.json"])
    _require(len(planned) == len(coarse_candidates) and len({row["configuration_id"] for row in planned}) == len(planned)
             and {row["configuration_id"]: row for row in planned} == coarse_by_id, "coarse candidate universe differs from original grid")
    _require(inputs.read(files["planned_frames.json"]) == planned_pairs, "coarse frame plan differs from sample metadata")
    expected_pairs = {(vid, frame) for vid, frame in planned_pairs}
    records = coarse.get("candidate_manifests", [])
    _require(len(records) == len(coarse_candidates) and len({row["path"] for row in records}) == len(records), "missing or duplicate coarse candidate manifests")
    summaries = []
    seen: set[str] = set()
    for index, reference in enumerate(records, 1):
        child_path = inputs.verify(reference["path"], reference["sha256"])
        child = inputs.read(child_path)
        config = child.get("config", {})
        identifier = config.get("configuration_id")
        _require(identifier in coarse_by_id and identifier not in seen, "duplicate or unexpected coarse candidate")
        seen.add(identifier)
        _require(child.get("status") == "complete" and child.get("git_dirty") is False
                 and child.get("source_hash") == coarse.get("source_hash") and child.get("git_sha") == coarse.get("git_sha"),
                 "coarse candidate is incomplete or belongs to different code")
        _require(child.get("provenance_capture") == capture, "coarse candidate snapshot differs from batch")
        _require(child.get("config_hash") == config_hash(config), "candidate resolved-config hash mismatch")
        expected = coarse_by_id[identifier]
        _require(config.get("method") == "threshold" and config.get("params") == expected["params"]
                 and config.get("evaluation") == expected["evaluation"], "candidate parameters/evaluation differ from original grid")
        provenance = config.get("provenance", {})
        _require(provenance.get("search_plan_hash") == plan_hash and provenance.get("sample_hash") == sample_hash
                 and provenance.get("batch_id") == coarse["run_id"] and provenance.get("sample_mode") == "coarse",
                 "candidate plan/sample provenance differs")
        child_files = inputs.artifacts(child, child_path)
        _require({"summary.json", "frame_metrics.csv", "video_summary.csv", "detections.csv"} <= set(child_files), "missing candidate artifacts")
        candidate_summary = inputs.read(child_files["summary.json"])
        _require(candidate_summary == child.get("summary") == inputs.read(files[f"candidate_{index:03d}.json"]), "candidate summary copies differ")
        _require(candidate_summary.get("configuration_id") == identifier and candidate_summary.get("mode") == "coarse"
                 and candidate_summary.get("plan_hash") == plan_hash and candidate_summary.get("sample_hash") == sample_hash,
                 "candidate summary belongs to another plan/sample")
        frames = inputs.read(child_files["frame_metrics.csv"])
        frame_pairs = [(row["video_id"], int(row["frame"])) for row in frames]
        _require(len(frame_pairs) == len(set(frame_pairs)) == len(expected_pairs) and set(frame_pairs) == expected_pairs,
                 "coarse candidate has incomplete, extra or duplicate frames")
        _require(all(row["configuration_id"] == identifier and row["evaluation_protocol_id"] == _PROTOCOL
                     and row["sample_hash"] == sample_hash and row["annotated"] == "True" for row in frames),
                 "coarse frame metadata or annotation state differs")
        summaries.append(candidate_summary)
    _require(summary.get("completed_candidates") == len(coarse_candidates) and summary.get("frames_per_candidate") == len(expected_pairs)
             and summary.get("frame_evaluations") == len(coarse_candidates) * len(expected_pairs), "coarse batch completeness counts differ")
    ranked = rank_candidates(summaries, list(coarse_by_id))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    _csv_equals(inputs.read(files["candidate_metrics.csv"]), summaries, "candidate metrics CSV")
    _csv_equals(inputs.read(files["ranking.csv"]), ranked, "ranking CSV")
    _require(inputs.read(files["shortlist.json"]) == ranked[:5], "coarse shortlist is not the complete top five")
    parent_ids = [row["configuration_id"] for row in ranked[:5]]
    verification_paths = []
    for path in sorted(derived_path.parent.glob("verification*.json")):
        path = inputs.verify(path)
        if inputs.reference(path)["sha256"] == derived.get("verification_sha256"):
            verification_paths.append(path)
    _require(len(verification_paths) == 1, "derived plan must identify one existing independent verification by SHA256")
    verification_path = verification_paths[0]
    verification_record = inputs.read(verification_path)
    _require(verification_record.get("status") == "passed" and verification_record.get("ranking_complete_match") is True
             and verification_record.get("batch_manifest_sha256") == inputs.reference(coarse_path)["sha256"]
             and inputs.path(verification_record["batch_manifest"]) == coarse_path
             and verification_record.get("plan_hash") == plan_hash and verification_record.get("sample_hash") == sample_hash
             and verification_record.get("independent_top5") == parent_ids, "independent verification does not certify this coarse selection")
    resolved = _expand(parent_ids, coarse_by_id, rule)
    expected_derived = {
        "status": "planned_not_executed", "kind": "deterministic_instantiation_of_registered_refinement",
        "coarse_manifest": str(coarse_path), "coarse_manifest_sha256": inputs.reference(coarse_path)["sha256"],
        "verification_sha256": inputs.reference(verification_path)["sha256"], "plan_hash": plan_hash,
        "sample_hash": sample_hash, "rule": rule, "candidate_count": len(resolved),
        "frames_per_video": rule["frames_per_video"], "videos": plan["protocol"]["train_ids"],
        "frame_evaluations": len(resolved) * len(_TRAIN) * rule["frames_per_video"], "candidates": resolved,
    }
    _require(canonical_json(derived) == canonical_json(expected_derived), "derived refinement plan differs from deterministic reconstruction")
    references = {"coarse_manifest": inputs.reference(coarse_path), "derived_plan": inputs.reference(derived_path),
                  "coarse_verification": inputs.reference(verification_path), "sample_manifest": inputs.reference(sample_path)}
    provenance = {**references, "plan_hash": plan_hash, "sample_hash": sample_hash,
                  "search_plan_id": plan["plan_id"], "parent_candidate_ids": parent_ids,
                  "candidate_count": len(resolved), "frames_per_video": rule["frames_per_video"],
                  "frame_evaluations": expected_derived["frame_evaluations"],
                  "candidate_expansion_sha256": config_hash(resolved, 64),
                  "validated_input_count": len(inputs.records),
                  "validated_input_hashes_sha256": config_hash(sorted((key, row["sha256"]) for key, row in inputs.records.items()), 64),
                  "interpretation": "training_refinement_not_generalization_estimate",
                  "requires_new_cost_projection_before_execution": True}
    candidates = [{"configuration_id": row["configuration_id"], "method": row["method"],
                   "params": copy.deepcopy(row["params"]), "evaluation": copy.deepcopy(plan["evaluation"]),
                   "run": {"split": "train", "seed": plan["run"]["seed"], "save_video": False},
                   "provenance": {"search_plan_id": plan["plan_id"], "refinement_parent_ids": list(row["parents"]),
                                  "derived_plan_sha256": references["derived_plan"]["sha256"],
                                  "coarse_manifest_sha256": references["coarse_manifest"]["sha256"]}}
                  for row in resolved]
    return candidates, provenance
