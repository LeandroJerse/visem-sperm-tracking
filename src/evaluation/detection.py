"""Official centre-distance evaluation for sperm-cell detection.

Predictions and manual annotations are associated one-to-one with the
Hungarian algorithm.  A pair is valid only when its centre distance is at most
``center_gate_px`` (10 px by default, with sensitivity at 15 and 20 px).
The default target is individual annotations (classes 0 and 2). Unmatched
predictions inside GT cluster boxes may be ignored only when they are outside
every individual matching disk. Predictions are never filtered by their class.
Explicit ``binary`` and ``class_aware`` policies preserve historical evaluation.

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

DEFAULT_CENTER_GATE_PX = 10.0
DEFAULT_SENSITIVITY_GATES_PX = (15.0, 20.0)
DEFAULT_CLASS_POLICY = "individuals_ignore_clusters"
DEFAULT_EVALUATION_PROTOCOL_ID = "center_distance_v3_individuals_ignore_clusters_10px"
CLASS_POLICIES = {"binary", "class_aware", DEFAULT_CLASS_POLICY}


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
    ignored_predictions: tuple[int, ...] = ()
    ignored_ground_truth: tuple[int, ...] = ()

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
        raw = item.cx, item.cy, getattr(item, "class_id", 0)
    elif isinstance(item, Mapping):
        raw = item["cx"], item["cy"], item.get("class_id", 0)
    elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
        if len(item) < 2:
            raise ValueError("A centre sequence must contain at least (cx, cy)")
        raw = item[0], item[1], item[2] if len(item) > 2 else 0
    else:
        raise TypeError(f"Unsupported detection representation: {type(item).__name__}")
    try:
        cx, cy, class_value = (float(value) for value in raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Detection centres and class ids must be numeric") from exc
    if not math.isfinite(cx) or not math.isfinite(cy):
        raise ValueError("Detection centre coordinates must be finite")
    if class_value not in (0, 1, 2):
        raise ValueError("Unknown class id; expected VISEM class 0, 1 or 2")
    return cx, cy, int(class_value)


def _validate_gate(gate: float) -> float:
    gate = float(gate)
    if not math.isfinite(gate) or gate < 0:
        raise ValueError("center/sensitivity gates must be finite and non-negative")
    return gate


def _cluster_bounds(item: Any) -> tuple[float, float, float, float]:
    """Read a GT rectangle in pixels; no expansion or clipping is applied."""
    cx, cy, _ = _center_and_class(item)
    try:
        if hasattr(item, "w") and hasattr(item, "h"):
            width, height = float(item.w), float(item.h)
        elif isinstance(item, Mapping):
            width, height = float(item["w"]), float(item["h"])
        else:
            # Sequence convention extends (cx, cy, class_id) with width, height.
            width, height = float(item[3]), float(item[4])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("GT cluster boxes require finite positive w and h") from exc
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("GT cluster boxes require finite positive w and h")
    bounds = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError("GT cluster box bounds must be finite")
    return bounds


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
    class_policy: str = DEFAULT_CLASS_POLICY,
) -> MatchingResult:
    """Associate detections one-to-one using gated centre distance.

    Invalid pairs receive a penalty large enough that the assignment first
    maximises the number of valid pairs and only then minimises their total
    distance.  Thus a close invalid-class pair cannot displace a valid pair in
    class-aware mode.
    """
    center_gate_px = _validate_gate(center_gate_px)
    policy = _normalise_policy(class_policy)
    pred_values = [_center_and_class(item) for item in predictions]
    all_gt_values = [_center_and_class(item) for item in ground_truth]
    individual_policy = policy == DEFAULT_CLASS_POLICY
    cluster_indices = tuple(i for i, (_, _, cls) in enumerate(all_gt_values) if cls == 1)
    boxes = [_cluster_bounds(ground_truth[i]) for i in cluster_indices] if individual_policy else []
    gt_indices = [i for i, (_, _, cls) in enumerate(all_gt_values)
                  if not individual_policy or cls in (0, 2)]
    gt_values = [all_gt_values[i] for i in gt_indices]

    distances: list[list[float]] = []
    valid: list[list[bool]] = []
    for px, py, pred_class in pred_values:
        distance_row: list[float] = []
        valid_row: list[bool] = []
        for gx, gy, gt_class in gt_values:
            distance = math.hypot(px - gx, py - gy)
            same_class = policy != "class_aware" or pred_class == gt_class
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
        DetectionMatch(i, gt_indices[j], distances[i][j])
        for i, j in assigned
        if valid[i][j]
    )
    matched_predictions = {match.prediction_index for match in matches}
    matched_gt = {match.ground_truth_index for match in matches}
    unmatched = [i for i in range(len(pred_values)) if i not in matched_predictions]
    ignored: set[int] = set()
    if individual_policy:
        for i in unmatched:
            # Even an already matched individual protects its entire disk:
            # extra predictions inside it remain FP, including class-1 outputs.
            if any(distance <= center_gate_px for distance in distances[i]):
                continue
            px, py, _ = pred_values[i]
            if any(x0 <= px <= x1 and y0 <= py <= y1 for x0, y0, x1, y1 in boxes):
                ignored.add(i)
    return MatchingResult(
        matches=matches,
        unmatched_predictions=tuple(i for i in unmatched if i not in ignored),
        unmatched_ground_truth=tuple(i for i in gt_indices if i not in matched_gt),
        ignored_predictions=tuple(sorted(ignored)),
        ignored_ground_truth=cluster_indices if individual_policy else (),
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


_QUALITY_FIELDS = (
    "tp", "fp", "fn", "precision", "recall", "f1", "center_error_mean_px",
    "center_error_median_px", "center_error_max_px", "center_error_sum_px",
    "count_error", "count_abs_error", "count_bias", "count_mae",
)
_PRIMARY_FIELDS = _QUALITY_FIELDS + (
    "primary_evaluable", "n_predictions_scored", "n_predictions_ignored", "n_ground_truth_scored",
)


def _quality_metrics(result: MatchingResult, *, evaluable: bool = True) -> dict[str, Any]:
    distances = [match.distance_px for match in result.matches]
    precision, recall, f1 = _prf(result.tp, result.fp, result.fn) if evaluable else (None, None, None)
    count_error = result.fp - result.fn
    return {
        "tp": result.tp, "fp": result.fp, "fn": result.fn,
        "precision": precision, "recall": recall, "f1": f1,
        "center_error_mean_px": statistics.fmean(distances) if distances else None,
        "center_error_median_px": statistics.median(distances) if distances else None,
        "center_error_max_px": max(distances) if distances else None,
        "center_error_sum_px": sum(distances), "count_error": count_error,
        "count_abs_error": abs(count_error), "count_bias": count_error,
        "count_mae": abs(count_error),
    }


def evaluate_frame(
    predictions: Sequence[Any],
    ground_truth: Sequence[Any] | None,
    *,
    video_id: str = "",
    frame: int = 0,
    annotated: bool | None = None,
    center_gate_px: float = DEFAULT_CENTER_GATE_PX,
    class_policy: str = DEFAULT_CLASS_POLICY,
    detection_ms: float | None = None,
    sensitivity_gates_px: Sequence[float] = DEFAULT_SENSITIVITY_GATES_PX,
) -> dict[str, Any]:
    """Evaluate without changing raw predictions or annotations.

    ``n_predictions``/``n_ground_truth`` remain raw aliases. Primary count
    error compares scored predictions with scored GT objects (individuals for
    the default policy), never an inferred biological cell count. Cluster-only
    frames without scored predictions have undefined primary PRF, but a zero
    evaluated-count error; count MAE/bias use every annotated frame.
    """
    policy = _normalise_policy(class_policy)
    center_gate_px = _validate_gate(center_gate_px)
    for item in predictions:
        _center_and_class(item)
    is_annotated = ground_truth is not None if annotated is None else bool(annotated)
    if is_annotated and ground_truth is None:
        raise ValueError("annotated=True requires explicit ground truth; use [] for a true empty frame")
    base: dict[str, Any] = {
        "video_id": str(video_id),
        "frame": int(frame),
        "annotated": is_annotated,
        "class_policy": policy,
        "center_gate_px": float(center_gate_px),
        "n_predictions": len(predictions),
        "n_predictions_raw": len(predictions),
        "n_ground_truth": None,
        "n_ground_truth_raw": None,
        "n_gt_individuals": None,
        "n_gt_clusters": None,
        "has_gt_clusters": None,
        "count_error_raw": None,
        "count_abs_error_raw": None,
        "detection_ms": detection_ms,
    }
    sensitivity_gates = sorted({_validate_gate(gate) for gate in sensitivity_gates_px} - {center_gate_px})
    gates = [center_gate_px, *sensitivity_gates]
    for i, gate in enumerate(gates):
        suffix = "" if i == 0 else f"_at_{_gate_suffix(gate)}px"
        base.update({f"{field}{suffix}": None for field in _PRIMARY_FIELDS})
        base[f"primary_evaluable{suffix}"] = False
        base.update({f"secondary_all_objects_{field}{suffix}": None for field in _QUALITY_FIELDS})
    if not is_annotated:
        return base

    gt = list(ground_truth or [])
    classes = [_center_and_class(item)[2] for item in gt]
    n_clusters = classes.count(1)
    n_individuals = len(gt) - n_clusters
    raw_error = len(predictions) - len(gt)
    base.update(
        {
            "n_ground_truth": len(gt), "n_ground_truth_raw": len(gt),
            "n_gt_individuals": n_individuals, "n_gt_clusters": n_clusters,
            "has_gt_clusters": n_clusters > 0,
            "count_error_raw": raw_error, "count_abs_error_raw": abs(raw_error),
        }
    )
    for i, gate in enumerate(gates):
        suffix = "" if i == 0 else f"_at_{_gate_suffix(gate)}px"
        result = match_detections(predictions, gt, center_gate_px=gate, class_policy=policy)
        n_ignored = len(result.ignored_predictions)
        n_scored = len(predictions) - n_ignored
        gt_scored = len(gt) - len(result.ignored_ground_truth)
        evaluable = not (policy == DEFAULT_CLASS_POLICY and n_clusters and not gt_scored and not n_scored)
        primary = {
            **_quality_metrics(result, evaluable=evaluable), "primary_evaluable": evaluable,
            "n_predictions_scored": n_scored, "n_predictions_ignored": n_ignored,
            "n_ground_truth_scored": gt_scored,
        }
        base.update({f"{field}{suffix}": value for field, value in primary.items()})
        # Reuse the same assignment when the target/policy already is binary
        # all-objects; otherwise compute a genuinely independent comparison.
        secondary = result if policy == "binary" or (policy == DEFAULT_CLASS_POLICY and not n_clusters) else match_detections(
            predictions, gt, center_gate_px=gate, class_policy="binary"
        )
        base.update({f"secondary_all_objects_{field}{suffix}": value
                     for field, value in _quality_metrics(secondary).items()})
    return base


def aggregate_frame_metrics(
    frame_metrics: Iterable[Mapping[str, Any]], *, video_id: str | None = None
) -> dict[str, Any]:
    """Aggregate counts over all annotated frames, never mean frame F1.

    Primary count MAE/bias always use the fixed annotated-frame universe,
    including cluster-only frames with zero scored objects. Undefined primary
    PRF does not remove a frame from that count-error denominator.
    """
    records = list(frame_metrics)
    if video_id is not None:
        records = [row for row in records if str(row.get("video_id", "")) == str(video_id)]
    annotated = [row for row in records if bool(row.get("annotated"))]
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
        "frames_with_clusters": sum(bool(row.get("n_gt_clusters")) for row in annotated),
        "frames_with_individual_gt": sum(bool(row.get("n_gt_individuals")) for row in annotated),
        "frames_true_empty_gt": sum(row.get("n_ground_truth_raw", row.get("n_ground_truth")) == 0 for row in annotated),
        "frames_cluster_only_gt": sum(bool(row.get("n_gt_clusters")) and row.get("n_gt_individuals") == 0 for row in annotated),
        "n_predictions_raw": sum(int(row.get("n_predictions_raw", row.get("n_predictions", 0)) or 0) for row in records),
        "n_predictions_unannotated": sum(int(row.get("n_predictions_raw", row.get("n_predictions", 0)) or 0) for row in records if not row.get("annotated")),
        "n_ground_truth_raw": sum(int(row.get("n_ground_truth_raw", row.get("n_ground_truth", 0)) or 0) for row in annotated),
        "n_gt_individuals": sum(int(row.get("n_gt_individuals") or 0) for row in annotated),
        "n_gt_clusters": sum(int(row.get("n_gt_clusters") or 0) for row in annotated),
        "detection_ms_mean": statistics.fmean(detection_times) if detection_times else None,
        "detection_ms_median": statistics.median(detection_times) if detection_times else None,
        "detection_ms_max": max(detection_times) if detection_times else None,
    }
    raw_errors = [float(row["count_error_raw"]) for row in annotated if row.get("count_error_raw") is not None]
    result.update(count_error_raw=sum(raw_errors), count_abs_error_raw=sum(abs(value) for value in raw_errors),
                  count_bias_raw=statistics.fmean(raw_errors) if raw_errors else None,
                  count_mae_raw=statistics.fmean(abs(value) for value in raw_errors) if raw_errors else None)
    gate_pattern = re.compile(r"^tp(?P<suffix>_at_.+px)$")
    gate_suffixes = ["", *sorted({match.group("suffix") for row in records for key in row
                                if (match := gate_pattern.match(str(key))) is not None})]
    for suffix in gate_suffixes:
        scored = [row for row in annotated if row.get(f"tp{suffix}") is not None]
        effective = [row for row in scored if row.get(f"primary_evaluable{suffix}", True)]
        result[f"frames_primary_evaluable{suffix}"] = len(effective)
        result[f"frames_primary_unevaluable{suffix}"] = len(scored) - len(effective)
        result[f"frames_with_ignored_predictions{suffix}"] = sum(bool(row.get(f"n_predictions_ignored{suffix}")) for row in scored)
        for name in ("n_predictions_scored", "n_predictions_ignored", "n_ground_truth_scored"):
            result[f"{name}{suffix}"] = sum(int(row.get(f"{name}{suffix}") or 0) for row in scored)
        for prefix in ("", "secondary_all_objects_"):
            evaluated = [row for row in annotated if row.get(f"{prefix}tp{suffix}") is not None]
            tp, fp, fn = (sum(int(row.get(f"{prefix}{metric}{suffix}") or 0) for row in evaluated)
                          for metric in ("tp", "fp", "fn"))
            evidence = bool(evaluated) and (bool(prefix) or bool(effective) or tp + fp + fn > 0)
            precision, recall, f1 = _prf(tp, fp, fn) if evidence else (None, None, None)
            center_sum = sum(float(row.get(f"{prefix}center_error_sum_px{suffix}") or 0) for row in evaluated)
            errors = [float(row[f"{prefix}count_error{suffix}"]) for row in evaluated
                      if row.get(f"{prefix}count_error{suffix}") is not None]
            absolute_errors = [abs(value) for value in errors]
            quality = {
                "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
                "center_error_mean_px": center_sum / tp if tp else None,
                "center_error_sum_px": center_sum, "count_error": sum(errors),
                "count_abs_error": sum(absolute_errors),
                "count_mae": statistics.fmean(absolute_errors) if absolute_errors else None,
                "count_bias": statistics.fmean(errors) if errors else None,
                "count_evaluated_frames": len(errors),
            }
            result.update({f"{prefix}{field}{suffix}": value for field, value in quality.items()})
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
    # Sensitivity columns come from the actual records. Injecting current
    # defaults here would add a spurious 15 px column to historical 15/10/20.
    default_fields = list(evaluate_frame([], None, sensitivity_gates_px=()).keys())
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
        class_policy: str = DEFAULT_CLASS_POLICY,
        sensitivity_gates_px: Sequence[float] = DEFAULT_SENSITIVITY_GATES_PX,
    ) -> None:
        self.center_gate_px = _validate_gate(center_gate_px)
        self.class_policy = _normalise_policy(class_policy)
        self.sensitivity_gates_px = tuple(_validate_gate(gate) for gate in sensitivity_gates_px)
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
