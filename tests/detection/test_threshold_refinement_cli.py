"""Refinement executes every master frame and cannot reuse a coarse benchmark."""
import copy
import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from script.detection.test.threshold import search
from src.detection.base import Detection
from src.experiments import runs


class Sample:
    video_ids = tuple(map(str, (11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82)))
    sample_hash = "synthetic-refinement"

    def __init__(self, cache):
        self.cache_dir = cache

    def indices(self, mode, video):
        return tuple(range(48)) if mode == "master" else (24,) if mode == "benchmark" else (0, 4)

    def frames(self, mode):
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[4:7, 4:7] = 210
        image.flags.writeable = False
        for vid in self.video_ids:
            for frame in self.indices(mode, vid):
                yield vid, frame, image, (Detection(5.500123456789, 5.5, 3, 3, object_id="original"),)


@pytest.fixture
def context(tmp_path, monkeypatch):
    for module in (runs, search):
        monkeypatch.setattr(module, "_git_dirty", lambda _: False)
        monkeypatch.setattr(module, "_source_hash", lambda _: "source")
    monkeypatch.setattr(runs, "_git_sha", lambda _: "1234567")
    monkeypatch.setattr(runs, "environment_snapshot", lambda: {"synthetic": True})
    plan = search.load_config(search.REPOSITORY_ROOT / search.DEFAULT_PLAN)
    plan["search_space"] = {"threshold_value": [200, 255], "morph_iterations": [0], "close_iterations": [0]}
    plan["sampling"]["coarse_frames_per_video"] = 2
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "manifest.json").write_text('{}')
    sample = Sample(cache)
    execution = search.load_config(search.REPOSITORY_ROOT / search.DEFAULT_REFINEMENT)
    operational = {"execution": execution, "execution_hash": "execution",
                   "execution_path": str(tmp_path / "refinement.yaml"), "execution_sha256": "synthetic",
                   "candidates": search.expand_coarse_candidates(plan),
                   "provenance": {"sample_hash": sample.sample_hash, "plan_hash": search.config_hash(plan, 64)},
                   "budget": {**plan["budget"], **execution["budget"]}, "parent_validation_seconds": 0.01}
    monkeypatch.setattr(search, "_load_refinement", lambda path, p: copy.deepcopy(operational))
    return plan, sample, operational


def batch(tmp_path, context, mode, benchmark=None):
    plan, sample, _ = context
    return search.run_batch(plan, sample, mode, cache_validation_seconds=0.01,
                            output_root=tmp_path / "runs", benchmark=benchmark,
                            refinement_config=tmp_path / "refinement.yaml" if mode in search.REFINEMENT_MODES else None)


def test_benchmark_then_all_48_master_frames_produce_two_training_finalists(tmp_path, context):
    plan, _, operational = context
    plan["search_space"]["threshold_value"] = [190, 200, 255]
    operational["candidates"] = search.expand_coarse_candidates(plan)
    benchmark = batch(tmp_path, context, "refinement_benchmark")
    manifest = json.loads(benchmark.read_text())
    assert manifest["summary"]["frame_evaluations"] == 36
    assert not benchmark.with_name("ranking.csv").exists()
    assert not benchmark.with_name("finalists.json").exists()
    assert manifest["summary"]["projected_refinement_seconds"] == pytest.approx(
        .02 + 96 * manifest["summary"]["candidate_loop_seconds"])
    refined = batch(tmp_path, context, "refine", {"path": str(benchmark)})
    manifest = json.loads(refined.read_text())
    assert manifest["summary"]["frame_evaluations"] == 1728
    assert manifest["stage"] == "refinement"
    assert manifest["summary"]["interpretation"] == "training_finalists_not_promoted"
    assert not refined.with_name("shortlist.json").exists()
    finalists = json.loads(refined.with_name("finalists.json").read_text())
    assert [r["configuration_id"] for r in finalists] == ["t190_o0_c0", "t200_o0_c0"]
    with refined.with_name("ranking.csv").open() as stream:
        ranking = list(csv.DictReader(stream))
    assert [r["configuration_id"] for r in ranking] == ["t190_o0_c0", "t200_o0_c0", "t255_o0_c0"]
    for record in manifest["candidate_manifests"]:
        path = Path(record["path"])
        child = json.loads(path.read_text())
        assert child["config"]["provenance"]["sample_mode"] == "master"
        with path.with_name("frame_metrics.csv").open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 576
        assert {(row["video_id"], int(row["frame"])) for row in rows} == {
            (vid, frame) for vid in Sample.video_ids for frame in range(48)}


