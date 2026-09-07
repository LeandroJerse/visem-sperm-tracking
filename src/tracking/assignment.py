"""Association primitives with an optional SciPy fast path.

The local Hungarian implementation is O(n^3) and keeps the classical trackers
usable in a minimal NumPy-only environment.  SciPy is used automatically when
available.
"""
from __future__ import annotations

import numpy as np


def linear_sum_assignment(cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Solve rectangular linear assignment, preferring SciPy when installed."""
    cost = np.asarray(cost_matrix, dtype=float)
    if cost.ndim != 2:
        raise ValueError("cost_matrix must be two-dimensional")
    if 0 in cost.shape:
        return np.empty(0, dtype=int), np.empty(0, dtype=int)

    try:  # pragma: no cover - availability depends on the environment
        from scipy.optimize import linear_sum_assignment as scipy_lsa

        return scipy_lsa(cost)
    except (ImportError, ValueError):
        return _hungarian_numpy(cost)


def _hungarian_numpy(cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Shortest augmenting-path Hungarian solver for a rectangular matrix."""
    original = np.asarray(cost_matrix, dtype=float)
    transposed = original.shape[0] > original.shape[1]
    cost = original.T.copy() if transposed else original.copy()
    n_rows, n_cols = cost.shape  # algorithm below requires rows <= columns

    finite = cost[np.isfinite(cost)]
    scale = max(1.0, float(np.max(np.abs(finite))) if finite.size else 1.0)
    forbidden = scale * (n_rows + n_cols + 1) * 1_000_000.0
    cost[~np.isfinite(cost)] = forbidden

    u = np.zeros(n_rows + 1, dtype=float)
    v = np.zeros(n_cols + 1, dtype=float)
    p = np.zeros(n_cols + 1, dtype=int)
    way = np.zeros(n_cols + 1, dtype=int)

    for row in range(1, n_rows + 1):
        p[0] = row
        min_values = np.full(n_cols + 1, np.inf, dtype=float)
        used = np.zeros(n_cols + 1, dtype=bool)
        col0 = 0
        while True:
            used[col0] = True
            row0 = p[col0]
            delta = np.inf
            col1 = 0
            for col in range(1, n_cols + 1):
                if used[col]:
                    continue
                current = cost[row0 - 1, col - 1] - u[row0] - v[col]
                if current < min_values[col]:
                    min_values[col] = current
                    way[col] = col0
                if min_values[col] < delta:
                    delta = min_values[col]
                    col1 = col
            for col in range(n_cols + 1):
                if used[col]:
                    u[p[col]] += delta
                    v[col] -= delta
                else:
                    min_values[col] -= delta
            col0 = col1
            if p[col0] == 0:
                break
        while True:
            col1 = way[col0]
            p[col0] = p[col1]
            col0 = col1
            if col0 == 0:
                break

    row_ind: list[int] = []
    col_ind: list[int] = []
    for col in range(1, n_cols + 1):
        if p[col] != 0:
            row_ind.append(p[col] - 1)
            col_ind.append(col - 1)
    rows = np.asarray(row_ind, dtype=int)
    cols = np.asarray(col_ind, dtype=int)
    order = np.argsort(rows)
    rows, cols = rows[order], cols[order]
    if transposed:
        rows, cols = cols, rows
        order = np.argsort(rows)
        rows, cols = rows[order], cols[order]
    return rows, cols


def match_cost_matrix(
    cost_matrix: np.ndarray,
    *,
    max_cost: float | None = None,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Assign finite pairs, then return matches and unmatched row/column IDs."""
    cost = np.asarray(cost_matrix, dtype=float)
    if cost.ndim != 2:
        raise ValueError("cost_matrix must be two-dimensional")
    n_rows, n_cols = cost.shape
    if n_rows == 0 or n_cols == 0:
        return [], list(range(n_rows)), list(range(n_cols))

    rows, cols = linear_sum_assignment(cost)
    matches: list[tuple[int, int]] = []
    matched_rows: set[int] = set()
    matched_cols: set[int] = set()
    for row, col in zip(rows.tolist(), cols.tolist()):
        value = cost[row, col]
        if not np.isfinite(value) or (max_cost is not None and value > max_cost):
            continue
        matches.append((row, col))
        matched_rows.add(row)
        matched_cols.add(col)
    unmatched_rows = [idx for idx in range(n_rows) if idx not in matched_rows]
    unmatched_cols = [idx for idx in range(n_cols) if idx not in matched_cols]
    return matches, unmatched_rows, unmatched_cols


def pairwise_center_distance(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Euclidean distances between arrays of center-format boxes."""
    a = np.asarray(boxes_a, dtype=float).reshape(-1, 4)
    b = np.asarray(boxes_b, dtype=float).reshape(-1, 4)
    if len(a) == 0 or len(b) == 0:
        return np.empty((len(a), len(b)), dtype=float)
    diff = a[:, None, :2] - b[None, :, :2]
    return np.linalg.norm(diff, axis=2)


def pairwise_iou(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """IoU matrix for arrays of center-format ``(cx, cy, w, h)`` boxes."""
    a = np.asarray(boxes_a, dtype=float).reshape(-1, 4)
    b = np.asarray(boxes_b, dtype=float).reshape(-1, 4)
    if len(a) == 0 or len(b) == 0:
        return np.empty((len(a), len(b)), dtype=float)

    a_xyxy = np.column_stack(
        (a[:, 0] - a[:, 2] / 2, a[:, 1] - a[:, 3] / 2,
         a[:, 0] + a[:, 2] / 2, a[:, 1] + a[:, 3] / 2)
    )
    b_xyxy = np.column_stack(
        (b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2,
         b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2)
    )
    top_left = np.maximum(a_xyxy[:, None, :2], b_xyxy[None, :, :2])
    bottom_right = np.minimum(a_xyxy[:, None, 2:], b_xyxy[None, :, 2:])
    intersection_size = np.maximum(0.0, bottom_right - top_left)
    intersection = intersection_size[..., 0] * intersection_size[..., 1]
    area_a = np.maximum(0.0, a[:, 2]) * np.maximum(0.0, a[:, 3])
    area_b = np.maximum(0.0, b[:, 2]) * np.maximum(0.0, b[:, 3])
    union = area_a[:, None] + area_b[None, :] - intersection
    return np.divide(
        intersection,
        union,
        out=np.zeros_like(intersection),
        where=union > 0,
    )
