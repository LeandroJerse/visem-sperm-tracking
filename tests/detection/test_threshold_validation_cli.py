"""Coordinator integration with generated videos; no research source access."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from script.detection.test.threshold import validate as cli
from src.experiments import runs
from src.detection.strict_inputs import FullVideoInput


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    plan = yaml.safe_load(Path(cli.DEFAULT_PLAN).read_text(encoding="utf-8"))
    frames = {"14": 2, "19": 3, "36": 2, "52": 3}
    source = tmp_path / "synthetic_sources"
    for video_id, count in frames.items():
        folder = source / video_id
        labels = folder / "labels_ftid"
        labels.mkdir(parents=True)
        writer = cv2.VideoWriter(str(folder / f"{video_id}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (32, 24))
        if not writer.isOpened():
            pytest.skip("Synthetic MP4 encoder unavailable")
        try:
            for frame in range(count):
                pixels = np.zeros((24, 32, 3), dtype=np.uint8)
                pixels[9:15, 12:20] = 255
                writer.write(pixels)
                (labels / f"{video_id}_frame_{frame}_with_ftid.txt").write_text("42 0 .5 .5 .25 .25\n", encoding="utf-8")
        finally:
            writer.release()
    plan["input"].update(root=str(source), width=32, height=24, expected_frames=frames)
    candidates = [{"configuration_id": ident, "method": "threshold",
                   "params": {"threshold_value": threshold, "morph_iterations": 0, "close_iterations": 2,
                              "morph_kernel": 3, "min_area": 3, "max_area": 300, "blur": 1,
                              "adaptive": False, "invert": False},
                   "evaluation": copy.deepcopy(plan["evaluation"]), "provenance": {}}
                  for ident, threshold in (("t219_o0_c2", 219), ("t218_o0_c2", 218))]
    provenance = {"plan_hash": "synthetic", "expected_frames_per_video": frames,
                  "exact_frame_plan": [[v, i] for v in cli.VALIDATION_IDS for i in range(frames[v])],
                  "validated_inputs": []}
    monkeypatch.setattr(cli, "load_validation_plan", lambda _: copy.deepcopy((plan, candidates, provenance)))
    monkeypatch.setattr(cli, "_git_dirty", lambda _: False)
    monkeypatch.setattr(runs, "_git_dirty", lambda _: False)
    monkeypatch.setattr(runs, "_git_sha", lambda _: "synthetic")
    monkeypatch.setattr(runs, "_source_hash", lambda _: "synthetic-source")
    monkeypatch.setattr(runs, "environment_snapshot", lambda: {"synthetic": True})
    return tmp_path / "output", plan, candidates, provenance


def test_all_eight_full_runs_export_and_verify_before_selecting(experiment):
    output, plan, _, _ = experiment
    batch_path = cli.run_validation(output_root=output)
    batch = read(batch_path / "manifest.json")
    assert batch["status"] == "complete"
    assert batch["summary"]["frame_evaluations"] == 20
    assert batch["summary"]["frames_per_candidate"] == 10
    assert batch["summary"]["n_runs"] == 8
    assert batch["provenance_verification"]["status"] == "verified"
    selection = read(batch_path / "selection.json")
    assert selection["status"] == "validation_selected_not_frozen"
    assert selection["configuration_id"] == "t218_o0_c2"  # Identical quality: deterministic lexical tie break.
    assert not selection["test_executed"] and not selection["five_fold_executed"]
    pairs = set()
    for ref in batch["candidate_manifests"]:
        assert cli.sha256_file(ref["path"]) == ref["sha256"]
        child = read(ref["path"])
        summary = child["summary"]
        pairs.add((summary["configuration_id"], summary["video_id"]))
        assert summary["frames_total"] == plan["input"]["expected_frames"][summary["video_id"]]
        assert summary["frame_coverage_verified"] is True
        assert child["input_verification"]["status"] == "verified"
        assert child["frame_coverage_verification"]["status"] == "verified"
        for name, digest in child["artifact_hashes"].items():
            assert cli.sha256_file(child["artifacts"][name]) == digest
    assert len(pairs) == 8


def assert_failed_without_selection(output):
    batches = [read(p) for p in output.rglob("manifest.json") if read(p)["method"] == "threshold_validation"]
    assert len(batches) == 1 and batches[0]["status"] == "failed"
    assert batches[0]["selection_valid"] is False
    assert not list(output.rglob("selection.json"))


@pytest.mark.parametrize("failure", ["missing_frame", "duplicate_frame", "wrong_video", "unannotated",
                                    "wrong_summary", "no_eof", "fractional_tp", "wrong_gate", "wrong_f1"])
def test_bad_export_or_summary_never_selects(experiment, monkeypatch, failure):
    output, _, _, _ = experiment
    actual = cli.run_on_video
    def corrupt(*args, **kwargs):
        summary = actual(*args, **kwargs)
        path = kwargs["out_frames_csv"]
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        if failure == "missing_frame":
            rows.pop()
        elif failure == "duplicate_frame":
            rows[-1]["frame"] = rows[0]["frame"]
        elif failure == "wrong_video":
            rows[0]["video_id"] = "24"
        elif failure == "unannotated":
            rows[0]["annotated"] = "False"
        elif failure == "wrong_summary":
            summary["tp"] += 1
        elif failure == "fractional_tp":
            rows[0]["tp"] = "1.5"
        elif failure == "wrong_gate":
            rows[0]["center_gate_px"] = "999"
        elif failure == "wrong_f1":
            rows[0]["f1"] = "-0.25"
        else:
            summary["completeness"]["extra_read_eof"] = False
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
        return summary
    monkeypatch.setattr(cli, "run_on_video", corrupt)
    with pytest.raises(ValueError):
        cli.run_validation(output_root=output)
    assert_failed_without_selection(output)


def test_missing_label_fails_before_any_detector(experiment, monkeypatch):
    output, plan, _, _ = experiment
    label = Path(plan["input"]["root"]) / "52/labels_ftid/52_frame_1_with_ftid.txt"
    label.unlink()  # Generated fixture only.
    monkeypatch.setattr(cli, "build_detector", lambda *a, **k: pytest.fail("Incomplete input reached detector"))
    with pytest.raises(ValueError, match="coverage"):
        cli.run_validation(output_root=output)
    assert_failed_without_selection(output)


def test_source_changed_after_video_aborts(experiment, monkeypatch):
    output, plan, _, _ = experiment
    actual = cli.run_on_video
    def change_source(*args, **kwargs):
        summary = actual(*args, **kwargs)
        label = Path(plan["input"]["root"]) / kwargs["video_id"] / "labels_ftid" / f"{kwargs['video_id']}_frame_0_with_ftid.txt"
        label.write_text("changed synthetic source", encoding="utf-8")
        return summary
    monkeypatch.setattr(cli, "run_on_video", change_source)
    with pytest.raises(ValueError, match="changed"):
        cli.run_validation(output_root=output)
    assert_failed_without_selection(output)


def test_final_source_recheck_required_after_all_eight_runs(experiment, monkeypatch):
    output, _, _, _ = experiment
    actual = FullVideoInput.verify_current
    calls = []
    def verify(value):
        calls.append(value.video_id)
        if len(calls) == 9:
            raise ValueError("synthetic late source change")
        return actual(value)
    monkeypatch.setattr(FullVideoInput, "verify_current", verify)
    with pytest.raises(ValueError, match="late source"):
        cli.run_validation(output_root=output)
    assert len(calls) == 9
    assert_failed_without_selection(output)


@pytest.mark.parametrize("target", ["manifest.json", "detections.csv", "planned_pairs.json", "input_contracts.json"])
def test_child_tampering_after_completion_invalidates_batch(experiment, monkeypatch, target):
    output, _, _, _ = experiment
    actual = FullVideoInput.verify_current
    calls = []
    def verify(value):
        calls.append(value.video_id)
        if len(calls) == 9:
            path = next(p for p in output.rglob(target)
                        if target in {"planned_pairs.json", "input_contracts.json"} or "_batch__" not in str(p))
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n")
        return actual(value)
    monkeypatch.setattr(FullVideoInput, "verify_current", verify)
    with pytest.raises(ValueError, match="(child .* changed|batch artifact changed)"):
        cli.run_validation(output_root=output)
    assert_failed_without_selection(output)


def test_complete_parent_chain_is_resolved_again_before_ranking(experiment, monkeypatch):
    output, _, _, _ = experiment
    actual = cli.load_validation_plan
    calls = []
    def changed(path):
        calls.append(path)
        if len(calls) == 2:
            raise ValueError("Synthetic coarse-parent artifact changed")
        return actual(path)
    monkeypatch.setattr(cli, "load_validation_plan", changed)
    with pytest.raises(ValueError, match="coarse-parent"):
        cli.run_validation(output_root=output)
    assert len(calls) == 2
    assert_failed_without_selection(output)


def test_dirty_git_rejected_before_any_metadata_or_source(experiment, monkeypatch):
    output, _, _, _ = experiment
    monkeypatch.setattr(cli, "_git_dirty", lambda _: True)
    monkeypatch.setattr(cli, "load_validation_plan", lambda _: pytest.fail("Read prerequisites with dirty Git"))
    with pytest.raises(RuntimeError, match="Commit"):
        cli.run_validation(output_root=output)
    assert not output.exists()


def test_invalid_plan_cannot_open_sources(experiment, monkeypatch):
    output, _, _, _ = experiment
    def invalid(_):
        raise ValueError("Invalid registered plan")
    monkeypatch.setattr(cli, "load_validation_plan", invalid)
    monkeypatch.setattr(cli, "prepare_full_video_input", lambda *a, **k: pytest.fail("Invalid plan opened sources"))
    with pytest.raises(ValueError, match="Invalid"):
        cli.run_validation(output_root=output)
    assert not output.exists()


def test_budget_rejects_excess_predictions_without_truncation(experiment, monkeypatch):
    output, plan, _, _ = experiment
    plan["budget"]["max_predictions_per_frame"] = 0
    with pytest.raises(RuntimeError, match="Prediction budget"):
        cli.run_validation(output_root=output)
    assert_failed_without_selection(output)


def test_dry_run_reads_only_metadata(experiment, monkeypatch, capsys):
    monkeypatch.setattr(cli, "prepare_full_video_input", lambda *a, **k: pytest.fail("Dry run opened sources"))
    assert cli.main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "metadata_verified_no_validation_input_opened"


def test_output_may_not_pollute_research_sources(monkeypatch):
    monkeypatch.setattr(cli, "load_validation_plan", lambda _: pytest.fail("Invalid output opened prerequisites"))
    with pytest.raises(ValueError, match="data/sources"):
        cli.run_validation(output_root="data/sources/forbidden_output")


@pytest.mark.parametrize("override", ["--max-frames", "--video-id", "--set"])
def test_no_cli_override_can_change_registered_universe(override):
    with pytest.raises(SystemExit):
        cli.main([override, "1"])
