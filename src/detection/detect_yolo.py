"""Modern detector (later phase) - YOLO inference wrapper.

This is the principal modern detector for the project. It is a thin wrapper over
Ultralytics YOLO and requires a model trained/fine-tuned on VISEM-Tracking
(whose labels are already in native YOLO format). Implemented as a stub for now:
it only activates when ``ultralytics`` is installed and ``weights`` is given.

Future modern detectors (not implemented here): Faster R-CNN (theoretical
comparison), U-Net / Mask R-CNN (precise masks), SAM (assisted segmentation).
"""
from __future__ import annotations

import numpy as np

from .base_detector import Detection, Detector


class YoloDetector(Detector):
    name = "yolo"

    def __init__(self, weights: str | None = None, conf: float = 0.25, imgsz: int = 640) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover - optional dependency
            raise ImportError(
                "YOLO requer o pacote 'ultralytics' (pip install ultralytics). "
                "Detector moderno - fase posterior do TCC."
            ) from e
        if weights is None:
            raise ValueError(
                "YoloDetector requer --weights (modelo treinado no VISEM-Tracking)."
            )
        self._model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        result = self._model.predict(
            frame_bgr, conf=self.conf, imgsz=self.imgsz, verbose=False
        )[0]
        dets: list[Detection] = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            score = float(box.conf[0])
            w = x2 - x1
            h = y2 - y1
            dets.append(
                Detection(cx=x1 + w / 2.0, cy=y1 + h / 2.0, w=w, h=h,
                          class_id=class_id, score=score)
            )
        return dets
