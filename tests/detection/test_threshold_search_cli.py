"""Exercise real batch export and failure rules with tiny synthetic videos."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from script.detection.test.threshold import search
from src.detection.base import Detection
from src.experiments import runs


class Sample:
    video_ids = tuple(map(str, (11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82)))
    sample_hash = "synthetic_pixels_and_gt"

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    def indices(self, mode, video_id):
        return (0,) if mode == "benchmark" else (0, 4)

    def frames(self, mode):
        pixels = np.zeros((16, 16, 3), dtype=np.uint8)
        pixels[4:7, 4:7] = 210
        pixels.flags.writeable = False
        for video in self.video_ids:
            for frame in self.indices(mode, video):
                yield video, frame, pixels, (Detection(5.500123456789, 5.5, 3, 3, object_id="original-id"),)


@pytest.fixture
def setup(monkeypatch, tmp_path_factory):
    for module in (search, runs):
        monkeypatch.setattr(module, "_git_dirty", lambda _: False)
        monkeypatch.setattr(module, "_git_sha", lambda _: "1234567")
        monkeypatch.setattr(module, "_source_hash", lambda _: "stable-source")
    monkeypatch.setattr(runs, "environment_snapshot", lambda: {"synthetic": True})
    plan = search.load_config(search.REPOSITORY_ROOT / search.DEFAULT_PLAN)
    plan["search_space"] = {"threshold_value": [200, 255], "morph_iterations": [0], "close_iterations": [0]}
    plan["sampling"].update(coarse_frames_per_video=2, benchmark_frames_per_video=1)
    cache_dir = tmp_path_factory.mktemp("synthetic-threshold-cache")
    (cache_dir / "manifest.json").write_text(json.dumps({
        "status": "complete", "sample_hash": Sample.sample_hash, "synthetic": True,
    }), encoding="utf-8")
    return plan, Sample(cache_dir)


def batch(tmp_path, setup, mode="benchmark", **kwargs):
    plan, sample = setup
    return search.run_batch(plan, sample, mode, cache_validation_seconds=0.1, output_root=tmp_path, **kwargs)


def test_complete_benchmark_then_coarse_exports_every_frame_and_raw_gt(tmp_path, setup):
    _, sample = setup
    sample_manifest = (sample.cache_dir / "manifest.json").resolve()
    expected_reference = {"sample_manifest_path": str(sample_manifest),
                          "sample_manifest_sha256": search.sha256_file(sample_manifest)}
    benchmark = batch(tmp_path, setup)
    assert not benchmark.with_name("ranking.csv").exists()
    report = json.loads(benchmark.read_text())
    assert report["config"]["input"] == {"sample_hash": sample.sample_hash, **expected_reference}
    benchmark_artifacts = {"planned_candidates.json", "planned_frames.json", "candidate_001.json",
                           "candidate_002.json", "candidate_metrics.csv"}
    assert set(report["artifacts"]) == set(report["artifact_hashes"]) == benchmark_artifacts
    assert report["summary"]["frame_evaluations"] == 24
    assert report["summary"]["selection_allowed"] is False
    coarse = batch(tmp_path, setup, "coarse", benchmark={"path": str(benchmark)})
    manifest = json.loads(coarse.read_text())
    assert manifest["config"]["input"] == {"sample_hash": sample.sample_hash, **expected_reference}
    assert set(manifest["artifacts"]) == set(manifest["artifact_hashes"]) == (
        benchmark_artifacts | {"ranking.csv", "shortlist.json"}
    )
    for item in (report, manifest):
        for artifact, path in item["artifacts"].items():
            assert search.sha256_file(Path(path)) == item["artifact_hashes"][artifact]
    assert manifest["summary"]["frame_evaluations"] == 48
    ranked = list(csv.DictReader(coarse.with_name("ranking.csv").open()))
    assert [row["configuration_id"] for row in ranked] == ["t200_o0_c0", "t255_o0_c0"]
    assert [float(row["macro_video_f1"]) for row in ranked] == [1, 0]
    for record in manifest["candidate_manifests"]:
        child = Path(record["path"])
        provenance = json.loads(child.read_text())["config"]["provenance"]
        assert {key: provenance[key] for key in expected_reference} == expected_reference
        assert provenance["sample_hash"] == sample.sample_hash
        assert provenance["batch_manifest_path"] == str(coarse.resolve())
        per_video = list(csv.DictReader(child.with_name("video_summary.csv").open()))
        assert len(per_video) == 12
        assert {int(row["frames_total"]) for row in per_video} == {2}
        rows = list(csv.DictReader(child.with_name("detections.csv").open()))
        gt = [row for row in rows if row["source"] == "manual"]
        assert len(gt) == 24
        assert float(gt[0]["cx"]) == 5.500123456789
        assert {row["object_id"] for row in gt} == {"original-id"}


@pytest.mark.parametrize("failure", ["detections.csv", "frame_metrics.csv", "detector"])
def test_export_failure_preserves_partial_bytes_and_original_error(tmp_path, setup, monkeypatch, failure):
    original_write = search.write_csv_exclusive
    attempted = []
    partial = b"synthetic interrupted export\n"
    original_error = (ValueError("synthetic detector failure") if failure == "detector"
                      else OSError(f"synthetic interrupted {failure}"))

    def failing_write(path, rows, fieldnames=None):
        target = Path(path)
        if target.name in {"detections.csv", "frame_metrics.csv"}:
            attempted.append(target)
            if target.name == failure or failure == "detector":
                with target.open("xb") as stream:
                    stream.write(partial)
                if failure == "detector":
                    raise OSError(f"synthetic export failure: {target.name}")
                raise original_error
        return original_write(path, rows, fieldnames)

    if failure == "detector":
        class BrokenDetector:
            def detect(self, pixels):
                raise original_error
        monkeypatch.setattr(search, "build_detector", lambda *args, **kwargs: BrokenDetector())
    monkeypatch.setattr(search, "write_csv_exclusive", failing_write)
    with pytest.raises(type(original_error)) as raised:
        batch(tmp_path, setup)
    assert raised.value is original_error
    assert len(attempted) == len(set(attempted)) == 2
    assert {path.name for path in attempted} == {"detections.csv", "frame_metrics.csv"}
    for path in attempted:
        if path.name == failure or failure == "detector":
            assert path.read_bytes() == partial
        else:
            assert path.read_bytes() != partial
    manifests = [json.loads(path.read_text()) for path in tmp_path.rglob("manifest.json")]
    assert len(manifests) == 2
    assert all(item["status"] == "failed" and item["error"] == str(original_error) for item in manifests)
    candidate = next(item for item in manifests if item["method"] == "threshold")
    assert len(candidate["export_errors"]) == (2 if failure == "detector" else 1)
    assert all(item["error_type"] == "OSError" for item in candidate["export_errors"])
    assert not list(tmp_path.rglob("ranking.csv"))
    assert not list(tmp_path.rglob("shortlist.json"))


def test_unavailable_failure_manifests_cannot_replace_original_exception(tmp_path, setup, monkeypatch):
    original_error = ValueError("synthetic original detector failure")
    failure_attempts = []

    class BrokenDetector:
        def detect(self, pixels):
            raise original_error

    def unavailable_manifest(context, error, **kwargs):
        failure_attempts.append((context.method, error))
        raise OSError("synthetic unavailable failure-manifest destination")

    monkeypatch.setattr(search, "build_detector", lambda *args, **kwargs: BrokenDetector())
    monkeypatch.setattr(search.RunContext, "fail", unavailable_manifest)
    with pytest.raises(ValueError) as raised:
        batch(tmp_path, setup)
    assert raised.value is original_error
    assert failure_attempts == [("threshold", original_error), ("threshold_search", original_error)]
    assert len(original_error.__notes__) == 2
    assert all("could not be written" in note for note in original_error.__notes__)
    assert not list(tmp_path.rglob("ranking.csv"))
    assert not list(tmp_path.rglob("shortlist.json"))


@pytest.mark.parametrize("fault", ["missing_frame", "duplicate_frame", "too_many_predictions", "source_changed"])
def test_failed_batch_preserves_manifest_without_ranking(tmp_path, setup, monkeypatch, fault):
    plan, sample = setup
    if fault in {"missing_frame", "duplicate_frame"}:
        original = sample.frames
        def invalid(mode):
            rows = list(original(mode))
            yield from (rows[:-1] if fault == "missing_frame" else [*rows[:-1], rows[0]])
        monkeypatch.setattr(sample, "frames", invalid)
    elif fault == "too_many_predictions":
        plan["budget"]["max_predictions_per_frame"] = 0
    else:
        monkeypatch.setattr(search, "_source_hash", lambda _: "changed-source")
    with pytest.raises((ValueError, RuntimeError)):
        batch(tmp_path, setup)
    manifests = [json.loads(path.read_text()) for path in tmp_path.rglob("manifest.json")]
    batches = [item for item in manifests if item["method"] == "threshold_search"]
    assert len(batches) == 1 and batches[0]["status"] == "failed"
    assert batches[0]["selection_allowed"] is False
    assert not list(tmp_path.rglob("ranking.csv"))
    assert not list(tmp_path.rglob("shortlist.json"))


@pytest.mark.parametrize("fault", ["artifact", "batch_artifact", "manifest", "plan", "sample", "budget"])
def test_coarse_refuses_changed_or_over_budget_benchmark(tmp_path, setup, fault):
    plan, sample = setup
    path = batch(tmp_path, setup)
    manifest = json.loads(path.read_text())
    child_path = Path(manifest["candidate_manifests"][0]["path"])
    if fault == "artifact":
        child_path.with_name("detections.csv").write_text("corrupted")
    elif fault == "batch_artifact":
        path.with_name("candidate_metrics.csv").write_text("corrupted")
    elif fault == "manifest":
        child_path.write_text("{}")
    elif fault == "plan":
        plan["run"]["seed"] = 43
    elif fault == "sample":
        sample.sample_hash = "changed"
    else:
        manifest["summary"]["projected_coarse_seconds"] = 999999
        path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, RuntimeError)):
        batch(tmp_path, setup, "coarse", benchmark={"path": str(path)})
    assert not list(tmp_path.rglob("ranking.csv"))


def test_coarse_requires_benchmark_before_creating_runs(tmp_path, setup):
    with pytest.raises(ValueError, match="benchmark"):
        batch(tmp_path, setup, "coarse")
    assert not list(tmp_path.iterdir())


def test_dry_run_does_not_load_sources_or_create_cache(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("dry run must not touch data")
    monkeypatch.setattr(search, "prepare_sample", forbidden)
    monkeypatch.setattr(search, "load_sample", forbidden)
    search.main(["--mode", "prepare", "--dry-run"])
    assert json.loads(capsys.readouterr().out)["candidates"] == 171
