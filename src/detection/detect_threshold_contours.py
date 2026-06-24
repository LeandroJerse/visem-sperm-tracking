"""Classical baseline #1 - thresholding + connected components.

Sperm heads appear as bright (white) blobs in phase-contrast microscopy.
Otsu binarisation (THRESH_BINARY, no inversion) isolates the bright foreground;
a morphological opening removes noise; connected-component labelling
(cv2.connectedComponentsWithStats, 8-connectivity) counts and bounds each
region. Using connected components instead of findContours is the standard
classical approach: each region gets a unique integer label, area and bounding
box come directly from the stats matrix, no contour approximation needed.
"""
from __future__ import annotations

import cv2
import numpy as np

from .base_detector import Detection, Detector


class ThresholdContourDetector(Detector):
    name = "threshold"

    def __init__(
        self,
        min_area: float = 3.0,
        max_area: float = 300.0,
        blur: int = 1,
        invert: bool = False,
        threshold_value: int | None = None,
        adaptive: bool = False,
        adaptive_block: int = 21,
        adaptive_c: int = 5,
        morph_kernel: int = 3,
        morph_iterations: int = 1,
        close_iterations: int = 1,
    ) -> None:
        self.min_area = min_area
        self.max_area = max_area
        self.blur = blur if blur % 2 == 1 else blur + 1  # must be odd; 1 = disabled
        self.invert = invert
        self.threshold_value = threshold_value  # None = Otsu; 0-255 = fixed
        self.adaptive = adaptive
        self.adaptive_block = adaptive_block if adaptive_block % 2 == 1 else adaptive_block + 1
        self.adaptive_c = adaptive_c
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel)
        )
        self.morph_iterations = morph_iterations
        self.close_iterations = close_iterations  # 0 = desabilitado

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self.blur > 1:
            gray = cv2.GaussianBlur(gray, (self.blur, self.blur), 0)

        thresh_type = cv2.THRESH_BINARY_INV if self.invert else cv2.THRESH_BINARY
        if self.adaptive:
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                thresh_type, self.adaptive_block, self.adaptive_c,
            )
        elif self.threshold_value is not None:
            _, binary = cv2.threshold(gray, self.threshold_value, 255, thresh_type)
        else:
            _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.kernel, iterations=self.morph_iterations)
        if self.close_iterations > 0:
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self.kernel, iterations=self.close_iterations)

        n_labels, _, stats, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
        dets: list[Detection] = []
        for label in range(1, n_labels):  # 0 is background
            area = float(stats[label, cv2.CC_STAT_AREA])
            if area < self.min_area or area > self.max_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = float(stats[label, cv2.CC_STAT_WIDTH])
            h = float(stats[label, cv2.CC_STAT_HEIGHT])
            dets.append(
                Detection(cx=x + w / 2.0, cy=y + h / 2.0, w=w, h=h,
                          class_id=0, score=1.0)
            )
        return dets
