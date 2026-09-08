from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from src.evaluation.detection import aggregate_frame_metrics, evaluate_frame
from src.experiments.config import config_hash
from src.experiments.detection_search import summarize_candidate
from src.experiments import detection_validation as validation


EVALUATION = {"protocol_id": "center_distance_v3_individuals_ignore_clusters_10px",
              "class_policy": "individuals_ignore_clusters", "center_gate_px": 10,
              "sensitivity_gates_px": [15, 20]}
COUNTS = {"14": 1, "19": 2, "36": 3, "52": 4}
ROOT = Path(__file__).resolve().parents[2]


def video_rows(ident="a", counts=None, missed_video=None):
    counts = counts or COUNTS
    result = []
    for vid, frames in counts.items():
        metric = evaluate_frame([] if vid == missed_video else [(0, 0, 0)], [(0, 0, 0)], video_id=vid, detection_ms=1.0)
        row = aggregate_frame_metrics([metric] * frames, video_id=vid)
        row.update(configuration_id=ident, evaluation_protocol_id=EVALUATION["protocol_id"],
                   **{k: v for k, v in EVALUATION.items() if k != "protocol_id"},
                   split="val", status="complete", frame_coverage_verified=True)
        result.append(row)
    return result


def candidate(ident="a", **kwargs):
    return validation.summarize_validation_candidate(video_rows(ident, **kwargs), kwargs.get("counts", COUNTS))


def test_validation_uses_equal_video_weight_with_unequal_frame_counts():
    summary = candidate(missed_video="52")
    assert summary["n_videos"] == 4
    assert summary["frames_total"] == 10
    assert summary["macro_video_f1"] == 0.75
    assert summary["macro_video_f1"] != 6 / 10
    assert summary["macro_video_count_mae"] == 0.25
    assert summary["interpretation"] == validation.VALIDATION_INTERPRETATION
    for suffix in ("", "_at_15px", "_at_20px"):
        assert summary["macro_video_f1" + suffix] == 0.75
        assert summary["macro_video_secondary_all_objects_f1" + suffix] == 0.75
        assert summary["count_evaluated_frames" + suffix] == 10


@pytest.mark.parametrize("change", [
    "missing_video", "duplicate_video", "test_video", "different_candidate", "missing_certificate",
    "false_certificate", "wrong_split", "failed", "incomplete_frames", "unannotated",
    "wrong_gate", "missing_secondary", "bad_arithmetic", "nonfinite", "negative_frames",
    "duplicate_normalized_expected_id",
])
def test_validation_summary_rejects_incomplete_or_inconsistent_input(change):
    rows, counts = video_rows(), dict(COUNTS)
    if change == "missing_video": rows.pop()
    elif change == "duplicate_video": rows[1] = copy.deepcopy(rows[0])
    elif change == "test_video": rows[0]["video_id"] = "24"
    elif change == "different_candidate": rows[0]["configuration_id"] = "b"
    elif change == "missing_certificate": rows[0].pop("frame_coverage_verified")
    elif change == "false_certificate": rows[0]["frame_coverage_verified"] = False
    elif change == "wrong_split": rows[0]["split"] = "train"
    elif change == "failed": rows[0]["status"] = "failed"
    elif change == "incomplete_frames": rows[0]["frames_total"] = 0
    elif change == "unannotated": rows[0]["frames_unannotated"] = 1
    elif change == "wrong_gate": rows[0]["center_gate_px"] = 15
    elif change == "missing_secondary": rows[0].pop("secondary_all_objects_tp_at_20px")
    elif change == "bad_arithmetic": rows[0]["tp_at_15px"] += 1
    elif change == "nonfinite": rows[0]["f1"] = float("nan")
    elif change == "negative_frames": counts["14"] = -1
    else: counts[14] = 1
    with pytest.raises(ValueError):
        validation.summarize_validation_candidate(rows, counts)


