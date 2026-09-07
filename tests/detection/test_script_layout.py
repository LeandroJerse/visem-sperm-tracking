"""Contratos dos wrappers e da bancada manual reorganizada."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from src.core.paths import EXPERIMENT_TESTS_ROOT
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


def test_frame_helper_preserves_unannotated_gap(tmp_path):
    ground_truth = frames.load_gt(tmp_path, frame_index=17, w=640, h=480)
    assert ground_truth is not None
    assert ground_truth.annotated is False
    assert ground_truth.detections == ()
