"""Contratos dos wrappers e da bancada manual reorganizada."""

from __future__ import annotations

import importlib
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.core.paths import EXPERIMENT_TESTS_ROOT
from src.detection.base import Detection
from src.detection.io import GroundTruthFrame
from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID, evaluate_frame
from script.detection.test.threshold.single_frame import (
    DEFAULT_TEST_ROOT,
    _configuration_identity,
    _resolved_parameters,
)
from script.detection.test.threshold import batch_frames, frames, single_frame


@pytest.mark.parametrize(
    ("wrapper_name", "implementation_name"),
    [
        ("script.detection.application.run_detection", "src.detection.pipeline"),
        ("script.detection.application.run_split", "src.detection.split_runner"),
        (
            "script.detection.application.yolo.evaluate",
            "src.detection.yolo_evaluation",
        ),
        ("script.detection.test.yolo.train", "src.detection.yolo_training"),
        ("script.detection.test.yolo.evaluate", "src.detection.yolo_evaluation"),
        ("script.detection.test.run_detection", "src.detection.pipeline"),
        ("script.detection.test.run_split", "src.detection.split_runner"),
        ("script.tracking.application.run_tracking", "src.tracking.pipeline"),
        ("script.tracking.test.run_tracking", "src.tracking.pipeline"),
        ("script.flow.application.run_flow", "src.flow.pipeline"),
        ("script.flow.test.run_flow", "src.flow.pipeline"),
        ("script.prediction.application.run_prediction", "src.prediction.pipeline"),
        ("script.prediction.test.run_prediction", "src.prediction.pipeline"),
        (
            "script.integration.application.enrich_tracks_with_flow",
            "src.integration.enrich_tracks_with_flow",
        ),
    ],
)
def test_application_wrapper_is_thin(wrapper_name: str, implementation_name: str):
    wrapper = importlib.import_module(wrapper_name)
    implementation = importlib.import_module(implementation_name)
    assert wrapper.main is implementation.main


def test_frame_screening_configuration_identity_is_stable_and_separated():
    params = _resolved_parameters(
        "threshold",
        {"threshold_value": 200, "close_iterations": 2},
        None,
    )
    first = _configuration_identity("threshold", params)
    second = _configuration_identity("threshold", dict(reversed(list(params.items()))))
    alternative = _configuration_identity(
        "threshold",
        _resolved_parameters(
            "threshold",
            {"threshold_value": 190, "close_iterations": 1},
            None,
        ),
    )

    assert DEFAULT_TEST_ROOT == EXPERIMENT_TESTS_ROOT / "detection"
    assert first == second
    assert first[0] == "threshold"
    assert first[1].startswith("t200_o1_c2__cfg")
    assert alternative[1].startswith("t190_o1_c1__cfg")
    assert first != alternative


def test_single_frame_rejects_blocked_test_before_decoding(monkeypatch):
    monkeypatch.setattr(
        single_frame,
        "resolve_source",
        lambda video, video_id: (Path("blocked.mp4"), Path("labels"), "24"),
    )

    def fail_if_decoded(*args, **kwargs):
        raise AssertionError("the blocked test video must not be decoded")

    monkeypatch.setattr(single_frame, "read_frame", fail_if_decoded)
    with pytest.raises(ValueError, match="teste bloqueado"):
        single_frame.main(["--method", "threshold", "--id", "24", "--frame", "0"])


def test_batch_frame_screening_rejects_blocked_test_ids():
    with pytest.raises(SystemExit, match="teste bloqueado"):
        batch_frames.main(["--ids", "24", "--dry-run"])


def test_single_frame_rejects_known_test_path_before_decoding(tmp_path, monkeypatch):
    root = tmp_path / "known_tracking"
    blocked = root / "24" / "24.mp4"
    blocked.parent.mkdir(parents=True)
    blocked.touch()
    monkeypatch.setattr(single_frame, "VISEM_TRACKING_TRAIN_ROOT", root)
    monkeypatch.setattr(single_frame, "load_split_spec", lambda *args: SimpleNamespace(train={"11"}, val=set(), test={"24"}))

    def fail_if_decoded(*args, **kwargs):
        raise AssertionError("--video must not bypass the known test guard")

    monkeypatch.setattr(single_frame, "read_frame", fail_if_decoded)
    with pytest.raises(ValueError, match="teste bloqueado"):
        single_frame.main(["--method", "threshold", "--video", str(blocked)])
    assert single_frame._known_tracking_video_id(tmp_path / "raw" / "24.mp4") is None