def test_ranking_has_predeclared_ties_and_ignores_timing_and_sensitivity():
    a, b = candidate("a"), candidate("b")
    b["macro_video_detection_ms_mean"] = 0
    a["macro_video_detection_ms_mean"] = 999999
    b["macro_video_f1_at_15px"] = 1
    a["macro_video_f1_at_15px"] = 0
    def order():
        return [r["configuration_id"] for r in validation.rank_validation_candidates([b, a], ["a", "b"])]
    assert order() == ["a", "b"]
    a["macro_video_count_mae"] = 0.1
    assert order() == ["b", "a"]
    b["macro_video_recall"] = 0.9
    assert order() == ["a", "b"]
    a["macro_video_f1"] = a["macro_video_f1_individuals_center_10px"] = 0.8
    assert order() == ["b", "a"]


@pytest.mark.parametrize("change", ["subset", "duplicate", "unexpected", "incomplete", "nonfinite",
                                    "unequal_plans", "bad_counts", "missing_gate", "bad_alias", "test_scope"])
def test_ranking_requires_two_complete_consistent_candidates(change):
    a, b = candidate("a"), candidate("b")
    rows = [a, b]
    if change == "subset": rows.pop()
    elif change == "duplicate": rows = [a, copy.deepcopy(a)]
    elif change == "unexpected": b["configuration_id"] = "c"
    elif change == "incomplete": b["complete"] = False
    elif change == "nonfinite": b["macro_video_secondary_all_objects_recall_at_20px"] = float("inf")
    elif change == "unequal_plans": b = candidate("b", counts={"14": 2, "19": 2, "36": 3, "52": 4}); rows[1] = b
    elif change == "bad_counts": b["fp"] += 1
    elif change == "missing_gate": b.pop("count_evaluated_frames_at_20px")
    elif change == "bad_alias": b["macro_video_f1_individuals_center_10px"] = 0.9
    else: b["interpretation"] = "independent_test"
    with pytest.raises(ValueError):
        validation.rank_validation_candidates(rows, ["a", "b"])


@pytest.fixture
def declared_plan():
    return yaml.safe_load((ROOT / "configs/detection/threshold/validation_v3.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("section", "key", "value"), [
    ("protocol", "validation_ids", [14, 19, 36, 24]),
    ("protocol", "test_ids_blocked", [24, 38, 47]),
    ("input", "expected_frames", {14: 1470, 19: 1470, 36: 1470, 52: 1470}),
    ("input", "resize", True), ("input", "ground_truth_available_to_detector", True),
    ("input", "label_format", "guess"), ("input", "read_mode", "sampled"),
    ("evaluation", "center_gate_px", 15), ("evaluation", "sensitivity_gates_px", [20]),
    ("selection", "timing_used_for_ranking", True), ("selection", "sensitivity_used_for_ranking", True),
    ("selection", "video_weighting", "frame_count"), ("selection", "hypothesis_tests", True),
    ("selection", "tie_breakers", ["configuration_id_asc"]),
    ("budget", "batch_soft_wall_seconds", 1801), ("budget", "max_predictions_per_frame", 2001),
    ("run", "split", "test"), ("run", "seed", 123), ("run", "reset_detector_per_video", False),
    ("refinement", "candidate_ids", ["t218_o0_c2", "t219_o0_c2"]),
    ("refinement", "manifest_sha256", "invalid"),
])
def test_plan_rejects_unregistered_drift_before_any_references(declared_plan, section, key, value):
    declared_plan[section][key] = value
    with pytest.raises(ValueError):
        validation._rules(declared_plan)


def test_plan_expected_counts_and_parameter_hashes_are_fixed(declared_plan):
    assert sum(validation._rules(declared_plan).values()) == 5850
    declared_plan["refinement"]["parameter_hashes"]["t219_o0_c2"] = "0" * 64
    with pytest.raises(ValueError, match="parameters"):
        validation._rules(declared_plan)


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding="utf-8")


def _csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifacts(directory, names):
    return ({name: str(directory / name) for name in names}, {name: _sha(directory / name) for name in names})


