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

from ..base import Detection, Detector


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

    def _run_pipeline(
        self, frame_bgr: np.ndarray, *, collect_stages: bool
    ) -> tuple[list[Detection], list[tuple[str, np.ndarray]]]:
        """Execute one canonical pipeline, optionally retaining diagnostics.

        The frame-screening tool calls this same implementation used by
        :meth:`detect`; it never reconstructs segmentation logic in a script.
        """

        stages: list[tuple[str, np.ndarray]] = []
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if collect_stages:
            stages.append(("1_gray", gray.copy()))
        if self.blur > 1:
            gray = cv2.GaussianBlur(gray, (self.blur, self.blur), 0)
            if collect_stages:
                stages.append((f"2_blur_{self.blur}", gray.copy()))

        thresh_type = cv2.THRESH_BINARY_INV if self.invert else cv2.THRESH_BINARY
        if self.adaptive:
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                thresh_type, self.adaptive_block, self.adaptive_c,
            )
            threshold_stage = "3_adaptive_thresh"
        elif self.threshold_value is not None:
            _, binary = cv2.threshold(gray, self.threshold_value, 255, thresh_type)
            threshold_stage = f"3_fixed_thresh_{self.threshold_value}"
        else:
            used_value, binary = cv2.threshold(
                gray, 0, 255, thresh_type + cv2.THRESH_OTSU
            )
            threshold_stage = f"3_otsu_thresh_{int(used_value)}"
        if collect_stages:
            stages.append((threshold_stage, binary.copy()))

        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.kernel, iterations=self.morph_iterations)
        if collect_stages:
            stages.append(
                (f"4_morph_open_x{self.morph_iterations}", binary.copy())
            )
        if self.close_iterations > 0:
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self.kernel, iterations=self.close_iterations)
            if collect_stages:
                stages.append(
                    (f"5_morph_close_x{self.close_iterations}", binary.copy())
                )

        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
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
        if collect_stages:
            colored = np.zeros((*binary.shape, 3), dtype=np.uint8)
            for label in range(1, n_labels):
                area = float(stats[label, cv2.CC_STAT_AREA])
                if area < self.min_area or area > self.max_area:
                    continue
                hue = int(((label * 0.618033988749895) % 1.0) * 179)
                color = cv2.cvtColor(
                    np.array([[[hue, 220, 210]]], dtype=np.uint8),
                    cv2.COLOR_HSV2BGR,
                )[0, 0]
                colored[labels == label] = color
            component_step = "6" if self.close_iterations > 0 else "5"
            stages.append((f"{component_step}_labeled_components", colored))
        return dets, stages

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        detections, _ = self._run_pipeline(frame_bgr, collect_stages=False)
        return detections

    def diagnostic_stages(
        self, frame_bgr: np.ndarray
    ) -> list[tuple[str, np.ndarray]]:
        """Return images produced by the exact detection implementation."""

        _, stages = self._run_pipeline(frame_bgr, collect_stages=True)
        return stages
