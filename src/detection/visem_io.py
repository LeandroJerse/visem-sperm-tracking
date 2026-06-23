"""I/O helpers for the VISEM / VISEM-Tracking datasets.

Responsibilities:
    * YOLO (normalized) <-> pixel bounding-box conversion
    * Parsing VISEM-Tracking label files (``class cx cy w h [track_id]``)
    * Listing per-frame label files in natural order
    * Writing the unified detection CSV used across the detection module

The unified CSV schema (one row per object per frame, long format)::

    video_id, frame, source, object_id, class_id, class_name,
    cx, cy, w, h, x, y, score

``source`` is ``detection`` or ``manual`` so automatic detections and manual
ground-truth annotations can live in the same file and be compared downstream.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .base_detector import Detection

# VISEM-Tracking classes (per the Scientific Data 2023 paper, Table 2).
CLASS_NAMES = {0: "normal", 1: "cluster", 2: "pinhead"}

CSV_FIELDS = [
    "video_id", "frame", "source", "object_id", "class_id", "class_name",
    "cx", "cy", "w", "h", "x", "y", "score",
]


# --------------------------------------------------------------------------- #
# Coordinate conversion
# --------------------------------------------------------------------------- #
def yolo_to_pixels(
    cx: float, cy: float, w: float, h: float, img_w: int, img_h: int
) -> tuple[float, float, float, float, float, float]:
    """Convert a normalized YOLO box to pixels.

    Returns ``(x, y, w_px, h_px, cx_px, cy_px)`` where ``x, y`` is the top-left
    corner. Inputs ``cx, cy, w, h`` are in ``[0, 1]``.
    """
    cx_px = cx * img_w
    cy_px = cy * img_h
    w_px = w * img_w
    h_px = h * img_h
    x = cx_px - w_px / 2.0
    y = cy_px - h_px / 2.0
    return x, y, w_px, h_px, cx_px, cy_px


def pixels_to_yolo(
    x: float, y: float, w_px: float, h_px: float, img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Inverse of :func:`yolo_to_pixels`.

    ``x, y`` is the top-left corner in pixels. Returns normalized
    ``(cx, cy, w, h)`` in ``[0, 1]``.
    """
    cx = (x + w_px / 2.0) / img_w
    cy = (y + h_px / 2.0) / img_h
    w = w_px / img_w
    h = h_px / img_h
    return cx, cy, w, h


# --------------------------------------------------------------------------- #
# Ground-truth label parsing
# --------------------------------------------------------------------------- #
def parse_label_line(line: str, img_w: int, img_h: int) -> Detection | None:
    """Parse one VISEM-Tracking label line into a pixel-space ``Detection``.

    Handles both annotation layouts in the dataset:
      * ``labels/``      -> ``class cx cy w h``             (no track id)
      * ``labels_ftid/`` -> ``track_id class cx cy w h``    (track id first,
        a LabelBox string such as ``ckz3v9nzv00033867jsekqdcl``)

    Detection is decided by whether the first token is numeric (then it is the
    class -> ``labels`` layout) or not (then it is the track id -> ``labels_ftid``
    layout). Returns ``None`` for blank/malformed lines.
    """
    parts = line.split()
    if len(parts) < 5:
        return None

    def _is_number(tok: str) -> bool:
        try:
            float(tok)
            return True
        except ValueError:
            return False

    track_id: int | str = -1
    if _is_number(parts[0]):
        # labels/: class cx cy w h
        class_id = int(float(parts[0]))
        coords = parts[1:5]
    else:
        # labels_ftid/: track_id class cx cy w h
        if len(parts) < 6:
            return None
        track_id = parts[0]
        class_id = int(float(parts[1]))
        coords = parts[2:6]

    cx, cy, w, h = (float(v) for v in coords)
    x, y, w_px, h_px, cx_px, cy_px = yolo_to_pixels(cx, cy, w, h, img_w, img_h)
    return Detection(
        cx=cx_px, cy=cy_px, w=w_px, h=h_px,
        class_id=class_id, score=1.0, object_id=track_id,
    )


def load_gt_frame(label_path: str | Path, img_w: int, img_h: int) -> list[Detection]:
    """Load all ground-truth detections from a single label ``.txt`` file."""
    path = Path(label_path)
    if not path.exists():
        return []
    dets: list[Detection] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        det = parse_label_line(line, img_w, img_h)
        if det is not None:
            dets.append(det)
    return dets


def _natural_key(path: Path) -> list:
    """Sort key that orders ``frame_2`` before ``frame_10``."""
    return [int(tok) if tok.isdigit() else tok for tok in re.split(r"(\d+)", path.name)]


def list_label_files(gt_dir: str | Path) -> list[Path]:
    """Return the per-frame ``.txt`` label files in natural frame order."""
    return sorted(Path(gt_dir).glob("*.txt"), key=_natural_key)


# --------------------------------------------------------------------------- #
# CSV output
# --------------------------------------------------------------------------- #
def detection_to_row(video_id: str, frame_idx: int, source: str, det: Detection) -> dict:
    """Build a unified-CSV row dict from a ``Detection``."""
    return {
        "video_id": video_id,
        "frame": frame_idx,
        "source": source,
        "object_id": det.object_id,
        "class_id": det.class_id,
        "class_name": CLASS_NAMES.get(det.class_id, str(det.class_id)),
        "cx": round(det.cx, 2),
        "cy": round(det.cy, 2),
        "w": round(det.w, 2),
        "h": round(det.h, 2),
        "x": round(det.x, 2),
        "y": round(det.y, 2),
        "score": round(det.score, 4),
    }


def write_detections_csv(rows: list[dict], path: str | Path) -> Path:
    """Write rows (from :func:`detection_to_row`) to a CSV with the standard header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path
