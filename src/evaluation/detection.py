"""Official centre-distance evaluation for sperm-cell detection.

Predictions and manual annotations are associated one-to-one with the
Hungarian algorithm.  A pair is valid only when its centre distance is at most
``center_gate_px`` (15 px by default).  The main comparison collapses all VISEM
classes into one object class; passing ``class_policy="class_aware"`` additionally
requires equal class ids.

Missing labels are *not* negative examples.  Call :func:`evaluate_frame` with
``ground_truth=None`` (or ``annotated=False``) and that frame is represented as
unannotated, then excluded from aggregate quality metrics.
"""
from __future__ import annotations

import csv
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_CENTER_GATE_PX = 15.0
CLASS_POLICIES = {"binary", "class_aware"}


@dataclass(frozen=True)
class DetectionMatch:
    """One valid prediction/ground-truth association."""

    prediction_index: int
    ground_truth_index: int
    distance_px: float


@dataclass(frozen=True)
class MatchingResult:
    """Result of one-to-one matching for a single annotated frame."""

    matches: tuple[DetectionMatch, ...]
    unmatched_predictions: tuple[int, ...]
    unmatched_ground_truth: tuple[int, ...]

    @property
    def tp(self) -> int:
        return len(self.matches)

    @property
    def fp(self) -> int:
        return len(self.unmatched_predictions)

    @property
    def fn(self) -> int:
        return len(self.unmatched_ground_truth)


def _normalise_policy(class_policy: str) -> str:
    policy = class_policy.strip().lower().replace("-", "_")
    if policy not in CLASS_POLICIES:
        raise ValueError(
            f"class_policy must be one of {sorted(CLASS_POLICIES)}, got {class_policy!r}"
        )
    return policy


def _center_and_class(item: Any) -> tuple[float, float, int]:
    """Read ``(cx, cy, class_id)`` from a Detection, mapping or sequence."""
    if hasattr(item, "cx") and hasattr(item, "cy"):
        return float(item.cx), float(item.cy), int(getattr(item, "class_id", 0))
    if isinstance(item, Mapping):
        return float(item["cx"]), float(item["cy"]), int(item.get("class_id", 0))
    if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
        if len(item) < 2:
            raise ValueError("A centre sequence must contain at least (cx, cy)")
        return float(item[0]), float(item[1]), int(item[2]) if len(item) > 2 else 0
    raise TypeError(f"Unsupported detection representation: {type(item).__name__}")


