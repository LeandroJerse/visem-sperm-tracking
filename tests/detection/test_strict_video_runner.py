"""Complete-video execution on generated images/mocked decoders only."""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.detection import runner, strict_inputs
from src.detection.base import Detection
from src.detection.strict_inputs import prepare_full_video_input


class Capture:
    def __init__(self, frames, *, advertised=3, width=32, height=24):
        self.frames = list(frames)
        self.advertised = advertised
        self.width, self.height = width, height
        self.calls = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.width, cv2.CAP_PROP_FRAME_HEIGHT: self.height,
                cv2.CAP_PROP_FRAME_COUNT: self.advertised, cv2.CAP_PROP_FPS: 30}[prop]

    def getBackendName(self):
        return "SYNTHETIC"

    def read(self):
        self.calls += 1
        if self.calls > len(self.frames):
            return False, None
        return True, self.frames[self.calls - 1]

    def release(self):
        self.released = True


def frames(count=3):
    return [np.full((24, 32, 3), index, dtype=np.uint8) for index in range(count)]


def rows(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    folder = tmp_path / "sources" / "11"
    labels = folder / "labels_ftid"
    labels.mkdir(parents=True)
    video = folder / "11.mp4"
    video.write_bytes(b"synthetic-video")
    (labels / "11_frame_0_with_ftid.txt").write_text("5 0 .5 .5 .25 .25\n", encoding="utf-8")
    (labels / "11_frame_2_with_ftid.txt").write_text("", encoding="utf-8")
    metadata = Capture([])
    monkeypatch.setattr(strict_inputs.cv2, "VideoCapture", lambda _: metadata)
    value = prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                     expected_height=24, expected_frame_count=3)
    assert metadata.calls == 0
    return value


def execute(value, tmp_path, detector=None, **kwargs):
    supplied = {"video_id": value.video_id, "gt_dir": value.gt_dir, "full_video_input": value,
                "out_frames_csv": tmp_path / "metrics.csv", "verbose": False}
    supplied.update(kwargs)
    return runner.run_on_video(
        detector or SimpleNamespace(name="synthetic", reset=lambda: None,
                                     detect=lambda _: [Detection(16, 12, 8, 6)]),
        value.video_path, tmp_path / "detections.csv", **supplied,
    )


def test_complete_video_reads_extra_eof_and_preserves_unlabeled_empty(prepared, tmp_path, monkeypatch):
    capture = Capture(frames())
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    callback_frames = []
    summary = execute(prepared, tmp_path, progress_callback=lambda frame, predictions: callback_frames.append((frame, len(predictions))))
    assert capture.calls == 4 and capture.released
    assert callback_frames == [(0, 1), (1, 1), (2, 1)]
    assert summary["completeness"] == {
        "status": "complete", "expected_frames": 3, "decoded_frames": 3, "frame_metric_rows": 3,
        "extra_read_eof": True, "input_hash_verification": "required_before_batch_completion",
    }
    assert summary["full_video_input"]["input_hash"] == prepared.input_hash
    assert (summary["frames_annotated"], summary["frames_unannotated"]) == (2, 1)
    assert (summary["tp"], summary["fp"], summary["fn"]) == (1, 1, 0)
    assert [row["annotated"] for row in rows(tmp_path / "metrics.csv")] == ["True", "False", "True"]
    assert prepared.verify_current()["status"] == "verified"


@pytest.mark.parametrize("actual,message,completed", [(0, "Premature EOF", 0), (2, "Premature EOF", 2),
                                                        (4, "extra decoded frames", 3)])
def test_truncated_or_extra_video_fails_and_preserves_partial_csvs(prepared, tmp_path, monkeypatch, actual, message, completed):
    capture = Capture(frames(actual))
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    with pytest.raises(ValueError, match=message):
        execute(prepared, tmp_path)
    assert capture.released
    assert len(rows(tmp_path / "metrics.csv")) == completed
    assert all(int(row["frame"]) < completed for row in rows(tmp_path / "detections.csv"))


@pytest.mark.parametrize("invalid", [np.zeros((24, 31, 3), dtype=np.uint8),
                                     np.zeros((24, 32), dtype=np.uint8),
                                     np.zeros((24, 32, 3), dtype=np.float32), None])
