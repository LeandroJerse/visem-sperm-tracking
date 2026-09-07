"""Synthetic tests for the official detection evaluator."""
from __future__ import annotations

import csv
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.detection.base import Detection
from src.evaluation.detection import (
    DetectionEvaluator,
    aggregate_by_video,
    aggregate_frame_metrics,
    evaluate_frame,
    match_detections,
    write_frame_metrics_csv,
)


def det(cx: float, cy: float, class_id: int = 0) -> Detection:
    return Detection(cx=cx, cy=cy, w=4, h=4, class_id=class_id)


def test_default_gate_rejects_twelve_pixels_but_sensitivity_accepts():
    predictions, ground_truth = [det(0, 0)], [det(12, 0)]
    evaluator = DetectionEvaluator()
    rows = [
        evaluate_frame(predictions, ground_truth),
        evaluator.add_frame(predictions, ground_truth),
        evaluator.summary(),
    ]
    for row in rows:
        assert (row["tp"], row["fp"], row["fn"], row["f1"]) == (0, 1, 1, 0)
        for radius in (15, 20):
            assert (row[f"tp_at_{radius}px"], row[f"fp_at_{radius}px"],
                    row[f"fn_at_{radius}px"], row[f"f1_at_{radius}px"]) == (1, 0, 0, 1)
    assert rows[0]["center_gate_px"] == 10


def test_default_ten_pixel_gate_includes_the_boundary_only():
    on_boundary = match_detections([det(0, 0)], [det(6, 8)])
    outside = match_detections([det(0, 0)], [det(10.01, 0)])
    assert (on_boundary.tp, on_boundary.fp, on_boundary.fn) == (1, 0, 0)
    assert on_boundary.matches[0].distance_px == 10
    assert (outside.tp, outside.fp, outside.fn) == (0, 1, 1)


@pytest.mark.parametrize("legacy", [False, True])
def test_cli_resolution_preserves_explicit_historical_gates(legacy):
    from src.detection.pipeline import parse_args, resolve_cli_config

    arguments = ["--set", "evaluation.center_gate_px=15", "--set",
                 "evaluation.sensitivity_gates_px=[10,20]", "--set",
                 "evaluation.class_policy=binary"] if legacy else []
    evaluation = resolve_cli_config(parse_args(arguments))["evaluation"]
    row = evaluate_frame([det(0, 0)], [det(12, 0)], **{
        key: evaluation[key] for key in ("center_gate_px", "sensitivity_gates_px", "class_policy")
    })
    assert row["center_gate_px"] == (15 if legacy else 10)
    assert (row["tp"], row["fp"], row["fn"]) == ((1, 0, 0) if legacy else (0, 1, 1))
    if legacy:
        assert row["tp_at_10px"] == 0
        assert "tp_at_15px" not in row
    else:
        assert row["tp_at_15px"] == 1
    assert row["tp_at_20px"] == 1


def test_frozen_historical_yaml_keeps_its_evaluation_under_new_defaults():
    from src.detection.pipeline import parse_args, resolve_cli_config

    frozen_path = (Path(__file__).resolve().parents[2]
                   / "configs/frozen/detection/threshold/t200_o1_c2.yaml")
    config = resolve_cli_config(parse_args(["--config", str(frozen_path)]))
    evaluation = config["evaluation"]
    assert config["run"]["frozen"] is True
    assert evaluation["center_gate_px"] == 15
    assert evaluation["sensitivity_gates_px"] == [10, 20]
    assert evaluation.get("protocol_id") != "center_distance_v2_10px"
    row = evaluate_frame([det(0, 0)], [det(12, 0)], **{
        key: evaluation[key] for key in ("center_gate_px", "sensitivity_gates_px", "class_policy")
    })
    assert (row["tp"], row["fp"], row["fn"]) == (1, 0, 0)
    assert row["tp_at_10px"] == 0 and row["tp_at_20px"] == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_runner_writes_metrics_with_effective_gates(tmp_path, monkeypatch, legacy):
    from src.detection import runner

    class SyntheticCapture:
        def __init__(self, _path):
            self.done = False

        def isOpened(self):
            return True

        def get(self, prop):
            return 30 if prop == runner.cv2.CAP_PROP_FPS else 100

        def read(self):
            if self.done:
                return False, None
            self.done = True
            return True, object()

        def release(self):
            pass

    detector = SimpleNamespace(name="synthetic", reset=lambda: None,
                               detect=lambda _frame: [det(0, 0)])
    monkeypatch.setattr(runner.cv2, "VideoCapture", SyntheticCapture)
    monkeypatch.setattr(runner, "index_label_files", lambda _path: {0: "synthetic"})
    monkeypatch.setattr(runner, "load_gt_for_frame", lambda *_args, **_kwargs:
                        SimpleNamespace(annotated=True, detections=[det(12, 0)]))
    gates = {"center_gate_px": 15, "sensitivity_gates_px": (10, 20), "class_policy": "binary"} if legacy else {}
    output = tmp_path / "frame_metrics.csv"
    summary = runner.run_on_video(
        detector, "synthetic.mp4", tmp_path / "detections.csv", gt_dir="synthetic",
        out_frames_csv=output, verbose=False, **gates,
    )
    with output.open(newline="", encoding="utf-8") as handle:
        row, = csv.DictReader(handle)
    assert float(row["center_gate_px"]) == (15 if legacy else 10)
    assert (summary["tp"], summary["fp"], summary["fn"]) == ((1, 0, 0) if legacy else (0, 1, 1))
    if legacy:
        assert float(row["tp_at_10px"]) == 0
        assert "tp_at_15px" not in row
    else:
        assert float(row["tp_at_15px"]) == 1
    assert float(row["tp_at_20px"]) == 1


