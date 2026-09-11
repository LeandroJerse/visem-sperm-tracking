"""Prospective comparison of static classical detectors on one training cache.

This module never decodes videos or modifies the frozen threshold baseline.
The registered cache loader authenticates source and derived bytes; scoring
uses the shared v3 individuals/ignore-clusters evaluator. A complete search
selects two training finalists per searched family, never a promoted detector.
"""
from __future__ import annotations

import copy
import csv
import inspect
import json
import math
import random
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT, resolve_from_repository
from src.detection.io import CSV_FIELDS, detection_to_row
from src.detection.registry import DETECTORS, build_detector, scientific_algorithm_id
from src.evaluation.detection import DetectionEvaluator
from src.experiments.config import canonical_json, config_hash, load_config
from src.experiments.detection_sample import TRAIN_IDS, TrainingSample, load_sample
from src.experiments.detection_search import _evaluation, _selection, rank_candidates, summarize_candidate
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot, _git_dirty, _source_hash
from src.experiments.sweep import parameter_grid


ORIGINAL_PLAN = "configs/detection/comparison/classical_v1.yaml"
ORIGINAL_PLAN_HASH = "6dd487d03f4de19ee27983fc9c4308d7a6c5bfcd0f444bfc8c21290a9f85d43b"
DEFAULT_PLAN = "configs/detection/comparison/classical_v1_operational_v2.yaml"
FAMILIES = {"threshold": "threshold", "otsu": "threshold", "adaptive_threshold": "threshold",
            "hybrid_threshold": "hybrid_threshold", "blob": "blob", "watershed": "watershed"}
PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _positive(value: Any, label: str) -> None:
    _require(not isinstance(value, bool) and isinstance(value, (int, float))
             and math.isfinite(value) and value > 0, f"{label} must be finite and positive")


def validate_operational_revision(plan: dict) -> None:
    """Authenticate the parent and permit only the registered guard revision.

    The 640*480 ceiling is an operational allowance, not a proof that every
    detector can emit at most one center per pixel. RAM/storage remain guarded.
    """
    revision = plan.get("operational_revision")
    if revision is None:
        _require(plan.get("plan_id") == "classical_detection_comparison_v1_20260911",
                 "unknown plan identity without operational lineage")
        _require(plan.get("budget", {}).get("max_predictions_per_frame") == 2000,
                 "the original prediction ceiling is immutable; use operational v2")
        return
    _require(isinstance(revision, dict) and set(revision) == {
        "parent_plan_path", "parent_plan_canonical_sha256", "reason", "previous_max_predictions_per_frame",
        "failed_batch_manifest", "failed_candidate_manifest"}, "unknown operational revision metadata")
    _require(revision["parent_plan_path"] == ORIGINAL_PLAN
             and revision["parent_plan_canonical_sha256"] == ORIGINAL_PLAN_HASH,
             "operational revision must identify the immutable v1 parent")
    _require(revision["reason"] == "retry_prediction_guard_without_scientific_change"
             and revision["previous_max_predictions_per_frame"] == 2000, "unexpected operational revision reason or previous ceiling")
    _require(plan.get("plan_id") == "classical_detection_comparison_v1_operational_v2_20260911"
             and plan.get("budget", {}).get("max_predictions_per_frame") == 640 * 480,
             "operational v2 requires its own identity and registered 307200 prediction ceiling")
    parent = load_config(resolve_from_repository(ORIGINAL_PLAN))
    _require(config_hash(parent, 64) == ORIGINAL_PLAN_HASH, "original parent YAML changed")
    restored = copy.deepcopy(plan)
    restored.pop("operational_revision")
    restored["plan_id"] = parent["plan_id"]
    restored["budget"]["max_predictions_per_frame"] = 2000
    _require(canonical_json(restored) == canonical_json(parent),
             "operational revision changed scientific parameters, inputs, selection or another resource limit")
    for key in ("failed_batch_manifest", "failed_candidate_manifest"):
        reference = revision[key]
        _require(isinstance(reference, dict) and set(reference) == {"path", "sha256"}
                 and isinstance(reference["path"], str) and reference["path"].endswith("/manifest.json")
                 and isinstance(reference["sha256"], str) and len(reference["sha256"]) == 64
                 and all(char in "0123456789abcdef" for char in reference["sha256"]), "invalid failed-run lineage reference")


