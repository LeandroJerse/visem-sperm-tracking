"""Causal, fixed-parameter extrapolation using sampled apparent image flow.

This module consumes numeric histories already authenticated by the caller.
It does not read images, choose a cohort, sample fields, or authenticate hashes.
In particular, subtracting apparent flow defines an algebraic residual, not an
estimate of intrinsic cell velocity or physical fluid velocity.
"""
from __future__ import annotations

import numpy as np


def _array(value: np.ndarray, shape: tuple[int, ...], name: str, kinds: str) -> np.ndarray:
    if (not isinstance(value, np.ndarray) or np.ma.isMaskedArray(value)
            or value.shape != shape or value.dtype.kind not in kinds):
        raise ValueError(f"{name} must be an unmasked array of shape {shape} and dtype kind {kinds}")
    return value


def _float64(value: np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    value = _array(value, shape, name, "iuf")
    try:
        with np.errstate(over="raise", invalid="raise"):
            return np.asarray(value, dtype=np.float64)
    except (ValueError, OverflowError, FloatingPointError) as exc:
        raise ValueError(f"{name} cannot be represented as float64") from exc


def _frames(value: np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    value = _array(value, shape, name, "iu")
    if np.any(value < 0) or np.any(value > np.iinfo(np.int64).max):
        raise ValueError(f"{name} must contain nonnegative frame indices fitting int64")
    return np.asarray(value, dtype=np.int64)


class CausalFlowConstantVelocityPredictor:
    """Extrapolate median residual displacement plus the last observed flow.

    For each origin ``t`` and each future step ``h=1..10``, return::

        p[t] + h * (median_s(p[s+1] - p[s] - f[s]) + f[t-1])

    The median acts component by component over ``s=t-5..t-1``; ``f[s]``
    means the forward displacement sampled at ``p[s]`` in pair ``s -> s+1``.
    Keeping the last observed sample constant is a prediction assumption.
    There is no argument for future flow, future positions, or oracle modes.

    Histories have 20 consecutive positions and carry all 19 observed pairs.
    Only the last five flow samples enter the formula and must be valid.
    Earlier invalid samples must be represented by two NaNs, with an explicit
    false validity flag. They remain available for coverage reporting, but are
    never imputed or used by the arithmetic. The caller must select and report
    the common eligible cohort before calling this predictor for either arm
    of an ablation. An ineligible row rejects the entire batch.

    This deliberately does not inherit the historical float32 single-track
    interface. Both the intermediate arithmetic and output use float64; input
    precision already lost before this call cannot be recovered.
    """

    name = "cv_median5_flow_last"
    uses_flow = True

    def predict_batch(
        self,
        histories: np.ndarray,
        *,
        flow_history: np.ndarray,
        flow_validity: np.ndarray,
        history_frames: np.ndarray,
        flow_pairs: np.ndarray,
        origin_frames: np.ndarray,
    ) -> np.ndarray:
        """Return ``[N,10,2]`` without clipping positions to image boundaries.

        Required input shapes are ``histories[N,20,2]``,
        ``flow_history[N,19,2]``, boolean ``flow_validity[N,19]``, integer
        ``history_frames[N,20]``, integer ``flow_pairs[N,19,2]`` (from, to),
        and integer ``origin_frames[N]``. The final observed frame equals the
        origin, and every pair must exactly match its two historical frames.
        Hashes, video/ID membership, and source-coordinate sampling must have
        been checked upstream; numeric arrays alone cannot certify them.
        """
        if (not isinstance(histories, np.ndarray) or histories.ndim != 3
                or histories.shape[0] == 0):
            raise ValueError("histories must have shape (N>0, 20, 2)")
        count = histories.shape[0]
        positions = _float64(histories, (count, 20, 2), "histories")
        if not np.isfinite(positions).all():
            raise ValueError("histories must contain only finite positions")
        flows = _float64(flow_history, (count, 19, 2), "flow_history")
        valid = _array(flow_validity, (count, 19), "flow_validity", "b")
        if not np.isfinite(flows[valid]).all():
            raise ValueError("valid flow samples must contain only finite values")
        if not np.isnan(flows[~valid]).all():
            raise ValueError("invalid flow samples must contain two NaNs, never imputed values")
        if not valid[:, -5:].all():
            raise ValueError("select a common eligible cohort before prediction: last five flows required")

        frames = _frames(history_frames, (count, 20), "history_frames")
        pairs = _frames(flow_pairs, (count, 19, 2), "flow_pairs")
        origins = _frames(origin_frames, (count,), "origin_frames")
        if np.any(origins < 19):
            raise ValueError("origin_frames must permit 20 nonnegative historical frame indices")
        expected = origins[:, None] - 19 + np.arange(20, dtype=np.int64)
        if not np.array_equal(frames, expected):
            raise ValueError("history_frames must be consecutive and end at the origin")
        if (not np.array_equal(pairs[:, :, 0], frames[:, :-1])
                or not np.array_equal(pairs[:, :, 1], frames[:, 1:])):
            raise ValueError("flow_pairs must match consecutive history frames available by the origin")

        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                differences = np.diff(positions[:, -6:, :], axis=1)
                residual = np.median(differences - flows[:, -5:, :], axis=1)
                step = residual + flows[:, -1, :]
                horizons = np.arange(1, 11, dtype=np.float64)
                predicted = positions[:, -1:, :] + horizons[None, :, None] * step[:, None, :]
        except (OverflowError, FloatingPointError) as exc:
            raise ValueError("causal flow prediction arithmetic overflowed") from exc
        if not np.isfinite(predicted).all():
            raise ValueError("causal flow prediction produced non-finite positions")
        return predicted
