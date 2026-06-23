"""Classical baseline #2 - blob detection.

``cv2.SimpleBlobDetector`` is well suited to small, roughly circular, dark
objects like sperm heads. We filter by color (dark) and area; circularity /
convexity / inertia filters are off by default because sperm heads are small and
noisy, but are exposed as constructor args for tuning.
"""
from __future__ import annotations

import cv2
import numpy as np

from .base_detector import Detection, Detector


class BlobDetector(Detector):
    name = "blob"

    def __init__(
        self,
        min_area: float = 2.0,
        max_area: float = 200.0,
        min_threshold: float = 10.0,
        max_threshold: float = 200.0,
        threshold_step: float = 10.0,
        dark: bool = True,
        min_circularity: float | None = None,
        min_convexity: float | None = None,
    ) -> None:
        params = cv2.SimpleBlobDetector_Params()
        params.minThreshold = min_threshold
        params.maxThreshold = max_threshold
        params.thresholdStep = threshold_step

        params.filterByColor = True
        params.blobColor = 0 if dark else 255

        params.filterByArea = True
        params.minArea = min_area
        params.maxArea = max_area

        params.filterByCircularity = min_circularity is not None
        if min_circularity is not None:
            params.minCircularity = min_circularity

        params.filterByConvexity = min_convexity is not None
        if min_convexity is not None:
            params.minConvexity = min_convexity

        params.filterByInertia = False

        self._detector = cv2.SimpleBlobDetector_create(params)

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        keypoints = self._detector.detect(gray)
        dets: list[Detection] = []
        for kp in keypoints:
            diameter = float(kp.size)
            dets.append(
                Detection(cx=float(kp.pt[0]), cy=float(kp.pt[1]),
                          w=diameter, h=diameter, class_id=0, score=1.0)
            )
        return dets
