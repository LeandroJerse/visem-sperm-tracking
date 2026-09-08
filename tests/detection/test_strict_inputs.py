"""Synthetic input-contract tests; no dataset videos or labels are opened."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from src.detection import strict_inputs
from src.detection.io import load_gt_frame, parse_gt_text, parse_label_line
from src.detection.strict_inputs import prepare_full_video_input


class MetadataCapture:
    def __init__(self, *, width=32, height=24, frames=3, fps=30.0, opened=True):
        self.values = {cv2.CAP_PROP_FRAME_WIDTH: width, cv2.CAP_PROP_FRAME_HEIGHT: height,
                       cv2.CAP_PROP_FRAME_COUNT: frames, cv2.CAP_PROP_FPS: fps}
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, prop):
        return self.values[prop]

    def getBackendName(self):
        return "SYNTHETIC_METADATA"

    def read(self):
        raise AssertionError("Preparation must not decode pixels")

    def release(self):
        self.released = True


def source_tree(tmp_path):
    folder = tmp_path / "sources" / "11"
    labels = folder / "labels_ftid"
    labels.mkdir(parents=True)
    video = folder / "11.mp4"
    video.write_bytes(b"synthetic-video-content")
    (labels / "11_frame_0_with_ftid.txt").write_text("123 0 0.5 0.5 0.25 0.25\n", encoding="utf-8")
    (labels / "11_frame_2_with_ftid.txt").write_text("", encoding="utf-8")
    return video, labels


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    video, labels = source_tree(tmp_path)
    capture = MetadataCapture()
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: capture)
    value = prepare_full_video_input(video, labels, video_id="11", expected_width=32,
                                     expected_height=24, expected_frame_count=3)
    return value, capture


def test_strict_numeric_identity_and_empty_missing_states(prepared):
    value, capture = prepared
    assert capture.released
    first, absent, empty = value.gt_frames
    assert first.annotated and first.detections[0].object_id == "123"
    assert (first.detections[0].cx, first.detections[0].cy) == (16, 12)
    assert not absent.annotated and absent.label_path is None
    assert empty.annotated and empty.detections == ()
    reference = value.reference()
    assert reference["ground_truth"]["annotated_frames"] == 2
    assert reference["ground_truth"]["unannotated_indices"] == [1]
    assert reference["ground_truth"]["annotated_empty_frames"] == 1
    assert reference["video_metadata"]["backend"] == "SYNTHETIC_METADATA"
    assert json.loads(json.dumps(reference)) == reference
    assert value.verify_current()["status"] == "verified"


def test_prepared_gt_and_export_are_detached(prepared):
    value, _ = prepared
    value.gt_frame(0).detections[0].cx = -1000
    external = value.reference()
    external["ground_truth"]["files"][0]["sha256"] = "changed"
    assert value.gt_frame(0).detections[0].cx == 16
    assert value.reference()["ground_truth"]["files"][0]["sha256"] != "changed"
    assert value.verify_current()["input_hash"] == value.input_hash


def test_reference_hash_is_stable_without_timestamps(prepared, monkeypatch):
    value, _ = prepared
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: MetadataCapture())
    again = prepare_full_video_input(value.video_path, value.gt_dir, video_id=11,
                                    expected_width=32, expected_height=24, expected_frame_count=3)
    assert again.reference() == value.reference()


@pytest.mark.parametrize("line", [
    "0 0.5 0.5 0.1 0.1", "id 0 0.5 0.5 0.1", "id 0 0.5 0.5 0.1 0.1 extra",
    "id 0.9 0.5 0.5 0.1 0.1", "id 3 0.5 0.5 0.1 0.1", "id 0 nan 0.5 0.1 0.1",
    "id 0 0.5 inf 0.1 0.1", "id 0 1.1 0.5 0.1 0.1", "id 0 0.5 0.5 0 0.1",
    "id 2 0.5 0.5 -0.1 0.1", "id 0 0.01 0.5 0.1 0.1", "id 1 0.5 0.99 0.1 0.1",
    "id 0 invalid 0.5 0.1 0.1",
])
def test_strict_parser_rejects_invalid_lines_with_context(line):
    with pytest.raises(ValueError, match=r"sample.txt:2:"):
        parse_gt_text("\n" + line, 32, 24, strict_ftid=True, label_path="sample.txt")


def test_strict_duplicate_identity_fails_and_blank_lines_remain_empty():
    with pytest.raises(ValueError, match="Duplicate GT track identity"):
        parse_gt_text("9 0 .5 .5 .1 .1\n9 2 .3 .3 .1 .1", 32, 24, strict_ftid=True)
    assert parse_gt_text(" \n\t", 32, 24, strict_ftid=True) == []
    assert parse_label_line("0 .5", 32, 24) is None  # legacy remains permissive


def test_strict_missing_file_raises_instead_of_becoming_negative(tmp_path):
    path = tmp_path / "missing.txt"
    assert load_gt_frame(path, 32, 24) == []
    with pytest.raises(FileNotFoundError):
        load_gt_frame(path, 32, 24, strict_ftid=True)


@pytest.mark.parametrize("mutation", ["video", "label", "remove", "add", "rename", "auxiliary"])
def test_current_verification_detects_content_and_inventory_changes(prepared, mutation):
    value, _ = prepared
    label = value.gt_dir / "11_frame_0_with_ftid.txt"
    if mutation == "video":
        value.video_path.write_bytes(b"other-video")
    elif mutation == "label":
        label.write_text("123 0 .4 .5 .25 .25", encoding="utf-8")
    elif mutation == "remove":
        label.unlink()
    elif mutation == "rename":
        label.rename(value.gt_dir / "11_frame_1_with_ftid.txt")
    else:
        name = "11_frame_1_with_ftid.txt" if mutation == "add" else "aux.npy"
        (value.gt_dir / name).write_bytes(b"")
    with pytest.raises(ValueError, match="changed"):
        value.verify_current()


@pytest.mark.parametrize("filename", ["12_frame_1_with_ftid.txt", "11_frame_3_with_ftid.txt",
                                       "11_frame_-1_with_ftid.txt", "11_frame_1.txt", "000001.txt"])
def test_noncanonical_or_outside_label_index_fails(tmp_path, monkeypatch, filename):
    video, labels = source_tree(tmp_path)
    (labels / filename).write_text("", encoding="utf-8")
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: MetadataCapture())
    with pytest.raises(ValueError, match="filename|outside"):
        prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                 expected_height=24, expected_frame_count=3)


def test_duplicate_encoded_index_fails(tmp_path, monkeypatch):
    video, labels = source_tree(tmp_path)
    (labels / "11_frame_00_with_ftid.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: MetadataCapture())
    with pytest.raises(ValueError, match="Duplicate label index"):
        prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                 expected_height=24, expected_frame_count=3)


@pytest.mark.parametrize("metadata", [{"width": 64}, {"height": 48}, {"frames": 2},
                                      {"frames": 3.5}, {"fps": 0}, {"fps": float("nan")}, {"opened": False}])
def test_metadata_mismatch_releases_capture_without_decoding(tmp_path, monkeypatch, metadata):
    video, labels = source_tree(tmp_path)
    capture = MetadataCapture(**metadata)
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: capture)
    with pytest.raises(ValueError):
        prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                 expected_height=24, expected_frame_count=3)
    assert capture.released


def test_shorter_registered_video_uses_explicit_count(tmp_path, monkeypatch):
    video, labels = source_tree(tmp_path)
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: MetadataCapture(frames=1440))
    value = prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                     expected_height=24, expected_frame_count=1440)
    assert value.expected_frame_count == 1440
    assert len(value.gt_frames) == 1440


def test_canonical_folder_and_gt_identity_checked_before_opening_metadata(tmp_path, monkeypatch):
    video, labels = source_tree(tmp_path)
    wrong_gt = tmp_path / "12" / "labels_ftid"
    wrong_gt.mkdir(parents=True)
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: pytest.fail("must fail before capture"))
    with pytest.raises(ValueError, match="same video's"):
        prepare_full_video_input(video, wrong_gt, video_id=11)
    with pytest.raises(ValueError, match="Canonical video"):
        prepare_full_video_input(video, labels, video_id=12)


@pytest.mark.parametrize("field,value", [("expected_frame_count", 0), ("expected_frame_count", 3.0),
                                         ("expected_width", -1), ("expected_height", True), ("video_id", "../11")])
def test_invalid_expectations_fail_before_sources_are_opened(field, value):
    args = {"video_id": 11, "expected_width": 32, "expected_height": 24, "expected_frame_count": 3}
    args[field] = value
    with pytest.raises(ValueError):
        prepare_full_video_input(Path("does-not-exist"), Path("also-absent"), **args)
