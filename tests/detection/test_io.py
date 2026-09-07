"""Unit tests for coordinate conversion and label parsing in detection.io."""
from __future__ import annotations

import csv
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from src.detection.base import Detection
from src.detection.classical.threshold import ThresholdContourDetector
from src.detection.hybrid.enhanced_threshold import HybridThresholdDetector
from src.detection.io import (
    extract_frame_index,
    index_label_files,
    load_gt_frame,
    load_gt_for_frame,
    parse_label_line,
    pixels_to_yolo,
    yolo_to_pixels,
)
from src.detection.runner import run_on_video

IMG_W, IMG_H = 640, 480


def test_yolo_pixel_roundtrip():
    cx, cy, w, h = 0.5, 0.25, 0.1, 0.2
    x, y, w_px, h_px, cx_px, cy_px = yolo_to_pixels(cx, cy, w, h, IMG_W, IMG_H)
    # Center maps to the expected pixel location.
    assert cx_px == 0.5 * IMG_W
    assert cy_px == 0.25 * IMG_H
    # Round-trip back to normalized coords.
    rcx, rcy, rw, rh = pixels_to_yolo(x, y, w_px, h_px, IMG_W, IMG_H)
    assert np.allclose([rcx, rcy, rw, rh], [cx, cy, w, h])


def test_top_left_corner():
    # A box centered at the image center with full-ish size.
    x, y, w_px, h_px, _, _ = yolo_to_pixels(0.5, 0.5, 0.5, 0.5, IMG_W, IMG_H)
    assert x == IMG_W * 0.25
    assert y == IMG_H * 0.25
    assert w_px == IMG_W * 0.5
    assert h_px == IMG_H * 0.5


def test_parse_label_line_ftid_class1():
    # labels_ftid/ layout with a non-zero class (cluster).
    det = parse_label_line("abc123 1 0.5 0.5 0.1 0.2", IMG_W, IMG_H)
    assert det is not None
    assert det.class_id == 1
    assert det.object_id == "abc123"
    assert det.cx == 0.5 * IMG_W
    assert det.w == 0.1 * IMG_W


def test_parse_label_line_without_track_id():
    # labels/ layout: class cx cy w h (no track id)
    det = parse_label_line("0 0.5 0.5 0.1 0.2", IMG_W, IMG_H)
    assert det is not None
    assert det.class_id == 0
    assert det.object_id == -1


def test_parse_label_line_ftid_format():
    # labels_ftid/ layout: track_id(string) class cx cy w h
    det = parse_label_line("ckz3v9nzv00033867jsekqdcl 0 0.5 0.5 0.1 0.2", IMG_W, IMG_H)
    assert det is not None
    assert det.object_id == "ckz3v9nzv00033867jsekqdcl"
    assert det.class_id == 0
    assert det.cx == 0.5 * IMG_W
    assert det.w == 0.1 * IMG_W


def test_parse_label_line_malformed():
    assert parse_label_line("", IMG_W, IMG_H) is None
    assert parse_label_line("0 0.5", IMG_W, IMG_H) is None


def test_load_gt_frame(tmp_path):
    # Real labels_ftid layout: track_id(string) class cx cy w h
    label = tmp_path / "frame_0.txt"
    label.write_text(
        "trackA 0 0.5 0.5 0.1 0.2\ntrackB 2 0.25 0.75 0.05 0.05\n", encoding="utf-8"
    )
    dets = load_gt_frame(label, IMG_W, IMG_H)
    assert len(dets) == 2
    assert {d.class_id for d in dets} == {0, 2}
    assert {d.object_id for d in dets} == {"trackA", "trackB"}


def test_load_gt_frame_missing(tmp_path):
    assert load_gt_frame(tmp_path / "nope.txt", IMG_W, IMG_H) == []


def test_extract_frame_index_ignores_video_id():
    assert extract_frame_index("11_frame_7.txt") == 7
    assert extract_frame_index("82_frame_123_with_ftid.txt") == 123
    assert extract_frame_index("000042.txt") == 42


def test_index_and_load_gt_preserve_missing_vs_empty(tmp_path):
    (tmp_path / "23_frame_0_with_ftid.txt").write_text(
        "trackA 0 0.5 0.5 0.1 0.2\n", encoding="utf-8"
    )
    (tmp_path / "23_frame_2_with_ftid.txt").write_text("", encoding="utf-8")
    index = index_label_files(tmp_path)
    assert set(index) == {0, 2}

    present = load_gt_for_frame(tmp_path, 0, IMG_W, IMG_H, label_index=index)
    missing = load_gt_for_frame(tmp_path, 1, IMG_W, IMG_H, label_index=index)
    empty = load_gt_for_frame(tmp_path, 2, IMG_W, IMG_H, label_index=index)
    assert present.annotated and len(present.detections) == 1
    assert not missing.annotated and missing.detections == ()
    assert empty.annotated and empty.detections == ()