def _hungarian_min_cost(cost: list[list[float]]) -> list[tuple[int, int]]:
    """Return a minimum-cost rectangular assignment in O(n^3).

    This is the shortest-path/potential form of the Hungarian algorithm.  It
    solves all rows when rows <= columns and transposes otherwise.  Keeping it
    here avoids making the evaluation policy depend on an optional SciPy
    installation.
    """
    if not cost or not cost[0]:
        return []
    n_rows = len(cost)
    n_cols = len(cost[0])
    if any(len(row) != n_cols for row in cost):
        raise ValueError("Cost matrix must be rectangular")

    transposed = n_rows > n_cols
    matrix = (
        [[cost[i][j] for i in range(n_rows)] for j in range(n_cols)]
        if transposed
        else cost
    )
    n = len(matrix)
    m = len(matrix[0])

    # 1-indexed implementation; p[j] is the row assigned to column j.
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        minv = [math.inf] * (m + 1)
        used = [False] * (m + 1)
        j0 = 0
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                current = matrix[i0 - 1][j - 1] - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(0, m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    pairs: list[tuple[int, int]] = []
    for column in range(1, m + 1):
        row = p[column]
        if row == 0:
            continue
        pair = (column - 1, row - 1) if transposed else (row - 1, column - 1)
        pairs.append(pair)
    return sorted(pairs)


def match_detections(
    predictions: Sequence[Any],
    ground_truth: Sequence[Any],
    center_gate_px: float = DEFAULT_CENTER_GATE_PX,
    class_policy: str = "binary",
) -> MatchingResult:
    """Associate detections one-to-one using gated centre distance.

    Invalid pairs receive a penalty large enough that the assignment first
    maximises the number of valid pairs and only then minimises their total
    distance.  Thus a close invalid-class pair cannot displace a valid pair in
    class-aware mode.
    """
    if center_gate_px < 0:
        raise ValueError("center_gate_px must be non-negative")
    policy = _normalise_policy(class_policy)
    pred_values = [_center_and_class(item) for item in predictions]
    gt_values = [_center_and_class(item) for item in ground_truth]
    if not pred_values or not gt_values:
        return MatchingResult(
            matches=(),
            unmatched_predictions=tuple(range(len(pred_values))),
            unmatched_ground_truth=tuple(range(len(gt_values))),
        )

    distances: list[list[float]] = []
    valid: list[list[bool]] = []
    for px, py, pred_class in pred_values:
        distance_row: list[float] = []
        valid_row: list[bool] = []
        for gx, gy, gt_class in gt_values:
            distance = math.hypot(px - gx, py - gy)
            same_class = policy == "binary" or pred_class == gt_class
            distance_row.append(distance)
            valid_row.append(same_class and distance <= center_gate_px)
        distances.append(distance_row)
        valid.append(valid_row)

    assignment_size = min(len(pred_values), len(gt_values))
    invalid_penalty = (assignment_size + 1) * (center_gate_px + 1.0)
    costs = [
        [distances[i][j] if valid[i][j] else invalid_penalty for j in range(len(gt_values))]
        for i in range(len(pred_values))
    ]
    assigned = _hungarian_min_cost(costs)
    matches = tuple(
        DetectionMatch(i, j, distances[i][j])
        for i, j in assigned
        if valid[i][j]
    )
    matched_predictions = {match.prediction_index for match in matches}
    matched_gt = {match.ground_truth_index for match in matches}
    return MatchingResult(
        matches=matches,
        unmatched_predictions=tuple(
            i for i in range(len(pred_values)) if i not in matched_predictions
        ),
        unmatched_ground_truth=tuple(i for i in range(len(gt_values)) if i not in matched_gt),
    )


# Descriptive alias used in methodology code and notebooks.
hungarian_match = match_detections


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    # Empty/empty is a correct frame.  If just one side is empty, F1 remains 0.
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _gate_suffix(gate: float) -> str:
    """Stable, column-safe label for a sensitivity gate."""
    return f"{float(gate):g}".replace(".", "p")


def evaluate_frame(
    predictions: Sequence[Any],
    ground_truth: Sequence[Any] | None,
    *,
    video_id: str = "",
    frame: int = 0,
    annotated: bool | None = None,
    center_gate_px: float = DEFAULT_CENTER_GATE_PX,
    class_policy: str = "binary",
    detection_ms: float | None = None,
    sensitivity_gates_px: Sequence[float] = (),
) -> dict[str, Any]:
    """Evaluate one frame and return a flat, CSV/JSON-friendly record."""
    policy = _normalise_policy(class_policy)
    is_annotated = ground_truth is not None if annotated is None else bool(annotated)
    base: dict[str, Any] = {
        "video_id": str(video_id),
        "frame": int(frame),
        "annotated": is_annotated,
        "class_policy": policy,
        "center_gate_px": float(center_gate_px),
        "n_predictions": len(predictions),
        "n_ground_truth": None,
        "tp": None,
        "fp": None,
        "fn": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "center_error_mean_px": None,
        "center_error_median_px": None,
        "center_error_max_px": None,
        "center_error_sum_px": None,
        "count_error": None,
        "count_abs_error": None,
        "count_bias": None,
        "count_mae": None,
        "detection_ms": detection_ms,
    }
    sensitivity_gates = sorted(
        {float(gate) for gate in sensitivity_gates_px if float(gate) != center_gate_px}
    )
    if any(gate < 0 for gate in sensitivity_gates):
        raise ValueError("sensitivity gates must be non-negative")
    for gate in sensitivity_gates:
        suffix = _gate_suffix(gate)
        for metric in ("tp", "fp", "fn", "precision", "recall", "f1"):
            base[f"{metric}_at_{suffix}px"] = None
    if not is_annotated:
        return base

    gt = list(ground_truth or [])
    result = match_detections(
        predictions, gt, center_gate_px=center_gate_px, class_policy=policy
    )
    distances = [match.distance_px for match in result.matches]
    precision, recall, f1 = _prf(result.tp, result.fp, result.fn)
    count_error = len(predictions) - len(gt)
    base.update(
        {
            "n_ground_truth": len(gt),
            "tp": result.tp,
            "fp": result.fp,
            "fn": result.fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "center_error_mean_px": statistics.fmean(distances) if distances else None,
            "center_error_median_px": statistics.median(distances) if distances else None,
            "center_error_max_px": max(distances) if distances else None,
            "center_error_sum_px": sum(distances),
            "count_error": count_error,
            "count_abs_error": abs(count_error),
            "count_bias": count_error,
            "count_mae": abs(count_error),
        }
    )
    for gate in sensitivity_gates:
        alternative = match_detections(
            predictions, gt, center_gate_px=gate, class_policy=policy
        )
        alt_precision, alt_recall, alt_f1 = _prf(
            alternative.tp, alternative.fp, alternative.fn
        )
        suffix = _gate_suffix(gate)
        base.update(
            {
                f"tp_at_{suffix}px": alternative.tp,
                f"fp_at_{suffix}px": alternative.fp,
                f"fn_at_{suffix}px": alternative.fn,
                f"precision_at_{suffix}px": alt_precision,
                f"recall_at_{suffix}px": alt_recall,
                f"f1_at_{suffix}px": alt_f1,
            }
        )
    return base


def aggregate_frame_metrics(
    frame_metrics: Iterable[Mapping[str, Any]], *, video_id: str | None = None
) -> dict[str, Any]:
    """Micro-aggregate annotated frames and report count error per frame."""
    records = list(frame_metrics)
    if video_id is not None:
        records = [row for row in records if str(row.get("video_id", "")) == str(video_id)]
    annotated = [row for row in records if bool(row.get("annotated"))]
    tp = sum(int(row.get("tp") or 0) for row in annotated)
    fp = sum(int(row.get("fp") or 0) for row in annotated)
    fn = sum(int(row.get("fn") or 0) for row in annotated)
    if annotated:
        precision, recall, f1 = _prf(tp, fp, fn)
    else:
        # No manual evidence means no accuracy claim, even if predictions ran.
        precision = recall = f1 = None
    matched = sum(int(row.get("tp") or 0) for row in annotated)
    center_sum = sum(float(row.get("center_error_sum_px") or 0.0) for row in annotated)
    count_errors = [float(row.get("count_error") or 0.0) for row in annotated]
    count_abs_errors = [float(row.get("count_abs_error") or 0.0) for row in annotated]
    detection_times = [
        float(row["detection_ms"])
        for row in records
        if row.get("detection_ms") is not None
    ]
    resolved_video_id = video_id
    if resolved_video_id is None:
        ids = {str(row.get("video_id", "")) for row in records}
        resolved_video_id = next(iter(ids)) if len(ids) == 1 else None
    result = {
        "video_id": resolved_video_id,
        "frames_total": len(records),
        "frames_annotated": len(annotated),
        "frames_unannotated": len(records) - len(annotated),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "center_error_mean_px": center_sum / matched if matched else None,
        "count_mae": statistics.fmean(count_abs_errors) if count_abs_errors else None,
        "count_bias": statistics.fmean(count_errors) if count_errors else None,
        "detection_ms_mean": statistics.fmean(detection_times) if detection_times else None,
        "detection_ms_median": statistics.median(detection_times) if detection_times else None,
        "detection_ms_max": max(detection_times) if detection_times else None,
    }
    gate_pattern = re.compile(r"^tp_at_(?P<suffix>.+px)$")
    gate_suffixes = sorted(
        {
            match.group("suffix")
            for row in annotated
            for key in row
            if (match := gate_pattern.match(str(key))) is not None
        }
    )
    for suffix in gate_suffixes:
        gate_tp = sum(int(row.get(f"tp_at_{suffix}") or 0) for row in annotated)
        gate_fp = sum(int(row.get(f"fp_at_{suffix}") or 0) for row in annotated)
        gate_fn = sum(int(row.get(f"fn_at_{suffix}") or 0) for row in annotated)
        gate_precision, gate_recall, gate_f1 = _prf(gate_tp, gate_fp, gate_fn)
        result.update(
            {
                f"tp_at_{suffix}": gate_tp,
                f"fp_at_{suffix}": gate_fp,
                f"fn_at_{suffix}": gate_fn,
                f"precision_at_{suffix}": gate_precision,
                f"recall_at_{suffix}": gate_recall,
                f"f1_at_{suffix}": gate_f1,
            }
        )
    return result


def aggregate_by_video(frame_metrics: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return one aggregate record per video id."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in frame_metrics:
        groups.setdefault(str(row.get("video_id", "")), []).append(row)
    return {
        video_id: aggregate_frame_metrics(rows, video_id=video_id)
        for video_id, rows in sorted(groups.items())
    }


def write_frame_metrics_csv(
    frame_metrics: Iterable[Mapping[str, Any]], path: str | Path
) -> Path:
    """Write flat per-frame records, including unannotated frames."""
    records = [dict(row) for row in frame_metrics]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    default_fields = list(evaluate_frame([], None).keys())
    extra_fields = sorted({key for row in records for key in row} - set(default_fields))
    fields = default_fields + extra_fields
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    return path


class DetectionEvaluator:
    """Small accumulator useful to runners that process frames incrementally."""

    def __init__(
        self,
        center_gate_px: float = DEFAULT_CENTER_GATE_PX,
        class_policy: str = "binary",
        sensitivity_gates_px: Sequence[float] = (),
    ) -> None:
        if center_gate_px < 0:
            raise ValueError("center_gate_px must be non-negative")
        self.center_gate_px = float(center_gate_px)
        self.class_policy = _normalise_policy(class_policy)
        self.sensitivity_gates_px = tuple(float(gate) for gate in sensitivity_gates_px)
        if any(gate < 0 for gate in self.sensitivity_gates_px):
            raise ValueError("sensitivity gates must be non-negative")
        self.frames: list[dict[str, Any]] = []

    def add_frame(
        self,
        predictions: Sequence[Any],
        ground_truth: Sequence[Any] | None,
        *,
        video_id: str = "",
        frame: int = 0,
        annotated: bool | None = None,
        detection_ms: float | None = None,
    ) -> dict[str, Any]:
        record = evaluate_frame(
            predictions,
            ground_truth,
            video_id=video_id,
            frame=frame,
            annotated=annotated,
            center_gate_px=self.center_gate_px,
            class_policy=self.class_policy,
            detection_ms=detection_ms,
            sensitivity_gates_px=self.sensitivity_gates_px,
        )
        self.frames.append(record)
        return record

    def summary(self, video_id: str | None = None) -> dict[str, Any]:
        return aggregate_frame_metrics(self.frames, video_id=video_id)

    def by_video(self) -> dict[str, dict[str, Any]]:
        return aggregate_by_video(self.frames)
