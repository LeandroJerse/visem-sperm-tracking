"""Optical-flow metrics and geometry with no OpenCV dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .base import FlowResult, as_gray_float


def _flow_array(value: FlowResult | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(value, FlowResult):
        return value.flow, value.valid.copy()
    flow = np.asarray(value, dtype=np.float32)
    if flow.ndim != 3 or flow.shape[-1] != 2:
        raise ValueError("flow must have shape (height, width, 2)")
    return flow, np.isfinite(flow).all(axis=-1)


def sample_field(
    field: np.ndarray,
    points_xy: np.ndarray,
    *,
    outside_value: float = np.nan,
) -> tuple[np.ndarray, np.ndarray]:
    """Bilinearly sample an ``H x W`` or ``H x W x C`` array at ``(x, y)``."""

    values = np.asarray(field)
    points = np.asarray(points_xy, dtype=np.float32)
    if values.ndim not in (2, 3):
        raise ValueError("field must have shape (H,W) or (H,W,C)")
    if points.ndim < 1 or points.shape[-1] != 2:
        raise ValueError("points_xy must have final dimension 2")
    original_shape = points.shape[:-1]
    flat = points.reshape(-1, 2)
    height, width = values.shape[:2]
    finite = np.isfinite(flat).all(axis=1)
    inside = (
        finite
        & (flat[:, 0] >= 0)
        & (flat[:, 0] <= width - 1)
        & (flat[:, 1] >= 0)
        & (flat[:, 1] <= height - 1)
    )
    channels = () if values.ndim == 2 else (values.shape[2],)
    output = np.full((len(flat),) + channels, outside_value, dtype=np.float32)
    if inside.any():
        p = flat[inside]
        x0 = np.floor(p[:, 0]).astype(int)
        y0 = np.floor(p[:, 1]).astype(int)
        x1 = np.minimum(x0 + 1, width - 1)
        y1 = np.minimum(y0 + 1, height - 1)
        wx = p[:, 0] - x0
        wy = p[:, 1] - y0
        if values.ndim == 3:
            wx = wx[:, None]
            wy = wy[:, None]
        top = values[y0, x0] * (1.0 - wx) + values[y0, x1] * wx
        bottom = values[y1, x0] * (1.0 - wx) + values[y1, x1] * wx
        output[inside] = top * (1.0 - wy) + bottom * wy
    return output.reshape(original_shape + channels), inside.reshape(original_shape)


def endpoint_error(
    predicted: FlowResult | np.ndarray,
    target: FlowResult | np.ndarray,
    mask: np.ndarray | None = None,
    *,
    reduction: str = "mean",
) -> float | np.ndarray:
    """Endpoint error (EPE); use only where target flow is genuinely known."""

    predicted_flow, predicted_valid = _flow_array(predicted)
    target_flow, target_valid = _flow_array(target)
    if predicted_flow.shape != target_flow.shape:
        raise ValueError("predicted and target flow shapes differ")
    valid = predicted_valid & target_valid
    if mask is not None:
        requested = np.asarray(mask, dtype=bool)
        if requested.shape != valid.shape:
            raise ValueError("mask shape differs from flow")
        valid &= requested
    error = np.linalg.norm(predicted_flow - target_flow, axis=-1)
    if reduction == "none":
        return np.where(valid, error, np.nan)
    if reduction != "mean":
        raise ValueError("reduction must be 'mean' or 'none'")
    return float(error[valid].mean()) if valid.any() else float("nan")


def warp_next_to_previous(next_frame: np.ndarray, forward_flow: np.ndarray) -> np.ndarray:
    """Reconstruct the previous frame by sampling next at ``p + flow(p)``."""

    flow, _ = _flow_array(forward_flow)
    image = np.asarray(next_frame)
    if image.shape[:2] != flow.shape[:2]:
        raise ValueError("image and flow sizes differ")
    y, x = np.mgrid[: flow.shape[0], : flow.shape[1]].astype(np.float32)
    points = np.stack((x + flow[..., 0], y + flow[..., 1]), axis=-1)
    warped, _ = sample_field(image, points, outside_value=np.nan)
    return warped


def photometric_warp_error(
    previous_frame: np.ndarray,
    next_frame: np.ndarray,
    forward_flow: FlowResult | np.ndarray,
    mask: np.ndarray | None = None,
) -> float:
    """Mean absolute brightness error after forward-flow warping."""

    flow, valid = _flow_array(forward_flow)
    previous = as_gray_float(previous_frame)
    following = as_gray_float(next_frame)
    warped = warp_next_to_previous(following, flow)
    valid &= np.isfinite(warped)
    if mask is not None:
        requested = np.asarray(mask, dtype=bool)
        if requested.shape != valid.shape:
            raise ValueError("mask shape differs from flow")
        valid &= requested
    return float(np.abs(previous - warped)[valid].mean()) if valid.any() else float("nan")


@dataclass(frozen=True)
class ConsistencyResult:
    error: np.ndarray
    valid: np.ndarray
    consistent: np.ndarray
    mean_error: float
    fraction_consistent: float


def forward_backward_consistency(
    forward: FlowResult | np.ndarray,
    backward: FlowResult | np.ndarray,
    *,
    threshold: float = 1.5,
) -> ConsistencyResult:
    """Check ``F(p) + B(p + F(p)) == 0`` with bilinear sampling."""

    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    forward_flow, forward_valid = _flow_array(forward)
    backward_flow, backward_valid = _flow_array(backward)
    if forward_flow.shape != backward_flow.shape:
        raise ValueError("forward and backward flow shapes differ")
    height, width = forward_flow.shape[:2]
    y, x = np.mgrid[:height, :width].astype(np.float32)
    destination = np.stack(
        (x + forward_flow[..., 0], y + forward_flow[..., 1]), axis=-1
    )
    sampled_backward, inside = sample_field(backward_flow, destination)
    sampled_valid, _ = sample_field(
        backward_valid.astype(np.float32), destination, outside_value=0.0
    )
    valid = forward_valid & inside & (sampled_valid >= 0.999)
    error = np.linalg.norm(forward_flow + sampled_backward, axis=-1)
    error = np.where(valid, error, np.nan).astype(np.float32)
    consistent = valid & (error <= threshold)
    mean_error = float(np.nanmean(error)) if valid.any() else float("nan")
    fraction = float(consistent.sum() / valid.sum()) if valid.any() else float("nan")
    return ConsistencyResult(error, valid, consistent, mean_error, fraction)


def temporal_flow_change(
    first: FlowResult | np.ndarray,
    following: FlowResult | np.ndarray,
    *,
    advect: bool = True,
) -> dict[str, float | np.ndarray]:
    """Measure frame-to-frame change of two consecutive flow fields.

    With ``advect=True``, the second field is sampled at ``p + first(p)`` so
    approximately corresponding locations are compared.  This is an apparent
    acceleration/stability descriptor, not an accuracy metric: true motion may
    legitimately change between frames.
    """

    first_flow, first_valid = _flow_array(first)
    next_flow, next_valid = _flow_array(following)
    if first_flow.shape != next_flow.shape:
        raise ValueError("consecutive flow shapes differ")
    if advect:
        height, width = first_flow.shape[:2]
        y, x = np.mgrid[:height, :width].astype(np.float32)
        points = np.stack(
            (x + first_flow[..., 0], y + first_flow[..., 1]), axis=-1
        )
        compared, inside = sample_field(next_flow, points)
        sampled_valid, _ = sample_field(
            next_valid.astype(np.float32), points, outside_value=0.0
        )
        valid = first_valid & inside & (sampled_valid >= 0.999)
    else:
        compared = next_flow
        valid = first_valid & next_valid
    change = np.linalg.norm(compared - first_flow, axis=-1)
    change = np.where(valid, change, np.nan).astype(np.float32)
    return {
        "change": change,
        "mean_change": float(np.nanmean(change)) if valid.any() else float("nan"),
        "p95_change": float(np.nanpercentile(change, 95)) if valid.any() else float("nan"),
        "valid_fraction": float(valid.mean()),
    }


def evaluate_flow_pair(
    previous_frame: np.ndarray,
    next_frame: np.ndarray,
    forward: FlowResult,
    backward: FlowResult | None = None,
    target: FlowResult | np.ndarray | None = None,
) -> dict[str, Any]:
    """Collect applicable real-data and synthetic-data metrics."""

    metrics: dict[str, Any] = {
        "photometric_mae": photometric_warp_error(previous_frame, next_frame, forward),
        "valid_fraction": float(forward.valid.mean()),
    }
    if backward is not None:
        consistency = forward_backward_consistency(forward, backward)
        metrics.update(
            {
                "forward_backward_mae": consistency.mean_error,
                "consistent_fraction": consistency.fraction_consistent,
            }
        )
    if target is not None:
        metrics["epe"] = endpoint_error(forward, target)
    return metrics
