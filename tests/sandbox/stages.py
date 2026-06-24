"""Intermediate-stage extraction for each classical detector.

The ``Detector.detect`` interface only returns the final boxes. To *tune* a
method you need to see what happens in between — the binary mask, the morphology
result, the distance transform, etc. These functions reproduce each detector's
internal pipeline **reading the detector's own attributes** (``min_area``,
``kernel``, thresholds...), so editing a base detector's parameters is reflected
here without duplicating the values.

Each ``stages_<method>`` returns an ordered list of ``(name, image)`` where
``image`` is a uint8 array (grayscale or BGR) ready to be written to disk.
"""
from __future__ import annotations

import cv2
import numpy as np


def _norm(img: np.ndarray) -> np.ndarray:
    """Scale a float image to 0-255 uint8 for visualization."""
    img = img.astype(np.float32)
    mn, mx = float(img.min()), float(img.max())
    if mx - mn < 1e-9:
        return np.zeros(img.shape, dtype=np.uint8)
    return ((img - mn) / (mx - mn) * 255.0).astype(np.uint8)


def stages_threshold(det, frame_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    out = [("1_gray", gray)]
    if det.blur > 1:
        gray = cv2.GaussianBlur(gray, (det.blur, det.blur), 0)
        out.append((f"2_blur_{det.blur}", gray))

    thresh_type = cv2.THRESH_BINARY_INV if det.invert else cv2.THRESH_BINARY
    if det.adaptive:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresh_type, det.adaptive_block, det.adaptive_c,
        )
        out.append(("3_adaptive_thresh", binary))
    else:
        _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        out.append(("3_otsu_thresh", binary))

    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, det.kernel, iterations=1)
    out.append(("4_morph_open", opened))
    return out


def stages_watershed(det, frame_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    out = [("1_gray", gray)]
    if det.blur > 1:
        gray = cv2.GaussianBlur(gray, (det.blur, det.blur), 0)
        out.append((f"2_blur_{det.blur}", gray))

    thresh_type = cv2.THRESH_BINARY_INV if det.invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
    out.append(("3_otsu_thresh", binary))

    opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, det.kernel, iterations=1)
    out.append(("4_morph_open", opening))
    sure_bg = cv2.dilate(opening, det.kernel, iterations=2)
    out.append(("5_sure_bg", sure_bg))

    dist = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    out.append(("6_dist_transform", _norm(dist)))
    max_dist = dist.max()
    if max_dist > 0:
        _, sure_fg = cv2.threshold(dist, det.dist_ratio * max_dist, 255, 0)
        sure_fg = sure_fg.astype(np.uint8)
        out.append(("7_sure_fg", sure_fg))
        unknown = cv2.subtract(sure_bg, sure_fg)
        out.append(("8_unknown", unknown))
    return out


def stages_blob(det, frame_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return [("1_gray", gray)]


def stages_bgsub(
    det, frame_bgr: np.ndarray, warmup_frames: list[np.ndarray]
) -> list[tuple[str, np.ndarray]]:
    """Prime the background model on ``warmup_frames``, then show the mask.

    ``det.reset()`` rebuilds the model; the warmup frames are applied with the
    default learning rate so the target frame is scored against an adapted
    background. With no warmup the mask is essentially the first-frame model and
    will be noisy — that is expected, increase ``--warmup``.
    """
    det.reset()
    for f in warmup_frames:
        det._subtractor.apply(f)

    raw = det._subtractor.apply(frame_bgr)
    out = [(f"1_raw_mask_warmup{len(warmup_frames)}", raw)]
    _, hard = cv2.threshold(raw, 200, 255, cv2.THRESH_BINARY)
    out.append(("2_thresh_200", hard))
    opened = cv2.morphologyEx(hard, cv2.MORPH_OPEN, det.kernel, iterations=1)
    out.append(("3_morph_open", opened))
    return out


def compute_stages(
    method: str, det, frame_bgr: np.ndarray, warmup_frames: list[np.ndarray]
) -> list[tuple[str, np.ndarray]]:
    """Dispatch to the per-method stage extractor. Empty list if unsupported."""
    if method == "threshold":
        return stages_threshold(det, frame_bgr)
    if method == "watershed":
        return stages_watershed(det, frame_bgr)
    if method == "blob":
        return stages_blob(det, frame_bgr)
    if method == "bgsub":
        return stages_bgsub(det, frame_bgr, warmup_frames)
    return []  # yolo: no classical intermediate stages