def expand_candidates(plan: dict) -> list[dict]:
    """Validate the declared experiment before reading any sample or results."""
    _require(plan.get("kind") == "static_classical_detection_comparison_v1", "unsupported comparison contract")
    validate_operational_revision(plan)
    _require(isinstance(plan.get("plan_id"), str) and bool(plan["plan_id"]), "missing plan ID")
    _evaluation(plan.get("evaluation"))
    _selection(plan.get("selection"))
    _require(plan["selection"].get("finalists_per_family") == 2
             and plan["selection"].get("promotion_allowed") is False
             and plan["selection"].get("validation_released") is False,
             "select two training finalists per searched family, without validation release or promotion")
    _require(tuple(map(str, plan.get("train_ids", []))) == TRAIN_IDS, "only the exact twelve training videos are allowed")
    _require(plan.get("sampling") == {"smoke_mode": "benchmark", "search_mode": "master",
                                      "smoke_frames_per_video": 1, "search_frames_per_video": 48},
             "only the registered 1/48 frame subsets are supported")
    _require(plan.get("run") == {"split": "train", "seed": 42, "opencv_threads": 1, "save_video": False},
             "comparison requires train, seed42, one OpenCV thread, no video export")
    budget = plan.get("budget", {})
    _require(budget.get("wall_seconds_limit") is None and "wall_seconds_limit" in budget,
             "this registered plan monitors time without a wall-clock cutoff")
    for key in ("max_rss_mb", "max_batch_artifact_mb", "max_predictions_per_frame"):
        _positive(budget.get(key), key)
    _require(type(budget["max_predictions_per_frame"]) is int, "prediction ceiling must be an integer")
    groups = plan.get("families", [])
    _require(isinstance(groups, list) and len(groups) == len(FAMILIES)
             and {item.get("family") for item in groups} == set(FAMILIES), "declare each of the six static families exactly once")
    candidates, signatures = [], set()
    for group in groups:
        family, method = group["family"], group.get("method")
        _require(method == FAMILIES[family], "family is bound to another detector implementation")
        fixed, grid = group.get("params"), group.get("search_space")
        _require(isinstance(fixed, dict) and isinstance(grid, dict) and not set(fixed) & set(grid), "fixed and varied parameters must be disjoint")
        _require(all(isinstance(values, list) and values for values in grid.values()), "search axes must be nonempty lists")
        combinations = list(parameter_grid(grid)) if grid else [{}]
        _require(group.get("expected_candidates") == len(combinations), "family candidate count differs from its registered grid")
        constructor = inspect.signature(DETECTORS[method].__init__).parameters
        keys = set(constructor) - {"self"}
        for index, varying in enumerate(combinations, 1):
            params = {**fixed, **varying}
            _require(set(params) == keys, f"{family} must resolve every constructor parameter explicitly")
            _require(scientific_algorithm_id(method, params=params) == family, "resolved parameters change the scientific family")
            _require(params.get("min_area") == 3 and params.get("max_area") == 300, "all declared area thresholds are fixed at 3..300")
            for key, value in params.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    _require(math.isfinite(value), "non-finite detector parameter")
                if key in {"blur", "morph_kernel", "adaptive_block", "background_kernel"}:
                    _require(type(value) is int and value > 0 and value % 2 == 1, "odd kernels must be explicit; implicit adjustment is forbidden")
            signature = canonical_json({"method": method, "params": params})
            _require(signature not in signatures, "duplicate resolved detector configuration")
            signatures.add(signature)
            identifier = "t218_o0_c2_reference_v1" if family == "threshold" else f"{family}_v1_{index:03d}"
            candidates.append({"configuration_id": identifier, "method": method, "family": family,
                               "params": copy.deepcopy(params), "evaluation": copy.deepcopy(plan["evaluation"]),
                               "run": copy.deepcopy(plan["run"])})
    reference = next(item for item in candidates if item["family"] == "threshold")
    expected = {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
                "min_area": 3, "max_area": 300, "threshold_value": 218, "morph_iterations": 0,
                "close_iterations": 2, "adaptive_block": 21, "adaptive_c": 5}
    _require(reference["params"] == expected
             and sum(item["family"] == "threshold" for item in candidates) == 1, "T218/o0/c2 is a fixed development reference")
    _require(len(candidates) == plan.get("expected_candidates"), "total candidate count differs")
    return candidates


def _pin(path: Path, expected: str) -> str:
    observed = sha256_file(path)
    _require(observed == expected, f"input SHA256 mismatch: {path}")
    return observed


