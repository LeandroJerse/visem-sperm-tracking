from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from script.detection.test import refine_classical as cli
from src.detection.base import Detection
from src.detection.io import CSV_FIELDS, detection_to_row
from src.evaluation.detection import DetectionEvaluator
from src.experiments import classical_detection_comparison as comparison
from src.experiments import classical_detection_refinement as refinement
from src.experiments import runs
from src.experiments.config import canonical_json, config_hash, load_config
from src.experiments.detection_sample import TRAIN_IDS


@pytest.fixture
def plan():
    return refinement.load_plan(refinement.REPOSITORY_ROOT / refinement.DEFAULT_PLAN)


@pytest.fixture
def parents(plan):
    # Fixed identities of the authenticated search finalists; no metrics or
    # pixels are opened by these pure protocol/constructor tests.
    ids = ["otsu_v1_004", "otsu_v1_003", "adaptive_threshold_v1_002", "adaptive_threshold_v1_008", "hybrid_threshold_v1_002", "hybrid_threshold_v1_001", "blob_v1_003", "blob_v1_002", "watershed_v1_005", "watershed_v1_002"]
    old = load_config(refinement.REPOSITORY_ROOT / plan["parents"]["comparison_plan"]["path"])
    options = {row["configuration_id"]: row for row in comparison.expand_candidates(old)}
    return [copy.deepcopy(options[key]) for key in ids]


def test_decimal_neighborhood_counts_dedup_and_all_parent_lineages(plan, parents):
    before = copy.deepcopy(parents)
    candidates = refinement.expand_candidates(plan, parents)
    assert parents == before
    assert len(candidates) == 45
    assert {family: sum(row["family"] == family for row in candidates) for family in refinement.FAMILIES} == plan["expected_by_family"]
    assert sum(len(row["refinement_lineage"]) for row in candidates) == 51
    assert sum(origin["axis"] is None for row in candidates for origin in row["refinement_lineage"]) == 10
    assert len({canonical_json({"method": row["method"], "params": row["params"]}) for row in candidates}) == 45
    assert all(row["family"] != "threshold" for row in candidates)
    for row in candidates:
        for origin in row["refinement_lineage"]:
            parent = next(item for item in parents if item["configuration_id"] == origin["parent_configuration_id"])
            changed = [key for key in row["params"] if row["params"][key] != parent["params"][key]]
            assert changed == ([] if origin["axis"] is None else [origin["axis"]])
    assert {row["params"]["clip_limit"] for row in candidates if row["family"] == "hybrid_threshold"} == {0.5, 1, 1.5}
    assert {row["params"]["dist_ratio"] for row in candidates if row["family"] == "watershed"} == {0.3, 0.4, 0.5}
    # No clipping adds another parent lineage at the lower boundary.
    assert all(not (origin["axis"] == "morph_iterations" and origin["delta"] == -1 and row["params"]["morph_iterations"] == 0) for row in candidates if row["family"] == "otsu" for origin in row["refinement_lineage"] if next(p for p in parents if p["configuration_id"] == origin["parent_configuration_id"])["params"]["morph_iterations"] == 0)


@pytest.mark.parametrize("index", range(45))
def test_every_resolved_constructor_accepts_readonly_synthetic_pixels(plan, parents, index):
    candidate = refinement.expand_candidates(plan, parents)[index]
    pixels = np.zeros((48, 48, 3), dtype=np.uint8)
    pixels[15:21, 15:21] = 240
    pixels.flags.writeable = False
    before = pixels.copy()
    detector = refinement.build_detector(candidate["method"], params=candidate["params"])
    detected = detector.detect(pixels)
    assert np.array_equal(pixels, before)
    assert all(np.isfinite([row.cx, row.cy, row.w, row.h]).all() for row in detected)


