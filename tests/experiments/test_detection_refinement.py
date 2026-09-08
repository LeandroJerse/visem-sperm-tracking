from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from src.evaluation.detection import aggregate_frame_metrics, evaluate_frame
from src.experiments.config import config_hash
from src.experiments.detection_refinement import load_refinement_candidates
from src.experiments.detection_search import expand_coarse_candidates, rank_candidates, summarize_candidate


TRAIN = [11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82]


def _json(path: Path, value=None):
    if value is None:
        return json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def _plan():
    return {
        "plan_id": "synthetic_refinement", "method": "threshold",
        "params": {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3, "min_area": 3, "max_area": 300},
        "search_space": {"threshold_value": [0, 16, 128, 240, 255], "morph_iterations": [0], "close_iterations": [0]},
        "evaluation": {"protocol_id": "center_distance_v3_individuals_ignore_clusters_10px", "center_gate_px": 10,
                       "sensitivity_gates_px": [15, 20], "class_policy": "individuals_ignore_clusters"},
        "selection": {"primary": "macro_video_f1_individuals_center_10px",
                      "tie_breakers": ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"],
                      "timing_used_for_ranking": False, "comparisons_require_all_candidates_and_all_planned_frames": True,
                      "coarse_shortlist_size": 5},
        "protocol": {"train_ids": TRAIN}, "sampling": {"coarse_frames_per_video": 12, "master_frames_per_video": 48},
        "run": {"split": "train", "seed": 42, "save_video": False},
        "refinement_plan": {"status": "design_only_not_executable_in_current_runner",
                            "parent_candidates": "top_5_from_complete_coarse_search", "threshold_offsets": list(range(-15, 16)),
                            "clamp_threshold_to": [0, 255], "inherit_parent_morphology": True,
                            "fixed_min_area": 3, "fixed_max_area": 300, "deduplicate_resolved_parameters": True,
                            "frames_per_video": 48, "maximum_candidates": 155, "maximum_frame_evaluations": 89280,
                            "finalists_for_later_full_validation": 2, "soft_wall_seconds": 7200,
                            "requires_new_cost_projection_before_execution": True},
    }


def _fixture_expansion(parents, coarse_candidates):
    # Deliberately reconstruct by sets of (threshold, opening, closing), apart
    # from the production resolver and its deduplication implementation.
    coarse = {row["configuration_id"]: row for row in coarse_candidates}
    origins = {}
    for parent in parents:
        params = coarse[parent]["params"]
        low, high = max(0, params["threshold_value"]-15), min(255, params["threshold_value"]+15)
        for threshold in range(low, high+1):
            identity = (threshold, params["morph_iterations"], params["close_iterations"])
            origins.setdefault(identity, set()).add(parent)
    result = []
    for (threshold, opening, closing), parent_set in sorted(origins.items()):
        exemplar = coarse[sorted(parent_set)[0]]
        params = {**exemplar["params"], "threshold_value": threshold}
        result.append({"configuration_id": f"t{threshold:03d}_o{opening}_c{closing}", "method": "threshold",
                       "params": params, "parents": [parent for parent in parents if parent in parent_set]})
    return result