def load_comparison_sample(plan: dict) -> TrainingSample:
    """Authenticate the existing cache with its unchanged original plan."""
    expand_candidates(plan)
    if "operational_revision" in plan:
        revision = plan["operational_revision"]
        failures = []
        for key in ("failed_batch_manifest", "failed_candidate_manifest"):
            reference = revision[key]
            path = resolve_from_repository(reference["path"])
            _require(path.is_relative_to(REPOSITORY_ROOT / "data/tests/detection"), "failed-run lineage must stay under detection experiments")
            _pin(path, reference["sha256"])
            failures.append(json.loads(path.read_text(encoding="utf-8")))
        batch, candidate = failures
        _require(batch.get("status") == candidate.get("status") == "failed"
                 and batch.get("selection_allowed") is False and batch.get("completed_candidates") == 36
                 and candidate.get("observed_frames") == 8
                 and candidate.get("config", {}).get("configuration_id") == "adaptive_threshold_v1_004"
                 and batch.get("git_sha") == candidate.get("git_sha") == "574038b"
                 and batch.get("error") == candidate.get("error") == "prediction ceiling exceeded at 30/781; no truncation permitted",
                 "lineage does not identify the preserved v1 operational failure")
    inputs = plan["input"]
    base_path = resolve_from_repository(inputs["sample_plan"])
    base = load_config(base_path)
    _require(config_hash(base, 64) == inputs["sample_plan_canonical_sha256"], "original sample plan changed")
    cache = resolve_from_repository(inputs["cache_manifest"]).parent
    _pin(cache / "manifest.json", inputs["cache_manifest_sha256"])
    sample = load_sample(cache, base)
    _require(sample.sample_hash == inputs["sample_hash"], "sample identity differs")
    _pin(cache / "manifest.json", inputs["cache_manifest_sha256"])
    return sample


def _sample_reference(sample: Any) -> dict:
    path = (Path(sample.cache_dir) / "manifest.json").resolve()
    return {"sample_manifest_path": str(path), "sample_manifest_sha256": sha256_file(path),
            "sample_hash": sample.sample_hash}


def verify_cache_unchanged(sample: Any) -> None:
    """Hash all consumed cache arrays/GT again before releasing any ranking."""
    cache = Path(sample.cache_dir)
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    _require(manifest == sample.manifest, "cache manifest changed during comparison")
    for record in manifest["videos"].values():
        path = (cache / record["array_path"]).resolve()
        _require(path.is_relative_to(cache.resolve()), "cache array escaped its directory")
        _pin(path, record["array_sha256"])
    _pin(cache / "ground_truth.csv", manifest["ground_truth"]["sha256"])


def _sample_mode(mode: str) -> str:
    _require(mode in {"smoke", "search"}, "only smoke/train and search/train are supported")
    return "benchmark" if mode == "smoke" else "master"


def _pairs(sample: Any, mode: str) -> list[tuple[str, int]]:
    return [(str(video), int(frame)) for video in sample.video_ids for frame in sample.indices(_sample_mode(mode), video)]


def _check_budget(plan: dict, monitor: ResourceMonitor, artifact_bytes: int = 0) -> None:
    resources = monitor.summary()
    rss = resources["ram_rss_peak_mb"]
    _require(rss is not None, "RSS monitor unavailable: resources cannot be certified")
    _require(rss <= plan["budget"]["max_rss_mb"], "RAM ceiling exceeded; comparison must stop without ranking")
    _require(artifact_bytes <= plan["budget"]["max_batch_artifact_mb"] * 1024**2,
             "artifact ceiling exceeded; comparison must stop without ranking")