def test_frame_helper_preserves_unannotated_gap(tmp_path):
    ground_truth = frames.load_gt(tmp_path, frame_index=17, w=640, h=480)
    assert ground_truth is not None
    assert ground_truth.annotated is False
    assert ground_truth.detections == ()


def test_single_frame_distinguishes_10px_from_sensitivity_and_keeps_history(tmp_path, monkeypatch):
    root = tmp_path / "detection"
    run_path = root / "threshold" / "synthetic_run"
    run_path.mkdir(parents=True)
    comparison_root = root / "threshold" / "_comparisons" / "frame_screening"
    historical = comparison_root / "by_video" / "video_11.csv"
    historical.parent.mkdir(parents=True)
    historical.write_text("old_15px_result\n", encoding="utf-8")
    captured: dict = {}

    def create_context(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            path=run_path, run_id="synthetic", configuration_id="synthetic",
            complete=lambda **kwargs: None, fail=lambda exc: None,
        )

    monkeypatch.setattr(single_frame, "RunContext", SimpleNamespace(create=create_context))
    monkeypatch.setattr(single_frame, "DEFAULT_TEST_ROOT", root)
    monkeypatch.setattr(single_frame, "resolve_source", lambda *args: (Path("11.mp4"), Path("labels"), "11"))
    monkeypatch.setattr(single_frame, "load_split_spec", lambda *args: SimpleNamespace(train={"11"}, val=set(), test={"24"}))
    monkeypatch.setattr(single_frame, "read_frame", lambda *args: (np.zeros((64, 64, 3), dtype=np.uint8), 64, 64))
    monkeypatch.setattr(single_frame, "load_gt", lambda *args: GroundTruthFrame(0, True, (Detection(20, 20, 8, 8),)))
    monkeypatch.setattr(single_frame, "build_detector", lambda *args: SimpleNamespace(
        name="synthetic", detect=lambda frame: [Detection(32, 20, 8, 8)],
    ))

    summary = single_frame.main(["--method", "threshold", "--id", "11", "--no-stages"])
    assert summary["metric_primary"] == "f1_individuals_center_10px"
    assert summary["center_gate_px"] == 10.0
    assert summary["f1"] == 0.0
    assert summary["tp"] == 0 and summary["fp"] == 1 and summary["fn"] == 1
    assert summary["f1_at_15px"] == 1.0 and summary["f1_at_20px"] == 1.0
    assert captured["config"]["evaluation"] == {
        "protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID, "center_gate_px": 10.0,
        "sensitivity_gates_px": [15.0, 20.0], "class_policy": "individuals_ignore_clusters",
    }
    assert historical.read_text(encoding="utf-8") == "old_15px_result\n"
    comparison = comparison_root / DEFAULT_EVALUATION_PROTOCOL_ID / "by_video" / "video_11.csv"
    with comparison.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert row["metric_primary"] == "f1_individuals_center_10px"
    assert json.loads(row["sensitivity_gates_px"]) == [15.0, 20.0]
    assert float(row["f1"]) == 0.0 and float(row["f1_at_15px"]) == 1.0


def test_threshold_battery_preserves_sensitivity_when_aggregating_by_video(tmp_path, monkeypatch):
    monkeypatch.setattr(batch_frames, "DEFAULT_TEST_ROOT", tmp_path)
    monkeypatch.setattr(batch_frames, "CONFIGS", [("synthetic", {})])

    def synthetic_summary(argv):
        video_id = argv[argv.index("--id") + 1]
        matched = video_id == "12"
        spatial = evaluate_frame(
            [Detection(20 if matched else 32, 20, 8, 8)],
            [Detection(20, 20, 8, 8)], video_id=video_id,
        )
        return {
            **spatial,
            "count_diff": 0, "count_ratio": 1.0, "n_ground_truth": 1, "n_detections": 1,
        }

    monkeypatch.setattr(batch_frames, "run_single_frame", synthetic_summary)
    batch_frames.run_battery(["11", "12"], [0, 1], False, "train")
    parent = tmp_path / "threshold" / "_comparisons" / "frame_screening"
    assert not list(parent.glob("batch_*.csv"))
    output = next((parent / DEFAULT_EVALUATION_PROTOCOL_ID).glob("batch_*.csv"))
    with output.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["metric_primary"] == "macro_video_f1_individuals_center_10px"
    assert row["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert float(row["macro_video_f1"]) == 0.5
    assert float(row["macro_video_f1_at_15px"]) == 1.0
    assert float(row["macro_video_f1_at_20px"]) == 1.0
    assert int(row["total_tp_at_15px"]) == 4
    assert json.loads(row["sensitivity_gates_px"]) == [15.0, 20.0]