def test_hungarian_is_one_to_one_and_gate_is_inclusive():
    result = match_detections(
        [det(0, 0), det(10, 0)],
        [det(0, 0), det(25, 0)],
        center_gate_px=15,
    )
    assert result.tp == 2
    assert result.fp == 0
    assert result.fn == 0
    assert sorted(match.distance_px for match in result.matches) == [0, 15]


def test_hungarian_maximises_valid_pairs_before_distance():
    # The cheapest first pair (p0-g0) would leave p1 invalid. A global
    # assignment instead uses p0-g1 and p1-g0, yielding two valid matches.
    result = match_detections(
        [det(0, 0), det(3, 0)],
        [det(1, 0), det(-3, 0)],
        center_gate_px=3,
    )
    assert result.tp == 2
    assert result.fp == 0
    assert result.fn == 0


def test_binary_policy_collapses_classes_and_class_aware_does_not():
    pred = [det(10, 10, class_id=0)]
    gt = [det(10, 10, class_id=2)]
    assert match_detections(pred, gt, class_policy="binary").tp == 1
    aware = match_detections(pred, gt, class_policy="class-aware")
    assert aware.tp == 0
    assert aware.fp == 1
    assert aware.fn == 1


def test_frame_metrics_tp_fp_fn_center_and_count_errors():
    metrics = evaluate_frame(
        [det(0, 0), det(100, 100)],
        [det(3, 4), det(20, 20)],
        video_id="11",
        frame=7,
        center_gate_px=15,
    )
    assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (1, 1, 1)
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["center_error_mean_px"] == 5
    assert metrics["count_error"] == 0
    assert metrics["count_abs_error"] == 0


def test_unannotated_is_distinct_from_annotated_empty():
    skipped = evaluate_frame([det(1, 1)], None, frame=1)
    annotated_empty = evaluate_frame([det(1, 1)], [], frame=2)
    assert skipped["annotated"] is False
    assert skipped["fp"] is None
    assert annotated_empty["annotated"] is True
    assert annotated_empty["fp"] == 1
    assert annotated_empty["n_ground_truth"] == 0


def test_aggregate_ignores_unannotated_frames_and_uses_micro_prf():
    frames = [
        evaluate_frame([det(0, 0)], [det(0, 0)], video_id="11", frame=0),
        evaluate_frame([det(1, 1)], None, video_id="11", frame=1),
        evaluate_frame([], [det(5, 5)], video_id="11", frame=2),
    ]
    summary = aggregate_frame_metrics(frames)
    assert summary["frames_total"] == 3
    assert summary["frames_annotated"] == 2
    assert summary["frames_unannotated"] == 1
    assert (summary["tp"], summary["fp"], summary["fn"]) == (1, 0, 1)
    assert summary["precision"] == 1.0
    assert summary["recall"] == 0.5
    assert math.isclose(summary["f1"], 2 / 3)
    assert summary["count_mae"] == 0.5
    assert summary["count_bias"] == -0.5


def test_no_annotated_frames_makes_no_accuracy_claim():
    summary = aggregate_frame_metrics([evaluate_frame([det(0, 0)], None)])
    assert summary["frames_annotated"] == 0
    assert summary["precision"] is None
    assert summary["recall"] is None
    assert summary["f1"] is None


def test_accumulator_aggregates_each_video_separately():
    evaluator = DetectionEvaluator(center_gate_px=10)
    evaluator.add_frame([det(0, 0)], [det(0, 0)], video_id="11")
    evaluator.add_frame([], [det(0, 0)], video_id="12")
    grouped = aggregate_by_video(evaluator.frames)
    assert grouped["11"]["f1"] == 1.0
    assert grouped["12"]["f1"] == 0.0


def test_sensitivity_gates_do_not_change_the_primary_gate(tmp_path):
    predictions = [det(0, 0), det(19, 0)]
    ground_truth = [det(0, 0), det(30, 0)]
    evaluator = DetectionEvaluator(
        center_gate_px=15, sensitivity_gates_px=(10, 20), class_policy="binary"
    )

    row = evaluator.add_frame(predictions, ground_truth, annotated=True)
    summary = evaluator.summary()

    assert row["tp"] == 2
    assert row["tp_at_10px"] == 1
    assert row["tp_at_20px"] == 2
    assert summary["f1"] == 1.0
    assert summary["f1_at_10px"] == 0.5
    assert summary["f1_at_20px"] == 1.0
    output = write_frame_metrics_csv([row], tmp_path / "historical.csv")
    with output.open(encoding="utf-8", newline="") as handle:
        csv_row, = csv.DictReader(handle)
    assert "tp_at_10px" in csv_row and "tp_at_20px" in csv_row
    assert "tp_at_15px" not in csv_row
