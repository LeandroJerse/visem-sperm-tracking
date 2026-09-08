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
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .base import Detection

# VISEM-Tracking classes (per the Scientific Data 2023 paper, Table 2).
CLASS_NAMES = {0: "normal", 1: "cluster", 2: "pinhead"}

CSV_FIELDS = [
    "video_id", "frame", "source", "object_id", "class_id", "class_name",
    "cx", "cy", "w", "h", "x", "y", "score",
]

_FRAME_INDEX_RE = re.compile(
    r"(?:^|[_-])frame[_-]?(?P<index>\d+)(?=$|[_-])", re.IGNORECASE
)


@dataclass(frozen=True)
class GroundTruthFrame:
    """Ground-truth state for one video frame.

    ``annotated=False`` means that no label file exists and the frame must be
    excluded from quantitative evaluation.  An existing, empty label file is
    represented by ``annotated=True`` and ``detections=()``: that is a valid
    manually annotated negative frame.
    """

    frame_idx: int
    annotated: bool
    detections: tuple[Detection, ...] = ()
    label_path: Path | None = None


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
def parse_label_line(
    line: str, img_w: int, img_h: int, *, strict_ftid: bool = False,
) -> Detection | None:
    """Parse one VISEM-Tracking label line into a pixel-space ``Detection``.

    Handles both annotation layouts in the dataset:
      * ``labels/``      -> ``class cx cy w h``             (no track id)
      * ``labels_ftid/`` -> ``track_id class cx cy w h``    (track id first,
        a LabelBox string such as ``ckz3v9nzv00033867jsekqdcl``)

    Detection is decided by whether the first token is numeric (then it is the
    class -> ``labels`` layout) or not (then it is the track id -> ``labels_ftid``
    layout). Returns ``None`` for blank/malformed lines.

    ``strict_ftid=True`` instead requires the explicit six-field tracked
    layout, including when the track ID is numeric; nonblank malformed lines
    raise and all boxes must have valid finite geometry inside the image.
    """
    if strict_ftid:
        return _parse_strict_ftid_line(line, img_w, img_h)
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


def _parse_strict_ftid_line(line: str, img_w: int, img_h: int) -> Detection | None:
    """Parse the explicit six-field layout; numeric track IDs remain IDs."""
    if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0
               for value in (img_w, img_h)):
        raise ValueError("Image dimensions must be positive integers")
    parts = line.split()
    if not parts:
        return None
    if len(parts) != 6 or parts[1] not in {"0", "1", "2"}:
        raise ValueError("Expected six fields: track_id class[0/1/2] cx cy w h")
    try:
        cx, cy, width, height = (float(value) for value in parts[2:])
    except ValueError as exc:
        raise ValueError("Normalized GT coordinates must be numeric") from exc
    if not all(math.isfinite(value) and 0 <= value <= 1
               for value in (cx, cy, width, height)) or min(width, height) <= 0:
        raise ValueError("Normalized GT coordinates must be finite/in range, with positive dimensions")
    x, y, w_px, h_px, cx_px, cy_px = yolo_to_pixels(cx, cy, width, height, img_w, img_h)
    if min(x, y) < -1e-9 or x + w_px > img_w + 1e-9 or y + h_px > img_h + 1e-9:
        raise ValueError("GT box extends outside the image")
    return Detection(cx_px, cy_px, w_px, h_px, class_id=int(parts[1]), object_id=parts[0])


