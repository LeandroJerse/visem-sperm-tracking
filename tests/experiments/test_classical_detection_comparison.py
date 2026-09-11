"""Fail-closed protocol tests and real exports using synthetic frame data only."""
import copy
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from script.detection.test import compare_classical as cli
from src.detection.base import Detection
from src.experiments import classical_detection_comparison as comparison
from src.experiments import runs


@pytest.fixture
def plan():
    return comparison.load_config(comparison.REPOSITORY_ROOT / comparison.DEFAULT_PLAN)


def test_registered_grid_is_complete_unique_and_explicit(plan):
    candidates = comparison.expand_candidates(plan)
    assert len(candidates) == 43
    assert len({row["configuration_id"] for row in candidates}) == 43
    assert {family: sum(row["family"] == family for row in candidates) for family in comparison.FAMILIES} == {
        "threshold": 1, "otsu": 4, "adaptive_threshold": 18, "hybrid_threshold": 8, "blob": 6, "watershed": 6}
    assert all(row["params"]["min_area"] == 3 and row["params"]["max_area"] == 300 for row in candidates)
    assert comparison.expand_candidates(plan) == candidates


@pytest.mark.parametrize("index", range(43))
def test_every_registered_detector_accepts_readonly_synthetic_pixels(plan, index):
    candidate = comparison.expand_candidates(plan)[index]
    pixels = np.full((96, 96, 3), 70, dtype=np.uint8)
    pixels[20:25, 30:35] = 250
    pixels[60:66, 60:66] = 10
    pixels.flags.writeable = False
    before = pixels.tobytes()
    detector = comparison.build_detector(candidate["method"], params=candidate["params"])
    detections = detector.detect(pixels)
    assert pixels.tobytes() == before
    for item in detections:
        assert np.isfinite([item.cx, item.cy, item.w, item.h, item.score]).all()
        assert item.w > 0 and item.h > 0


@pytest.mark.parametrize("fault", ["split", "videos", "time_cutoff", "implicit_blur", "promotion", "validation",
                                  "candidate_count", "duplicate_axis", "unknown_family", "unknown_parameter", "area", "reference"])
def test_invalid_protocol_rejected_without_input_reads(plan, fault, monkeypatch):
    monkeypatch.setattr(comparison, "load_sample", lambda *args: pytest.fail("sample opened"))
    if fault == "split":
        plan["run"]["split"] = "test"
    elif fault == "videos":
        plan["train_ids"][-1] = 24
    elif fault == "time_cutoff":
        plan["budget"]["wall_seconds_limit"] = 7200
    elif fault == "implicit_blur":
        plan["families"][0]["params"]["blur"] = 2
    elif fault == "promotion":
        plan["selection"]["promotion_allowed"] = True
    elif fault == "validation":
        plan["selection"]["validation_released"] = True
    elif fault == "candidate_count":
        plan["expected_candidates"] = 42
    elif fault == "duplicate_axis":
        plan["families"][1]["search_space"]["morph_iterations"] = [0, 0]
    elif fault == "unknown_family":
        plan["families"][1]["family"] = "yolo"
    elif fault == "unknown_parameter":
        plan["families"][1]["params"]["magic"] = 1
    elif fault == "area":
        plan["families"][1]["params"]["max_area"] = 600
    else:
        plan["families"][0]["params"]["threshold_value"] = 200
    with pytest.raises(ValueError):
        comparison.load_comparison_sample(plan)