@pytest.mark.parametrize("fault", ["extra_plan", "extra_selection", "threshold", "test", "seed_bool", "thread_bool", "area", "axis", "odd", "cap", "cutoff", "float_count", "extra_param", "boolean_param", "even_kernel", "parent_duplicate", "parent_order", "parent_sha", "qa_sha", "parent_path", "evaluation"])
def test_refinement_rejects_unregistered_protocol_inputs(plan, parents, fault):
    if fault == "extra_plan": plan["extra"] = 1
    elif fault == "extra_selection": plan["selection"]["score"] = "speed"
    elif fault == "threshold": parents[0]["family"] = "threshold"
    elif fault == "test": plan["train_ids"][0] = 24
    elif fault == "seed_bool": plan["run"]["seed"] = True
    elif fault == "thread_bool": plan["run"]["opencv_threads"] = True
    elif fault == "area": parents[0]["params"]["min_area"] = 2
    elif fault == "axis": plan["neighborhood"][0]["axes"][0]["step"] = 2
    elif fault == "odd": plan["neighborhood"][0]["axes"][0]["odd"] = 0
    elif fault == "cap": plan["budget"]["max_predictions_per_frame"] = 2000
    elif fault == "cutoff": plan["budget"]["wall_seconds_limit"] = 7200
    elif fault == "float_count": plan["expected_candidates"] = 45.0
    elif fault == "extra_param": parents[0]["params"]["secret_override"] = 1
    elif fault == "boolean_param": parents[0]["params"]["morph_iterations"] = True
    elif fault == "even_kernel": parents[0]["params"]["blur"] = 2
    elif fault == "parent_duplicate": parents[1] = copy.deepcopy(parents[0])
    elif fault == "parent_order": parents.reverse()
    elif fault == "parent_sha": plan["parents"]["search_manifest"]["sha256"] = "0" * 64
    elif fault == "qa_sha": plan["parents"]["search_qa"]["sha256"] = "0" * 64
    elif fault == "parent_path": plan["parents"]["finalists"]["path"] = "../outside.json"
    elif fault == "evaluation": plan["evaluation"]["center_gate_px"] = 15
    with pytest.raises(ValueError):
        refinement.expand_candidates(plan, parents)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e309}'])
def test_strict_json_rejects_ambiguous_values(tmp_path, text):
    path = tmp_path / "invalid.json"; path.write_text(text)
    with pytest.raises(ValueError): refinement.read_json(path)


@pytest.mark.parametrize("text", ["kind: one\nkind: two\n", "kind: .nan\n", "kind: 2026-09-11\n"])
def test_strict_yaml_rejects_duplicate_nonfinite_and_date(tmp_path, text):
    path = tmp_path / "invalid.yaml"; path.write_text(text)
    with pytest.raises(ValueError): refinement.load_plan(path)


def test_source_inventory_authenticates_subset_but_allows_new_files(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    old = tmp_path / "src/old.py"; old.write_bytes(b"old\n")
    (tmp_path / "src/new.py").write_bytes(b"new\n")
    name = b"src/old.py"
    digest = hashlib.sha256(len(name).to_bytes(4, "big") + name + b"old\n").hexdigest()
    monkeypatch.setattr(refinement, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(refinement, "resolve_from_repository", lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value)
    monkeypatch.setattr(refinement.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"src/old.py\nREADME.md\n"))
    assert refinement._source_inventory({"git_sha": "1234567", "source_hash": digest}) == {str(old): refinement.sha256_file(old)}
    old.write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="aggregate"):
        refinement._source_inventory({"git_sha": "1234567", "source_hash": digest})


class Sample:
    video_ids = TRAIN_IDS
    sample_hash = "synthetic-only"
    def __init__(self, path):
        self.cache_dir = path
        path.mkdir()
        (path / "ground_truth.csv").write_text("header\n")
        self.manifest = {"videos": {}, "ground_truth": {"sha256": refinement.sha256_file(path / "ground_truth.csv")}}
        (path / "manifest.json").write_text(json.dumps(self.manifest))
    def indices(self, mode, video):
        return (0,) if mode == "benchmark" else tuple(range(48))
    def frames(self, mode):
        image = np.zeros((64, 64, 3), dtype=np.uint8); image.flags.writeable = False
        for video in self.video_ids:
            for frame in self.indices(mode, video):
                yield video, frame, image, (Detection(20.25, 20, 5, 5, class_id=0, object_id="a"), Detection(38, 20, 5, 5, class_id=2, object_id="b"), Detection(54, 54, 16, 16, class_id=1, object_id="cluster"))


