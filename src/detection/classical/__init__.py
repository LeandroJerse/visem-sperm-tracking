"""Detectores clássicos, sem treinamento supervisionado."""

from .background_subtraction import (
    BackgroundSubtractionDetector,
    KNNDetector,
    MOG2Detector,
)
from .blob import BlobDetector
from .threshold import ThresholdContourDetector
from .watershed import WatershedDetector

__all__ = [
    "BackgroundSubtractionDetector",
    "BlobDetector",
    "KNNDetector",
    "MOG2Detector",
    "ThresholdContourDetector",
    "WatershedDetector",
]