def test_detection_corner_properties():
    d = Detection(cx=100, cy=50, w=20, h=10)
    assert d.x == 90
    assert d.y == 45
    assert d.xyxy == (90, 45, 110, 55)


def test_threshold_detector_runs_on_synthetic_frame():
    # Dark background with a few small bright squares -> detector should find them.
    frame = np.zeros((IMG_H, IMG_W, 3), dtype=np.uint8)
    centers = [(100, 100), (300, 200), (500, 400)]
    for (cx, cy) in centers:
        frame[cy - 3:cy + 3, cx - 3:cx + 3] = 255
    det = ThresholdContourDetector(min_area=4, max_area=200)
    results = det.detect(frame)
    assert len(results) == len(centers)


def test_hybrid_threshold_detects_bright_objects_after_background_correction():
    # A smooth non-uniform background plus compact, bright foreground objects.
    gradient = np.tile(np.linspace(40, 120, IMG_W, dtype=np.uint8), (IMG_H, 1))
    frame = np.repeat(gradient[:, :, None], 3, axis=2)
    centers = [(100, 100), (300, 200), (500, 400)]
    for cx, cy in centers:
        frame[cy - 3:cy + 3, cx - 3:cx + 3] = 240
    detector = HybridThresholdDetector(
        min_area=10,
        max_area=100,
        background_kernel=15,
        threshold_value=30,
        morph_kernel=1,
        open_iterations=0,
        close_iterations=0,
    )
    assert len(detector.detect(frame)) == len(centers)


def test_runner_uses_encoded_frame_index_and_writes_annotation_status(tmp_path, monkeypatch):
    class FakeCapture:
        def __init__(self, _path):
            self.index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            import cv2
            if prop == cv2.CAP_PROP_FPS:
                return 30
            if prop == cv2.CAP_PROP_FRAME_WIDTH:
                return IMG_W
            if prop == cv2.CAP_PROP_FRAME_HEIGHT:
                return IMG_H
            return 0

        def read(self):
            if self.index >= 3:
                return False, None
            self.index += 1
            return True, np.zeros((IMG_H, IMG_W, 3), dtype=np.uint8)

        def release(self):
            return None

    class EmptyDetector:
        name = "empty"

        def reset(self):
            return None

        def detect(self, _frame):
            return []

    from src.detection import runner

    monkeypatch.setattr(runner.cv2, "VideoCapture", FakeCapture)
    gt_dir = tmp_path / "labels"
    gt_dir.mkdir()
    (gt_dir / "11_frame_0.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    # frame 1 deliberately absent; frame 2 is explicitly annotated empty.
    (gt_dir / "11_frame_2.txt").write_text("", encoding="utf-8")

    out_csv = tmp_path / "detections.csv"
    out_frames = tmp_path / "frames.csv"
    summary = run_on_video(
        EmptyDetector(),
        "fake.mp4",
        out_csv,
        out_video=None,
        gt_dir=gt_dir,
        out_frames_csv=out_frames,
        verbose=False,
    )
    with out_frames.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["annotated"] for row in rows] == ["True", "False", "True"]
    assert [row["n_ground_truth"] for row in rows] == ["1", "", "0"]
    assert summary["annotated_frames"] == 2
    assert summary["unannotated_frames"] == 1


def test_detection_cli_resolves_yaml_and_bare_detector_overrides(tmp_path):
    from src.detection.pipeline import parse_args, resolve_cli_config

    config_path = tmp_path / "threshold.yaml"
    config_path.write_text(
        "method: threshold\n"
        "params:\n"
        "  min_area: 3\n"
        "evaluation:\n"
        "  center_gate_px: 15\n"
        "run:\n"
        "  seed: 42\n"
        "search_space:\n"
        "  threshold_value: [190, 200]\n",
        encoding="utf-8",
    )
    args = parse_args(
        [
            "--config", str(config_path),
            "--video", "video.mp4",
            "--stage", "validation",
            "--split", "val",
            "--set", "min_area=9",
            "--set", "evaluation.center_gate_px=20",
        ]
    )
    config = resolve_cli_config(args)
    assert config["method"] == "threshold"
    assert config["params"]["min_area"] == 9
    assert config["evaluation"]["center_gate_px"] == 20
    assert config["run"]["stage"] == "validation"
    assert config["run"]["split"] == "val"
    assert config["search_space"]["threshold_value"] == [190, 200]