def test_refinement_cannot_reuse_coarse_benchmark(tmp_path, context):
    coarse_benchmark = batch(tmp_path, context, "benchmark")
    with pytest.raises(ValueError, match="mesma etapa"):
        batch(tmp_path, context, "refine", {"path": str(coarse_benchmark)})


@pytest.mark.parametrize("fault", ["sample", "execution", "parameters", "budget"])
def test_refinement_rejects_incompatible_inputs_before_new_candidates(tmp_path, context, fault):
    benchmark = batch(tmp_path, context, "refinement_benchmark")
    plan, sample, execution = context
    if fault == "sample":
        execution["provenance"]["sample_hash"] = "other"
    elif fault == "execution":
        execution["execution_hash"] = "other"
    elif fault == "parameters":
        execution["candidates"][0]["params"]["min_area"] = 4
    else:
        execution["budget"]["allow_refine_if_projection_seconds_at_most"] = 0
    with pytest.raises((ValueError, RuntimeError)):
        batch(tmp_path, context, "refine", {"path": str(benchmark)})
    assert not list((tmp_path / "runs").rglob("finalists.json"))


def test_incomplete_master_sample_stops_without_finalists(tmp_path, context, monkeypatch):
    benchmark = batch(tmp_path, context, "refinement_benchmark")
    _, sample, _ = context
    original = sample.frames
    def incomplete(mode):
        for vid, frame, pixels, gt in original(mode):
            if frame != 47:
                yield vid, frame, pixels, gt
    monkeypatch.setattr(sample, "frames", incomplete)
    with pytest.raises(ValueError, match="Universo"):
        batch(tmp_path, context, "refine", {"path": str(benchmark)})
    assert not list((tmp_path / "runs").rglob("finalists.json"))
    manifests = [json.loads(p.read_text()) for p in (tmp_path / "runs").rglob("manifest.json")]
    refined = [r for r in manifests if r["method"] == "threshold_search" and r["config"]["mode"] == "refine"]
    assert len(refined) == 1 and refined[0]["status"] == "failed"


def test_refinement_uses_registered_7200_seconds_not_coarse_budget(context, monkeypatch):
    plan, _, execution = context
    monkeypatch.setattr(search.time, "perf_counter", lambda: 2000)
    monitor = search.ResourceMonitor()
    search._check_budget(plan, "refine", 0, monitor, budget=execution["budget"])
    with pytest.raises(search.SearchBudgetExceeded):
        search._check_budget(plan, "coarse", 0, monitor)


@pytest.mark.parametrize("component", ["cache_validation_seconds", "parent_validation_seconds", "candidate_loop_seconds"])
def test_negative_time_cannot_be_offset_by_other_positive_times(tmp_path, context, component):
    benchmark = batch(tmp_path, context, "refinement_benchmark")
    manifest = json.loads(benchmark.read_text())
    summary = manifest["summary"]
    for key in ("cache_validation_seconds", "parent_validation_seconds", "candidate_loop_seconds"):
        summary[key] = 100.0
    summary[component] = -1.0
    summary["projected_refinement_seconds"] = (summary["cache_validation_seconds"]
        + summary["parent_validation_seconds"] + 96 * summary["candidate_loop_seconds"])
    assert summary["projected_refinement_seconds"] > 0
    benchmark.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Componente de tempo"):
        batch(tmp_path, context, "refine", {"path": str(benchmark)})


@pytest.mark.parametrize("section,key,value", [
    ("sampling", "refinement_mode", "coarse"),
    ("sampling", "refinement_frames_per_video", 12),
    ("sampling", "benchmark_mode", "master"),
    ("selection", "finalists", 3),
    ("selection", "inherit_ranking_rule_from_base_plan", False),
    ("benchmark", "selection_allowed", True),
    ("benchmark", "projection_safety_factor", 1),
    ("budget", "benchmark_soft_wall_seconds", 601),
    ("budget", "refine_soft_wall_seconds", 7201),
    ("budget", "allow_refine_if_projection_seconds_at_most", 4801),
    ("budget", "inherit_resource_limits_from_base_plan", False),
])
def test_operational_policy_cannot_silently_change(tmp_path, monkeypatch, section, key, value):
    plan = search.load_config(search.REPOSITORY_ROOT / search.DEFAULT_PLAN)
    execution = search.load_config(search.REPOSITORY_ROOT / search.DEFAULT_REFINEMENT)
    execution[section][key] = value
    path = tmp_path / "execution.yaml"
    path.write_text(yaml.safe_dump(execution), encoding="utf-8")
    def unexpected(*args):
        pytest.fail("Invalid policy must be rejected before reading parent artifacts")
    monkeypatch.setattr(search, "load_refinement_candidates", unexpected)
    with pytest.raises(ValueError, match="Regra operacional"):
        search._load_refinement(path, plan)
