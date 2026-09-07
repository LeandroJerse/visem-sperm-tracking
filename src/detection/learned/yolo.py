"""Modern detector (later phase) - YOLO inference wrapper.

This is the principal modern detector for the project. It is a thin wrapper over
Ultralytics YOLO and requires a model trained/fine-tuned on VISEM-Tracking
(whose labels are already in native YOLO format). A dependência é carregada
somente quando a inferência é solicitada e pesos ajustados são obrigatórios.

Future modern detectors (not implemented here): Faster R-CNN (theoretical
comparison), U-Net / Mask R-CNN (precise masks), SAM (assisted segmentation).
"""
from __future__ import annotations

import numpy as np

from ..base import Detection, Detector


class YoloDetector(Detector):
    name = "yolo"

    def __init__(
        self,
        weights: str | None = None,
        conf: float = 0.25,
        imgsz: int = 640,
        nms_iou: float = 0.7,
    ) -> None:
        if weights is None:
            raise ValueError(
                "YoloDetector requer --weights (modelo treinado no VISEM-Tracking)."
            )
        try:
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover - optional dependency
            raise ImportError(
                "YOLO requer o pacote 'ultralytics' (pip install ultralytics). "
                "Detector moderno - fase posterior do TCC."
            ) from e
        if not 0.0 <= float(conf) <= 1.0:
            raise ValueError("conf deve estar no intervalo [0, 1].")
        if not 0.0 < float(nms_iou) <= 1.0:
            raise ValueError("nms_iou deve estar no intervalo (0, 1].")
        if int(imgsz) <= 0:
            raise ValueError("imgsz deve ser positivo.")
        self._model = YOLO(weights)
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.nms_iou = float(nms_iou)

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        result = self._model.predict(
            frame_bgr,
            conf=self.conf,
            imgsz=self.imgsz,
            iou=self.nms_iou,
            verbose=False,
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
