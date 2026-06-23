"""Drawing helpers: overlay detections / ground truth and write annotated video."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .base_detector import Detection

# BGR colors by annotation source.
COLORS = {
    "detection": (0, 255, 0),   # green
    "manual": (0, 0, 255),      # red
}


def draw_detections(
    frame: np.ndarray,
    dets: list[Detection],
    color: tuple[int, int, int],
    mode: str = "both",
    draw_id: bool = False,
) -> np.ndarray:
    """Draw detections in place on ``frame``.

    ``mode``: ``box`` (rectangle), ``centroid`` (filled dot), ``circle`` (dot),
    or ``both`` (rectangle + dot).
    """
    for d in dets:
        x, y, w, h = int(d.x), int(d.y), int(d.w), int(d.h)
        cx, cy = int(d.cx), int(d.cy)
        if mode in ("box", "both"):
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
        if mode in ("centroid", "circle", "both"):
            cv2.circle(frame, (cx, cy), 3, color, -1)
        if draw_id:
            oid = d.object_id
            # object_id may be an int index (detection) or a string track id (GT).
            if isinstance(oid, str):
                label = oid[:6] if oid else ""  # shorten long LabelBox hashes
            else:
                label = str(oid) if oid >= 0 else ""
            if label:
                cv2.putText(
                    frame, label, (x, max(0, y - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA,
                )
    return frame


def draw_legend(frame: np.ndarray, items: list[tuple[str, tuple[int, int, int]]]) -> np.ndarray:
    """Draw a small top-left legend: list of ``(label, color)``."""
    y = 16
    for label, color in items:
        cv2.putText(
            frame, label, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
        )
        y += 17
    return frame


def open_writer(path: str | Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    """Open an mp4 ``cv2.VideoWriter`` (creates parent dirs)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {path}")
    return writer