def parse_gt_text(
    text: str, img_w: int, img_h: int, *, strict_ftid: bool = False,
    label_path: str | Path = "<labels>",
) -> list[Detection]:
    """Parse already-read label text, preserving contextual strict errors."""
    detections: list[Detection] = []
    identities: set[int | str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            detection = parse_label_line(line, img_w, img_h, strict_ftid=strict_ftid)
            if detection is not None:
                if strict_ftid and detection.object_id in identities:
                    raise ValueError(f"Duplicate GT track identity {detection.object_id!r}")
                identities.add(detection.object_id)
                detections.append(detection)
        except (ValueError, OverflowError) as exc:
            if strict_ftid:
                raise ValueError(f"{label_path}:{line_number}: {exc}") from exc
            raise
    return detections


def load_gt_frame(
    label_path: str | Path, img_w: int, img_h: int, *, strict_ftid: bool = False,
) -> list[Detection]:
    """Load all ground-truth detections from a single label ``.txt`` file."""
    path = Path(label_path)
    if not strict_ftid and not path.exists():
        return []
    return parse_gt_text(
        path.read_text(encoding="utf-8-sig" if strict_ftid else "utf-8"),
        img_w, img_h, strict_ftid=strict_ftid, label_path=path,
    )


def _natural_key(path: Path) -> list:
    """Sort key that orders ``frame_2`` before ``frame_10``."""
    return [int(tok) if tok.isdigit() else tok for tok in re.split(r"(\d+)", path.name)]


def extract_frame_index(path: str | Path) -> int:
    """Extract the video frame index encoded in an annotation filename.

    Supported VISEM names include ``11_frame_7.txt`` and
    ``11_frame_7_with_ftid.txt``.  A numeric-only stem (for example
    ``000007.txt``) is accepted for interoperability with exported datasets.
    The video id at the beginning of a VISEM filename is deliberately ignored.
    """
    stem = Path(path).stem
    match = _FRAME_INDEX_RE.search(stem)
    if match is not None:
        return int(match.group("index"))
    if stem.isdigit():
        return int(stem)
    raise ValueError(f"Could not extract frame index from label filename: {Path(path).name}")


def list_label_files(gt_dir: str | Path) -> list[Path]:
    """Return the per-frame ``.txt`` label files in natural frame order."""
    return sorted(Path(gt_dir).glob("*.txt"), key=_natural_key)


def index_label_files(gt_dir: str | Path) -> dict[int, Path]:
    """Map the encoded frame number to its label file.

    This mapping is the source of truth for video/annotation alignment.  It is
    intentionally not based on the file's position in a sorted list, because a
    missing file then denotes an unannotated frame rather than an empty frame.
    """
    index: dict[int, Path] = {}
    for path in list_label_files(gt_dir):
        frame_idx = extract_frame_index(path)
        if frame_idx in index:
            raise ValueError(
                f"Duplicate label files for frame {frame_idx}: {index[frame_idx]} and {path}"
            )
        index[frame_idx] = path
    return index


def load_gt_for_frame(
    gt_dir: str | Path,
    frame_idx: int,
    img_w: int,
    img_h: int,
    *,
    label_index: dict[int, Path] | None = None,
) -> GroundTruthFrame:
    """Load one frame by its encoded index and preserve annotation status."""
    files = label_index if label_index is not None else index_label_files(gt_dir)
    label_path = files.get(int(frame_idx))
    if label_path is None:
        return GroundTruthFrame(frame_idx=int(frame_idx), annotated=False)
    detections = tuple(load_gt_frame(label_path, img_w, img_h))
    return GroundTruthFrame(
        frame_idx=int(frame_idx),
        annotated=True,
        detections=detections,
        label_path=label_path,
    )


# --------------------------------------------------------------------------- #
# CSV output
# --------------------------------------------------------------------------- #
def detection_to_row(video_id: str, frame_idx: int, source: str, det: Detection) -> dict:
    """Build a unified-CSV row without rounding coordinates or confidence.

    Python floats serialize with enough digits for an exact float round-trip.
    Converting NumPy scalars explicitly also avoids their shorter display
    formatting changing the values used by evaluation or tracking.
    """
    return {
        "video_id": video_id,
        "frame": frame_idx,
        "source": source,
        "object_id": det.object_id,
        "class_id": det.class_id,
        "class_name": CLASS_NAMES.get(det.class_id, str(det.class_id)),
        "cx": float(det.cx),
        "cy": float(det.cy),
        "w": float(det.w),
        "h": float(det.h),
        "x": float(det.x),
        "y": float(det.y),
        "score": float(det.score),
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
