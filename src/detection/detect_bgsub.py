"""Classical baseline #3 - background subtraction (motion).

Sperm cells move while the background is nearly static, so a background model
(MOG2 or KNN) isolates moving foreground. The foreground mask is thresholded and
morphologically opened, then contours give bounding boxes. This detector is
stateful: the background model adapts over time, so ``reset`` rebuilds it
between videos.
"""
from __future__ import annotations

import cv2
import numpy as np

from .base_detector import Detection, Detector


class BackgroundSubtractionDetector(Detector):
    name = "bgsub"

    def __init__(
        self,
        method: str = "MOG2",
        min_area: float = 3.0,
        max_area: float = 400.0,
        history: int = 200,
        var_threshold: float = 16.0,
        dist2_threshold: float = 400.0,
        detect_shadows: bool = False,
        morph_kernel: int = 3,
    ) -> None:
        self.method = method.upper()
        self.min_area = min_area
        self.max_area = max_area
        self.history = history
        self.var_threshold = var_threshold
        self.dist2_threshold = dist2_threshold
        self.detect_shadows = detect_shadows
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel)
        )
        self._subtractor = None
        self.reset()

    def reset(self) -> None:
        if self.method == "KNN":
            self._subtractor = cv2.createBackgroundSubtractorKNN(
                history=self.history,
                dist2Threshold=self.dist2_threshold,
                detectShadows=self.detect_shadows,
            )
        else:
            self._subtractor = cv2.createBackgroundSubtractorMOG2(
                history=self.history,
                varThreshold=self.var_threshold,
                detectShadows=self.detect_shadows,
            )

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        mask = self._subtractor.apply(frame_bgr)
        # Drop shadow values (127) if shadow detection is on; keep hard foreground.
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel, iterations=1)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
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