def _build(tmp_path, plan=None, priorities=None):
    plan = copy.deepcopy(plan or _plan())
    batch_dir = tmp_path / "coarse"
    batch_dir.mkdir()
    sample_path = tmp_path / "sample.json"
    sample_hash = "a" * 64
    sample = {"sample_hash": sample_hash, "plan_sha256": config_hash(plan, 64), "video_ids": list(map(str, TRAIN)),
              "selections": {str(vid): {"coarse": list(range(12)), "master": list(range(48))} for vid in TRAIN}}
    _json(sample_path, sample)
    candidates = expand_coarse_candidates(plan)
    priorities = priorities or [row["configuration_id"] for row in candidates]
    sample_ref = {"sample_hash": sample_hash, "sample_manifest_path": str(sample_path), "sample_manifest_sha256": _hash(sample_path)}
    capture = {"mode": "shared_batch", "snapshot_sha256": "c" * 64}
    batch = {"status": "complete", "run_id": "synthetic_batch", "git_sha": "synthetic", "git_dirty": False,
             "source_hash": "b" * 64, "config": {"plan": plan, "input": sample_ref},
             "provenance_capture": capture,
             "provenance_verification": {"status": "verified", "scope": "batch_end_before_ranking", "snapshot_sha256": "c" * 64},
             "summary": {"mode": "coarse", "complete": True, "selection_allowed": True, "plan_hash": config_hash(plan, 64),
                         "sample_hash": sample_hash, "completed_candidates": len(candidates), "frames_per_candidate": 144,
                         "frame_evaluations": len(candidates)*144}, "candidate_manifests": []}
    pairs = [[str(vid), frame] for vid in TRAIN for frame in range(12)]
    _json(batch_dir / "planned_candidates.json", candidates)
    _json(batch_dir / "planned_frames.json", pairs)
    summaries = []
    for index, candidate in enumerate(candidates, 1):
        identifier = candidate["configuration_id"]
        child_dir = tmp_path / identifier
        child_dir.mkdir()
        config = copy.deepcopy(candidate)
        config["provenance"].update(search_plan_hash=config_hash(plan, 64), sample_hash=sample_hash,
                                    batch_id=batch["run_id"], sample_mode="coarse")
        # One actual synthetic association template per candidate; no detector.
        correct = 10-priorities.index(identifier) if identifier in priorities else 0
        gt = [(i*100, 0, 0) for i in range(10)]
        pred = gt[:correct] + [(10000+i*100, 0, 0) for i in range(10-correct)]
        frame = evaluate_frame(pred, gt, video_id="11", frame=0, detection_ms=1)
        frame.update(configuration_id=identifier, evaluation_protocol_id=plan["evaluation"]["protocol_id"], sample_hash=sample_hash)
        frames = [{**frame, "video_id": str(vid), "frame": number} for vid in TRAIN for number in range(12)]
        video_summaries = []
        for vid in TRAIN:
            video = aggregate_frame_metrics([row for row in frames if row["video_id"] == str(vid)], video_id=str(vid))
            video.update(configuration_id=identifier, evaluation_protocol_id=plan["evaluation"]["protocol_id"],
                         class_policy=plan["evaluation"]["class_policy"], center_gate_px=10, sensitivity_gates_px=[15, 20])
            video_summaries.append(video)
        summary = summarize_candidate(video_summaries, TRAIN, 12)
        summary.update(mode="coarse", plan_hash=config_hash(plan, 64), sample_hash=sample_hash)
        _csv(child_dir / "frame_metrics.csv", frames)
        _csv(child_dir / "video_summary.csv", video_summaries)
        _csv(child_dir / "detections.csv", [])
        _json(child_dir / "summary.json", summary)
        child = {"status": "complete", "git_dirty": False, "git_sha": batch["git_sha"], "source_hash": batch["source_hash"],
                 "config": config, "config_hash": config_hash(config), "summary": summary, "provenance_capture": copy.deepcopy(capture)}
        child["artifacts"] = {p.name: str(p) for p in child_dir.iterdir()}
        child["artifact_hashes"] = {key: _hash(Path(value)) for key, value in child["artifacts"].items()}
        child_path = child_dir / "manifest.json"
        _json(child_path, child)
        batch["candidate_manifests"].append({"path": str(child_path), "sha256": _hash(child_path)})
        _json(batch_dir / f"candidate_{index:03d}.json", summary)
        summaries.append(summary)
    ranked = rank_candidates(summaries, [row["configuration_id"] for row in candidates])
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    _csv(batch_dir / "candidate_metrics.csv", summaries)
    _csv(batch_dir / "ranking.csv", ranked)
    _json(batch_dir / "shortlist.json", ranked[:5])
    batch["artifacts"] = {p.name: str(p) for p in batch_dir.iterdir()}
    batch["artifact_hashes"] = {key: _hash(Path(value)) for key, value in batch["artifacts"].items()}
    batch["config_hash"] = config_hash(batch["config"])
    coarse_path = batch_dir / "manifest.json"
    _json(coarse_path, batch)
    top5 = [row["configuration_id"] for row in ranked[:5]]
    verification = {"status": "passed", "ranking_complete_match": True, "batch_manifest": str(coarse_path),
                    "batch_manifest_sha256": _hash(coarse_path), "plan_hash": config_hash(plan, 64),
                    "sample_hash": sample_hash, "independent_top5": top5}
    verification_path = tmp_path / "verification_synthetic.json"
    _json(verification_path, verification)
    resolved = _fixture_expansion(top5, candidates)
    derived = {"status": "planned_not_executed", "kind": "deterministic_instantiation_of_registered_refinement",
               "coarse_manifest": str(coarse_path), "coarse_manifest_sha256": _hash(coarse_path),
               "verification_sha256": _hash(verification_path), "plan_hash": config_hash(plan, 64),
               "sample_hash": sample_hash, "rule": plan["refinement_plan"], "candidate_count": len(resolved),
               "frames_per_video": 48, "videos": TRAIN, "frame_evaluations": len(resolved)*576, "candidates": resolved}
    derived_path = tmp_path / "refinement_plan.json"
    _json(derived_path, derived)
    return {"coarse": coarse_path, "derived": derived_path, "plan": plan, "verification": verification_path,
            "sample": sample_path, "batch_dir": batch_dir, "tmp": tmp_path}


