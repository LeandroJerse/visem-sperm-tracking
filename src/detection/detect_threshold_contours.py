"""Classical baseline #1 - thresholding + contours.

Sperm heads appear as small dark blobs over a bright phase-contrast background,
so we threshold the inverted intensity (Otsu or adaptive), clean the mask with a
morphological opening, then extract one bounding box per external contour,
filtering by area to drop noise and large debris.
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
        blur: int = 3,
        invert: bool = True,
        adaptive: bool = False,
        adaptive_block: int = 21,
        adaptive_c: int = 5,
        morph_kernel: int = 3,
    ) -> None:
        self.min_area = min_area
        self.max_area = max_area
        self.blur = blur if blur % 2 == 1 else blur + 1  # must be odd
        self.invert = invert
        self.adaptive = adaptive
        self.adaptive_block = adaptive_block if adaptive_block % 2 == 1 else adaptive_block + 1
        self.adaptive_c = adaptive_c
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel)
        )

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
        else:
            _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.kernel, iterations=1)

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        dets: list[Detection] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area or area > self.max_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            dets.append(
                Detection(cx=x + w / 2.0, cy=y + h / 2.0, w=float(w), h=float(h),
                          class_id=0, score=1.0)
            )
        return dets
