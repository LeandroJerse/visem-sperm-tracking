"""Authenticated, one-axis local refinement of five static detector families.

The immutable comparison supplies ten parents. T218 is authenticated historical
evidence, never an executed candidate or a member of this refinement ranking.
The evaluation/export kernel preserves the comparison contract while recording
explicit refinement stages. Only a complete run can release training finalists.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import inspect
import itertools
import json
import math
import random
import subprocess
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT, resolve_from_repository
from src.detection.io import CSV_FIELDS, detection_to_row
from src.detection.registry import DETECTORS, build_detector, scientific_algorithm_id
from src.evaluation.detection import DetectionEvaluator
from src.experiments import classical_detection_comparison as comparison
from src.experiments.config import canonical_json, config_hash, load_config
from src.experiments.detection_sample import TRAIN_IDS, TrainingSample, load_sample
from src.experiments.detection_search import _evaluation, _selection, rank_candidates, summarize_candidate
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot, _git_dirty, _source_hash

DEFAULT_PLAN = "configs/detection/comparison/classical_refinement_v1.yaml"
SEARCH_SHA256 = "8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0"
SEARCH_QA_SHA256 = "c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792"
COMPARISON_PLAN_HASH = "a86c8a68180e89802150a2cb3d354a5dc9657e64270d820d9fb7269f64a6dbf5"
FAMILIES = tuple(name for name in comparison.FAMILIES if name != "threshold")
PROTOCOL = comparison.PROTOCOL
NEIGHBORHOOD = {
    "otsu": [("morph_iterations", 1, 0, 2, False), ("close_iterations", 1, 0, 3, False)],
    "adaptive_threshold": [("adaptive_block", 8, 3, 127, True), ("adaptive_c", 2, None, None, False), ("morph_iterations", 1, 0, 2, False)],
    "hybrid_threshold": [("clip_limit", 0.5, 0.5, 4, False), ("background_kernel", 8, 3, 63, True), ("open_iterations", 1, 0, 2, False)],
    "blob": [("min_threshold", 20, 0, 245, False)],
    "watershed": [("blur", 2, 1, 7, True), ("dist_ratio", 0.1, 0.1, 0.9, False)],
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _same(left: Any, right: Any) -> bool:
    """JSON equality keeps booleans distinct from integer 0/1."""
    return canonical_json(left) == canonical_json(right)


def _counts(record: dict, expected: dict[str, int]) -> bool:
    return all(type(record.get(key)) is int and record[key] == value for key, value in expected.items())


def read_json(path: Path) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject(value):
        raise ValueError(f"non-finite JSON number: {value}")
    def finite_float(value):
        result = float(value)
        _require(math.isfinite(result), "non-finite JSON number")
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject, parse_float=finite_float)


def load_plan(path: Path) -> dict:
    """Reject duplicate YAML keys and types outside the JSON contract."""
    class StrictLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            _require(type(key) is str and key not in result, "duplicate or non-string YAML key")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    plan = yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    def json_types(value):
        if type(value) is dict:
            for item in value.values():
                json_types(item)
        elif type(value) is list:
            for item in value:
                json_types(item)
        else:
            _require(value is None or type(value) in (str, int, float, bool), "unsupported YAML value type")
            _require(type(value) is not float or math.isfinite(value), "non-finite YAML value")
    json_types(plan)
    validate_plan(plan)
    return plan


def _safe_path(value: Any, *, parent: Path | None = None) -> Path:
    _require(type(value) is str and bool(value) and "\x00" not in value, "path must be a nonempty string")
    path = resolve_from_repository(value).resolve()
    _require(path.is_relative_to((parent or REPOSITORY_ROOT).resolve()), "path escapes its allowed directory")
    return path


def _digest(value: Any) -> None:
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "invalid SHA256")


def _reference(value: Any, *, canonical: bool = False) -> None:
    key = "canonical_sha256" if canonical else "sha256"
    _require(type(value) is dict and set(value) == {"path", key}, "reference requires exactly path and digest")
    _safe_path(value["path"])
    _digest(value[key])


def _pin(path: Path, expected: str, files: dict[str, str] | None = None) -> str:
    _digest(expected)
    actual = sha256_file(path)
    _require(actual == expected, f"SHA256 mismatch: {path}")
    if files is not None:
        previous = files.setdefault(str(path.resolve()), expected)
        _require(previous == expected, "conflicting hashes for one input path")
    return actual


def _artifacts(manifest: dict, directory: Path, files: dict[str, str]) -> dict[str, Path]:
    artifacts, hashes = manifest.get("artifacts"), manifest.get("artifact_hashes")
    _require(type(artifacts) is dict and bool(artifacts) and type(hashes) is dict and set(artifacts) == set(hashes), "artifacts require exact hash coverage")
    result = {}
    for key, value in artifacts.items():
        path = _safe_path(value, parent=directory)
        _require(path.parent == directory.resolve() and path.name != "manifest.json" and path.name not in result, "invalid or repeated artifact path")
        _pin(path, hashes[key], files)
        result[path.name] = path
    return result


def validate_plan(plan: dict) -> None:
    expected_keys = {"plan_id", "kind", "parents", "input", "sampling", "train_ids", "run", "evaluation", "selection", "budget", "neighborhood", "expected_candidates", "expected_proposals", "expected_valid_proposals", "expected_by_family"}
    _require(type(plan) is dict and set(plan) == expected_keys, "unknown or missing refinement plan fields")
    _require(plan["kind"] == "static_classical_detection_refinement_v1" and plan["plan_id"] == "classical_detection_refinement_v1_20260911", "unsupported refinement contract")
    _evaluation(plan["evaluation"])
    _selection(plan["selection"])
    _require(_same(plan["run"], {"split": "train", "seed": 42, "opencv_threads": 1, "save_video": False}), "refinement requires exact train/seed/thread controls")
    _require(type(plan["train_ids"]) is list and all(type(v) in (int, str) for v in plan["train_ids"]) and tuple(map(str, plan["train_ids"])) == TRAIN_IDS, "only the exact twelve training videos are allowed")
    _require(_same(plan["sampling"], {"smoke_mode": "benchmark", "refinement_mode": "master", "smoke_frames_per_video": 1, "refinement_frames_per_video": 48}), "only the registered benchmark/master subsets are allowed")
    _require(_same(plan["budget"], {"wall_seconds_limit": None, "max_rss_mb": 2048, "max_batch_artifact_mb": 2048, "max_predictions_per_frame": 307200, "on_failure": "stop_without_selection_preserve_partial_artifacts"}), "resource guards must match the registered refinement contract")
    selection = plan["selection"]
    _require(set(selection) == {"primary", "tie_breakers", "comparisons_require_all_candidates_and_all_planned_frames", "timing_used_for_ranking", "finalists_per_family", "expected_finalists", "historical_threshold_reference_reexecuted", "promotion_allowed", "validation_released", "interpretation", "comparability_limit"}, "unknown or missing selection fields")
    _require(type(selection.get("finalists_per_family")) is int and selection["finalists_per_family"] == 2 and type(selection.get("expected_finalists")) is int and selection["expected_finalists"] == 10 and all(selection.get(key) is False for key in ("historical_threshold_reference_reexecuted", "promotion_allowed", "validation_released")), "only ten training finalists, with T218 historical and validation blocked")
    expected_axes = [{"family": family, "axes": [dict(zip(("parameter", "step", "min", "max", "odd"), axis)) for axis in NEIGHBORHOOD[family]]} for family in FAMILIES]
    _require(_same(plan["neighborhood"], expected_axes), "neighborhood must retain the prospective one-axis steps and discard limits")
    _require(_same({k: plan[k] for k in ("expected_candidates", "expected_proposals", "expected_valid_proposals", "expected_by_family")}, {"expected_candidates": 45, "expected_proposals": 54, "expected_valid_proposals": 51, "expected_by_family": dict(zip(FAMILIES, (8, 13, 11, 6, 7)))}), "registered proposal/candidate counts differ")
    parents = plan["parents"]
    _require(type(parents) is dict and set(parents) == {"search_manifest", "search_qa", "comparison_plan", "finalists"}, "declare the four parent references")
    for key, value in parents.items():
        _reference(value, canonical=key == "comparison_plan")
    _require(parents["search_manifest"]["sha256"] == SEARCH_SHA256 and parents["search_qa"]["sha256"] == SEARCH_QA_SHA256 and parents["comparison_plan"]["canonical_sha256"] == COMPARISON_PLAN_HASH, "unapproved parent search or QA identity")
    base = load_config(_safe_path(parents["comparison_plan"]["path"]))
    _require(config_hash(base, 64) == COMPARISON_PLAN_HASH, "comparison plan changed")
    _require(_same(plan["input"], base["input"]) and _same(plan["evaluation"], base["evaluation"]), "cache, source sample or evaluation cannot change during refinement")


def _source_inventory(manifest: dict) -> dict[str, str]:
    """Reconstruct the clean historical worktree fingerprint; new files may exist."""
    revision = manifest.get("git_sha")
    _require(type(revision) is str and 7 <= len(revision) <= 40 and all(c in "0123456789abcdef" for c in revision), "invalid historical Git revision")
    def git(*arguments):
        result = subprocess.run(["git", *arguments], cwd=REPOSITORY_ROOT, capture_output=True, check=True, timeout=30)
        return result.stdout
    paths = git("ls-tree", "-r", "--name-only", revision).decode("utf-8").splitlines()
    paths = [name for name in paths if (name.split("/", 1)[0] in {"src", "script", "configs"} and Path(name).suffix.lower() in {".py", ".yaml", ".yml"} and "__pycache__" not in Path(name).parts) or name in {"pyproject.toml", "requirements.txt", "requirements-core.lock"}]
    _require(bool(paths), "historical source inventory is empty")
    aggregate, inventory = hashlib.sha256(), {}
    for name in sorted(paths, key=str.lower):
        path = _safe_path(name)
        # Restrict the current bytes to the historical Git inventory. Matching
        # the pinned aggregate authenticates every old file without guessing
        # whether checkout filters would reproduce its historical line endings.
        content = path.read_bytes()
        relative = name.encode("utf-8")
        aggregate.update(len(relative).to_bytes(4, "big")); aggregate.update(relative); aggregate.update(content)
        digest = hashlib.sha256(content).hexdigest()
        _pin(path, digest)
        inventory[str(path)] = digest
    _require(aggregate.hexdigest() == manifest.get("source_hash"), "historical source inventory does not reproduce the recorded aggregate hash")
    return inventory


def load_parents(plan: dict) -> dict:
    """Authenticate prior QA and bytes, without repeating its numerical audit."""
    validate_plan(plan)
    references, files = plan["parents"], {}
    paths = {key: _safe_path(value["path"]) for key, value in references.items()}
    for key in ("search_manifest", "search_qa", "finalists"):
        _pin(paths[key], references[key]["sha256"], files)
    base = load_config(paths["comparison_plan"])
    _pin(paths["comparison_plan"], sha256_file(paths["comparison_plan"]), files)
    search, qa = read_json(paths["search_manifest"]), read_json(paths["search_qa"])
    _require(type(search) is dict and search.get("status") == "complete" and search.get("stage") == "search" and search.get("git_dirty") is False and _same(search.get("config", {}).get("plan"), base), "parent search is incomplete or belongs to another protocol")
    summary = search.get("summary", {})
    _require(summary.get("complete") is True and type(summary.get("completed_candidates")) is int and summary["completed_candidates"] == 43 and summary.get("frames_per_candidate") == 576 and summary.get("frame_evaluations") == 24768 and summary.get("validation_released") is False, "parent search counts/scope differ")
    _require(type(qa) is dict and qa.get("status") == "passed" and qa.get("mode") == "search" and _safe_path(qa.get("manifest")) == paths["search_manifest"] and qa.get("manifest_sha256") == references["search_manifest"]["sha256"] and qa.get("plan_hash") == COMPARISON_PLAN_HASH and qa.get("candidates") == 43 and qa.get("frames_per_candidate") == 576 and qa.get("historical_t218_parity", {}).get("status") == "passed", "parent QA does not authenticate the complete approved search")
    capture = search.get("provenance_capture", {})
    verification = search.get("provenance_verification", {})
    _require(verification.get("status") == "verified" and verification.get("snapshot_sha256") == capture.get("snapshot_sha256") and search.get("config_hash") == config_hash(search["config"]), "parent provenance/configuration certification differs")
    artifacts = _artifacts(search, paths["search_manifest"].parent, files)
    _require(artifacts.get("family_finalists.json") == paths["finalists"], "finalists are not the authenticated parent artifact")
    expected = {item["configuration_id"]: item for item in comparison.expand_candidates(base)}
    planned = read_json(artifacts["planned_candidates.json"])
    _require(type(planned) is list and len(planned) == 43 and _same({item["configuration_id"]: item for item in planned}, expected), "parent configuration universe differs")
    records = search.get("candidate_manifests")
    _require(type(records) is list and len(records) == 43, "parent requires all43 candidate manifests")
    children, summaries = {}, []
    for record in records:
        _reference(record)
        path = _safe_path(record["path"], parent=REPOSITORY_ROOT / "data/tests/detection")
        _pin(path, record["sha256"], files)
        child = read_json(path)
        config = child.get("config", {})
        identifier = config.get("configuration_id")
        _require(identifier in expected and identifier not in children, "duplicate/unexpected parent candidate")
        _require(child.get("status") == "complete" and child.get("stage") == "search" and child.get("git_dirty") is False and child.get("git_sha") == search["git_sha"] and child.get("source_hash") == search["source_hash"] and _same(child.get("provenance_capture"), capture) and child.get("config_hash") == config_hash(config), "parent candidate provenance differs")
        wanted = copy.deepcopy(expected[identifier]); wanted["run"]["stage"] = "search"
        _require(set(config) == set(wanted) | {"provenance"} and all(_same(config[key], value) for key, value in wanted.items()), "parent candidate parameters or fields differ")
        child_files = _artifacts(child, path.parent, files)
        _require(set(child_files) == {"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"}, "parent child artifact schema differs")
        child_summary = read_json(child_files["summary.json"])
        _require(_same(child_summary, child.get("summary")) and child_summary.get("complete") is True and child_summary.get("frames_total") == 576, "parent summary is incomplete")
        children[identifier] = {**copy.deepcopy(expected[identifier]), "parent_manifest": {"path": str(path), "sha256": record["sha256"]}, "parent_source_hash": child["source_hash"], "parent_git_sha": child["git_sha"]}
        summaries.append(child_summary)
    ranked = rank_candidates(summaries, list(expected))
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    finalists = [row for family in comparison.FAMILIES for row in [item for item in ranked if item["family"] == family][:2]]
    _require(_same(read_json(paths["finalists"]), finalists) and qa.get("family_finalist_ids") == [row["configuration_id"] for row in finalists], "parent family finalists differ from authenticated complete ranking")
    parents = [children[row["configuration_id"]] for row in finalists if row["family"] != "threshold"]
    reference = {**children["t218_o0_c2_reference_v1"], "reexecuted": False, "interpretation": "historical_development_reference_not_ranked"}
    source_files = _source_inventory(search)
    files.update(source_files)
    return {"parents": parents, "historical_reference": reference, "authentication": {"search_manifest": {"path": str(paths["search_manifest"]), "sha256": references["search_manifest"]["sha256"]}, "search_qa": {"path": str(paths["search_qa"]), "sha256": references["search_qa"]["sha256"]}, "authenticated_files": files, "historical_source_files": source_files, "historical_source_hash": search["source_hash"], "historical_git_sha": search["git_sha"], "numerical_parent_qa_repeated": False}}


def verify_parent_inputs(bundle: dict) -> None:
    for name, digest in bundle["authentication"]["authenticated_files"].items():
        _pin(_safe_path(name), digest)


def _parameters(parent: dict) -> None:
    family, method, params = parent.get("family"), parent.get("method"), parent.get("params")
    _require(family in FAMILIES and method == comparison.FAMILIES[family] and type(params) is dict, "invalid refinement parent family")
    required = set(inspect.signature(DETECTORS[method].__init__).parameters) - {"self"}
    _require(set(params) == required and scientific_algorithm_id(method, params=params) == family, "all and only the original constructor parameters must be explicit")
    for name, value in params.items():
        _require(type(value) is bool if name in {"adaptive", "invert", "dark", "dark_objects"} else value is None or type(value) in (int, float), "unsupported detector parameter type")
        if type(value) in (int, float):
            _require(math.isfinite(value), "non-finite detector parameter")
        if name in {"blur", "morph_kernel", "adaptive_block", "background_kernel"}:
            _require(type(value) is int and value > 0 and value % 2 == 1, "odd kernels cannot be silently adjusted")
    _require(params.get("min_area") == 3 and params.get("max_area") == 300, "area range changed")


def expand_candidates(plan: dict, parents: list[dict]) -> list[dict]:
    """Resolve Decimal neighbors, discard invalid proposals, merge all lineages."""
    validate_plan(plan)
    _require(type(parents) is list and len(parents) == 10 and len({p.get("configuration_id") for p in parents}) == 10, "exactly ten unique parents are required")
    for parent in parents:
        _parameters(parent)
    _require([p["family"] for p in parents] == [family for family in FAMILIES for _ in range(2)], "parent order/family counts differ")
    result, proposals, valid = [], 0, 0
    for group in plan["neighborhood"]:
        family, signatures, family_candidates = group["family"], {}, []
        for parent in [item for item in parents if item["family"] == family]:
            options = [(None, 0, copy.deepcopy(parent["params"]))]
            for axis in group["axes"]:
                name, step = axis["parameter"], Decimal(str(axis["step"]))
                for direction in (-1, 1):
                    value = Decimal(str(parent["params"][name])) + step * direction
                    delta = step * direction
                    proposals += 1
                    if (axis["min"] is not None and value < Decimal(str(axis["min"]))) or (axis["max"] is not None and value > Decimal(str(axis["max"]))):
                        continue
                    integer = name not in {"clip_limit", "dist_ratio"}
                    if integer:
                        _require(value == value.to_integral_value(), "integer parameter gained a fractional step")
                    # Keep mathematically integral continuous values in the
                    # parent's spelling so an existing parent deduplicates.
                    converted = int(value) if integer or value == value.to_integral_value() else float(value)
                    _require(not axis["odd"] or type(converted) is int and converted % 2 == 1, "proposed kernel must already be odd")
                    changed = copy.deepcopy(parent["params"]); changed[name] = converted
                    options.append((name, int(delta) if integer else float(delta), changed))
            proposals += 1
            for axis, delta, params in options:
                valid += 1
                signature = canonical_json({"method": parent["method"], "params": params})
                lineage = {"parent_configuration_id": parent["configuration_id"], "axis": axis, "delta": delta}
                if signature in signatures:
                    signatures[signature]["refinement_lineage"].append(lineage)
                    continue
                candidate = {"configuration_id": f"{family}_refinement_v1_{len(family_candidates) + 1:03d}", "method": parent["method"], "family": family, "params": params, "evaluation": copy.deepcopy(plan["evaluation"]), "run": copy.deepcopy(plan["run"]), "refinement_lineage": [lineage]}
                signatures[signature] = candidate
                family_candidates.append(candidate)
        _require(len(family_candidates) == plan["expected_by_family"][family], "deduplicated family count differs")
        result.extend(family_candidates)
    _require(proposals == plan["expected_proposals"] and valid == plan["expected_valid_proposals"] and len(result) == plan["expected_candidates"], "resolved proposal counts differ")
    return result


def load_refinement_sample(plan: dict) -> TrainingSample:
    validate_plan(plan)
    inputs = plan["input"]
    sample_plan = load_config(_safe_path(inputs["sample_plan"]))
    _require(config_hash(sample_plan, 64) == inputs["sample_plan_canonical_sha256"], "sample plan changed")
    path = _safe_path(inputs["cache_manifest"])
    _pin(path, inputs["cache_manifest_sha256"])
    sample = load_sample(path.parent, sample_plan)
    _require(sample.sample_hash == inputs["sample_hash"], "sample identity differs")
    _pin(path, inputs["cache_manifest_sha256"])
    return sample


def _sample_mode(mode: str) -> str:
    _require(mode in {"refinement_smoke", "refinement"}, "only refinement_smoke/train and refinement/train are permitted")
    return "benchmark" if mode == "refinement_smoke" else "master"


def _pairs(sample: Any, mode: str) -> list[tuple[str, int]]:
    return [(str(video), int(frame)) for video in sample.video_ids for frame in sample.indices(_sample_mode(mode), video)]


_sample_reference = comparison._sample_reference
_check_budget = comparison._check_budget
_bytes = comparison._bytes
verify_cache_unchanged = comparison.verify_cache_unchanged


def run_candidate(candidate: dict, sample: Any, plan: dict, mode: str, batch: RunContext,
                  snapshot: RunSnapshot, monitor: ResourceMonitor, output_root: Path | None) -> dict:
    """Comparison kernel with explicit refinement modes and retained lineage.

    Pixel access, evaluator, raw export and aggregation match the immutable
    comparison kernel. Repeated parent configurations certify that parity.
    """
    config = copy.deepcopy(candidate)
    config["run"]["stage"] = mode
    config["provenance"] = {"plan_id": plan["plan_id"], "plan_hash": config_hash(plan, 64),
                             **_sample_reference(sample), "sample_mode": _sample_mode(mode),
                             "batch_manifest_path": str(batch.path / "manifest.json")}
    context = RunContext.create(module="detection", method=candidate["method"], algorithm=candidate["family"],
                                stage=mode, seed=plan["run"]["seed"], config=config, output_root=output_root,
                                provenance_snapshot=snapshot, snapshot_origin_batch_manifest=batch.path / "manifest.json")
    evaluator = DetectionEvaluator(center_gate_px=10, class_policy="individuals_ignore_clusters", sensitivity_gates_px=[15, 20])
    resources = ResourceMonitor()
    raw, observed, attempted, export_errors = [], [], set(), []
    artifacts = {"detections_csv": str(context.path / "detections.csv"),
                 "frame_metrics_csv": str(context.path / "frame_metrics.csv")}
    detector_seconds = evaluation_seconds = 0.0

    def export_observed(best_effort: bool = False) -> None:
        for key, rows, fields in (("detections_csv", raw, CSV_FIELDS), ("frame_metrics_csv", evaluator.frames, None)):
            if key in attempted:
                continue
            attempted.add(key)
            try:
                write_csv_exclusive(artifacts[key], rows, fields)
            except BaseException as exc:
                export_errors.append({"artifact": key, "error": str(exc), "error_type": type(exc).__name__})
                if not best_effort:
                    raise

    try:
        detector = build_detector(candidate["method"], params=candidate["params"])
        previous_video = None
        for video, frame, pixels, gt in sample.frames(_sample_mode(mode)):
            _check_budget(plan, monitor)
            if video != previous_video:
                detector.reset()
                previous_video = video
            began = time.perf_counter()
            detections = detector.detect(pixels)
            elapsed = time.perf_counter() - began
            detector_seconds += elapsed
            _require(len(detections) <= plan["budget"]["max_predictions_per_frame"],
                     f"prediction ceiling exceeded at {video}/{frame}: observed={len(detections)}, "
                     f"limit={plan['budget']['max_predictions_per_frame']}; no truncation permitted")
            began = time.perf_counter()
            row = evaluator.add_frame(detections, gt, video_id=str(video), frame=frame,
                                      annotated=True, detection_ms=elapsed * 1000)
            evaluation_seconds += time.perf_counter() - began
            row.update(configuration_id=candidate["configuration_id"], family=candidate["family"],
                       evaluation_protocol_id=PROTOCOL, sample_hash=sample.sample_hash)
            raw.extend(detection_to_row(str(video), frame, "detection", item) for item in detections)
            raw.extend(detection_to_row(str(video), frame, "manual", item) for item in gt)
            observed.append((str(video), int(frame)))
            resources.sample()
        _require(observed == _pairs(sample, mode), "missing, duplicate, reordered or extra frames")
        video_rows = []
        aggregated = evaluator.by_video()
        for video in sample.video_ids:
            row = aggregated[str(video)]
            row.update(configuration_id=candidate["configuration_id"], family=candidate["family"],
                       evaluation_protocol_id=PROTOCOL, class_policy="individuals_ignore_clusters",
                       center_gate_px=10, sensitivity_gates_px=[15, 20], sample_hash=sample.sample_hash)
            video_rows.append(row)
        summary = summarize_candidate(video_rows, sample.video_ids,
                                      {str(video): len(sample.indices(_sample_mode(mode), video)) for video in sample.video_ids})
        export_started = time.perf_counter()
        export_observed()
        write_csv_exclusive(context.path / "video_summary.csv", video_rows)
        summary.update(mode=mode, family=candidate["family"], method=candidate["method"],
                       run_id=context.run_id, manifest_path=str(context.path / "manifest.json"),
                       plan_hash=config_hash(plan, 64), sample_hash=sample.sample_hash,
                       detector_seconds=detector_seconds, evaluation_seconds=evaluation_seconds,
                       export_seconds=time.perf_counter() - export_started, **resources.summary())
        write_json_exclusive(context.path / "summary.json", summary)
        artifacts.update(video_summary_csv=str(context.path / "video_summary.csv"), summary_json=str(context.path / "summary.json"))
        _check_budget(plan, monitor)
        context.complete(summary=summary, artifacts=artifacts,
                         artifact_hashes={key: sha256_file(value) for key, value in artifacts.items()})
        return summary
    except BaseException as exc:
        export_observed(best_effort=True)
        try:
            context.fail(exc, artifacts=artifacts, observed_frames=len(observed),
                         expected_frames=len(_pairs(sample, mode)), export_errors=export_errors)
        except BaseException as failure:
            exc.add_note(f"Failure manifest could not be written: {failure}")
        raise


def _iter_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        _require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), "CSV has missing/duplicate columns")
        for row in reader:
            _require(None not in row and all(value is not None for value in row.values()), "malformed CSV row")
            yield row


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(_iter_csv(path))


def check_parent_parity(candidate: dict, summary: dict, parents: list[dict], pairs: list[tuple[str, int]]) -> list[dict]:
    """Compare repeated parent outputs on exactly the current training frames."""
    parent_ids = [row["parent_configuration_id"] for row in candidate["refinement_lineage"] if row["axis"] is None]
    if not parent_ids:
        return []
    child_path = Path(summary["manifest_path"]).resolve()
    child = read_json(child_path)
    child_files = _artifacts(child, child_path.parent, {})
    allowed = set(pairs)
    excluded = {"configuration_id", "detection_ms"}
    records = []
    for identifier in parent_ids:
        parent = next(row for row in parents if row["configuration_id"] == identifier)
        _require(_same(parent["params"], candidate["params"]), "parent parity control parameters differ")
        path = _safe_path(parent["parent_manifest"]["path"])
        _pin(path, parent["parent_manifest"]["sha256"])
        original = read_json(path)
        original_files = _artifacts(original, path.parent, {})
        counts = {}
        for filename in ("detections.csv", "frame_metrics.csv"):
            current = _iter_csv(child_files[filename])
            previous = (row for row in _iter_csv(original_files[filename]) if (row["video_id"], int(row["frame"])) in allowed)
            count = 0
            for actual, expected in itertools.zip_longest(current, previous):
                _require(actual is not None and expected is not None, f"parent parity row count differs: {identifier}/{filename}")
                count += 1
                _require(set(actual) == set(expected), "parent parity CSV columns differ")
                for key in set(actual) - excluded:
                    if actual[key] == expected[key]:
                        continue
                    try:
                        left, right = float(actual[key]), float(expected[key])
                    except (TypeError, ValueError):
                        raise ValueError(f"parent parity differs: {identifier}/{filename}/{key}") from None
                    _require(math.isfinite(left) and math.isfinite(right) and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-9), f"parent parity differs: {identifier}/{filename}/{key}")
            counts[filename] = count
        records.append({"parent_configuration_id": identifier, "configuration_id": candidate["configuration_id"], "parent_manifest": parent["parent_manifest"], "status": "passed", "frames_compared": len(pairs), "rows_compared": counts, "excluded_fields": sorted(excluded), "absolute_tolerance": 1e-9, "relative_tolerance": 1e-12})
    return records


def check_smoke(path: Path, qa_path: Path, plan: dict, sample: Any, candidates: list[dict], bundle: dict) -> dict:
    path, qa_path = path.resolve(), qa_path.resolve()
    reference = {"path": str(path), "sha256": sha256_file(path)}
    qa_reference = {"path": str(qa_path), "sha256": sha256_file(qa_path)}
    manifest, qa = read_json(path), read_json(qa_path)
    summary = manifest.get("summary", {})
    _require(manifest.get("status") == "complete" and manifest.get("stage") == "refinement_smoke" and manifest.get("git_dirty") is False and summary.get("mode") == "refinement_smoke" and summary.get("complete") is True and summary.get("selection_allowed") is False, "refinement requires complete smoke without selection")
    _require(_same(manifest.get("config", {}).get("plan"), plan) and _same(manifest.get("config", {}).get("input"), _sample_reference(sample)) and summary.get("plan_hash") == config_hash(plan, 64) and summary.get("sample_hash") == sample.sample_hash, "smoke inputs or plan differ")
    _require(manifest.get("config_hash") == config_hash(manifest["config"]) and manifest.get("source_hash") == _source_hash(REPOSITORY_ROOT), "smoke belongs to different resolved configuration or code")
    capture, verification = manifest.get("provenance_capture", {}), manifest.get("provenance_verification", {})
    _require(verification.get("status") == "verified" and verification.get("snapshot_sha256") == capture.get("snapshot_sha256"), "smoke lacks final source verification")
    _require(type(qa) is dict and qa.get("status") == "passed" and qa.get("mode") == "refinement_smoke" and _safe_path(qa.get("manifest"), parent=path.parent) == path and qa.get("manifest_sha256") == reference["sha256"] and qa.get("plan_hash") == config_hash(plan, 64) and _counts(qa, {"candidates": len(candidates), "frames_per_candidate": 12, "frame_evaluations": len(candidates) * 12}), "independent smoke QA is missing, failed or incompatible")
    files = _artifacts(manifest, path.parent, {})
    expected = {item["configuration_id"]: item for item in candidates}
    planned = read_json(files["planned_candidates.json"])
    _require(type(planned) is list and len(planned) == len(expected) and _same({item["configuration_id"]: item for item in planned}, expected), "smoke planned candidates differ")
    pairs = _pairs(sample, "refinement_smoke")
    _require(_same(read_json(files["planned_frames.json"]), [list(pair) for pair in pairs]) and _counts(summary, {"completed_candidates": len(expected), "frames_per_candidate": len(pairs), "frame_evaluations": len(expected) * len(pairs)}), "smoke completeness differs")
    _require(_same(read_json(files["parents.json"]), bundle["parents"]) and _same(read_json(files["historical_reference.json"]), bundle["historical_reference"]) and _same(read_json(files["parent_authentication.json"]), bundle["authentication"]), "smoke parent lineage differs")
    records = manifest.get("candidate_manifests", [])
    _require(type(records) is list and len(records) == len(expected), "smoke child count differs")
    seen = set()
    for record in records:
        _reference(record)
        child_path = _safe_path(record["path"])
        _pin(child_path, record["sha256"])
        child = read_json(child_path)
        config, identifier = child.get("config", {}), child.get("config", {}).get("configuration_id")
        _require(identifier in expected and identifier not in seen, "unexpected/duplicate smoke child")
        seen.add(identifier)
        wanted = copy.deepcopy(expected[identifier]); wanted["run"]["stage"] = "refinement_smoke"
        _require(set(config) == set(wanted) | {"provenance"} and all(_same(config[key], value) for key, value in wanted.items()), "smoke child parameters or lineage differ")
        _require(child.get("status") == "complete" and child.get("stage") == "refinement_smoke" and child.get("git_dirty") is False and child.get("source_hash") == manifest["source_hash"] and child.get("git_sha") == manifest["git_sha"] and child.get("config_hash") == config_hash(config) and _same(child.get("provenance_capture"), capture), "smoke child provenance differs")
        child_files = _artifacts(child, child_path.parent, {})
        child_summary = child.get("summary", {})
        _require(child_summary.get("complete") is True and child_summary.get("mode") == "refinement_smoke" and child_summary.get("frames_total") == len(pairs) and _same(read_json(child_files["summary.json"]), child_summary), "incomplete smoke child summary")
        rows = _read_csv(child_files["frame_metrics.csv"])
        _require([(row["video_id"], int(row["frame"])) for row in rows] == pairs and all(row["configuration_id"] == identifier and row["evaluation_protocol_id"] == PROTOCOL and row["annotated"] == "True" for row in rows), "smoke child frames differ")
    _pin(path, reference["sha256"]); _pin(qa_path, qa_reference["sha256"])
    return {"smoke": reference, "smoke_qa": qa_reference}


def run_batch(plan: dict, sample: Any, mode: str, *, parents: dict, cache_validation_seconds: float,
              parent_validation_seconds: float, smoke_manifest: Path | None = None,
              smoke_qa: Path | None = None, output_root: Path | None = None) -> Path:
    candidates = expand_candidates(plan, parents["parents"])
    _sample_mode(mode)
    _require(_git_dirty(REPOSITORY_ROOT) is False, "commit code and protocol with clean Git before execution")
    _require(tuple(sample.video_ids) == TRAIN_IDS, "sample contains other videos")
    _require(type(cache_validation_seconds) in (int, float) and math.isfinite(cache_validation_seconds) and cache_validation_seconds >= 0 and type(parent_validation_seconds) in (int, float) and math.isfinite(parent_validation_seconds) and parent_validation_seconds >= 0, "authentication durations must be finite and nonnegative")
    for video in sample.video_ids:
        indices = sample.indices(_sample_mode(mode), video)
        _require(len(indices) == (1 if mode == "refinement_smoke" else 48) and list(indices) == sorted(set(indices)) and all(type(frame) is int and frame >= 0 for frame in indices), "sample indices differ from registered counts/order")
    provenance_input = {"smoke": None, "smoke_qa": None}
    if mode == "refinement":
        _require(smoke_manifest is not None and smoke_qa is not None, "complete smoke and independent smoke QA are required")
        provenance_input = check_smoke(smoke_manifest, smoke_qa, plan, sample, candidates, parents)
    else:
        _require(smoke_manifest is None and smoke_qa is None, "smoke cannot depend on another smoke")
    verify_parent_inputs(parents)
    cv2.setNumThreads(plan["run"]["opencv_threads"])
    np.random.seed(plan["run"]["seed"])
    random.Random(plan["run"]["seed"]).shuffle(candidates)
    started = time.perf_counter()
    monitor, snapshot = ResourceMonitor(), RunSnapshot.capture(REPOSITORY_ROOT)
    sample_reference = _sample_reference(sample)
    _require(sample_reference["sample_manifest_sha256"] == plan["input"]["cache_manifest_sha256"] and sample_reference["sample_hash"] == plan["input"]["sample_hash"], "sample is not pinned by this plan")
    config = {"configuration_id": plan["plan_id"] + "_batch", "plan": copy.deepcopy(plan), "input": sample_reference, "mode": mode, "provenance": provenance_input}
    batch = RunContext.create(module="detection", method="classical_refinement", algorithm="classical_refinement", stage=mode, seed=plan["run"]["seed"], config=config, output_root=output_root, provenance_snapshot=snapshot)
    summaries, parity, artifact_bytes = [], [], 0
    provenance = {"status": "not_performed", "scope": "batch_end_before_ranking"}
    try:
        for filename, value in (("planned_candidates.json", candidates), ("planned_frames.json", _pairs(sample, mode)), ("parents.json", parents["parents"]), ("historical_reference.json", parents["historical_reference"]), ("parent_authentication.json", parents["authentication"])):
            write_json_exclusive(batch.path / filename, value)
        loop_started = time.perf_counter()
        for index, candidate in enumerate(candidates, 1):
            _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
            summary = run_candidate(candidate, sample, plan, mode, batch, snapshot, monitor, output_root)
            summaries.append(summary)
            artifact_bytes += _bytes(Path(summary["manifest_path"]).parent)
            write_json_exclusive(batch.path / f"candidate_{index:03d}.json", summary)
            parity.extend(check_parent_parity(candidate, summary, parents["parents"], _pairs(sample, mode)))
            print(json.dumps({"mode": mode, "completed": index, "planned": len(candidates), "family": candidate["family"], "elapsed_seconds": round(time.perf_counter() - started, 2)}), flush=True)
        loop_seconds = time.perf_counter() - loop_started
        _require(len(parity) == 10 and {row["parent_configuration_id"] for row in parity} == {row["configuration_id"] for row in parents["parents"]}, "all ten parents require output parity before selection")
        write_json_exclusive(batch.path / "parent_parity.json", parity)
        _require(_sample_reference(sample) == sample_reference, "cache manifest changed during refinement")
        verify_cache_unchanged(sample)
        verify_parent_inputs(parents)
        for reference in provenance_input.values():
            if reference is not None:
                _pin(_safe_path(reference["path"]), reference["sha256"])
        try:
            provenance = snapshot.verify_current()
        except BaseException as exc:
            provenance = {"status": "failed", "scope": "batch_end_before_ranking", "error": str(exc)}
            raise
        # The same validator certifies complete summary coverage in smoke; its
        # ordering is never exported or used to select during that stage.
        ranked = rank_candidates(summaries, [item["configuration_id"] for item in candidates])
        _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
        write_csv_exclusive(batch.path / "candidate_metrics.csv", summaries)
        batch_summary = {"mode": mode, "complete": True, "plan_hash": config_hash(plan, 64), "sample_hash": sample.sample_hash, "completed_candidates": len(summaries), "frames_per_candidate": len(_pairs(sample, mode)), "frame_evaluations": len(summaries) * len(_pairs(sample, mode)), "cache_validation_seconds": cache_validation_seconds, "parent_validation_seconds": parent_validation_seconds, "candidate_loop_seconds": loop_seconds, "selection_allowed": mode == "refinement", "promotion_allowed": False, "validation_released": False, "historical_threshold_reference_reexecuted": False, "parent_parity_controls": len(parity), "wall_seconds_limit": None, "candidate_artifact_bytes": artifact_bytes, "interpretation": "training_finalists_not_promoted" if mode == "refinement" else "smoke_no_selection", **monitor.summary()}
        if mode == "refinement":
            for index, row in enumerate(ranked, 1):
                row["rank"] = index
            finalists = [row for family in FAMILIES for row in [item for item in ranked if item["family"] == family][:2]]
            _require(len(finalists) == 10 and all(row["family"] != "threshold" for row in ranked), "historical T218 cannot enter refinement ranking")
            write_csv_exclusive(batch.path / "ranking.csv", ranked)
            write_json_exclusive(batch.path / "family_finalists.json", finalists)
        _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
        files = {path.name: str(path) for path in sorted(batch.path.iterdir()) if path.is_file() and path.name != "manifest.json"}
        batch.complete(summary=batch_summary, artifacts=files, artifact_hashes={key: sha256_file(value) for key, value in files.items()}, provenance_verification=provenance, candidate_manifests=[{"path": row["manifest_path"], "sha256": sha256_file(row["manifest_path"])} for row in summaries])
    except BaseException as exc:
        try:
            batch.fail(exc, completed_candidates=len(summaries), selection_allowed=False, promotion_allowed=False, validation_released=False, historical_threshold_reference_reexecuted=False, provenance_verification=provenance)
        except BaseException as failure:
            exc.add_note(f"Batch failure manifest could not be written: {failure}")
        raise
    print(json.dumps({"batch_manifest": str(batch.path / "manifest.json"), **batch_summary}), flush=True)
    return batch.path / "manifest.json"