class SyntheticSample:
    video_ids = comparison.TRAIN_IDS
    sample_hash = "synthetic-no-source-data"

    def __init__(self, cache):
        self.cache_dir = cache
        gt_path = cache / "ground_truth.csv"
        gt_path.write_text("synthetic header\n", encoding="utf-8")
        self.manifest = {"synthetic": True, "videos": {}, "ground_truth": {"sha256": comparison.sha256_file(gt_path)}}
        (cache / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def indices(self, mode, video):
        return (0,) if mode == "benchmark" else tuple(range(48))

    def frames(self, mode):
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        image.flags.writeable = False
        for video in self.video_ids:
            for frame in self.indices(mode, video):
                yield video, frame, image, (
                    Detection(20.2500123456789, 20, 5, 5, class_id=0, object_id="individual-a"),
                    Detection(38, 20, 5, 5, class_id=2, object_id="individual-b"),
                    Detection(54, 54, 16, 16, class_id=1, object_id="cluster-original"))


class SyntheticDetector:
    def reset(self):
        pass

    def detect(self, image):
        return [Detection(20, 20, 5, 5), Detection(38, 20, 5, 5),
                Detection(21, 20, 3, 3), Detection(54, 54, 3, 3)]


@pytest.fixture
def setup(plan, monkeypatch, tmp_path):
    candidates = comparison.expand_candidates(plan)
    # The full 43 detector constructors are tested separately. Four candidates
    # exercise complete child/batch export and per-family finalist selection.
    subset = [candidates[index] for index in (0, 1, 2, 3)]
    monkeypatch.setattr(comparison, "expand_candidates", lambda unused: copy.deepcopy(subset))
    monkeypatch.setattr(comparison, "build_detector", lambda *args, **kwargs: SyntheticDetector())
    for module in (comparison, runs):
        monkeypatch.setattr(module, "_git_dirty", lambda _: False)
        monkeypatch.setattr(module, "_source_hash", lambda _: "synthetic-stable-code")
    monkeypatch.setattr(runs, "_git_sha", lambda _: "1234567")
    monkeypatch.setattr(runs, "environment_snapshot", lambda: {"synthetic": True})
    cache = tmp_path / "cache"
    cache.mkdir()
    sample = SyntheticSample(cache)
    plan["input"].update(cache_manifest_sha256=comparison.sha256_file(cache / "manifest.json"), sample_hash=sample.sample_hash)
    return plan, sample, tmp_path / "runs"


def _run(setup, mode="smoke", **kwargs):
    plan, sample, output = setup
    return comparison.run_batch(plan, sample, mode, cache_validation_seconds=0.01, output_root=output, **kwargs)


def test_smoke_then_search_preserves_every_frame_raw_id_and_cluster_count(setup):
    smoke = _run(setup)
    assert not smoke.with_name("ranking.csv").exists()
    search = _run(setup, "search", smoke_manifest=smoke)
    manifest = json.loads(search.read_text())
    assert manifest["summary"]["frame_evaluations"] == 4 * 576
    assert manifest["summary"]["selection_allowed"] is True
    assert manifest["summary"]["validation_released"] is False
    assert manifest["summary"]["promotion_allowed"] is False
    assert manifest["provenance_verification"]["status"] == "verified"
    finalists = json.loads(search.with_name("family_finalists.json").read_text())
    assert [row["family"] for row in finalists] == ["threshold", "otsu", "otsu"]
    for record in manifest["candidate_manifests"]:
        child_path = Path(record["path"])
        assert comparison.sha256_file(child_path) == record["sha256"]
        child = json.loads(child_path.read_text())
        assert child["summary"]["n_predictions_ignored"] == 576
        assert child["summary"]["tp"] == 1152 and child["summary"]["fp"] == 576 and child["summary"]["fn"] == 0
        assert child["summary"]["macro_video_f1"] == pytest.approx(0.8)
        assert child["summary"]["macro_video_secondary_all_objects_f1"] == pytest.approx(6 / 7)
        for key, artifact in child["artifacts"].items():
            assert comparison.sha256_file(artifact) == child["artifact_hashes"][key]
        with child_path.with_name("detections.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        manual = [row for row in rows if row["source"] == "manual"]
        assert len(manual) == 1728
        assert float(manual[0]["cx"]) == 20.2500123456789
        assert {row["object_id"] for row in manual} == {"individual-a", "individual-b", "cluster-original"}


@pytest.mark.parametrize("fault", ["missing", "duplicate", "detector", "excess_predictions", "changed_cache", "changed_code", "rss_missing"])
def test_incomplete_or_changed_batch_fails_without_ranking(setup, monkeypatch, fault):
    plan, sample, output = setup
    if fault in {"missing", "duplicate"}:
        original = sample.frames
        def broken(mode):
            rows = list(original(mode))
            yield from (rows[:-1] if fault == "missing" else [*rows[:-1], rows[0]])
        monkeypatch.setattr(sample, "frames", broken)
    elif fault == "detector":
        monkeypatch.setattr(SyntheticDetector, "detect", lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
    elif fault == "excess_predictions":
        plan["budget"]["max_predictions_per_frame"] = 3
    elif fault == "changed_cache":
        (sample.cache_dir / "ground_truth.csv").write_text("changed\n")
    elif fault == "changed_code":
        fingerprints = iter(["synthetic-stable-code", "changed"])
        monkeypatch.setattr(runs, "_source_hash", lambda _: next(fingerprints))
    else:
        real = comparison.ResourceMonitor.summary
        monkeypatch.setattr(comparison.ResourceMonitor, "summary", lambda self: {**real(self), "ram_rss_peak_mb": None})
    with pytest.raises((ValueError, RuntimeError)):
        _run(setup)
    manifests = [json.loads(path.read_text()) for path in output.rglob("manifest.json")]
    batch = next(item for item in manifests if item["method"] == "classical_comparison")
    assert batch["status"] == "failed" and batch["selection_allowed"] is False
    assert not list(output.rglob("ranking.csv"))
    assert not list(output.rglob("family_finalists.json"))


@pytest.mark.parametrize("fault", ["candidate_artifact", "batch_artifact", "child_manifest", "mode", "provenance", "plan", "sample"])
def test_search_refuses_altered_or_incompatible_smoke(setup, fault):
    smoke = _run(setup)
    manifest = json.loads(smoke.read_text())
    if fault in {"candidate_artifact", "child_manifest"}:
        child = Path(manifest["candidate_manifests"][0]["path"])
        (child.with_name("detections.csv") if fault == "candidate_artifact" else child).write_text("changed")
    elif fault == "batch_artifact":
        smoke.with_name("candidate_metrics.csv").write_text("changed")
    elif fault == "mode":
        manifest["summary"]["mode"] = "search"
        smoke.write_text(json.dumps(manifest))
    elif fault == "provenance":
        manifest["provenance_verification"]["status"] = "failed"
        smoke.write_text(json.dumps(manifest))
    elif fault == "plan":
        setup[0]["plan_id"] = "another-plan"
    else:
        setup[1].sample_hash = "another-sample"
    with pytest.raises(ValueError):
        _run(setup, "search", smoke_manifest=smoke)
    assert not list(setup[2].rglob("ranking.csv"))


def test_search_requires_smoke_before_creating_any_runs(setup):
    with pytest.raises(ValueError, match="smoke"):
        _run(setup, "search")
    assert not setup[2].exists()


def test_cli_dry_run_does_not_open_cache_or_require_clean_git(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_comparison_sample", lambda *args: pytest.fail("sample read"))
    monkeypatch.setattr(cli, "_git_dirty", lambda *args: pytest.fail("Git checked"))
    assert cli.main(["--mode", "search", "--dry-run"]) is None
    output = json.loads(capsys.readouterr().out)
    assert output["candidate_count"] == 43 and output["frame_evaluations"] == 24768


def test_failed_csv_export_preserves_partial_bytes_without_retry(setup, monkeypatch):
    original = comparison.write_csv_exclusive
    attempts = []
    def failing(path, rows, fieldnames=None):
        if Path(path).name == "detections.csv":
            attempts.append(str(path))
            Path(path).write_bytes(b"partial immutable export\n")
            raise OSError("synthetic interrupted CSV")
        return original(path, rows, fieldnames)
    monkeypatch.setattr(comparison, "write_csv_exclusive", failing)
    with pytest.raises(OSError, match="synthetic interrupted CSV"):
        _run(setup)
    assert len(attempts) == 1
    assert Path(attempts[0]).read_bytes() == b"partial immutable export\n"
    assert not list(setup[2].rglob("ranking.csv"))
