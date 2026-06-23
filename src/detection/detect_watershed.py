"""Intermediate classical baseline - watershed segmentation.

Useful for separating touching/overlapping cells (the ``cluster`` case). We
build a foreground mask (Otsu inverse), use the distance transform to find sure
foreground seeds, mark the unknown band, and run ``cv2.watershed`` to split the
regions. One bounding box per resulting labeled region (area-filtered).
"""
from __future__ import annotations

import cv2
import numpy as np

from .base_detector import Detection, Detector


class WatershedDetector(Detector):
    name = "watershed"

    def __init__(
        self,
        min_area: float = 3.0,
        max_area: float = 600.0,
        blur: int = 3,
        invert: bool = True,
        dist_ratio: float = 0.4,
        morph_kernel: int = 3,
    ) -> None:
        self.min_area = min_area
        self.max_area = max_area
        self.blur = blur if blur % 2 == 1 else blur + 1
        self.invert = invert
        self.dist_ratio = dist_ratio
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel)
        )

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self.blur > 1:
            gray = cv2.GaussianBlur(gray, (self.blur, self.blur), 0)

        thresh_type = cv2.THRESH_BINARY_INV if self.invert else cv2.THRESH_BINARY
        _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.kernel, iterations=1)
        sure_bg = cv2.dilate(opening, self.kernel, iterations=2)

        dist = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
        max_dist = dist.max()
        if max_dist <= 0:
            return []
        _, sure_fg = cv2.threshold(dist, self.dist_ratio * max_dist, 255, 0)
        sure_fg = sure_fg.astype(np.uint8)
        unknown = cv2.subtract(sure_bg, sure_fg)

        n_markers, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1            # background is 1, not 0
        markers[unknown == 255] = 0      # unknown region marked 0
        markers = cv2.watershed(frame_bgr, markers)

        dets: list[Detection] = []
        # Labels: -1 = boundaries, 1 = background, >=2 = objects.
        for label in range(2, n_markers + 1):
            ys, xs = np.where(markers == label)
            if xs.size == 0:
                continue
            area = float(xs.size)
            if area < self.min_area or area > self.max_area:
                continue
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            w = float(x1 - x0 + 1)
            h = float(y1 - y0 + 1)
            dets.append(
                Detection(cx=x0 + w / 2.0, cy=y0 + h / 2.0, w=w, h=h,
                          class_id=0, score=1.0)
            )
        return dets