def _load(bundle):
    return load_refinement_candidates(bundle["coarse"], bundle["derived"], bundle["plan"])


def _refresh_hashes(bundle):
    """Rehash synthetic metadata after deliberate corruption to exercise semantics."""
    coarse = _json(bundle["coarse"])
    for reference in coarse["candidate_manifests"]:
        path = Path(reference["path"])
        child = _json(path)
        child["artifact_hashes"] = {key: _hash(Path(value)) for key, value in child["artifacts"].items()}
        child["config_hash"] = config_hash(child["config"])
        _json(path, child)
        reference["sha256"] = _hash(path)
    coarse["artifact_hashes"] = {key: _hash(Path(value)) for key, value in coarse["artifacts"].items()}
    coarse["config_hash"] = config_hash(coarse["config"])
    _json(bundle["coarse"], coarse)
    verification = _json(bundle["verification"])
    verification["batch_manifest_sha256"] = _hash(bundle["coarse"])
    _json(bundle["verification"], verification)
    derived = _json(bundle["derived"])
    derived["coarse_manifest_sha256"] = _hash(bundle["coarse"])
    derived["verification_sha256"] = _hash(bundle["verification"])
    _json(bundle["derived"], derived)


def test_expansion_clips_endpoints_deduplicates_and_preserves_inputs(tmp_path):
    bundle = _build(tmp_path)
    before = {str(path): _hash(path) for path in tmp_path.rglob("*") if path.is_file()}
    candidates, provenance = _load(bundle)
    assert len(candidates) == 94
    assert len({row["configuration_id"] for row in candidates}) == 94
    assert candidates[0]["configuration_id"] == "t000_o0_c0"
    assert candidates[-1]["configuration_id"] == "t255_o0_c0"
    overlap = next(row for row in candidates if row["configuration_id"] == "t010_o0_c0")
    assert overlap["provenance"]["refinement_parent_ids"] == ["t000_o0_c0", "t016_o0_c0"]
    assert all(row["params"]["min_area"] == 3 and row["params"]["max_area"] == 300 for row in candidates)
    assert candidates[0]["run"] == {"split": "train", "seed": 42, "save_video": False}
    assert provenance["sample_hash"] == "a"*64
    assert provenance["plan_hash"] == config_hash(bundle["plan"], 64)
    assert provenance["frame_evaluations"] == 94*576
    assert before == {str(path): _hash(path) for path in tmp_path.rglob("*") if path.is_file()}
    candidates[0]["evaluation"]["sensitivity_gates_px"].append(99)
    assert candidates[1]["evaluation"]["sensitivity_gates_px"] == [15, 20]
    assert bundle["plan"]["evaluation"]["sensitivity_gates_px"] == [15, 20]


def test_recorded_parent_configuration_pattern_produces_117_not_a_global_constant(tmp_path):
    plan = _plan()
    plan["search_space"] = {"threshold_value": [200, 208, 224], "morph_iterations": [0, 1], "close_iterations": [1, 2]}
    parents = ["t224_o0_c2", "t208_o0_c2", "t224_o0_c1", "t200_o1_c2", "t208_o1_c2"]
    bundle = _build(tmp_path, plan, parents)
    candidates, provenance = _load(bundle)
    assert len(candidates) == 117
    assert provenance["parent_candidate_ids"] == parents
    assert provenance["frame_evaluations"] == 67392
    assert candidates[0]["configuration_id"] == "t185_o1_c2"
    assert candidates[-1]["configuration_id"] == "t239_o0_c2"
    shared = next(row for row in candidates if row["configuration_id"] == "t209_o0_c2")
    assert shared["provenance"]["refinement_parent_ids"] == ["t224_o0_c2", "t208_o0_c2"]


@pytest.mark.parametrize("change", ["threshold", "area", "morphology", "parents", "extra", "missing", "order", "count", "rule", "status", "unregistered_field", "verification"])
def test_rejects_altered_derived_plan(tmp_path, change):
    bundle = _build(tmp_path)
    derived = _json(bundle["derived"])
    if change == "threshold":
        derived["candidates"][0]["params"]["threshold_value"] = 1
    elif change == "area":
        derived["candidates"][0]["params"]["min_area"] = 5
    elif change == "morphology":
        derived["candidates"][0]["params"]["morph_iterations"] = 1
    elif change == "parents":
        derived["candidates"][0]["parents"] = ["invented"]
    elif change == "extra":
        derived["candidates"].append(copy.deepcopy(derived["candidates"][0]))
    elif change == "missing":
        derived["candidates"].pop()
    elif change == "order":
        derived["candidates"].reverse()
    elif change == "count":
        derived["candidate_count"] = 117
    elif change == "rule":
        derived["rule"]["threshold_offsets"] = [-15, 0, 15]
    elif change == "status":
        derived["status"] = "complete"
    elif change == "unregistered_field":
        derived["adaptive_search"] = True
    else:
        derived["verification_sha256"] = "0"*64
    _json(bundle["derived"], derived)
    with pytest.raises(ValueError):
        _load(bundle)