@pytest.fixture(scope="module")
def synthetic_graph(tmp_path_factory):
    """Synthetic metadata chain; the separately tested coarse loader is stubbed.

    All 117 refinement manifests, their CSVs, snapshots and selection artifacts
    remain real files checked by this module. No dataset source exists here.
    """
    root = tmp_path_factory.mktemp("validation_metadata")
    plan = yaml.safe_load((ROOT / "configs/detection/threshold/validation_v3.yaml").read_text(encoding="utf-8"))
    path = root / "configs/detection/threshold/validation_v3.yaml"
    splits = root / plan["protocol"]["splits_config"]
    splits.parent.mkdir(parents=True)
    splits.write_text(yaml.safe_dump({"fixed_split": {"train": list(map(int, validation._TRAIN)),
                      "val": [14, 19, 36, 52], "test": [24, 38, 47, 54]}}), encoding="utf-8")
    inventory = root / plan["protocol"]["inventory"]
    _csv(inventory, [{"video_id": v, "split": "val", "total_frames": n,
                     "annotated_frames": n, "annotation_status": "complete"}
                    for v, n in validation.VALIDATION_EXPECTED_FRAMES.items()])
    plan["protocol"].update(splits_sha256=_sha(splits), inventory_sha256=_sha(inventory))
    batch_dir, source_dir = root / "data/tests/refinement", root / "data/derived/parents"
    batch_path, qa_path = batch_dir / "manifest.json", batch_dir.parent / "verification.json"
    refs = {}
    for name in ("coarse_manifest", "derived_plan", "coarse_verification", "sample_manifest"):
        p = source_dir / f"{name}.json"
        content = {"sample_hash": "a" * 64, "video_ids": list(validation._TRAIN),
                   "selections": {v: {"master": list(range(48))} for v in validation._TRAIN}} if name == "sample_manifest" else {}
        _json(p, content); refs[name] = {"path": str(p), "sha256": _sha(p)}
    original = {"plan_id": "synthetic", "evaluation": EVALUATION}
    planned, summaries, children = [], [], []
    snapshot = {"mode": "shared_batch", "per_candidate_recheck": False,
                "captured_at": "2026-09-08T00:00:00+00:00", "process_id": 1,
                "origin_batch_manifest": str(batch_path)}
    snapshot["snapshot_sha256"] = config_hash({"repo_root": str(root.resolve()), "captured_at": snapshot["captured_at"],
                "process_id": 1, "git_sha": "synthetic", "git_dirty": False, "source_hash": "c" * 64,
                "environment": {"python": "synthetic"}}, 64)
    metric_templates = {}
    for kind, predictions in {"best": [(0, 0, 0), (50, 0, 0)],
                              "second": [(0, 0, 0), (50, 0, 0), (100, 0, 0)],
                              "other": [(0, 0, 0)]}.items():
        metric = evaluate_frame(predictions, [(0, 0, 0), (50, 0, 0)], detection_ms=1.0)
        metric_templates[kind] = aggregate_frame_metrics([metric] * 48)
    combinations = [(t, 0, 2) for t in range(193, 240)] + [(t, 0, 1) for t in range(209, 240)] + [(t, 1, 2) for t in range(185, 224)]
    pairs = [[v, i] for v in validation._TRAIN for i in range(48)]
    for number, (threshold, opening, closing) in enumerate(combinations, 1):
        ident = f"t{threshold}_o{opening}_c{closing}"
        params = {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
                  "min_area": 3, "max_area": 300, "threshold_value": threshold,
                  "morph_iterations": opening, "close_iterations": closing}
        registered = {"configuration_id": ident, "method": "threshold", "params": params,
                      "evaluation": EVALUATION, "run": {"split": "train"}, "provenance": {}}
        planned.append(registered)
        config = copy.deepcopy(registered)
        config["provenance"] = {"batch_id": "synthetic_batch", "sample_mode": "master",
                                "sample_hash": "a" * 64, "search_plan_hash": config_hash(original, 64),
                                "sample_manifest_sha256": refs["sample_manifest"]["sha256"]}
        kind = "best" if ident == "t219_o0_c2" else "second" if ident == "t218_o0_c2" else "other"
        video_summaries = []
        for v in validation._TRAIN:
            row = copy.deepcopy(metric_templates[kind])
            row.update(video_id=v, configuration_id=ident, evaluation_protocol_id=EVALUATION["protocol_id"],
                       **{k: value for k, value in EVALUATION.items() if k != "protocol_id"})
            video_summaries.append(row)
        summary = summarize_candidate(video_summaries, validation._TRAIN, 48)
        directory = root / "data/tests/candidates" / ident
        summary.update(mode="refine", plan_hash=config_hash(original, 64), sample_hash="a" * 64,
                       run_id=f"synthetic_{ident}", manifest_path=str(directory / "manifest.json"))
        summaries.append(summary)
        _json(directory / "summary.json", summary)
        _csv(directory / "video_summary.csv", video_summaries)
        _csv(directory / "frame_metrics.csv", [{"video_id": v, "frame": i, "configuration_id": ident,
              "evaluation_protocol_id": EVALUATION["protocol_id"], "sample_hash": "a" * 64, "annotated": True}
             for v, i in pairs])
        _csv(directory / "detections.csv", [{"synthetic": True}])
        artifacts, hashes = _artifacts(directory, ["summary.json", "video_summary.csv", "frame_metrics.csv", "detections.csv"])
        child = {"run_id": f"synthetic_{ident}", "status": "complete", "git_dirty": False, "git_sha": "synthetic", "source_hash": "c" * 64,
                 "environment": {"python": "synthetic"}, "provenance_capture": snapshot,
                 "config": config, "config_hash": config_hash(config), "summary": summary,
                 "artifacts": artifacts, "artifact_hashes": hashes}
        _json(directory / "manifest.json", child)
        children.append({"path": str(directory / "manifest.json"), "sha256": _sha(directory / "manifest.json")})
        _json(batch_dir / f"candidate_{number:03d}.json", summary)
    ranked = validation.rank_candidates(summaries, [r["configuration_id"] for r in planned])
    for rank, row in enumerate(ranked, 1): row["rank"] = rank
    _json(batch_dir / "planned_candidates.json", planned); _json(batch_dir / "planned_frames.json", pairs)
    _json(batch_dir / "finalists.json", ranked[:2])
    _csv(batch_dir / "candidate_metrics.csv", summaries); _csv(batch_dir / "ranking.csv", ranked)
    names = [f"candidate_{i:03d}.json" for i in range(1, 118)] + ["planned_candidates.json", "planned_frames.json", "finalists.json", "candidate_metrics.csv", "ranking.csv"]
    artifacts, hashes = _artifacts(batch_dir, names)
    config = {"plan": original, "refinement_provenance": refs}
    batch = {"run_id": "synthetic_batch", "status": "complete", "git_dirty": False, "git_sha": "synthetic",
             "source_hash": "c" * 64, "environment": {"python": "synthetic"}, "provenance_capture": snapshot,
             "provenance_verification": {"status": "verified", "scope": "batch_end_before_ranking", "snapshot_sha256": snapshot["snapshot_sha256"]},
             "config": config, "config_hash": config_hash(config), "candidate_manifests": children,
             "artifacts": artifacts, "artifact_hashes": hashes,
             "summary": {"mode": "refine", "complete": True, "selection_allowed": True, "completed_candidates": 117,
                         "frames_per_candidate": 576, "frame_evaluations": 67392, "plan_hash": config_hash(original, 64),
                         "sample_hash": "a" * 64, "refinement_execution_hash": "d" * 64}}
    _json(batch_path, batch)
    qa = {"status": "passed", "ranking_complete_match": True, "batch_manifest": str(batch_path),
          "batch_manifest_sha256": _sha(batch_path), "git_sha_of_verified_runs": "synthetic",
          "source_hash_of_verified_runs": "c" * 64, "plan_hash": config_hash(original, 64),
          "sample_hash": "a" * 64, "refinement_execution_hash": "d" * 64,
          "candidates": 117, "frames_per_video": 48, "frames_per_candidate": 576, "frame_evaluations": 67392,
          "videos": list(validation._TRAIN), "candidate_expansion_matches_registered_rule": True,
          "independent_top2": ["t219_o0_c2", "t218_o0_c2"]}
    _json(qa_path, qa)
    plan["refinement"].update(manifest=str(batch_path), manifest_sha256=_sha(batch_path),
                              finalists_sha256=_sha(batch_dir / "finalists.json"), verification=str(qa_path), verification_sha256=_sha(qa_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    return {"root": root, "path": path, "batch_path": batch_path, "qa_path": qa_path, "registered": planned}


@pytest.fixture
def graph(synthetic_graph, monkeypatch):
    monkeypatch.setattr(validation, "REPOSITORY_ROOT", synthetic_graph["root"])
    monkeypatch.setattr(validation, "load_refinement_candidates", lambda *args: (copy.deepcopy(synthetic_graph["registered"]), {"synthetic_coarse_chain": True}))
    before = {p: p.read_bytes() for p in synthetic_graph["root"].rglob("*") if p.is_file()}
    yield synthetic_graph
    for path, content in before.items():
        if path.read_bytes() != content: path.write_bytes(content)


def _refresh_chain(graph, batch, child_index=None, child=None):
    if child is not None:
        child_path = Path(batch["candidate_manifests"][child_index]["path"])
        child["config_hash"] = config_hash(child["config"])
        child["artifact_hashes"] = {k: _sha(Path(p)) for k, p in child["artifacts"].items()}
        _json(child_path, child)
        batch["candidate_manifests"][child_index]["sha256"] = _sha(child_path)
    batch["artifact_hashes"] = {k: _sha(Path(p)) for k, p in batch["artifacts"].items()}
    _json(graph["batch_path"], batch)
    qa = json.loads(graph["qa_path"].read_text()); qa["batch_manifest_sha256"] = _sha(graph["batch_path"])
    _json(graph["qa_path"], qa)
    plan = yaml.safe_load(graph["path"].read_text())
    plan["refinement"].update(manifest_sha256=_sha(graph["batch_path"]), verification_sha256=_sha(graph["qa_path"]))
    graph["path"].write_text(yaml.safe_dump(plan), encoding="utf-8")


def test_loader_verifies_complete_synthetic_chain_without_sources(graph):
    plan, finalists, provenance = validation.load_validation_plan(graph["path"])
    assert [r["configuration_id"] for r in finalists] == ["t219_o0_c2", "t218_o0_c2"]
    assert len(provenance["exact_frame_plan"]) == 5850
    assert len({tuple(pair) for pair in provenance["exact_frame_plan"]}) == 5850
    assert provenance["exact_frame_plan"][-1] == ["52", 1439]
    assert provenance["plan_hash"] == config_hash(plan, 64)
    assert len(provenance["training_finalist_manifests"]) == 2
    assert not (graph["root"] / "data/sources").exists()


@pytest.mark.parametrize("change", ["missing_candidate", "duplicate_pair", "changed_parameter", "ranking", "hash", "snapshot"])
def test_loader_rejects_corrupted_graph_even_with_refreshed_outer_hashes(graph, change):
    batch = json.loads(graph["batch_path"].read_text())
    child_path = Path(batch["candidate_manifests"][0]["path"])
    child = json.loads(child_path.read_text())
    if change == "missing_candidate":
        batch["candidate_manifests"].pop(); _refresh_chain(graph, batch)
    elif change == "duplicate_pair":
        p = Path(child["artifacts"]["frame_metrics.csv"])
        with p.open(newline="") as stream: rows = list(csv.DictReader(stream))
        rows[1] = rows[0].copy(); _csv(p, rows); _refresh_chain(graph, batch, 0, child)
    elif change == "changed_parameter":
        child["config"]["params"]["threshold_value"] = 40; _refresh_chain(graph, batch, 0, child)
    elif change == "ranking":
        p = Path(batch["artifacts"]["ranking.csv"])
        with p.open(newline="") as stream: rows = list(csv.DictReader(stream))
        rows[0], rows[1] = rows[1], rows[0]; _csv(p, rows); _refresh_chain(graph, batch)
    elif change == "hash":
        child_path.write_text(child_path.read_text() + "\n")
    else:
        child["provenance_capture"]["snapshot_sha256"] = "f" * 64; _refresh_chain(graph, batch, 0, child)
    with pytest.raises(ValueError):
        validation.load_validation_plan(graph["path"])


def test_source_metadata_path_and_duplicate_yaml_keys_are_rejected(graph):
    with pytest.raises(ValueError, match="source access"):
        validation._MetadataInputs().verify(graph["root"] / "data/sources/forbidden.csv")
    text = graph["path"].read_text()
    graph["path"].write_text(text + "\nstage: test\n")
    with pytest.raises(ValueError, match="duplicate YAML"):
        validation.load_validation_plan(graph["path"])
