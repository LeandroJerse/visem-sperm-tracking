"""Contratos sintéticos da triagem temporal de MOG2/KNN."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.core.paths import REPOSITORY_ROOT
from src.detection.base import Detection
from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID
from src.experiments.config import ConfigError
from src.experiments.sampling import ClipWindow
from script.detection.test.background_subtraction import batch_clips


def _synthetic_video(path: Path, evaluation_frames: set[int]) -> tuple[int, int]:
    width, height = 64, 48
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (width, height)
    )
    assert writer.isOpened()
    for frame_idx in range(220):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        if frame_idx in evaluation_frames:
            cv2.circle(frame, (32, 24), 5, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return width, height


def _labels(folder: Path, frame_indices: set[int], width: int, height: int) -> None:
    folder.mkdir()
    # Box centred on the synthetic circle, in canonical YOLO coordinates.
    line = f"0 {32 / width} {24 / height} {10 / width} {10 / height}\n"
    for frame_idx in frame_indices:
        (folder / f"11_frame_{frame_idx}.txt").write_text(line, encoding="utf-8")


def _config() -> dict:
    config = copy.deepcopy(batch_clips.DEFAULTS)
    config["method"] = "mog2"
    config["params"] = {
        "history": 20,
        "var_threshold": 16,
        "detect_shadows": False,
        "morph_kernel": 1,
        "min_area": 5,
        "max_area": 200,
    }
    config["sampling"] = {
        "unit": "clip",
        "clip_count": 2,
        "warmup_frames": 100,
        "scored_frames": 2,
    }
    config["run"].update({"stage": "smoke", "split": "train", "seed": 42})
    return config


def test_sampling_rejects_transient_shorter_than_one_hundred_frames():
    with pytest.raises(ConfigError, match=">= 100"):
        batch_clips._validate_sampling(
            {"clip_count": 1, "warmup_frames": 99, "scored_frames": 1}
        )


def test_clip_screening_refuses_the_blocked_test_split_before_video_access():
    with pytest.raises(ConfigError, match="somente treino"):
        batch_clips._select_train_ids(["24"])


@pytest.mark.parametrize(
    ("evaluation", "message"),
    [
        ({"center_gate_px": 15.0}, "a 10 px"),
        ({"sensitivity_gates_px": [20.0]}, "15 e 20 px"),
        ({"protocol_id": "historical_15px"}, "protocol_id"),
    ],
)
def test_official_evaluation_rejected_before_video_access(
    tmp_path, monkeypatch, evaluation, message
):
    config = _config()
    config["evaluation"].update(evaluation)

    def fail_if_opened(*args, **kwargs):
        raise AssertionError("invalid evaluation must not access the video")

    monkeypatch.setattr(batch_clips, "_video_probe", fail_if_opened)
    with pytest.raises(ConfigError, match=message):
        batch_clips.run_video_configuration(
            config,
            video_path=tmp_path / "must_not_be_opened.mp4",
            gt_dir=None,
            video_id="11",
            windows=[ClipWindow(0, 100, 101)],
        )


def test_mog2_distributed_clips_exclude_warmup_and_record_provenance(tmp_path):
    evaluated = {100, 101, 218, 219}
    video_path = tmp_path / "synthetic.avi"
    width, height = _synthetic_video(video_path, evaluated)
    gt_dir = tmp_path / "labels"
    _labels(gt_dir, evaluated, width, height)

    windows = batch_clips.plan_video_clips(
        video_path,
        clip_count=2,
        warmup_frames=100,
        scored_frames=2,
    )
    assert [(item.evaluation_start, item.evaluation_stop) for item in windows] == [
        (100, 102),
        (218, 220),
    ]

    summary = batch_clips.run_video_configuration(
        _config(),
        video_path=video_path,
        gt_dir=gt_dir,
        video_id="11",
        windows=windows,
        output_root=tmp_path / "data_tests",
        repo_root=REPOSITORY_ROOT,
    )
    run_dir = Path(summary["run_dir"])
    assert summary["warmup_frames_total"] == 200
    assert summary["scored_frames"] == 4
    assert summary["annotated_frames"] == 4
    assert summary["metric_primary"] == "f1_individuals_center_10px"
    assert summary["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert summary["sensitivity_gates_px"] == [15.0, 20.0]
    assert summary["f1_at_15px"] >= summary["f1"]
    assert summary["f1_at_20px"] >= summary["f1_at_15px"]
    assert summary["f1"] is not None
    assert summary["tp"] >= 1  # the real OpenCV MOG2 detected the inserted change

    with (run_dir / "frame_metrics.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        metric_rows = list(csv.DictReader(stream))
    assert {int(row["frame"]) for row in metric_rows} == evaluated
    assert all(row["warmup_excluded"] == "True" for row in metric_rows)
    assert all(float(row["center_gate_px"]) == 10.0 for row in metric_rows)
    assert all("f1_at_15px" in row and "f1_at_20px" in row for row in metric_rows)

    with (run_dir / "detections.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        detection_rows = list(csv.DictReader(stream))
    assert detection_rows
    assert {int(row["frame"]) for row in detection_rows} <= evaluated

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["config"]["evaluation"] == {
        "protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID,
        "center_gate_px": 10.0,
        "sensitivity_gates_px": [15.0, 20.0],
        "class_policy": "individuals_ignore_clusters",
    }
    assert manifest["config"]["input"]["clip_windows"] == [
        {
            "clip_index": 0,
            "warmup_start": 0,
            "evaluation_start": 100,
            "evaluation_stop_exclusive": 102,
            "warmup_frames": 100,
            "scored_frames_planned": 2,
        },
        {
            "clip_index": 1,
            "warmup_start": 118,
            "evaluation_start": 218,
            "evaluation_stop_exclusive": 220,
            "warmup_frames": 100,
            "scored_frames_planned": 2,
        },
    ]
    assert manifest["summary"]["warmup_excluded_from_metrics"] is True


def test_clip_comparison_records_the_three_gates_with_equal_video_weight(tmp_path):
    common = {
        "configuration_id": "synthetic", "configuration_hash": "hash",
        "count_mae": 0,
    }
    summaries = [
        {**common, "run_id": "one", "run_dir": "one", "f1": 0.0,
         "tp": 0, "fp": 1, "fn": 1,
         "f1_at_15px": 0.5, "f1_at_20px": 1.0},
        {**common, "run_id": "two", "run_dir": "two", "f1": 1.0,
         "tp": 1, "fp": 0, "fn": 0,
         "f1_at_15px": 1.0, "f1_at_20px": 1.0},
    ]
    csv_path, manifest_path = batch_clips._aggregate_configurations(
        summaries, method="mog2", output_root=tmp_path,
        batch_id="synthetic", invocation={},
    )
    with csv_path.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["evaluation_protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID
    assert row["metric_primary"] == "macro_video_f1_individuals_center_10px"
    assert float(row["macro_video_f1"]) == 0.5
    assert float(row["macro_video_f1_at_15px"]) == 0.75
    assert float(row["macro_video_f1_at_20px"]) == 1.0
    assert json.loads(row["sensitivity_gates_px"]) == [15.0, 20.0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["center_gate_px"] == 10.0
    assert manifest["sensitivity_gates_px"] == [15.0, 20.0]


def test_clip_cluster_only_run_preserves_raw_rows_and_secondary_in_all_artifacts(tmp_path, monkeypatch):
    video_path = tmp_path / "synthetic.avi"
    _synthetic_video(video_path, {100, 101})
    gt_dir = tmp_path / "cluster_labels"
    gt_dir.mkdir()
    for frame in (100, 101):
        (gt_dir / f"11_frame_{frame}.txt").write_text("1 0.5 0.5 0.5 0.5\n", encoding="utf-8")
    monkeypatch.setattr(batch_clips, "build_detector", lambda *args, **kwargs: SimpleNamespace(
        name="synthetic", reset=lambda: None,
        detect=lambda frame: [Detection(32, 24, 8, 8)],
    ))
    config = _config()
    config["sampling"]["clip_count"] = 1
    summary = batch_clips.run_video_configuration(
        config, video_path=video_path, gt_dir=gt_dir, video_id="11",
        windows=[ClipWindow(0, 100, 102)], output_root=tmp_path / "runs",
    )
    run_dir = Path(summary["run_dir"])
    assert summary["n_predictions_raw"] == 2
    assert summary["n_predictions_scored"] == 0
    assert summary["n_predictions_ignored"] == 2
    assert summary["n_ground_truth_raw"] == 2 and summary["n_ground_truth_scored"] == 0
    assert summary["f1"] is None and summary["count_mae"] == 0
    assert summary["count_evaluated_frames"] == 2
    assert summary["secondary_all_objects_f1"] == 1
    with (run_dir / "detections.csv").open(newline="", encoding="utf-8") as stream:
        raw = list(csv.DictReader(stream))
    assert len(raw) == 4 and sum(row["source"] == "manual" for row in raw) == 2
    with (run_dir / "frame_metrics.csv").open(newline="", encoding="utf-8") as stream:
        frame_rows = list(csv.DictReader(stream))
    assert all(row["primary_evaluable"] == "False" for row in frame_rows)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["secondary_all_objects_f1_at_20px"] == 1
    csv_path, _ = batch_clips._aggregate_configurations(
        [summary], method="mog2", output_root=tmp_path / "runs", batch_id="clusters", invocation={},
    )
    with csv_path.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["n_videos_with_gt"] == "1" and row["n_videos_primary_evaluable"] == "0"
    assert row["macro_video_f1"] == ""
    assert row["total_n_predictions_ignored_at_15px"] == "2"
    assert float(row["macro_video_secondary_all_objects_f1_at_20px"]) == 1
    assert row["total_frames_cluster_only_gt"] == "2"
