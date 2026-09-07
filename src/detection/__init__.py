"""Detecção de espermatozoides: clássica, híbrida e aprendida."""

from .base import Detection, Detector
from .classical import (
    BackgroundSubtractionDetector,
    BlobDetector,
    KNNDetector,
    MOG2Detector,
    ThresholdContourDetector,
    WatershedDetector,
)
from .hybrid import HybridThresholdDetector
from .learned import YoloDetector
from .registry import DETECTORS, build_detector

__all__ = [
    "BackgroundSubtractionDetector",
    "BlobDetector",
    "DETECTORS",
    "Detection",
    "Detector",
    "HybridThresholdDetector",
    "KNNDetector",
    "MOG2Detector",
    "ThresholdContourDetector",
    "WatershedDetector",
    "YoloDetector",
    "build_detector",
]