def test_detection_rejects_video_outside_declared_split_before_decode(
    tmp_path, monkeypatch
):
    from src.detection import pipeline as run_detection

    def must_not_build(*_args, **_kwargs):
        raise AssertionError("detector must not be built after a split mismatch")

    monkeypatch.setattr(run_detection, "build_detector", must_not_build)
    with pytest.raises(SystemExit, match="não pertence ao split/fold"):
        run_detection.main(
            [
                "--method", "threshold",
                "--video", "24.mp4",
                "--stage", "validation",
                "--split", "val",
                "--out-dir", str(tmp_path),
                "--no-video",
            ]
        )
    assert not list(tmp_path.iterdir())


def test_detection_direct_cli_cannot_use_all_alias_during_search_before_decode(
    tmp_path, monkeypatch
):
    from src.detection import pipeline as run_detection

    monkeypatch.setattr(
        run_detection,
        "build_detector",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must fail before detector construction")
        ),
    )
    with pytest.raises(SystemExit, match="inclui o teste"):
        run_detection.main(
            [
                "--method", "threshold",
                "--video", "24.mp4",
                "--stage", "search",
                "--split", "all",
                "--out-dir", str(tmp_path),
                "--no-video",
            ]
        )
    assert not list(tmp_path.iterdir())


def test_detection_frozen_run_requires_promoted_yaml_before_decode(tmp_path, monkeypatch):
    from src.detection import pipeline as run_detection

    monkeypatch.setattr(
        run_detection,
        "build_detector",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must fail before detector construction")
        ),
    )
    with pytest.raises(SystemExit, match="configs/frozen"):
        run_detection.main(
            [
                "--config", "configs/detection/threshold/t200_o1_c2.yaml",
                "--video", "24.mp4",
                "--stage", "test",
                "--split", "test",
                "--set", "run.frozen=true",
                "--out-dir", str(tmp_path),
            ]
        )


@pytest.mark.parametrize(
    "override",
    ["threshold_value=190", "params.min_area=9", "evaluation.center_gate_px=20"],
)
def test_detection_frozen_run_rejects_scientific_overrides_before_decode(
    override, tmp_path, monkeypatch
):
    from src.detection import pipeline as run_detection

    monkeypatch.setattr(
        run_detection,
        "build_detector",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must fail before detector construction")
        ),
    )
    with pytest.raises(SystemExit, match="parâmetros científicos"):
        run_detection.main(
            [
                "--config", "configs/frozen/detection/threshold/t200_o1_c2.yaml",
                "--video", "24.mp4",
                "--set", override,
                "--out-dir", str(tmp_path),
            ]
        )


