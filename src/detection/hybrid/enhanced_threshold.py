"""Hybrid classical detector for uneven microscopy illumination.

This is deliberately reported as a *hybrid of classical image-processing
stages*, not as a learned/ML model.  It combines local contrast normalisation
(CLAHE), morphological background correction (top-hat for bright objects or
black-hat for dark objects), configurable thresholding, morphology and
connected components.

The pure fixed/Otsu/adaptive threshold baselines remain unchanged in
``classical/threshold.py`` so the benefit of each added stage can be
measured rather than silently folded into the baseline.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..base import Detection, Detector


class HybridThresholdDetector(Detector):
    """CLAHE + background correction + threshold + connected components."""

    name = "hybrid_threshold"

    def __init__(
        self,
        min_area: float = 3.0,
        max_area: float = 300.0,
        clip_limit: float = 2.0,
        tile_grid_size: int = 8,
        background_kernel: int = 31,
        dark_objects: bool = False,
        threshold_value: int | None = None,
        morph_kernel: int = 3,
        open_iterations: int = 1,
        close_iterations: int = 1,
    ) -> None:
        if min_area < 0 or max_area < min_area:
            raise ValueError("Expected 0 <= min_area <= max_area")
        if clip_limit <= 0:
            raise ValueError("clip_limit must be positive")
        if tile_grid_size <= 0:
            raise ValueError("tile_grid_size must be positive")
        if background_kernel <= 1:
            raise ValueError("background_kernel must be greater than 1")
        if morph_kernel <= 0:
            raise ValueError("morph_kernel must be positive")
        if threshold_value is not None and not 0 <= threshold_value <= 255:
            raise ValueError("threshold_value must be in [0, 255] or None")

        self.min_area = float(min_area)
        self.max_area = float(max_area)
        self.clip_limit = float(clip_limit)
        self.tile_grid_size = int(tile_grid_size)
        self.background_kernel = (
            int(background_kernel)
            if int(background_kernel) % 2 == 1
            else int(background_kernel) + 1
        )
        self.dark_objects = bool(dark_objects)
        self.threshold_value = threshold_value
        self.morph_kernel = int(morph_kernel)
        self.open_iterations = int(open_iterations)
        self.close_iterations = int(close_iterations)

        self._clahe = cv2.createCLAHE(
            clipLimit=self.clip_limit,
            tileGridSize=(self.tile_grid_size, self.tile_grid_size),
        )
        self._background_element = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.background_kernel, self.background_kernel),
        )
        self._morph_element = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.morph_kernel, self.morph_kernel)
        )

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        normalised = self._clahe.apply(gray)
        correction = cv2.MORPH_BLACKHAT if self.dark_objects else cv2.MORPH_TOPHAT
        foreground = cv2.morphologyEx(
            normalised, correction, self._background_element
        )

        if self.threshold_value is None:
            _, binary = cv2.threshold(
                foreground, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:
            _, binary = cv2.threshold(
                foreground, self.threshold_value, 255, cv2.THRESH_BINARY
            )
        if self.open_iterations > 0:
            binary = cv2.morphologyEx(
                binary,
                cv2.MORPH_OPEN,
                self._morph_element,
                iterations=self.open_iterations,
            )
        if self.close_iterations > 0:
            binary = cv2.morphologyEx(
                binary,
                cv2.MORPH_CLOSE,
                self._morph_element,
                iterations=self.close_iterations,
            )

        n_labels, _, stats, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
        detections: list[Detection] = []
        for label in range(1, n_labels):
            area = float(stats[label, cv2.CC_STAT_AREA])
            if area < self.min_area or area > self.max_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            width = float(stats[label, cv2.CC_STAT_WIDTH])
            height = float(stats[label, cv2.CC_STAT_HEIGHT])
            detections.append(
                Detection(
                    cx=x + width / 2.0,
                    cy=y + height / 2.0,
                    w=width,
                    h=height,
                    class_id=0,
                    score=1.0,
                )
            )
        return detections
