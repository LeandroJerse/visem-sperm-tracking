"""Unit tests for coordinate conversion and label parsing in visem_io."""
from __future__ import annotations

import numpy as np

from src.detection.base_detector import Detection
from src.detection.detect_threshold_contours import ThresholdContourDetector
from src.detection.visem_io import (
    load_gt_frame,
    parse_label_line,
    pixels_to_yolo,
    yolo_to_pixels,
)

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


def test_detection_corner_properties():
    d = Detection(cx=100, cy=50, w=20, h=10)
    assert d.x == 90
    assert d.y == 45
    assert d.xyxy == (90, 45, 110, 55)


def test_threshold_detector_runs_on_synthetic_frame():
    # White background with a few small dark squares -> detector should find them.
    frame = np.full((IMG_H, IMG_W, 3), 255, dtype=np.uint8)
    centers = [(100, 100), (300, 200), (500, 400)]
    for (cx, cy) in centers:
        frame[cy - 3:cy + 3, cx - 3:cx + 3] = 0
    det = ThresholdContourDetector(min_area=4, max_area=200)
    results = det.detect(frame)
    assert len(results) == len(centers)
