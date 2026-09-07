"""Contratos sintéticos da triagem temporal de MOG2/KNN."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import ConfigError
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
    assert summary["metric_primary"] == "f1_center_15px"
    assert summary["f1"] is not None
    assert summary["tp"] >= 1  # the real OpenCV MOG2 detected the inserted change

    with (run_dir / "frame_metrics.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        metric_rows = list(csv.DictReader(stream))
    assert {int(row["frame"]) for row in metric_rows} == evaluated
    assert all(row["warmup_excluded"] == "True" for row in metric_rows)
    assert all(float(row["center_gate_px"]) == 15.0 for row in metric_rows)

    with (run_dir / "detections.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        detection_rows = list(csv.DictReader(stream))
    assert detection_rows
    assert {int(row["frame"]) for row in detection_rows} <= evaluated

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
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