class Detector:
    def reset(self): pass
    def detect(self, image):
        return [Detection(20, 20, 5, 5), Detection(38, 20, 5, 5), Detection(21, 20, 3, 3), Detection(54, 54, 3, 3)]


@pytest.fixture
def setup(plan, parents, monkeypatch, tmp_path):
    candidates = refinement.expand_candidates(plan, parents)
    # Ten repeated parents exercise five-family selection plus exact parity.
    candidates = [row for row in candidates if any(origin["axis"] is None for origin in row["refinement_lineage"])]
    assert len(candidates) == 10
    monkeypatch.setattr(refinement, "expand_candidates", lambda *args: copy.deepcopy(candidates))
    monkeypatch.setattr(refinement, "build_detector", lambda *a, **k: Detector())
    monkeypatch.setattr(refinement, "verify_parent_inputs", lambda bundle: None)
    original_safe = refinement._safe_path
    monkeypatch.setattr(refinement, "_safe_path", lambda value, **kwargs: original_safe(value, parent=kwargs.get("parent", tmp_path)) if Path(value).is_absolute() else original_safe(value, **kwargs))
    for module in (refinement, runs):
        monkeypatch.setattr(module, "_git_dirty", lambda _: False)
        monkeypatch.setattr(module, "_source_hash", lambda _: "synthetic-stable")
    monkeypatch.setattr(runs, "_git_sha", lambda _: "1234567")
    monkeypatch.setattr(runs, "environment_snapshot", lambda: {"synthetic": True})
    sample = Sample(tmp_path / "cache")
    plan["input"].update(cache_manifest_sha256=refinement.sha256_file(sample.cache_dir / "manifest.json"), sample_hash=sample.sample_hash)
    raw, metrics = [], []
    evaluator = DetectionEvaluator(center_gate_px=10, class_policy="individuals_ignore_clusters", sensitivity_gates_px=[15, 20])
    for video, frame, image, gt in sample.frames("master"):
        predictions = Detector().detect(image)
        row = evaluator.add_frame(predictions, gt, video_id=video, frame=frame, annotated=True, detection_ms=1)
        row.update(evaluation_protocol_id=refinement.PROTOCOL, sample_hash=sample.sample_hash)
        metrics.append(row)
        raw.extend(detection_to_row(video, frame, "detection", item) for item in predictions)
        raw.extend(detection_to_row(video, frame, "manual", item) for item in gt)
    for parent in parents:
        directory = tmp_path / "historical" / parent["configuration_id"]; directory.mkdir(parents=True)
        refinement.write_csv_exclusive(directory / "detections.csv", raw, CSV_FIELDS)
        rows = [{**row, "family": parent["family"], "configuration_id": parent["configuration_id"]} for row in metrics]
        refinement.write_csv_exclusive(directory / "frame_metrics.csv", rows)
        artifacts = {name: str(directory / name) for name in ("detections.csv", "frame_metrics.csv")}
        manifest = {"artifacts": artifacts, "artifact_hashes": {name: refinement.sha256_file(path) for name, path in artifacts.items()}}
        refinement.write_json_exclusive(directory / "manifest.json", manifest)
        parent["parent_manifest"] = {"path": str(directory / "manifest.json"), "sha256": refinement.sha256_file(directory / "manifest.json")}
        parent.update(parent_source_hash="synthetic-old", parent_git_sha="7654321")
    bundle = {"parents": parents, "historical_reference": {"configuration_id": "t218_o0_c2_reference_v1", "reexecuted": False}, "authentication": {"synthetic": True}}
    return plan, sample, bundle, tmp_path / "runs"


