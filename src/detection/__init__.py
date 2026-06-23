"""Sperm detection module (classical baselines first, modern detectors later).

Public API:
    Detection, Detector           -- base abstractions (base_detector)
    run_on_video                  -- frame loop runner (runner)
    DETECTORS                     -- name -> Detector class registry (run_detection)
"""
from .base_detector import Detection, Detector

__all__ = ["Detection", "Detector"]
