"""Small synthetic cases with known ground truth for flow validation."""
from __future__ import annotations

import numpy as np

from .base import FlowResult
from .metrics import sample_field


def constant_translation_flow(
    shape: tuple[int, int],
    displacement: tuple[float, float],
    *,
    valid_in_bounds_only: bool = True,
) -> FlowResult:
    """Create a known constant flow and optional visibility mask."""

    height, width = (int(shape[0]), int(shape[1]))
    if height <= 0 or width <= 0:
        raise ValueError("shape must be positive")
    u, v = float(displacement[0]), float(displacement[1])
    if not np.isfinite([u, v]).all():
        raise ValueError("displacement must be finite")
    flow = np.empty((height, width, 2), dtype=np.float32)
    flow[...] = (u, v)
    if valid_in_bounds_only:
        y, x = np.mgrid[:height, :width]
        valid = (
            (x + u >= 0)
            & (x + u <= width - 1)
            & (y + v >= 0)
            & (y + v <= height - 1)
        )
    else:
        valid = np.ones((height, width), dtype=bool)
    return FlowResult(
        flow,
        valid,
        metadata={"synthetic": "constant_translation", "u": u, "v": v},
    )


def translate_frame(
    frame: np.ndarray,
    displacement: tuple[float, float],
    *,
    fill_value: float = 0.0,
) -> np.ndarray:
    """Translate an image with bilinear inverse sampling."""

    image = np.asarray(frame)
    if image.ndim not in (2, 3):
        raise ValueError("frame must be grayscale or color")
    u, v = float(displacement[0]), float(displacement[1])
    height, width = image.shape[:2]
    y, x = np.mgrid[:height, :width].astype(np.float32)
    source_points = np.stack((x - u, y - v), axis=-1)
    translated, inside = sample_field(image, source_points, outside_value=fill_value)
    if image.ndim == 3:
        translated[~inside] = fill_value
    if np.issubdtype(image.dtype, np.integer):
        limits = np.iinfo(image.dtype)
        translated = np.clip(np.rint(translated), limits.min, limits.max)
    return translated.astype(image.dtype, copy=False)


def translation_case(
    frame: np.ndarray,
    displacement: tuple[float, float],
    *,
    fill_value: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, FlowResult]:
    """Return previous frame, translated next frame, and exact visible flow."""

    previous = np.asarray(frame).copy()
    following = translate_frame(previous, displacement, fill_value=fill_value)
    truth = constant_translation_flow(previous.shape[:2], displacement)
    return previous, following, truth