def _run(setup, mode="refinement_smoke", **kwargs):
    plan, sample, parents, output = setup
    return refinement.run_batch(plan, sample, mode, parents=parents, cache_validation_seconds=0.01, parent_validation_seconds=0.01, output_root=output, **kwargs)


def _qa(smoke):
    data = refinement.read_json(smoke)
    path = smoke.parent.parent / "synthetic_qa.json"
    refinement.write_json_exclusive(path, {"status": "passed", "mode": "refinement_smoke", "manifest": str(smoke), "manifest_sha256": refinement.sha256_file(smoke), "plan_hash": data["summary"]["plan_hash"], "candidates": 10, "frames_per_candidate": 12, "frame_evaluations": 120})
    return path


def test_complete_synthetic_smoke_refinement_parity_lineage_and_selection(setup):
    smoke = _run(setup)
    assert not smoke.with_name("ranking.csv").exists()
    output = _run(setup, "refinement", smoke_manifest=smoke, smoke_qa=_qa(smoke))
    manifest = refinement.read_json(output)
    assert manifest["stage"] == "refinement"
    assert manifest["summary"]["frame_evaluations"] == 5760
    assert manifest["summary"]["parent_parity_controls"] == 10
    assert manifest["summary"]["selection_allowed"] is True
    assert manifest["summary"]["historical_threshold_reference_reexecuted"] is False
    assert manifest["summary"]["validation_released"] is False
    assert manifest["summary"]["promotion_allowed"] is False
    finalists = refinement.read_json(output.with_name("family_finalists.json"))
    assert len(finalists) == 10 and all(row["family"] != "threshold" for row in finalists)
    assert all(row["macro_video_f1"] == pytest.approx(0.8) for row in finalists)
    parity = refinement.read_json(output.with_name("parent_parity.json"))
    assert len(parity) == 10 and all(row["status"] == "passed" and row["frames_compared"] == 576 for row in parity)
    for record in manifest["candidate_manifests"]:
        child = refinement.read_json(Path(record["path"]))
        assert child["stage"] == child["config"]["run"]["stage"] == "refinement"
        assert child["config"]["provenance"]["sample_mode"] == "master"
        assert child["config"]["refinement_lineage"]
        assert child["summary"]["tp"] == 1152 and child["summary"]["fp"] == 576 and child["summary"]["n_predictions_ignored"] == 576


@pytest.mark.parametrize("fault", ["missing", "duplicate", "detector", "excess_predictions", "changed_cache", "changed_source", "parity", "rss", "storage", "export"])
def test_operational_or_integrity_failure_preserves_receipt_without_ranking(setup, monkeypatch, fault):
    plan, sample, parents, output = setup
    if fault in {"missing", "duplicate"}:
        original = sample.frames
        def broken(mode):
            rows = list(original(mode))
            yield from rows[:-1] if fault == "missing" else [*rows[:-1], rows[0]]
        monkeypatch.setattr(sample, "frames", broken)
    elif fault == "detector": monkeypatch.setattr(Detector, "detect", lambda *a: (_ for _ in ()).throw(RuntimeError("synthetic detector failure")))
    elif fault == "excess_predictions": plan["budget"]["max_predictions_per_frame"] = 3
    elif fault == "changed_cache": (sample.cache_dir / "ground_truth.csv").write_text("changed\n")
    elif fault == "changed_source":
        values = iter(["synthetic-stable", "changed"])
        monkeypatch.setattr(runs, "_source_hash", lambda _: next(values))
    elif fault == "parity": monkeypatch.setattr(refinement, "check_parent_parity", lambda *a: (_ for _ in ()).throw(ValueError("synthetic parity mismatch")))
    elif fault == "rss":
        original = refinement.ResourceMonitor.summary
        monkeypatch.setattr(refinement.ResourceMonitor, "summary", lambda self: {**original(self), "ram_rss_peak_mb": None})
    elif fault == "storage": plan["budget"]["max_batch_artifact_mb"] = 0
    else:
        original = refinement.write_csv_exclusive
        def partial(path, rows, fields=None):
            if Path(path).name == "detections.csv":
                Path(path).write_bytes(b"preserved partial export\n")
                raise OSError("synthetic export failure")
            return original(path, rows, fields)
        monkeypatch.setattr(refinement, "write_csv_exclusive", partial)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        _run(setup)
    manifests = [refinement.read_json(path) for path in output.rglob("manifest.json")]
    batch = next(row for row in manifests if row["method"] == "classical_refinement")
    assert batch["status"] == "failed" and batch["selection_allowed"] is False
    assert not list(output.rglob("ranking.csv")) and not list(output.rglob("family_finalists.json"))
    if fault == "excess_predictions": assert "observed=4, limit=3" in batch["error"]
    if fault == "export": assert next(output.rglob("detections.csv")).read_bytes() == b"preserved partial export\n"