def _bytes(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def _artifacts(manifest: dict, directory: Path) -> dict[str, Path]:
    artifacts, hashes = manifest.get("artifacts", {}), manifest.get("artifact_hashes", {})
    _require(bool(artifacts) and set(artifacts) == set(hashes), "all artifacts require hashes")
    result = {}
    for key, value in artifacts.items():
        path = Path(value).resolve()
        _require(path.parent == directory.resolve() and path.name != "manifest.json", "artifact outside its run directory")
        _pin(path, hashes[key])
        _require(path.name not in result, "duplicate artifact path")
        result[path.name] = path
    return result


def check_smoke(path: Path, plan: dict, sample: Any, candidates: list[dict]) -> dict:
    """Require complete compatible smoke artifacts, without reading old pilots."""
    path = path.resolve()
    digest = sha256_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    _require(manifest.get("status") == "complete" and manifest.get("git_dirty") is False
             and summary.get("mode") == "smoke" and summary.get("complete") is True
             and summary.get("selection_allowed") is False, "search requires a complete smoke without selection")
    _require(manifest.get("config", {}).get("plan") == plan and summary.get("plan_hash") == config_hash(plan, 64)
             and summary.get("sample_hash") == sample.sample_hash
             and manifest.get("config", {}).get("input") == _sample_reference(sample), "smoke belongs to other inputs/plan")
    _require(manifest.get("config_hash") == config_hash(manifest["config"]), "smoke resolved-config hash differs")
    _require(manifest.get("source_hash") == _source_hash(REPOSITORY_ROOT), "smoke belongs to other code")
    capture, verification = manifest.get("provenance_capture", {}), manifest.get("provenance_verification", {})
    _require(verification.get("status") == "verified" and verification.get("snapshot_sha256") == capture.get("snapshot_sha256"),
             "smoke lacks final provenance verification")
    files = _artifacts(manifest, path.parent)
    expected = {item["configuration_id"]: item for item in candidates}
    planned = json.loads(files["planned_candidates.json"].read_text(encoding="utf-8"))
    _require(len(planned) == len(expected) and {item["configuration_id"]: item for item in planned} == expected, "smoke candidate plan differs")
    pairs = _pairs(sample, "smoke")
    _require(json.loads(files["planned_frames.json"].read_text()) == [list(pair) for pair in pairs], "smoke frame plan differs")
    _require(summary.get("completed_candidates") == len(candidates) and summary.get("frames_per_candidate") == len(pairs)
             and summary.get("frame_evaluations") == len(candidates) * len(pairs), "incomplete smoke counts")
    records = manifest.get("candidate_manifests", [])
    _require(len(records) == len(expected), "incomplete smoke candidate manifests")
    seen = set()
    for record in records:
        child_path = Path(record["path"]).resolve()
        _pin(child_path, record["sha256"])
        child = json.loads(child_path.read_text(encoding="utf-8"))
        config = child.get("config", {})
        identifier = config.get("configuration_id")
        _require(identifier in expected and identifier not in seen, "duplicate or unexpected smoke candidate")
        seen.add(identifier)
        _require(child.get("status") == "complete" and child.get("git_dirty") is False
                 and child.get("source_hash") == manifest["source_hash"]
                 and child.get("git_sha") == manifest["git_sha"], "incompatible/incomplete smoke candidate provenance")
        _require(child.get("config_hash") == config_hash(config)
                 and child.get("provenance_capture") == capture, "candidate config hash or shared snapshot differs")
        _require(all(config.get(key) == expected[identifier][key] for key in ("method", "family", "params", "evaluation")), "candidate parameters changed")
        child_files = _artifacts(child, child_path.parent)
        child_summary = child.get("summary", {})
        _require(child_summary.get("frames_total") == len(pairs) and child_summary.get("complete") is True
                 and child_summary.get("mode") == "smoke" and child_summary.get("sample_hash") == sample.sample_hash
                 and child_summary.get("plan_hash") == config_hash(plan, 64), "incomplete smoke candidate summary")
        _require(json.loads(child_files["summary.json"].read_text()) == child_summary, "candidate summary artifact differs")
        with child_files["frame_metrics.csv"].open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        _require([(row["video_id"], int(row["frame"])) for row in rows] == pairs
                 and all(row["configuration_id"] == identifier and row["evaluation_protocol_id"] == PROTOCOL
                         and row["annotated"] == "True" for row in rows), "smoke frame coverage/protocol differs")
    _pin(path, digest)
    return {"path": str(path), "sha256": digest}


def run_candidate(candidate: dict, sample: Any, plan: dict, mode: str, batch: RunContext,
                  snapshot: RunSnapshot, monitor: ResourceMonitor, output_root: Path | None) -> dict:
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


def run_batch(plan: dict, sample: Any, mode: str, *, cache_validation_seconds: float,
              smoke_manifest: Path | None = None, output_root: Path | None = None) -> Path:
    candidates = expand_candidates(plan)
    _sample_mode(mode)
    _require(_git_dirty(REPOSITORY_ROOT) is False, "commit the code and protocol with clean Git before execution")
    _require(tuple(sample.video_ids) == TRAIN_IDS, "sample contains other videos")
    for video in sample.video_ids:
        indices = sample.indices(_sample_mode(mode), video)
        _require(len(indices) == (1 if mode == "smoke" else 48)
                 and list(indices) == sorted(set(indices))
                 and all(type(frame) is int and frame >= 0 for frame in indices), "sample indices differ from registered counts/order")
    smoke = None
    if mode == "search":
        _require(smoke_manifest is not None, "a compatible complete smoke is required before search")
        smoke = check_smoke(smoke_manifest, plan, sample, candidates)
    else:
        _require(smoke_manifest is None, "smoke cannot depend on another smoke")
    cv2.setNumThreads(plan["run"]["opencv_threads"])
    np.random.seed(plan["run"]["seed"])
    random.Random(plan["run"]["seed"]).shuffle(candidates)
    started = time.perf_counter()
    monitor, snapshot = ResourceMonitor(), RunSnapshot.capture(REPOSITORY_ROOT)
    sample_reference = _sample_reference(sample)
    _require(sample_reference["sample_manifest_sha256"] == plan["input"]["cache_manifest_sha256"]
             and sample_reference["sample_hash"] == plan["input"]["sample_hash"], "sample is not pinned by this plan")
    config = {"configuration_id": plan["plan_id"] + "_batch", "plan": copy.deepcopy(plan),
              "input": sample_reference, "mode": mode, "provenance": {"smoke": smoke}}
    batch = RunContext.create(module="detection", method="classical_comparison", algorithm="classical_comparison",
                              stage=mode, seed=plan["run"]["seed"], config=config, output_root=output_root,
                              provenance_snapshot=snapshot)
    summaries, artifact_bytes = [], 0
    provenance = {"status": "not_performed", "scope": "batch_end_before_ranking"}
    try:
        write_json_exclusive(batch.path / "planned_candidates.json", candidates)
        write_json_exclusive(batch.path / "planned_frames.json", _pairs(sample, mode))
        loop_started = time.perf_counter()
        for index, candidate in enumerate(candidates, 1):
            _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
            summary = run_candidate(candidate, sample, plan, mode, batch, snapshot, monitor, output_root)
            summaries.append(summary)
            artifact_bytes += _bytes(Path(summary["manifest_path"]).parent)
            write_json_exclusive(batch.path / f"candidate_{index:03d}.json", summary)
            print(json.dumps({"mode": mode, "completed": index, "planned": len(candidates),
                              "family": candidate["family"], "elapsed_seconds": round(time.perf_counter() - started, 2)}), flush=True)
        loop_seconds = time.perf_counter() - loop_started
        _require(_sample_reference(sample) == sample_reference, "cache manifest changed during comparison")
        verify_cache_unchanged(sample)
        try:
            provenance = snapshot.verify_current()
        except BaseException as exc:
            provenance = {"status": "failed", "scope": "batch_end_before_ranking", "error": str(exc)}
            raise
        ranked = rank_candidates(summaries, [item["configuration_id"] for item in candidates])
        _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
        write_csv_exclusive(batch.path / "candidate_metrics.csv", summaries)
        batch_summary = {"mode": mode, "complete": True, "plan_hash": config_hash(plan, 64),
                         "sample_hash": sample.sample_hash, "completed_candidates": len(summaries),
                         "frames_per_candidate": len(_pairs(sample, mode)),
                         "frame_evaluations": len(summaries) * len(_pairs(sample, mode)),
                         "cache_validation_seconds": cache_validation_seconds, "candidate_loop_seconds": loop_seconds,
                         "selection_allowed": mode == "search", "promotion_allowed": False, "validation_released": False,
                         "wall_seconds_limit": None, "candidate_artifact_bytes": artifact_bytes,
                         "interpretation": "training_finalists_not_promoted" if mode == "search" else "smoke_no_selection",
                         **monitor.summary()}
        if mode == "search":
            for index, row in enumerate(ranked, 1):
                row["rank"] = index
            finalists = [row for family in FAMILIES
                         for row in [item for item in ranked if item["family"] == family][:2]]
            write_csv_exclusive(batch.path / "ranking.csv", ranked)
            write_json_exclusive(batch.path / "family_finalists.json", finalists)
        _check_budget(plan, monitor, artifact_bytes + _bytes(batch.path))
        files = {path.name: str(path) for path in sorted(batch.path.iterdir()) if path.is_file() and path.name != "manifest.json"}
        batch.complete(summary=batch_summary, artifacts=files, artifact_hashes={key: sha256_file(value) for key, value in files.items()},
                       provenance_verification=provenance,
                       candidate_manifests=[{"path": row["manifest_path"], "sha256": sha256_file(row["manifest_path"])} for row in summaries])
    except BaseException as exc:
        try:
            batch.fail(exc, completed_candidates=len(summaries), selection_allowed=False, promotion_allowed=False, validation_released=False,
                       provenance_verification=provenance)
        except BaseException as failure:
            exc.add_note(f"Batch failure manifest could not be written: {failure}")
        raise
    print(json.dumps({"batch_manifest": str(batch.path / "manifest.json"), **batch_summary}), flush=True)
    return batch.path / "manifest.json"