def test_bad_decoded_frame_never_reaches_detector(prepared, tmp_path, monkeypatch, invalid):
    capture = Capture([invalid])
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    detector = SimpleNamespace(name="synthetic", reset=lambda: None, detect=lambda _: pytest.fail("invalid frame reached detector"))
    with pytest.raises(ValueError, match="invalid dimensions/type"):
        execute(prepared, tmp_path, detector)
    assert capture.released


def test_callback_budget_failure_precedes_matching_and_does_not_truncate(prepared, tmp_path, monkeypatch):
    capture = Capture(frames())
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    all_predictions = [Detection(0, 0, 1, 1)] * 2001
    detector = SimpleNamespace(name="synthetic", reset=lambda: None, detect=lambda _: all_predictions)
    def enforce(frame_index, predictions):
        assert frame_index == 0 and predictions is all_predictions and len(predictions) == 2001
        raise RuntimeError("prediction budget exceeded")
    monkeypatch.setattr(runner.DetectionEvaluator, "add_frame", lambda *a, **k: pytest.fail("matching ran before budget guard"))
    with pytest.raises(RuntimeError, match="budget"):
        execute(prepared, tmp_path, detector, progress_callback=enforce)
    assert rows(tmp_path / "metrics.csv") == []
    assert rows(tmp_path / "detections.csv") == []
    assert capture.released


@pytest.mark.parametrize("override", [{"max_frames": 3}, {"max_frames": 0}, {"warmup_frames": 1},
                                       {"video_id": "12"}, {"gt_dir": None}])
def test_partial_or_mismatched_input_rejected_before_capture(prepared, tmp_path, monkeypatch, override):
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: pytest.fail("must reject before capture"))
    with pytest.raises(ValueError):
        execute(prepared, tmp_path, **override)


def test_changed_header_fails_before_detection(prepared, tmp_path, monkeypatch):
    capture = Capture(frames(), advertised=4)
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    with pytest.raises(ValueError, match="metadata frame_count"):
        execute(prepared, tmp_path)
    assert capture.released and capture.calls == 0


def test_detector_failure_releases_both_handles_and_preserves_previous_frames(prepared, tmp_path, monkeypatch):
    capture = Capture(frames())
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: capture)
    writer = SimpleNamespace(released=False, write=lambda _: None)
    writer.release = lambda: setattr(writer, "released", True)
    monkeypatch.setattr(runner, "open_writer", lambda *args: writer)
    def detect(frame):
        if int(frame[0, 0, 0]) == 1:
            raise RuntimeError("synthetic detector failure")
        return []
    detector = SimpleNamespace(name="synthetic", reset=lambda: None, detect=detect)
    with pytest.raises(RuntimeError, match="detector failure"):
        execute(prepared, tmp_path, detector, out_video=tmp_path / "annotated.mp4")
    assert capture.released and writer.released
    assert len(rows(tmp_path / "metrics.csv")) == 1


def test_strict_outputs_cannot_overwrite_or_enter_source_folder(prepared, tmp_path, monkeypatch):
    existing = tmp_path / "metrics.csv"
    existing.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(runner.cv2, "VideoCapture", lambda _: pytest.fail("must reject before capture"))
    with pytest.raises(FileExistsError):
        execute(prepared, tmp_path)
    assert existing.read_text(encoding="utf-8") == "preserve"
    with pytest.raises(ValueError, match="source video folder"):
        execute(prepared, tmp_path, out_frames_csv=prepared.gt_dir / "output.csv")


def test_generated_real_mp4_decodes_exactly_without_real_detector(tmp_path):
    folder = tmp_path / "sources" / "11"
    labels = folder / "labels_ftid"
    labels.mkdir(parents=True)
    video = folder / "11.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (32, 24))
    assert writer.isOpened(), "Synthetic MP4 encoder must be available"
    try:
        for index, frame in enumerate(frames()):
            writer.write(frame)
            (labels / f"11_frame_{index}_with_ftid.txt").write_text("", encoding="utf-8")
    finally:
        writer.release()
    value = prepare_full_video_input(video, labels, video_id=11, expected_width=32,
                                     expected_height=24, expected_frame_count=3)
    detector = SimpleNamespace(name="synthetic_empty", reset=lambda: None, detect=lambda _: [])
    summary = execute(value, tmp_path, detector)
    assert summary["completeness"]["decoded_frames"] == 3
    assert summary["frames_annotated"] == 3
    assert value.verify_current()["status"] == "verified"