@pytest.mark.parametrize("fault", ["qa_failed", "qa_hash", "qa_mode", "qa_counts", "qa_float", "child_artifact", "batch_artifact", "plan", "source", "lineage"])
def test_refinement_rejects_incompatible_smoke_or_qa_before_any_new_run(setup, monkeypatch, fault):
    smoke = _run(setup); qa_path = _qa(smoke)
    if fault.startswith("qa_"):
        qa = refinement.read_json(qa_path)
        key, value = {"qa_failed": ("status", "failed"), "qa_hash": ("manifest_sha256", "0" * 64), "qa_mode": ("mode", "refinement"), "qa_counts": ("candidates", 9), "qa_float": ("candidates", 10.0)}[fault]
        qa[key] = value; qa_path.write_text(json.dumps(qa))
    elif fault == "child_artifact":
        child = refinement.read_json(smoke)["candidate_manifests"][0]["path"]
        Path(child).with_name("detections.csv").write_text("changed\n")
    elif fault == "batch_artifact": smoke.with_name("parents.json").write_text("changed\n")
    elif fault == "plan": setup[0]["plan_id"] = "changed"
    elif fault == "source": monkeypatch.setattr(refinement, "_source_hash", lambda _: "changed")
    else: setup[2]["parents"][0]["parent_source_hash"] = "changed"
    before = set(setup[3].rglob("manifest.json"))
    with pytest.raises(ValueError): _run(setup, "refinement", smoke_manifest=smoke, smoke_qa=qa_path)
    assert set(setup[3].rglob("manifest.json")) == before


def test_refinement_requires_both_smoke_and_qa_before_runs(setup):
    with pytest.raises(ValueError, match="smoke"):
        _run(setup, "refinement")
    assert not setup[3].exists()


