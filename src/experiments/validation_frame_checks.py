"""Arithmetic and schema checks for typed V3 per-frame detection exports.

These checks do not reconstruct spatial matching from detections/GT. They
validate all observable count, metric and null-state invariants before any
aggregation can truncate invalid values or hide inconsistent frame metrics.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import Any

from src.evaluation.detection import (
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    _PRIMARY_FIELDS,
    _QUALITY_FIELDS,
)
from .detection_search import _evaluation


_GATES = (("", 10), ("_at_15px", 15), ("_at_20px", 20))
_SECONDARY = "secondary_all_objects_"
_BASE_FIELDS = {
    "video_id", "frame", "annotated", "class_policy", "center_gate_px",
    "evaluation_protocol_id", "n_predictions", "n_predictions_raw",
    "n_ground_truth", "n_ground_truth_raw", "n_gt_individuals", "n_gt_clusters",
    "has_gt_clusters", "count_error_raw", "count_abs_error_raw", "detection_ms",
}
_FIELDS = _BASE_FIELDS | {
    name + suffix for suffix, _gate in _GATES for name in _PRIMARY_FIELDS
} | {
    _SECONDARY + name + suffix for suffix, _gate in _GATES for name in _QUALITY_FIELDS
}


def _number(value: Any, name: str, *, minimum: float | None = None,
            maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite numeric value")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return number


def _integer(value: Any, name: str, *, signed: bool = False) -> int:
    number = _number(value, name)
    # Integral floats are valid after CSV typing; never silently truncate them.
    if not number.is_integer() or (not signed and number < 0):
        raise ValueError(f"{name} must be an {'signed ' if signed else 'nonnegative '}integer")
    if abs(number) > 2**53 - 1:
        raise ValueError(f"{name} exceeds exact integer precision of typed CSV numbers")
    return int(number)


def _same(actual: Any, expected: float, name: str) -> None:
    number = _number(actual, name)
    if not math.isclose(number, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Inconsistent {name}: {actual!r} != {expected!r}")


def _at_most(actual: float, maximum: float, name: str) -> None:
    if actual > maximum and not math.isclose(actual, maximum, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"Inconsistent {name}: {actual!r} exceeds {maximum!r}")


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a typed boolean")
    return value


def _quality(row: Mapping[str, Any], prefix: str, suffix: str, *, gate: int,
             predictions: int, ground_truth: int, evaluable: bool) -> int:
    def key(name: str) -> str:
        return prefix + name + suffix

    tp, fp, fn = (_integer(row[key(name)], key(name)) for name in ("tp", "fp", "fn"))
    if tp + fp != predictions or tp + fn != ground_truth:
        raise ValueError(f"Inconsistent TP/FP/FN denominators for {prefix or 'primary'}{suffix}")
    if evaluable:
        precision = tp / predictions if predictions else 1.0
        recall = tp / ground_truth if ground_truth else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        for name, expected in (("precision", precision), ("recall", recall), ("f1", f1)):
            _number(row[key(name)], key(name), minimum=0, maximum=1)
            _same(row[key(name)], expected, key(name))
    else:
        for name in ("precision", "recall", "f1"):
            if row[key(name)] is not None:
                raise ValueError(f"Unevaluable primary {key(name)} must be null")

    error = predictions - ground_truth
    for name, expected in (("count_error", error), ("count_abs_error", abs(error)),
                           ("count_bias", error), ("count_mae", abs(error))):
        observed = _integer(row[key(name)], key(name), signed=name in {"count_error", "count_bias"})
        if observed != expected:
            raise ValueError(f"Inconsistent per-frame {key(name)}: denominator is one annotated frame")

    total = _number(row[key("center_error_sum_px")], key("center_error_sum_px"), minimum=0)
    spatial = ("center_error_mean_px", "center_error_median_px", "center_error_max_px")
    if not tp:
        if total != 0 or any(row[key(name)] is not None for name in spatial):
            raise ValueError(f"No accepted matches: spatial sum must be zero and statistics null{suffix}")
        return tp
    mean, median, maximum = (_number(row[key(name)], key(name), minimum=0) for name in spatial)
    for name, value in zip(spatial, (mean, median, maximum)):
        _at_most(value, gate, key(name))
    _at_most(total, tp * gate, key("center_error_sum_px"))
    _same(mean, total / tp, key("center_error_mean_px"))
    _at_most(mean, maximum, key("mean_vs_max"))
    _at_most(median, maximum, key("median_vs_max"))
    _at_most(maximum, total, key("max_vs_sum"))
    if tp == 1:
        _same(median, total, key("center_error_median_px"))
        _same(maximum, total, key("center_error_max_px"))
    elif tp == 2:
        _same(median, mean, key("center_error_median_px"))
    else:
        half = tp // 2
        # Feasible sum bounds for sorted nonnegative distances with this median
        # and maximum. They do not purport to reconstruct individual distances.
        lower = half * median + maximum
        upper = (half + 1) * median + (half if tp % 2 else half - 1) * maximum
        _at_most(lower, total, key("median_sum_lower_bound"))
        _at_most(total, upper, key("median_sum_upper_bound"))
    return tp


def validate_exported_frame(row: dict, evaluation: dict) -> None:
    """Reject malformed or inconsistent typed V3 frame metrics without mutation.

    Missing annotations have null quantitative fields. A true annotated empty
    frame is evaluable; a cluster-only frame with no scored predictions has
    undefined primary PRF but retains its zero count error and denominator of
    one annotated frame. Secondary all-object evaluation remains defined.
    Integer-valued floats are accepted, as produced by a typed CSV reader.
    """
    _evaluation(evaluation)
    if not isinstance(row, Mapping) or set(row) != _FIELDS:
        missing = sorted(_FIELDS - set(row)) if isinstance(row, Mapping) else sorted(_FIELDS)
        extra = sorted(set(row) - _FIELDS, key=str) if isinstance(row, Mapping) else []
        raise ValueError(f"Invalid V3 frame schema; missing={missing}, extra={extra}")
    if not isinstance(row["video_id"], str) or not row["video_id"] or row["video_id"].strip() != row["video_id"]:
        raise ValueError("video_id must be a nonempty string without surrounding whitespace")
    _integer(row["frame"], "frame")
    annotated = _boolean(row["annotated"], "annotated")
    if row["class_policy"] != DEFAULT_CLASS_POLICY or row["evaluation_protocol_id"] != DEFAULT_EVALUATION_PROTOCOL_ID:
        raise ValueError("Frame policy/protocol differs from the registered V3 evaluation")
    if _number(row["center_gate_px"], "center_gate_px") != 10:
        raise ValueError("Frame center_gate_px must be the registered 10 px")
    raw_predictions = _integer(row["n_predictions_raw"], "n_predictions_raw")
    if _integer(row["n_predictions"], "n_predictions") != raw_predictions:
        raise ValueError("Raw prediction alias is inconsistent")
    if row["detection_ms"] is not None:
        _number(row["detection_ms"], "detection_ms", minimum=0)
    if not annotated:
        nullable = _FIELDS - {"video_id", "frame", "annotated", "class_policy", "evaluation_protocol_id",
                             "center_gate_px", "n_predictions", "n_predictions_raw", "detection_ms"}
        for suffix, _gate in _GATES:
            key = "primary_evaluable" + suffix
            if _boolean(row[key], key):
                raise ValueError("An unannotated frame cannot be primary-evaluable")
            nullable.remove(key)
        if any(row[key] is not None for key in nullable):
            raise ValueError("Unannotated quantitative/GT fields must be null, never zero negatives")
        return
    raw_gt = _integer(row["n_ground_truth_raw"], "n_ground_truth_raw")
    individuals = _integer(row["n_gt_individuals"], "n_gt_individuals")
    clusters = _integer(row["n_gt_clusters"], "n_gt_clusters")
    if _integer(row["n_ground_truth"], "n_ground_truth") != raw_gt or raw_gt != individuals + clusters:
        raise ValueError("Raw GT aliases and individual/cluster counts are inconsistent")
    if _boolean(row["has_gt_clusters"], "has_gt_clusters") != (clusters > 0):
        raise ValueError("has_gt_clusters differs from its count")
    for key, expected in (("count_error_raw", raw_predictions - raw_gt),
                          ("count_abs_error_raw", abs(raw_predictions - raw_gt))):
        if _integer(row[key], key, signed=key == "count_error_raw") != expected:
            raise ValueError(f"Inconsistent {key}")
    previous_tp = previous_secondary_tp = -1
    previous_ignored = raw_predictions
    for suffix, gate in _GATES:
        scored = _integer(row["n_predictions_scored" + suffix], "n_predictions_scored" + suffix)
        ignored = _integer(row["n_predictions_ignored" + suffix], "n_predictions_ignored" + suffix)
        scored_gt = _integer(row["n_ground_truth_scored" + suffix], "n_ground_truth_scored" + suffix)
        if scored + ignored != raw_predictions or scored_gt != individuals or (not clusters and ignored):
            raise ValueError(f"Inconsistent raw/scored/ignored counts{suffix}")
        evaluable = not (clusters > 0 and individuals == 0 and scored == 0)
        if _boolean(row["primary_evaluable" + suffix], "primary_evaluable" + suffix) != evaluable:
            raise ValueError(f"Incorrect primary-evaluable state{suffix}")
        tp = _quality(row, "", suffix, gate=gate, predictions=scored, ground_truth=individuals, evaluable=evaluable)
        secondary_tp = _quality(row, _SECONDARY, suffix, gate=gate,
                                predictions=raw_predictions, ground_truth=raw_gt, evaluable=True)
        if not tp <= secondary_tp <= tp + clusters:
            raise ValueError(f"Secondary cardinality is inconsistent with adding cluster targets{suffix}")
        if not clusters:
            for name in _QUALITY_FIELDS:
                primary, secondary = row[name + suffix], row[_SECONDARY + name + suffix]
                if primary is None or secondary is None:
                    if primary is not secondary:
                        raise ValueError(f"Without clusters both policies must coincide: {name}{suffix}")
                else:
                    _same(secondary, primary, _SECONDARY + name + suffix)
        if tp < previous_tp or secondary_tp < previous_secondary_tp or ignored > previous_ignored:
            raise ValueError(f"Gate expansion cannot reduce matching cardinality or increase ignored predictions{suffix}")
        previous_tp, previous_secondary_tp, previous_ignored = tp, secondary_tp, ignored
