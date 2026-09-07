"""Safe sampling helpers for optional flow-aware tracking."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


def sample_flow(
    flow: Any,
    bbox: np.ndarray,
    *,
    window_scale: float = 1.0,
) -> tuple[float, float]:
    """Return a robust local ``(u, v)`` flow estimate.

    Accepted inputs are ``None``, a uniform ``(u, v)`` pair, a callable taking
    ``(cx, cy)``, or a dense ``H x W x 2`` array.  Dense flow is reduced by the
    component-wise median inside the box, which is more robust to isolated
    sperm/artefact vectors than sampling one pixel.
    """
    if flow is None:
        return (0.0, 0.0)
    box = np.asarray(bbox, dtype=float).reshape(4)
    if window_scale <= 0:
        raise ValueError("window_scale must be positive")

    if isinstance(flow, Callable):
        return _finite_pair(flow(float(box[0]), float(box[1])))
    array = np.asarray(flow, dtype=float)
    if array.shape == (2,):
        return _finite_pair(array)
    if array.ndim != 3 or array.shape[2] != 2:
        raise ValueError("flow must be a (u, v) pair, callable, or H x W x 2 array")

    height, width = array.shape[:2]
    half_w = max(1.0, box[2] * window_scale / 2.0)
    half_h = max(1.0, box[3] * window_scale / 2.0)
    x1 = max(0, int(np.floor(box[0] - half_w)))
    x2 = min(width, int(np.ceil(box[0] + half_w)) + 1)
    y1 = max(0, int(np.floor(box[1] - half_h)))
    y2 = min(height, int(np.ceil(box[1] + half_h)) + 1)
    if x1 >= x2 or y1 >= y2:
        return (0.0, 0.0)
    region = array[y1:y2, x1:x2].reshape(-1, 2)
    valid = np.all(np.isfinite(region), axis=1)
    if not np.any(valid):
        return (0.0, 0.0)
    median = np.median(region[valid], axis=0)
    return (float(median[0]), float(median[1]))


def _finite_pair(value: Any) -> tuple[float, float]:
    pair = np.asarray(value, dtype=float).reshape(-1)
    if pair.size != 2:
        raise ValueError("Flow provider must return exactly two components")
    if not np.all(np.isfinite(pair)):
        return (0.0, 0.0)
    return (float(pair[0]), float(pair[1]))