def test_cli_dry_run_never_loads_sample_or_executes(plan, parents, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_parents", lambda unused: {"parents": parents})
    monkeypatch.setattr(cli, "load_refinement_sample", lambda *a: pytest.fail("sample opened"))
    monkeypatch.setattr(cli, "run_batch", lambda *a, **k: pytest.fail("experiment executed"))
    assert cli.main(["--mode", "refine", "--dry-run"]) is None
    report = json.loads(capsys.readouterr().out)
    assert report["candidate_count"] == 45 and report["frame_evaluations"] == 25920


@pytest.mark.parametrize("fault", ["status", "stage", "dirty", "count", "scope", "qa_status", "qa_mode", "qa_manifest", "qa_hash", "qa_plan", "qa_count", "qa_frames", "qa_parity", "capture"])
def test_parent_loader_rejects_unapproved_metadata_before_child_artifacts(plan, monkeypatch, fault):
    base = load_config(refinement.REPOSITORY_ROOT / plan["parents"]["comparison_plan"]["path"])
    path = refinement.REPOSITORY_ROOT / plan["parents"]["search_manifest"]["path"]
    search = {"status": "complete", "stage": "search", "git_dirty": False, "config": {"plan": base}, "summary": {"complete": True, "completed_candidates": 43, "frames_per_candidate": 576, "frame_evaluations": 24768, "validation_released": False}, "provenance_capture": {"snapshot_sha256": "synthetic"}, "provenance_verification": {"status": "verified", "snapshot_sha256": "synthetic"}}
    search["config_hash"] = config_hash(search["config"])
    qa = {"status": "passed", "mode": "search", "manifest": str(path), "manifest_sha256": refinement.SEARCH_SHA256, "plan_hash": refinement.COMPARISON_PLAN_HASH, "candidates": 43, "frames_per_candidate": 576, "historical_t218_parity": {"status": "passed"}}
    if fault == "status": search["status"] = "failed"
    elif fault == "stage": search["stage"] = "smoke"
    elif fault == "dirty": search["git_dirty"] = True
    elif fault == "count": search["summary"]["completed_candidates"] = 42
    elif fault == "scope": search["summary"]["validation_released"] = True
    elif fault == "qa_status": qa["status"] = "failed"
    elif fault == "qa_mode": qa["mode"] = "smoke"
    elif fault == "qa_manifest": qa["manifest"] = str(path.with_name("other.json"))
    elif fault == "qa_hash": qa["manifest_sha256"] = "0" * 64
    elif fault == "qa_plan": qa["plan_hash"] = "0" * 64
    elif fault == "qa_count": qa["candidates"] = 42
    elif fault == "qa_frames": qa["frames_per_candidate"] = 12
    elif fault == "qa_parity": qa["historical_t218_parity"]["status"] = "failed"
    else: search["provenance_verification"]["status"] = "failed"
    monkeypatch.setattr(refinement, "_pin", lambda *args: None)
    monkeypatch.setattr(refinement, "read_json", lambda filename: search if Path(filename) == path else qa)
    monkeypatch.setattr(refinement, "_artifacts", lambda *a: pytest.fail("unauthenticated parent artifacts consumed"))
    with pytest.raises(ValueError): refinement.load_parents(plan)


@pytest.mark.parametrize("fault", ["hash", "escaped", "duplicate", "missing_hash"])
def test_artifacts_require_contained_unique_paths_and_complete_hashes(tmp_path, fault):
    directory = tmp_path / "run"; directory.mkdir()
    target = directory / "data.csv"; target.write_bytes(b"synthetic\n")
    manifest = {"artifacts": {"data": str(target)}, "artifact_hashes": {"data": refinement.sha256_file(target)}}
    if fault == "hash": manifest["artifact_hashes"]["data"] = "0" * 64
    elif fault == "escaped": manifest["artifacts"]["data"] = str(tmp_path / "outside.csv")
    elif fault == "duplicate":
        manifest["artifacts"]["alias"] = str(target)
        manifest["artifact_hashes"]["alias"] = refinement.sha256_file(target)
    else: manifest["artifact_hashes"] = {}
    with pytest.raises(ValueError): refinement._artifacts(manifest, directory, {})


@pytest.mark.parametrize("fault", ["coordinate", "count", "identity"])
def test_parent_parity_rejects_changed_scientific_values_even_with_updated_hashes(setup, fault):
    plan, sample, bundle, output = setup
    parent = bundle["parents"][0]
    manifest_path = Path(parent["parent_manifest"]["path"])
    manifest = refinement.read_json(manifest_path)
    filename, key, value = {"coordinate": ("detections.csv", "cx", "999"), "count": ("frame_metrics.csv", "tp", "999"), "identity": ("detections.csv", "object_id", "changed")}[fault]
    path = Path(manifest["artifacts"][filename])
    rows = refinement._read_csv(path)
    rows[0][key] = value
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    manifest["artifact_hashes"][filename] = refinement.sha256_file(path)
    manifest_path.write_text(json.dumps(manifest))
    parent["parent_manifest"]["sha256"] = refinement.sha256_file(manifest_path)
    with pytest.raises(ValueError, match="parity"):
        _run(setup)
    assert not list(output.rglob("ranking.csv"))
