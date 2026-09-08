from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from script.prediction.test import prepare_ground_truth as cli
from src.detection.base import Detection
from src.detection.io import CSV_FIELDS, GroundTruthFrame


@pytest.fixture
def registered_plan(tmp_path, monkeypatch):
    # These are versioned protocol metadata, never original videos/labels.
    repository = cli.REPOSITORY_ROOT
    for relative in (cli.PLAN, "configs/protocol/splits.yaml", "data/manifests/visem_tracking.csv",
                     "data/manifests/annotation_gaps.csv"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / relative).read_bytes())
    monkeypatch.setattr(cli, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(cli, "prepare_full_video_input", lambda *a, **k: pytest.fail("source access"))
    return tmp_path / cli.PLAN


def test_plan_is_loadable_without_original_source_files(registered_plan):
    plan, refs = cli.load_plan(registered_plan)
    assert plan["protocol"]["train_ids"] == [int(video) for video in cli.TRAIN]
    assert len(refs) == 4
    assert all(len(item["sha256"]) == 64 for item in refs)
    assert not (cli.REPOSITORY_ROOT / "data/sources").exists()


@pytest.mark.parametrize("section,key,value", [
    ("protocol", "train_ids", [14, 19, 36, 52]),
    ("protocol", "splits_config", "other.yaml"),
    ("input", "root", "data/sources/another_cohort"),
    ("input", "expected_frames", {11: 10}),
    ("input", "missing_label_ranges", {}),
    ("input", "width", 1280),
    ("eligibility", "individual_classes", [0, 1, 2]),
    ("eligibility", "interpolate", True),
    ("eligibility", "interpolate", 0),
    ("eligibility", "preserve_original_track_ids", 1),
    ("windows", "history_length", 19),
    ("windows", "forecast_horizon", 11),
    ("windows", "stride", True),
    ("windows", "output", "future_features"),
    ("run", "split", "test"),
    ("run", "seed", 0),
    ("output", "overwrite", 0),
    ("output", "root", "data/results"),
])
def test_changed_scientific_contract_fails_before_snapshot_or_sources(
    registered_plan, monkeypatch, section, key, value
):
    plan = yaml.safe_load(registered_plan.read_text(encoding="utf-8"))
    plan[section][key] = value
    registered_plan.write_text(yaml.safe_dump(plan), encoding="utf-8")
    monkeypatch.setattr(cli.RunSnapshot, "capture", lambda: pytest.fail("snapshot before valid protocol"))
    with pytest.raises(ValueError, match="registered training-only"):
        cli.prepare(registered_plan)


def test_duplicate_yaml_key_is_not_hidden_by_last_value(registered_plan):
    with registered_plan.open("a", encoding="utf-8") as stream:
        stream.write("\nmethod: ground_truth_individuals\n")
    with pytest.raises(ValueError, match="Duplicate plan key"):
        cli.load_plan(registered_plan)


@pytest.mark.parametrize("relative", ["data/sources/not_opened.yaml", "configs/protocol/other.yaml", "../outside.yaml"])
def test_noncanonical_plan_path_is_rejected_before_file_read(registered_plan, relative):
    with pytest.raises(ValueError, match="canonical registered"):
        cli.load_plan(cli.REPOSITORY_ROOT / relative)


def test_changed_metadata_fails_without_reading_original_sources(registered_plan):
    path = cli.REPOSITORY_ROOT / "data/manifests/visem_tracking.csv"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("unexpected,row\n")
    with pytest.raises(ValueError, match="Changed versioned metadata"):
        cli.load_plan(registered_plan)


def test_gap_metadata_semantics_are_fixed(registered_plan):
    path = cli.REPOSITORY_ROOT / "data/manifests/annotation_gaps.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("823", "824"), encoding="utf-8")
    with pytest.raises(ValueError, match="Annotation-gap metadata"):
        cli.load_plan(registered_plan)


@pytest.fixture
def synthetic_run(registered_plan, monkeypatch, tmp_path):
    plan, _ = cli.load_plan(registered_plan)
    events = []
    # Small test-only universes exercise the coordinator and actual pure
    # eligibility module; the strict real-plan tests above retain all 12 IDs.
    monkeypatch.setattr(cli, "TRAIN", ("11", "12"))
    monkeypatch.setattr(cli, "EXPECTED_FRAMES", {"11": 32, "12": 32})
    monkeypatch.setattr(cli, "GAPS", {})
    plan = copy.deepcopy(plan)
    plan["input"]["expected_frames"] = {11: 32, 12: 32}
    plan["protocol"]["train_ids"] = [11, 12]
    monkeypatch.setattr(cli, "load_plan", lambda path: (events.append("plan") or plan, []))
    snapshot = SimpleNamespace(verify_current=lambda: events.append("snapshot_end") or {"status": "verified"})
    monkeypatch.setattr(cli.RunSnapshot, "capture", lambda: events.append("snapshot") or snapshot)
    folder = tmp_path / "data/derived/synthetic_preparation"
    folder.mkdir(parents=True)
    run = SimpleNamespace(path=folder, complete=Mock(), fail=Mock())
    monkeypatch.setattr(cli.RunContext, "create", lambda **kwargs: events.append("run") or run)
    monkeypatch.setattr(cli, "ResourceMonitor", lambda: SimpleNamespace(summary=lambda: {"ram_rss_peak_mb": 1.0}))
    sources = {}
    for video in cli.TRAIN:
        frames = tuple(GroundTruthFrame(index, True, (
            Detection(20.125, 30.375, 4.25, 6.5, class_id=0, object_id="original-id"),
            Detection(20.125, 30.375, 10.0, 12.0, class_id=1, object_id="cluster-id"),
        )) for index in range(32))
        sources[video] = SimpleNamespace(
            gt_frames=frames,
            reference=lambda video=video: {"video_id": video, "input_hash": video * 32},
            verify_current=lambda video=video: events.append(f"recheck_{video}") or {"status": "verified"},
        )

    def prepare_input(video_path, labels, **kwargs):
        video = kwargs["video_id"]
        events.append(f"source_{video}")
        assert kwargs["expected_width"] == 640 and kwargs["expected_height"] == 480
        assert kwargs["expected_frame_count"] == 32
        assert video_path.name == f"{video}.mp4" and labels.name == "labels_ftid"
        return sources[video]

    monkeypatch.setattr(cli, "prepare_full_video_input", prepare_input)
    return registered_plan, run, sources, events


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def test_preparation_exports_raw_individuals_and_window_indices_with_hashes(synthetic_run):
    path, run, sources, events = synthetic_run
    assert cli.prepare(path) == run.path
    assert events[:4] == ["plan", "snapshot", "run", "source_11"]
    assert events[-3:] == ["recheck_11", "recheck_12", "snapshot_end"]
    run.complete.assert_called_once()
    run.fail.assert_not_called()
    payload = run.complete.call_args.kwargs
    assert payload["summary"]["totals"]["frames_total"] == 64
    assert payload["summary"]["totals"]["raw_observations"] == 128
    assert payload["summary"]["totals"]["individual_observations"] == 64
    assert payload["summary"]["totals"]["windows_total"] == 6
    assert payload["summary"]["model_evaluated"] is False
    assert payload["summary"]["test_sources_read"] is False
    assert payload["summary"]["pixels_decoded"] is False
    assert len(payload["artifacts"]) == 15  # seven per video, plus complete summary
    for item in payload["artifacts"]:
        assert cli.reference(cli.REPOSITORY_ROOT / item["path"]) == item
    for video in cli.TRAIN:
        folder = run.path / "by_video" / video
        fields, raw = read_csv(folder / "ground_truth_raw.csv")
        assert fields == CSV_FIELDS and len(raw) == 64
        assert {row["object_id"] for row in raw} == {"original-id", "cluster-id"}
        fields, observations = read_csv(folder / "observations.csv")
        assert fields == cli.TABLE_FIELDS["observations"] and len(observations) == 32
        assert all(row["track_id"] == "original-id" for row in observations)
        assert float(observations[0]["cx"]) == 20.125
        fields, windows = read_csv(folder / "windows.csv")
        assert fields == cli.TABLE_FIELDS["windows"]
        assert [int(row["origin_frame"]) for row in windows] == [19, 20, 21]
        assert [int(row["future_end"]) for row in windows] == [29, 30, 31]
        assert not any("future_x" in row for row in windows)
        assert sources[video].gt_frames[0].detections[1].class_id == 1


def test_unexpected_missing_label_fails_before_export_or_completion(synthetic_run):
    path, run, sources, _ = synthetic_run
    frames = list(sources["11"].gt_frames)
    frames[5] = GroundTruthFrame(5, False)
    sources["11"].gt_frames = tuple(frames)
    with pytest.raises(ValueError, match="Unexpected annotation coverage"):
        cli.prepare(path)
    run.complete.assert_not_called()
    run.fail.assert_called_once()
    assert not (run.path / "by_video").exists()


def test_incomplete_frame_axis_fails_before_completion(synthetic_run):
    path, run, sources, _ = synthetic_run
    sources["11"].gt_frames = sources["11"].gt_frames[:-1]
    with pytest.raises(ValueError, match="complete expected universe"):
        cli.prepare(path)
    run.complete.assert_not_called()
    run.fail.assert_called_once()


@pytest.mark.parametrize("failure", ["source", "artifact"])
def test_final_integrity_failure_preserves_exports_without_completion(synthetic_run, failure):
    path, run, sources, _ = synthetic_run

    def changed():
        if failure == "source":
            raise RuntimeError("synthetic input changed")
        with (run.path / "by_video/11/observations.csv").open("a", encoding="utf-8") as stream:
            stream.write("changed\n")
        return {"status": "verified"}

    sources["11"].verify_current = changed
    with pytest.raises(RuntimeError, match="changed"):
        cli.prepare(path)
    run.complete.assert_not_called()
    run.fail.assert_called_once()
    assert (run.path / "by_video/12/summary.json").is_file()
    assert not (run.path / "summary.json").exists()


def test_preparation_cli_has_no_scientific_or_split_override(monkeypatch):
    monkeypatch.setattr(cli, "prepare", lambda *args: pytest.fail("preparation started"))
    with pytest.raises(SystemExit):
        cli.main(["--split", "test"])