def test_detection_frozen_manifest_records_promoted_yaml_hash(tmp_path, monkeypatch):
    from src.detection import pipeline as run_detection

    monkeypatch.setattr(run_detection, "build_detector", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        run_detection,
        "run_on_video",
        lambda *_args, **_kwargs: {
            "video_id": "24",
            "method": "threshold",
            "frames": 1,
            "detections": 0,
        },
    )
    summary = run_detection.main(
        [
            "--config", "configs/frozen/detection/threshold/t200_o1_c2.yaml",
            "--video", "24.mp4",
            "--no-video",
            "--out-dir", str(tmp_path),
        ]
    )
    manifest_path = next(tmp_path.rglob("manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = manifest["config"]["provenance"]
    assert Path(provenance["frozen_config_source"]).name == "t200_o1_c2.yaml"
    assert len(provenance["frozen_config_sha256"]) == 64
    assert summary["dataset_id"] == 24


def test_detection_cli_creates_a_new_run_and_complete_manifest_each_time(
    tmp_path, monkeypatch
):
    from src.detection import pipeline as run_detection

    monkeypatch.setattr(run_detection, "build_detector", lambda *args, **kwargs: object())

    def fake_run(_detector, **kwargs):
        return {
            "video_id": "11",
            "method": "threshold",
            "frames": 1,
            "detections": 0,
        }

    monkeypatch.setattr(run_detection, "run_on_video", fake_run)
    argv = [
        "--method", "threshold",
        "--video", "11.mp4",
        "--out-dir", str(tmp_path),
        "--no-video",
    ]
    first = run_detection.main(argv)
    second = run_detection.main(argv)
    assert first["run_id"] != second["run_id"]
    manifests = sorted(tmp_path.rglob("manifest.json"))
    assert len(manifests) == 2
    assert all(json.loads(path.read_text(encoding="utf-8"))["status"] == "complete" for path in manifests)
    assert len(list(tmp_path.rglob("metadata.json"))) == 2


def test_detection_frame_limit_uses_sampling_only_before_full_video_stages():
    from src.detection.pipeline import _resolve_frame_limit

    sampling = {"warmup_frames": 100, "scored_frames": 200}
    assert _resolve_frame_limit(
        stage="screen", configured_max_frames=None, sampling=sampling
    ) == (300, "sampling_warmup_plus_scored")
    assert _resolve_frame_limit(
        stage="validation", configured_max_frames=None, sampling=sampling
    ) == (None, "full_video")
    assert _resolve_frame_limit(
        stage="test", configured_max_frames=17, sampling=sampling
    ) == (17, "explicit")


@pytest.mark.parametrize("method", ["mog2", "knn"])
def test_stateful_detection_cli_resets_and_scores_only_after_warmup(
    method, tmp_path, monkeypatch
):
    from src.detection import pipeline as run_detection
    from src.detection import runner
    from src.detection.classical.background_subtraction import KNNDetector, MOG2Detector

    class FakeCapture:
        def __init__(self, _path):
            self.index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == runner.cv2.CAP_PROP_FPS:
                return 30
            if prop == runner.cv2.CAP_PROP_FRAME_WIDTH:
                return 64
            if prop == runner.cv2.CAP_PROP_FRAME_HEIGHT:
                return 48
            return 0

        def read(self):
            if self.index >= 20:
                return False, None
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            if self.index >= 2:
                frame[20:25, 20 + self.index:25 + self.index] = 255
            self.index += 1
            return True, frame

        def release(self):
            return None

    detector_type = MOG2Detector if method == "mog2" else KNNDetector

    class CountingDetector(detector_type):
        reset_calls = 0

        def reset(self):
            type(self).reset_calls += 1
            return super().reset()

    monkeypatch.setattr(runner.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setitem(run_detection.DETECTORS, method, CountingDetector)
    monkeypatch.setattr(run_detection, "resolve_video_id", lambda *args, **kwargs: 11)

    config_path = tmp_path / f"{method}.yaml"
    config_path.write_text(
        f"method: {method}\n"
        "params:\n"
        "  history: 5\n"
        "  min_area: 1\n"
        "  max_area: 1000\n"
        "  morph_kernel: 1\n"
        "  detect_shadows: false\n"
        "sampling:\n"
        "  warmup_frames: 2\n"
        "  scored_frames: 3\n"
        "run:\n"
        "  stage: screen\n"
        "  split: train\n"
        "  save_video: false\n",
        encoding="utf-8",
    )
    summary = run_detection.main(
        ["--config", str(config_path), "--video", "11.mp4", "--out-dir", str(tmp_path / "runs")]
    )

    assert CountingDetector.reset_calls == 2  # constructor plus per-video reset
    assert summary["frames"] == 5
    assert summary["warmup_frames"] == 2
    assert summary["scored_frames"] == 3
    assert summary["frame_limit_source"] == "sampling_warmup_plus_scored"
    with Path(summary["frames_csv"]).open(encoding="utf-8", newline="") as handle:
        frame_rows = list(csv.DictReader(handle))
    assert [int(row["frame"]) for row in frame_rows] == [2, 3, 4]


def test_yolo_detector_forwards_configured_nms_without_neural_dependency(monkeypatch):
    from src.detection.learned.yolo import YoloDetector

    calls: list[dict] = []

    class FakeModel:
        def predict(self, _frame, **kwargs):
            calls.append(kwargs)
            return [types.SimpleNamespace(boxes=[])]

    fake_module = types.ModuleType("ultralytics")
    fake_module.YOLO = lambda _weights: FakeModel()
    monkeypatch.setitem(sys.modules, "ultralytics", fake_module)

    detector = YoloDetector(
        weights="fake.pt", conf=0.15, imgsz=320, nms_iou=0.55
    )
    assert detector.detect(np.zeros((16, 16, 3), dtype=np.uint8)) == []
    assert calls == [
        {"conf": 0.15, "imgsz": 320, "iou": 0.55, "verbose": False}
    ]


def test_yolo_requires_frozen_weights_before_importing_optional_dependency():
    from src.detection.learned.yolo import YoloDetector

    with pytest.raises(ValueError, match="--weights"):
        YoloDetector(weights=None)
