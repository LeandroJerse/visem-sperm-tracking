"""Synthetic contracts for V3 propagation without opening dataset videos."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.detection.base import Detection
from src.detection.io import GroundTruthFrame
from src.detection import pipeline, runner
from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID, evaluate_frame
from src.experiments.config import ConfigError
from script.detection.test.threshold import batch_frames, single_frame


def _csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture
def synthetic_runner(monkeypatch):
    predictions = [
        [Detection(20, 20, 8, 8), Detection(21, 20, 8, 8),
         Detection(45, 20, 8, 8), Detection(20, 40, 8, 8, class_id=2)],
        [Detection(30, 20, 8, 8)],
        [Detection(50, 40, 8, 8)],
    ]
    labels = [
        GroundTruthFrame(0, True, (
            Detection(20, 20, 8, 8), Detection(20, 40, 8, 8, class_id=2),
            Detection(30, 20, 40, 20, class_id=1),
        )),
        GroundTruthFrame(1, True, (Detection(30, 20, 40, 20, class_id=1),)),
        GroundTruthFrame(2, False),
    ]

    class Capture:
        index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return {cv2.CAP_PROP_FPS: 20, cv2.CAP_PROP_FRAME_WIDTH: 64,
                    cv2.CAP_PROP_FRAME_HEIGHT: 64}.get(prop, 0)

        def read(self):
            if self.index == len(predictions):
                return False, None
            frame = np.full((64, 64, 3), self.index, dtype=np.uint8)
            self.index += 1
            return True, frame

        def release(self):
            pass

    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda *args: Capture())
    monkeypatch.setattr(runner, "index_label_files", lambda *args: {})
    monkeypatch.setattr(runner, "load_gt_for_frame", lambda folder, idx, *args, **kwargs: labels[idx])
    return SimpleNamespace(
        name="synthetic", reset=lambda: None,
        detect=lambda frame: predictions[int(frame[0, 0, 0])],
    )


def test_runner_preserves_raw_rows_and_propagates_ignore_secondary_and_fixed_count_denominator(
    tmp_path, synthetic_runner,
):
    summary = runner.run_on_video(
        synthetic_runner, tmp_path / "synthetic.mp4", tmp_path / "detections.csv",
        video_id="11", gt_dir=tmp_path / "labels", verbose=False,
    )
    raw = _csv(tmp_path / "detections.csv")
    assert len(raw) == 10
    assert sum(row["source"] == "detection" for row in raw) == 6
    assert sum(row["source"] == "manual" and row["class_id"] == "1" for row in raw) == 2
    frames = _csv(Path(summary["frames_csv"]))
    first, cluster_only, unannotated = frames
    assert first["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert (first["tp"], first["fp"], first["fn"]) == ("2", "1", "0")
    assert first["n_predictions_raw"] == "4"
    assert first["n_ground_truth_raw"] == "3"
    assert first["n_predictions_ignored"] == "1"
    assert first["n_predictions_scored"] == "3"
    assert cluster_only["primary_evaluable"] == "False"
    assert cluster_only["f1"] == "" and cluster_only["count_error"] == "0"
    assert cluster_only["secondary_all_objects_f1"] == "1.0"
    assert unannotated["annotated"] == "False" and unannotated["n_predictions_scored"] == ""
    assert summary["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert summary["frames_primary_unevaluable"] == 1
    assert summary["frames_cluster_only_gt"] == 1
    assert summary["count_evaluated_frames"] == 2
    assert summary["count_mae"] == 0.5  # the cluster-only zero remains in the denominator
    assert summary["n_predictions_raw"] == 6
    assert summary["n_predictions_scored"] == 3
    assert summary["n_predictions_ignored"] == 2
    assert summary["n_predictions_unannotated"] == 1
    assert summary["secondary_all_objects_f1_at_15px"] is not None
    assert summary["n_ground_truth_scored_at_20px"] == 2


def test_runner_explicit_historical_binary_evaluates_cluster_as_object(tmp_path, synthetic_runner):
    summary = runner.run_on_video(
        synthetic_runner, tmp_path / "synthetic.mp4", tmp_path / "legacy.csv",
        video_id="11", gt_dir=tmp_path / "labels", verbose=False,
        center_gate_px=15, sensitivity_gates_px=(10, 20), class_policy="binary",
    )
    assert summary["evaluation_protocol_id"] is None
    assert summary["n_ground_truth_scored"] == summary["n_ground_truth_raw"] == 4
    assert summary["n_predictions_ignored"] == 0
    assert summary["metric_primary"] == "f1_center_15px"
    assert "f1_at_10px" in summary and "f1_at_15px" not in summary


def test_cli_resolves_v3_and_preserves_explicit_legacy_evaluation(tmp_path):
    current = pipeline.resolve_cli_config(pipeline.parse_args(["--method", "threshold"]))
    assert current["evaluation"]["protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        "method: threshold\nevaluation:\n  center_gate_px: 15\n"
        "  sensitivity_gates_px: [10, 20]\n  class_policy: binary\n",
        encoding="utf-8",
    )
    resolved = pipeline.resolve_cli_config(pipeline.parse_args(["--config", str(legacy)]))
    assert resolved["evaluation"] == {
        "center_gate_px": 15, "sensitivity_gates_px": [10, 20], "class_policy": "binary",
    }
    with pytest.raises(ConfigError, match="protocol_id"):
        pipeline.resolve_cli_config(pipeline.parse_args([
            "--method", "threshold", "--set", "evaluation.protocol_id=center_distance_v2_10px",
        ]))
    with pytest.raises(ConfigError, match="protocol_id"):
        pipeline.resolve_cli_config(pipeline.parse_args([
            "--config", str(legacy), "--set", f"evaluation.protocol_id={DEFAULT_EVALUATION_PROTOCOL_ID}",
        ]))


def test_single_frame_cluster_only_exports_raw_gt_and_secondary_with_undefined_primary(tmp_path, monkeypatch):
    root = tmp_path / "detection"
    run_path = root / "threshold" / "synthetic_run"
    run_path.mkdir(parents=True)
    captured = {}

    def create_context(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            path=run_path, run_id="synthetic", configuration_id="synthetic",
            complete=lambda **kwargs: captured.update(completed=kwargs), fail=lambda exc: None,
        )

    monkeypatch.setattr(single_frame, "RunContext", SimpleNamespace(create=create_context))
    monkeypatch.setattr(single_frame, "DEFAULT_TEST_ROOT", root)
    monkeypatch.setattr(single_frame, "resolve_source", lambda *args: (Path("11.mp4"), Path("labels"), "11"))
    monkeypatch.setattr(single_frame, "load_split_spec", lambda *args: SimpleNamespace(train={"11"}, val=set(), test={"24"}))
    monkeypatch.setattr(single_frame, "read_frame", lambda *args: (np.zeros((64, 64, 3), dtype=np.uint8), 64, 64))
    monkeypatch.setattr(single_frame, "load_gt", lambda *args: GroundTruthFrame(0, True, (Detection(30, 20, 40, 20, class_id=1),)))
    monkeypatch.setattr(single_frame, "build_detector", lambda *args: SimpleNamespace(name="synthetic", detect=lambda frame: [Detection(30, 20, 8, 8)]))
    summary = single_frame.main(["--method", "threshold", "--id", "11", "--no-stages"])
    assert summary["f1"] is None and summary["count_diff"] == 0
    assert summary["n_ground_truth"] == 1 and summary["n_ground_truth_scored"] == 0
    assert summary["n_predictions_ignored"] == 1
    assert len(_csv(run_path / "detections.csv")) == 2
    comparison = root / "threshold" / "_comparisons" / "frame_screening" / DEFAULT_EVALUATION_PROTOCOL_ID / "by_video" / "video_11.csv"
    row = _csv(comparison)[0]
    assert row["n_predictions_ignored_at_15px"] == "1"
    assert row["secondary_all_objects_f1_at_20px"] == "1.0"
    assert row["primary_evaluable"] == "False" and row["f1"] == ""
    assert captured["completed"]["summary"]["secondary_all_objects_f1"] == 1.0
    assert json.loads((run_path / "summary.json").read_text(encoding="utf-8"))["count_scope"] == "scored_predictions_minus_individually_annotated_gt"


def test_frame_battery_keeps_cluster_only_frames_in_counts_and_reports_evaluable_videos(tmp_path, monkeypatch):
    monkeypatch.setattr(batch_frames, "DEFAULT_TEST_ROOT", tmp_path)
    monkeypatch.setattr(batch_frames, "CONFIGS", [("synthetic", {})])
    cluster = Detection(30, 20, 40, 20, class_id=1)
    first = evaluate_frame([Detection(30, 20, 8, 8)], [cluster], video_id="11")
    second = evaluate_frame([], [Detection(20, 20, 8, 8)], video_id="12")
    records = [{**row, "count_diff": row["count_error"], "count_ratio": None} for row in (first, second)]
    batch_frames._write_global_summary({"synthetic": records}, [0], ["11", "12"], "train")
    path = next((tmp_path / "threshold" / "_comparisons" / "frame_screening" / DEFAULT_EVALUATION_PROTOCOL_ID).glob("batch_*.csv"))
    row = _csv(path)[0]
    assert row["n_videos_primary_evaluable"] == "1"
    assert row["total_frames_cluster_only_gt"] == "1"
    assert row["total_n_predictions_ignored"] == "1"
    assert float(row["macro_video_count_mae"]) == 0.5
    assert float(row["macro_video_secondary_all_objects_f1"]) == 0.5