@pytest.mark.parametrize("target", ["ranking.csv", "shortlist.json", "planned_candidates.json", "child_manifest", "child_artifact", "sample"])
def test_rejects_bytes_changed_without_updating_recorded_hash(tmp_path, target):
    bundle = _build(tmp_path)
    if target == "sample":
        path = bundle["sample"]
    elif target.startswith("child"):
        path = Path(_json(bundle["coarse"])["candidate_manifests"][0]["path"])
        if target == "child_artifact":
            path = path.parent / "detections.csv"
    else:
        path = bundle["batch_dir"] / target
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="SHA256"):
        _load(bundle)


@pytest.mark.parametrize("change", ["status", "mode", "snapshot", "missing_candidate", "duplicate_candidate", "count", "rank_order", "shortlist", "frame_duplicate"])
def test_rejects_semantic_corruption_even_with_consistent_hashes(tmp_path, change):
    bundle = _build(tmp_path)
    coarse = _json(bundle["coarse"])
    if change == "status":
        coarse["status"] = "failed"
    elif change == "mode":
        coarse["summary"]["mode"] = "benchmark"
    elif change == "snapshot":
        coarse["provenance_verification"]["status"] = "not_performed"
    elif change == "missing_candidate":
        coarse["candidate_manifests"].pop()
    elif change == "duplicate_candidate":
        coarse["candidate_manifests"][-1] = coarse["candidate_manifests"][0]
    elif change == "count":
        coarse["summary"]["frame_evaluations"] -= 1
    elif change == "rank_order":
        path = bundle["batch_dir"] / "ranking.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows.reverse()
        _csv(path, rows)
    elif change == "shortlist":
        path = bundle["batch_dir"] / "shortlist.json"
        rows = _json(path)
        _json(path, rows[:-1])
    else:
        path = Path(coarse["candidate_manifests"][0]["path"]).parent / "frame_metrics.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[-1] = rows[0]
        _csv(path, rows)
    _json(bundle["coarse"], coarse)
    _refresh_hashes(bundle)
    with pytest.raises(ValueError):
        _load(bundle)


@pytest.mark.parametrize("change", ["evaluation", "threshold_offsets", "area", "split", "parents", "no_dedup", "cost_projection"])
def test_rejects_changes_to_registered_original_plan(tmp_path, change):
    bundle = _build(tmp_path)
    if change == "evaluation":
        bundle["plan"]["evaluation"]["center_gate_px"] = 15
    elif change == "threshold_offsets":
        bundle["plan"]["refinement_plan"]["threshold_offsets"] = [-15, 0, 15]
    elif change == "area":
        bundle["plan"]["refinement_plan"]["fixed_min_area"] = 5
    elif change == "split":
        bundle["plan"]["protocol"]["train_ids"][-1] = 24
    elif change == "parents":
        bundle["plan"]["selection"]["coarse_shortlist_size"] = 2
    elif change == "no_dedup":
        bundle["plan"]["refinement_plan"]["deduplicate_resolved_parameters"] = False
    else:
        bundle["plan"]["refinement_plan"]["requires_new_cost_projection_before_execution"] = False
    with pytest.raises(ValueError):
        _load(bundle)


def test_rejects_wrong_independent_verification_even_if_derived_hash_is_updated(tmp_path):
    bundle = _build(tmp_path)
    report = _json(bundle["verification"])
    report["independent_top5"].reverse()
    _json(bundle["verification"], report)
    derived = _json(bundle["derived"])
    derived["verification_sha256"] = _hash(bundle["verification"])
    _json(bundle["derived"], derived)
    with pytest.raises(ValueError, match="independent verification"):
        _load(bundle)


def test_refuses_source_or_pixel_paths_before_opening_them(tmp_path):
    bundle = _build(tmp_path)
    coarse = _json(bundle["coarse"])
    coarse["config"]["input"]["sample_manifest_path"] = str(tmp_path / "pixels.npy")
    _json(bundle["coarse"], coarse)
    _refresh_hashes(bundle)
    with pytest.raises(ValueError, match="only JSON/CSV"):
        _load(bundle)
