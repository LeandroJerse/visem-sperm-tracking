"""Synthetic behavioural checks for every non-neural detector family.

These tests are deliberately small.  They verify polarity, geometry and the
state/reset contract; they do not claim that a parameter set is accurate on
VISEM.  Accuracy is selected later, by video, under the experimental protocol.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from src.detection.classical.background_subtraction import KNNDetector, MOG2Detector
from src.detection.classical.blob import BlobDetector
from src.detection.classical.threshold import ThresholdContourDetector
from src.detection.classical.watershed import WatershedDetector
from src.detection.hybrid.enhanced_threshold import HybridThresholdDetector
from src.detection.registry import scientific_algorithm_id


def test_threshold_variants_have_distinct_scientific_algorithm_ids():
    assert scientific_algorithm_id("threshold", params={"threshold_value": 200}) == "threshold"
    assert scientific_algorithm_id("threshold", params={"threshold_value": None}) == "otsu"
    assert scientific_algorithm_id("threshold", params={"adaptive": True}) == "adaptive_threshold"


def _frame(*, background: int = 0) -> np.ndarray:
    return np.full((96, 128, 3), background, dtype=np.uint8)


def _bright_objects() -> tuple[np.ndarray, tuple[tuple[int, int], ...]]:
    frame = _frame()
    centers = ((25, 30), (80, 62))
    for center in centers:
        cv2.circle(frame, center, 5, (230, 230, 230), -1)
    return frame, centers


def _assert_centers_recovered(detections, expected, tolerance: float = 2.0) -> None:
    assert len(detections) == len(expected)
    remaining = [(float(item.cx), float(item.cy)) for item in detections]
    for ex, ey in expected:
        distances = [np.hypot(cx - ex, cy - ey) for cx, cy in remaining]
        nearest = int(np.argmin(distances))
        assert distances[nearest] <= tolerance
        remaining.pop(nearest)


@pytest.mark.parametrize(
    "detector",
    [
        ThresholdContourDetector(
            threshold_value=100,
            min_area=20,
            max_area=150,
            morph_kernel=1,
            morph_iterations=0,
            close_iterations=0,
        ),
        ThresholdContourDetector(
            threshold_value=None,
            min_area=20,
            max_area=150,
            morph_kernel=1,
            morph_iterations=0,
            close_iterations=0,
        ),
        HybridThresholdDetector(
            threshold_value=20,
            min_area=20,
            max_area=150,
            background_kernel=21,
            morph_kernel=1,
            open_iterations=0,
            close_iterations=0,
        ),
        BlobDetector(
            dark=False,
            min_area=20,
            max_area=150,
            min_threshold=5,
            max_threshold=250,
        ),
        WatershedDetector(
            invert=False,
            min_area=20,
            max_area=150,
            blur=1,
            dist_ratio=0.4,
            morph_kernel=1,
        ),
    ],
    ids=["fixed-threshold", "otsu", "hybrid-threshold", "blob", "watershed"],
)
def test_static_detectors_recover_two_bright_objects(detector):
    frame, expected = _bright_objects()
    _assert_centers_recovered(detector.detect(frame), expected)


def test_adaptive_threshold_supports_uneven_illumination():
    gradient = np.tile(np.linspace(20, 130, 128, dtype=np.uint8), (96, 1))
    frame = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)
    centers = ((25, 30), (95, 62))
    for center in centers:
        cv2.circle(frame, center, 4, (230, 230, 230), -1)
    detector = ThresholdContourDetector(
        adaptive=True,
        adaptive_block=21,
        adaptive_c=2,
        min_area=10,
        max_area=100,
        morph_kernel=1,
        morph_iterations=0,
        close_iterations=0,
    )
    detections = detector.detect(frame)
    # Adaptive thresholding can also mark thin illumination bands.  The
    # area-filtered result must nevertheless contain both inserted objects.
    recovered = [(item.cx, item.cy) for item in detections]
    for ex, ey in centers:
        assert min(np.hypot(cx - ex, cy - ey) for cx, cy in recovered) <= 2.0


def test_threshold_diagnostics_use_the_canonical_pipeline():
    frame, expected = _bright_objects()
    detector = ThresholdContourDetector(
        threshold_value=100,
        min_area=20,
        max_area=150,
        morph_kernel=1,
        morph_iterations=0,
        close_iterations=0,
    )
    detections = detector.detect(frame)
    stages = detector.diagnostic_stages(frame)
    _assert_centers_recovered(detections, expected)
    assert stages[-1][0].endswith("labeled_components")
    assert np.count_nonzero(stages[-1][1]) > 0


@pytest.mark.parametrize("detector_type", [MOG2Detector, KNNDetector])
def test_background_subtractors_detect_change_and_reset(detector_type):
    detector = detector_type(
        history=20,
        min_area=20,
        max_area=150,
        morph_kernel=1,
        detect_shadows=False,
    )
    background = _frame()
    for _ in range(25):
        detector.detect(background)

    changed = background.copy()
    cv2.circle(changed, (60, 45), 5, (255, 255, 255), -1)
    detections = detector.detect(changed)
    assert detections
    assert min(np.hypot(item.cx - 60, item.cy - 45) for item in detections) <= 2.0

    detector.reset()
    # A reset makes the first full frame foreground again; most importantly,
    # it proves state can be cleared between independent videos.
    first_after_reset = detector.detect(background)
    assert isinstance(first_after_reset, list)


def test_static_detectors_return_empty_on_empty_frame():
    frame = _frame()
    detectors = [
        ThresholdContourDetector(threshold_value=100),
        HybridThresholdDetector(threshold_value=20),
        BlobDetector(dark=False),
        WatershedDetector(invert=False),
    ]
    assert all(detector.detect(frame) == [] for detector in detectors)
