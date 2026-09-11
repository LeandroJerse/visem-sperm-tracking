"""Independent QA math, hostile artifacts and producer-schema compatibility.

Only these tests import the production evaluator, to create synthetic outputs
that the independent verifier must reconstruct without importing that code.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from script.detection.test import verify_classical_comparison as qa
from src.evaluation.detection import evaluate_frame, aggregate_frame_metrics
from src.experiments.detection_search import summarize_candidate


def box(cx=10, cy=10, *, cls=0, w=4, h=4, identity=""):
    return {"video_id": "11", "frame": 0, "source": "detection", "object_id": identity,
            "class_id": cls, "class_name": {0: "normal", 1: "cluster", 2: "pinhead"}[cls],
            "cx": float(cx), "cy": float(cy), "w": float(w), "h": float(h),
            "x": cx - w / 2, "y": cy - h / 2, "score": 1.0}


@pytest.mark.parametrize("predictions,gt,expected", [
    ([], [], (0, 0, 0, 0)),
    ([box()], [], (0, 1, 0, 0)),
    ([], [box()], (0, 0, 1, 0)),
    ([box(), box()], [box(), box(10, 10, cls=1, w=40, h=40)], (1, 1, 0, 0)),
    ([box(30, 10)], [box(10, 10), box(30, 10, cls=1, w=40, h=40)], (0, 0, 1, 1)),
    ([box(50, 10)], [box(30, 10, cls=1, w=40, h=40)], (0, 0, 0, 1)),
    ([box(50.001, 10)], [box(30, 10, cls=1, w=40, h=40)], (0, 1, 0, 0)),
    ([box(10, 10, cls=1)], [box(10, 10, cls=2), box(10, 10, cls=1, w=40, h=40)], (1, 0, 0, 0)),
])
def test_manual_counts_and_cluster_boundaries(predictions, gt, expected):
    result, _ = qa.quality(predictions, gt, 10, True, qa.Audit())
    assert tuple(result[k] for k in ("tp", "fp", "fn", "n_predictions_ignored")) == expected


def test_cardinality_has_priority_over_close_pair():
    matches, distances, _ = qa.solve_matching([box(0, 0), box(9, 0)], [box(0, 0), box(0, 10)], 10)
    assert matches == [(0, 1), (1, 0)]
    assert sum(distances[i, j] for i, j in matches) == 19


def test_increasing_radius_can_turn_cluster_ignore_into_false_positive():
    preds = [box(20, 20), box(32, 20)]
    gt = [box(20, 20), box(25, 20, cls=1, w=40, h=40)]
    a, _ = qa.quality(preds, gt, 10, True, qa.Audit())
    b, _ = qa.quality(preds, gt, 15, True, qa.Audit())
    assert (a["fp"], a["n_predictions_ignored"], a["f1"]) == (0, 1, 1)
    assert b["fp"] == 1 and b["n_predictions_ignored"] == 0 and b["f1"] < 1


def test_cluster_only_evidence_is_undefined_but_secondary_is_defined():
    result, _ = qa.frame_metrics([box()], [box(cls=1, w=40, h=40)], "11", 0, qa.Audit())
    assert result["f1"] is None
    assert result["primary_evaluable"] is False
    assert result["count_abs_error"] == 0
    assert result["secondary_all_objects_f1"] == 1


@pytest.mark.parametrize("seed", range(12))
def test_scipy_solution_agrees_with_brute_force(seed):
    rng = np.random.default_rng(seed)
    p = [box(*v) for v in rng.integers(0, 20, size=(3, 2))]
    g = [box(*v) for v in rng.integers(0, 20, size=(3, 2))]
    matches, distances, _ = qa.solve_matching(p, g, 10)
    score = (-len(matches), sum(distances[i, j] for i, j in matches))
    all_scores = []
    for permutation in itertools.permutations(range(3)):
        valid = [(i, j) for i, j in enumerate(permutation) if distances[i, j] <= 10]
        all_scores.append((-len(valid), sum(distances[i, j] for i, j in valid)))
    assert score == min(all_scores)


@pytest.mark.parametrize("seed", range(10))
def test_independent_frame_metrics_agree_with_producer_on_synthetic_geometry(seed):
    rng = np.random.default_rng(seed)
    p = [box(*v, cls=int(rng.integers(0, 3))) for v in rng.integers(0, 50, size=(12, 2))]
    g = [box(*v, cls=int(rng.integers(0, 3)), w=15, h=15) for v in rng.integers(0, 50, size=(7, 2))]
    audit = qa.Audit()
    expected, witness = qa.frame_metrics(p, g, "11", 0, audit)
    observed = evaluate_frame(p, g, video_id="11", frame=0, detection_ms=0.5)
    qa.compare_frame(observed, expected, witness, audit, "synthetic")
    assert audit.matchings == 6


def test_detects_cooptimal_matching():
    p, g = [box(0, 0), box(2, 0)], [box(1, 0), box(1, 0)]
    m, d, c = qa.solve_matching(p, g, 10)
    assert qa.has_cooptimal_assignment((m, d, c, 10))
    m, d, c = qa.solve_matching([box(0, 0)], [box(1, 0)], 10)
    assert not qa.has_cooptimal_assignment((m, d, c, 10))


@pytest.mark.parametrize("value", [True, None, "nan", "inf", float("inf"), "bad"])
def test_rejects_bad_numbers(value):
    with pytest.raises(qa.VerificationError):
        qa.number(value)


def test_rejects_duplicate_mapping_and_csv_columns():
    with pytest.raises(qa.VerificationError, match="duplicate"):
        qa._json('{"a":1,"a":2}')
    with pytest.raises(qa.VerificationError, match="duplicate"):
        yaml.load("a: 1\na: 2\n", Loader=qa.StrictYaml)
    with pytest.raises(qa.VerificationError, match="header"):
        qa.csv_rows(b"a,a\n1,2\n")
    with pytest.raises(qa.VerificationError, match="width"):
        qa.csv_rows(b"a,b\n1\n")


def test_numeric_tolerance_is_not_used_for_counts():
    audit = qa.Audit()
    audit.equal(1 + 1e-10, 1.0, "float")
    with pytest.raises(qa.VerificationError):
        audit.equal(1 + 1e-10, 1, "count")
    with pytest.raises(qa.VerificationError):
        audit.equal(float("nan"), 0.0, "nan")


def test_new_verifier_does_not_import_production_evaluator_or_cache():
    import ast
    tree = ast.parse(Path(qa.__file__).read_text(encoding="utf8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    assert not any(name.startswith("src.") for name in names)


def dump_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def seal(path, manifest):
    files = {p.name: str(p.resolve()) for p in path.parent.iterdir() if p.is_file() and p != path}
    manifest["artifacts"] = files
    manifest["artifact_hashes"] = {name: digest(Path(raw)) for name, raw in files.items()}
    if "config" in manifest:
        manifest["config_hash"] = qa.canonical_hash(manifest["config"])[:12]
    dump_json(path, manifest)


def synthetic_operational_plan(root, parent, monkeypatch):
    dump_json(root / qa.LEGACY_PLAN, parent)
    parent_hash = qa.canonical_hash(parent)
    failed_batch = dump_json(root / "failures/batch/manifest.json", {"status": "failed", "config": {"plan": parent}})
    failed_candidate = dump_json(root / "failures/candidate/manifest.json", {"status": "failed"})
    failure_hashes = {"failed_batch_manifest": digest(failed_batch), "failed_candidate_manifest": digest(failed_candidate)}
    monkeypatch.setattr(qa, "PARENT_PLAN_CANONICAL_SHA256", parent_hash)
    monkeypatch.setattr(qa, "FAILED_MANIFEST_HASHES", failure_hashes)
    plan = copy.deepcopy(parent)
    plan["plan_id"] = "classical_detection_comparison_v1_operational_v2_20260911"
    plan["budget"]["max_predictions_per_frame"] = 307200
    plan["operational_revision"] = {
        "parent_plan_path": qa.LEGACY_PLAN, "parent_plan_canonical_sha256": parent_hash,
        "reason": "retry_prediction_guard_without_scientific_change", "previous_max_predictions_per_frame": 2000,
        "failed_batch_manifest": {"path": str(failed_batch), "sha256": failure_hashes["failed_batch_manifest"]},
        "failed_candidate_manifest": {"path": str(failed_candidate), "sha256": failure_hashes["failed_candidate_manifest"]},
    }
    dump_json(root / qa.PLAN, plan)
    return plan


@pytest.fixture
def fixture_batch(tmp_path, monkeypatch):
    root = tmp_path
    plan = yaml.safe_load((qa.ROOT / qa.LEGACY_PLAN).read_text(encoding="utf8"))
    source_plan = yaml.safe_load((qa.ROOT / plan["input"]["sample_plan"]).read_text(encoding="utf8"))
    dump_json(root / plan["input"]["sample_plan"], source_plan)  # JSON is valid YAML.
    cache_path = root / plan["input"]["cache_manifest"]
    cache = {"schema_version": 1, "kind": "canonical_training_detection_sample", "status": "complete",
             "plan_sha256": qa.canonical_hash(source_plan), "video_ids": list(qa.TRAIN),
             "sampling": source_plan["sampling"], "split": {"fixture": "train"}, "audit": {"fixture": True},
             "selections": {}, "videos": {}, "frames": []}
    all_raw_gt, objects, historical_metrics = [], {}, []
    for video in qa.TRAIN:
        cache["selections"][video] = {"master": list(range(48)), "coarse": list(range(0, 48, 4)), "benchmark": [24]}
        array = cache_path.parent / f"frames/video_{video}.npy"
        array.parent.mkdir(parents=True, exist_ok=True)
        array.write_bytes(b"synthetic previously authenticated array bytes")
        cache["videos"][video] = {"array_path": f"frames/video_{video}.npy", "array_bytes": array.stat().st_size,
                                   "array_sha256": digest(array), "shape": [48, 480, 640, 3], "dtype": "uint8"}
        for frame in range(48):
            preds = [box(10, 10), box(10, 10), box(35, 40), box(55, 40), box(90, 90)]
            gt = [box(10, 10, identity="individual"), box(35, 40, cls=2, identity="small"),
                  box(40, 40, cls=1, w=50, h=50, identity="cluster")]
            for row in preds + gt:
                row.update(video_id=video, frame=frame)
            for row in gt:
                row["source"] = "manual"
            objects[(video, frame)] = preds, gt
            all_raw_gt.extend(gt)
            cache["frames"].append({"video_id": video, "frame": frame, "array_index": frame, "label": {"nonempty_lines": len(gt)}})
            historical_metrics.append(evaluate_frame(preds, gt, video_id=video, frame=frame, detection_ms=1.0))
    gt_path = cache_path.parent / "ground_truth.csv"
    dump_csv(gt_path, all_raw_gt)
    cache["ground_truth"] = {"path": "ground_truth.csv", "sha256": digest(gt_path), "rows": len(all_raw_gt), "bytes": gt_path.stat().st_size}
    cache["sample_hash"] = qa.canonical_hash({key: cache[key] for key in ("schema_version", "plan_sha256", "split", "audit", "video_ids", "sampling", "selections", "videos", "ground_truth", "frames")})
    dump_json(cache_path, cache)
    plan["input"].update(cache_manifest_sha256=digest(cache_path), sample_hash=cache["sample_hash"], sample_plan_canonical_sha256=qa.canonical_hash(source_plan))
    plan = synthetic_operational_plan(root, plan, monkeypatch)
    candidates = qa.independent_candidates(plan)
    pairs = [(video, 24) for video in qa.TRAIN]
    batch_path = root / "outputs/batch/manifest.json"
    batch_path.parent.mkdir(parents=True)
    capture = {"mode": "shared_batch", "snapshot_sha256": "a" * 64, "process_id": 123,
               "captured_at": "2026-09-11T00:00:00Z", "recheck_policy": "batch_end_before_ranking", "origin_batch_manifest": str(batch_path)}
    common = {"status": "complete", "git_dirty": False, "git_sha": "b" * 40, "source_hash": "c" * 64,
              "seed": 42, "stage": "smoke", "module": "detection", "environment": {"synthetic": True}, "provenance_capture": capture}
    input_reference = {"sample_manifest_path": str(cache_path), "sample_manifest_sha256": digest(cache_path), "sample_hash": cache["sample_hash"]}
    child_records, summaries, candidate_bytes = [], [], 0
    for index, candidate in enumerate(candidates, 1):
        path = root / f"outputs/{candidate['configuration_id']}/manifest.json"
        path.parent.mkdir(parents=True)
        config = copy.deepcopy(candidate)
        config["run"]["stage"] = "smoke"
        config["provenance"] = {"plan_id": plan["plan_id"], "plan_hash": qa.canonical_hash(plan), **input_reference,
                                "sample_mode": "benchmark", "batch_manifest_path": str(batch_path)}
        frames, raw, videos = [], [], []
        for video, frame in pairs:
            preds, gt = objects[(video, frame)]
            raw.extend(preds + gt)
            row = evaluate_frame(preds, gt, video_id=video, frame=frame, detection_ms=1.0)
            row.update(configuration_id=candidate["configuration_id"], family=candidate["family"], evaluation_protocol_id=qa.PROTOCOL, sample_hash=cache["sample_hash"])
            frames.append(row)
            video_row = aggregate_frame_metrics([row], video_id=video)
            video_row.update(configuration_id=candidate["configuration_id"], family=candidate["family"], evaluation_protocol_id=qa.PROTOCOL,
                             class_policy="individuals_ignore_clusters", center_gate_px=10, sensitivity_gates_px=[15, 20], sample_hash=cache["sample_hash"])
            videos.append(video_row)
        summary = summarize_candidate(videos, qa.TRAIN, 1)
        summary.update(mode="smoke", family=candidate["family"], method=candidate["method"], run_id=f"fixture-{index}", manifest_path=str(path),
                       plan_hash=qa.canonical_hash(plan), sample_hash=cache["sample_hash"], detector_seconds=0.012,
                       evaluation_seconds=0.1, export_seconds=0.1, ram_rss_peak_mb=100.0, resource_samples=13,
                       vram_allocated_peak_mb=None, vram_reserved_peak_mb=None)
        dump_csv(path.parent / "detections.csv", raw)
        dump_csv(path.parent / "frame_metrics.csv", frames)
        dump_csv(path.parent / "video_summary.csv", videos)
        dump_json(path.parent / "summary.json", summary)
        child = {**common, "run_id": f"fixture-{index}", "config": config, "summary": summary}
        seal(path, child)
        child_records.append({"path": str(path), "sha256": digest(path)})
        candidate_bytes += sum(p.stat().st_size for p in path.parent.iterdir())
        summaries.append(summary)
        dump_json(batch_path.parent / f"candidate_{index:03d}.json", summary)
    dump_json(batch_path.parent / "planned_candidates.json", candidates)
    dump_json(batch_path.parent / "planned_frames.json", pairs)
    dump_csv(batch_path.parent / "candidate_metrics.csv", summaries)
    summary = {"complete": True, "mode": "smoke", "plan_hash": qa.canonical_hash(plan), "sample_hash": cache["sample_hash"],
               "completed_candidates": 43, "frames_per_candidate": 12, "frame_evaluations": 516, "selection_allowed": False,
               "promotion_allowed": False, "validation_released": False, "wall_seconds_limit": None,
               "cache_validation_seconds": 0.1, "candidate_loop_seconds": 1.0, "ram_rss_peak_mb": 100.0,
               "resource_samples": 2, "candidate_artifact_bytes": candidate_bytes}
    batch = {**common, "config": {"plan": plan, "mode": "smoke", "input": input_reference, "provenance": {"smoke": None}},
             "summary": summary, "candidate_manifests": child_records,
             "provenance_verification": {"status": "verified", "scope": "batch_end_before_ranking", "snapshot_sha256": "a" * 64}}
    seal(batch_path, batch)
    historical = root / qa.THRESHOLD_REFERENCE
    historical.parent.mkdir(parents=True)
    dump_csv(historical.parent / "detections.csv", [row for pair in objects.values() for group in pair for row in group])
    dump_csv(historical.parent / "frame_metrics.csv", historical_metrics)
    seal(historical, {"status": "complete", "git_dirty": False})
    monkeypatch.setattr(qa, "THRESHOLD_REFERENCE_SHA256", digest(historical))
    return root, batch_path


def test_full_synthetic_smoke_and_historical_reference(fixture_batch):
    root, path = fixture_batch
    result = qa.verify_batch(path, root=root)
    assert result["status"] == "passed"
    assert result["frame_evaluations"] == 516
    assert result["scipy_matchings"] == 516 * 6
    assert result["historical_t218_parity"]["status"] == "passed"
    assert result["historical_t218_parity"]["frames_compared"] == 12
    assert result["distance_tie_limits"] == []
    assert result["comparisons"] > 100000
    assert result["operational_lineage"]["scientific_contract_identical_to_parent"] is True
    assert result["operational_lineage"]["current_prediction_guard"] == 307200


@pytest.mark.parametrize("fault", ["hash", "fp", "ignored", "sensitivity", "secondary", "gt", "extra_frame", "missing_candidate", "plan", "provenance", "undeclared"])
def test_corrupted_smoke_is_rejected_even_when_parent_hashes_are_updated(fixture_batch, fault):
    root, path = fixture_batch
    batch = json.loads(path.read_text())
    child_path = Path(batch["candidate_manifests"][0]["path"])
    child = json.loads(child_path.read_text())
    if fault == "hash":
        (child_path.parent / "frame_metrics.csv").write_text("corrupt", encoding="utf8")
    elif fault in {"fp", "ignored", "sensitivity", "secondary", "extra_frame"}:
        file = child_path.parent / "frame_metrics.csv"
        rows = qa.csv_rows(file.read_bytes())
        if fault == "extra_frame":
            rows[0]["frame"] = "999"
        else:
            key = {"fp": "fp", "ignored": "n_predictions_ignored", "sensitivity": "f1_at_15px",
                   "secondary": "secondary_all_objects_tp_at_20px"}[fault]
            rows[0][key] = "999"
        dump_csv(file, rows)
        seal(child_path, child)
    elif fault == "gt":
        file = child_path.parent / "detections.csv"
        rows = qa.csv_rows(file.read_bytes())
        row = next(r for r in rows if r["source"] == "manual")
        row["object_id"] = "forged"
        dump_csv(file, rows)
        seal(child_path, child)
    elif fault == "missing_candidate":
        batch["candidate_manifests"].pop()
    elif fault == "plan":
        child["config"]["params"]["max_area"] = 999
        seal(child_path, child)
    elif fault == "provenance":
        child["source_hash"] = "d" * 64
        seal(child_path, child)
    else:
        (child_path.parent / "unreported.csv").write_text("hello", encoding="utf8")
    if fault != "missing_candidate":
        batch["candidate_manifests"][0]["sha256"] = digest(child_path)
    seal(path, batch)
    with pytest.raises(qa.VerificationError):
        qa.verify_batch(path, root=root)


def test_hash_reader_catches_changes_and_path_escape(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"first")
    audit = qa.Audit()
    audit.read(path)
    path.write_bytes(b"second")
    with pytest.raises(qa.VerificationError, match="changed"):
        audit.read(path)
    with pytest.raises(qa.VerificationError, match="escapes"):
        qa.under(tmp_path, "../outside")


def test_registered_grid_is_exact_and_shuffled_deterministically():
    plan = yaml.safe_load((qa.ROOT / qa.PLAN).read_text(encoding="utf8"))
    expected = qa.independent_candidates(plan)
    assert len(expected) == 43 and expected == qa.independent_candidates(plan)
    assert {name: sum(r["family"] == name for r in expected) for name in qa.FAMILIES} == dict(zip(qa.FAMILIES, qa.COUNTS))
    plan["families"][0]["expected_candidates"] = 2
    with pytest.raises(qa.VerificationError):
        qa.independent_candidates(plan)


@pytest.mark.parametrize("fault", [None, "order", "rank", "finalists", "missing"])
def test_full_ranking_and_family_finalists(tmp_path, fault):
    summaries = []
    for family, count in zip(qa.FAMILIES, qa.COUNTS):
        for i in range(count):
            summaries.append({"configuration_id": f"{family}_{i:03d}", "family": family,
                              "macro_video_f1": 0.5 + (i % 2) * 0.1,
                              "macro_video_recall": 0.7 + (i % 3) * 0.01,
                              "macro_video_count_mae": float(i % 4), "detector_seconds": float(100 - i)})
    order = sorted(summaries, key=lambda r: (-r["macro_video_f1"], -r["macro_video_recall"], r["macro_video_count_mae"], r["configuration_id"]))
    ranked = [{**r, "rank": i + 1} for i, r in enumerate(order)]
    finalists = [r for family in qa.FAMILIES for r in [row for row in ranked if row["family"] == family][:2]]
    if fault == "order":
        ranked[0], ranked[1] = ranked[1], ranked[0]
    elif fault == "rank":
        ranked[0]["rank"] = 99
    elif fault == "finalists":
        finalists = finalists[:-1]
    elif fault == "missing":
        ranked.pop()
    dump_csv(tmp_path / "ranking.csv", ranked)
    dump_json(tmp_path / "family_finalists.json", finalists)
    files = {name: (tmp_path / name).read_bytes() for name in ("ranking.csv", "family_finalists.json")}
    if fault:
        with pytest.raises(qa.VerificationError):
            qa.verify_ranking(files, summaries, qa.Audit())
    else:
        ids = qa.verify_ranking(files, summaries, qa.Audit())
        assert len(ids) == 11 and len(set(ids)) == 11


@pytest.mark.parametrize("fault", [None, "grade", "data", "metric", "seed", "ram", "time", "guard", "parent_hash", "parent_file", "failure_hash", "failure_status", "extra_field"])
def test_operational_plan_authenticates_parent_and_allows_only_explicit_guard_revision(tmp_path, monkeypatch, fault):
    parent = yaml.safe_load((qa.ROOT / qa.LEGACY_PLAN).read_text(encoding="utf8"))
    plan = synthetic_operational_plan(tmp_path, parent, monkeypatch)
    if fault == "grade":
        plan["families"][1]["search_space"]["morph_iterations"] = [1, 2]
    elif fault == "data":
        plan["input"]["sample_hash"] = "e" * 64
    elif fault == "metric":
        plan["evaluation"]["center_gate_px"] = 20
    elif fault == "seed":
        plan["run"]["seed"] = 123
    elif fault == "ram":
        plan["budget"]["max_rss_mb"] = 4096
    elif fault == "time":
        plan["budget"]["wall_seconds_limit"] = 3600
    elif fault == "guard":
        plan["budget"]["max_predictions_per_frame"] = 307201
    elif fault == "parent_hash":
        plan["operational_revision"]["parent_plan_canonical_sha256"] = "f" * 64
    elif fault == "parent_file":
        changed = copy.deepcopy(parent)
        changed["families"][0]["params"]["threshold_value"] = 217
        dump_json(tmp_path / qa.LEGACY_PLAN, changed)
    elif fault == "failure_hash":
        plan["operational_revision"]["failed_batch_manifest"]["sha256"] = "f" * 64
    elif fault == "failure_status":
        path = Path(plan["operational_revision"]["failed_candidate_manifest"]["path"])
        dump_json(path, {"status": "complete"})
        changed_hash = digest(path)
        monkeypatch.setattr(qa, "FAILED_MANIFEST_HASHES", {**qa.FAILED_MANIFEST_HASHES, "failed_candidate_manifest": changed_hash})
        plan["operational_revision"]["failed_candidate_manifest"]["sha256"] = changed_hash
    elif fault == "extra_field":
        plan["unregistered"] = "scientific change"
    dump_json(tmp_path / qa.PLAN, plan)
    if fault:
        with pytest.raises(qa.VerificationError):
            qa.authenticated_plan(tmp_path, tmp_path / qa.PLAN, qa.Audit())
    else:
        actual, lineage = qa.authenticated_plan(tmp_path, tmp_path / qa.PLAN, qa.Audit())
        assert actual == plan and lineage["scientific_contract_identical_to_parent"] is True
        assert qa.independent_candidates(plan) == qa.independent_candidates(parent)
        legacy, history = qa.authenticated_plan(tmp_path, tmp_path / qa.LEGACY_PLAN, qa.Audit())
        assert legacy == parent and history["revision"] == "original_v1"


def test_cannot_pass_unregistered_plan_filename(tmp_path):
    with pytest.raises(qa.VerificationError, match="canonical"):
        qa.authenticated_plan(tmp_path, tmp_path / "unregistered.yaml", qa.Audit())
