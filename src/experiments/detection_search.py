"""Pure, fail-closed utilities for prospective threshold screening on training data.

Frames are aggregated within each video before videos receive equal weight.
This is training screening, not a generalization estimate: sampled frames are
not independent statistical samples. These utilities read no data or files.
"""
from __future__ import annotations

import copy
import math
import statistics
from collections.abc import Mapping, Sequence
from numbers import Integral, Real
from typing import Any

from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID

from .sweep import parameter_grid


_SUFFIXES = ("", "_at_15px", "_at_20px")
_PREFIXES = ("", "secondary_all_objects_")
_MACRO_METRICS = ("precision", "recall", "f1", "count_mae", "count_bias")
_QUALITY_COUNTS = ("tp", "fp", "fn", "count_error", "count_abs_error", "count_evaluated_frames")
_RAW_COUNTS = ("n_predictions_raw", "n_ground_truth_raw", "n_gt_individuals", "n_gt_clusters")
_SCORED_COUNTS = ("n_predictions_scored", "n_predictions_ignored", "n_ground_truth_scored")


def _finite(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {value!r}")
    return int(value)


def _id(value: Any, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, Integral)) or not str(value).strip():
        raise ValueError(f"{name} must be a nonempty string or integer")
    return str(value)


def _unique_ids(values: Sequence[Any], name: str, *, count: int | None = None) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of IDs")
    result = [_id(value, name) for value in values]
    if not result or len(set(result)) != len(result) or (count is not None and len(result) != count):
        raise ValueError(f"{name} must contain {'exactly ' + str(count) + ' ' if count else ''}unique IDs")
    return result


def _evaluation(evaluation: Mapping[str, Any]) -> None:
    if not isinstance(evaluation, Mapping):
        raise ValueError("evaluation must declare the v3 contract")
    if evaluation.get("protocol_id") != DEFAULT_EVALUATION_PROTOCOL_ID:
        raise ValueError("evaluation.protocol_id must be the v3 individuals/cluster contract")
    if evaluation.get("class_policy") != "individuals_ignore_clusters":
        raise ValueError("evaluation.class_policy must be individuals_ignore_clusters")
    if _finite(evaluation.get("center_gate_px"), "center_gate_px") != 10:
        raise ValueError("v3 requires the primary gate of 10 px")
    gates = evaluation.get("sensitivity_gates_px")
    if not isinstance(gates, Sequence) or isinstance(gates, (str, bytes)):
        raise ValueError("v3 requires sensitivity gates [15, 20]")
    if sorted(_finite(gate, "sensitivity_gate_px") for gate in gates) != [15, 20]:
        raise ValueError("v3 requires exactly the sensitivity gates 15 and 20 px")


def _parameters(params: Mapping[str, Any]) -> dict[str, Any]:
    required = {"threshold_value", "adaptive", "invert", "blur", "morph_kernel",
                "morph_iterations", "close_iterations", "min_area", "max_area"}
    if set(params) != required:
        raise ValueError(f"fixed-threshold params require exactly {sorted(required)}")
    result = dict(params)
    if result["adaptive"] is not False or result["invert"] is not False:
        raise ValueError("this search requires adaptive=false and invert=false")
    threshold = _integer(result["threshold_value"], "threshold_value")
    if threshold > 255:
        raise ValueError("threshold_value must be between 0 and 255; None/Otsu is not fixed threshold")
    for name in ("blur", "morph_kernel"):
        value = _integer(result[name], name, minimum=1)
        if value % 2 != 1:
            raise ValueError(f"{name} must be odd; implicit parameter adjustment is forbidden")
    for name in ("morph_iterations", "close_iterations"):
        _integer(result[name], name)
    minimum = _finite(result["min_area"], "min_area", minimum=0)
    maximum = _finite(result["max_area"], "max_area", minimum=0)
    if minimum <= 0 or maximum < minimum:
        raise ValueError("areas must satisfy 0 < min_area <= max_area")
    return result


def _selection(selection: Mapping[str, Any]) -> None:
    """Require the declared plan to match the implemented ranking semantics."""
    if not isinstance(selection, Mapping):
        raise ValueError("selection must explicitly declare the implemented ranking rules")
    if selection.get("primary") != "macro_video_f1_individuals_center_10px":
        raise ValueError("selection.primary must be macro_video_f1_individuals_center_10px")
    expected_ties = ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"]
    if selection.get("tie_breakers") != expected_ties:
        raise ValueError(f"selection.tie_breakers must be exactly {expected_ties!r} in that order")
    if selection.get("timing_used_for_ranking") is not False:
        raise ValueError("selection.timing_used_for_ranking must be false")
    if selection.get("comparisons_require_all_candidates_and_all_planned_frames") is not True:
        raise ValueError("selection must require all candidates and all planned frames")


def expand_coarse_candidates(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Resolve the full coarse grid in declared order; reject duplicate configurations.

    Only threshold/opening/closing vary in this stage. No candidate is sampled
    or discarded, including the endpoint thresholds 0 and 255.
    """
    if plan.get("method") != "threshold":
        raise ValueError("the coarse plan must use method='threshold'")
    plan_id = _id(plan.get("plan_id"), "plan_id")
    evaluation = plan.get("evaluation")
    _evaluation(evaluation)
    _selection(plan.get("selection"))
    run = plan.get("run", {})
    if run.get("split") != "train" or run.get("save_video") is not False:
        raise ValueError("the coarse search requires split=train and save_video=false")
    seed = _integer(run.get("seed"), "run.seed")
    grid = plan.get("search_space")
    if not isinstance(grid, Mapping) or set(grid) != {"threshold_value", "morph_iterations", "close_iterations"}:
        raise ValueError("coarse search_space must vary threshold_value, morph_iterations and close_iterations")
    if any(not isinstance(values, Sequence) or isinstance(values, (str, bytes)) for values in grid.values()):
        raise ValueError("every search-space parameter needs a sequence of values")
    fixed = plan.get("params")
    if not isinstance(fixed, Mapping) or set(fixed) & set(grid):
        raise ValueError("fixed params and search_space must be separate mappings without overlapping keys")
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for varying in parameter_grid(grid):
        params = _parameters({**fixed, **varying})
        signature = tuple(params[name] for name in sorted(params))
        if signature in seen:
            raise ValueError("duplicate resolved parameters in coarse search_space")
        seen.add(signature)
        configuration_id = (f"t{params['threshold_value']:03d}"
                            f"_o{params['morph_iterations']}_c{params['close_iterations']}")
        candidates.append({
            "configuration_id": configuration_id,
            "method": "threshold",
            "params": copy.deepcopy(params),
            "evaluation": copy.deepcopy(dict(evaluation)),
            "run": {"split": "train", "seed": seed, "save_video": False},
            "provenance": {"search_plan_id": plan_id},
        })
    return candidates


def _frame_plan(expected: int | Mapping[Any, int], video_ids: Sequence[str]) -> dict[str, int]:
    if isinstance(expected, Mapping):
        frames: dict[str, int] = {}
        for raw_id, number in expected.items():
            video_id = _id(raw_id, "expected_frames_per_video ID")
            if video_id in frames:
                raise ValueError("duplicate normalized ID in expected_frames_per_video")
            frames[video_id] = _integer(number, "expected frames", minimum=1)
        if set(frames) != set(video_ids):
            raise ValueError("expected_frames_per_video must cover exactly the expected videos")
        return {video_id: frames[video_id] for video_id in video_ids}
    number = _integer(expected, "expected_frames_per_video", minimum=1)
    return dict.fromkeys(video_ids, number)


def _equal(actual: float, expected: float, name: str) -> None:
    # Only tolerate binary floating-point arithmetic/serialization, never rank rounding.
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"inconsistent {name}: {actual!r} != {expected!r}")


def _count(record: Mapping[str, Any], name: str) -> int:
    return _integer(record.get(name), name)


def _quality(record: Mapping[str, Any], prefix: str, suffix: str, frames: int,
             predictions: int, ground_truth: int) -> None:
    def name(metric: str) -> str:
        return f"{prefix}{metric}{suffix}"

    tp, fp, fn = (_count(record, name(metric)) for metric in ("tp", "fp", "fn"))
    if tp + fp != predictions or tp + fn != ground_truth:
        raise ValueError(f"inconsistent TP/FP/FN and counts for {prefix or 'primary'}{suffix}")
    if _count(record, name("count_evaluated_frames")) != frames:
        raise ValueError(f"incomplete {name('count_evaluated_frames')}")
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    for metric, expected in (("precision", precision), ("recall", recall), ("f1", f1)):
        _equal(_finite(record.get(name(metric)), name(metric)), expected, name(metric))
    error = _finite(record.get(name("count_error")), name("count_error"))
    absolute_error = _finite(record.get(name("count_abs_error")), name("count_abs_error"), minimum=0)
    _equal(error, fp - fn, name("count_error"))
    if (not absolute_error.is_integer() or absolute_error < abs(error)
            or absolute_error > predictions + ground_truth
            or (absolute_error - error) % 2 != 0):
        raise ValueError(f"inconsistent {name('count_abs_error')}")
    _equal(_finite(record.get(name("count_bias")), name("count_bias")), error / frames, name("count_bias"))
    _equal(_finite(record.get(name("count_mae")), name("count_mae"), minimum=0), absolute_error / frames, name("count_mae"))


def _validate_video(record: Mapping[str, Any], expected_frames: int) -> None:
    _evaluation({
        "protocol_id": record.get("evaluation_protocol_id"),
        "class_policy": record.get("class_policy"),
        "center_gate_px": record.get("center_gate_px"),
        "sensitivity_gates_px": record.get("sensitivity_gates_px"),
    })
    for name in ("frames_total", "frames_annotated"):
        if _count(record, name) != expected_frames:
            raise ValueError(f"incomplete {name}: all planned annotated frames are required")
    if _count(record, "frames_unannotated") != 0:
        raise ValueError("unannotated frames cannot enter this screening")
    if record.get("status", "complete") != "complete":
        raise ValueError("video summary is not complete")
    raw_predictions, raw_gt, individuals, clusters = (_count(record, name) for name in _RAW_COUNTS)
    if raw_gt != individuals + clusters:
        raise ValueError("raw ground truth must equal individuals plus clusters")
    for suffix in _SUFFIXES:
        scored, ignored, scored_gt = (_count(record, name + suffix) for name in _SCORED_COUNTS)
        if scored + ignored != raw_predictions or scored_gt != individuals:
            raise ValueError(f"inconsistent raw/scored/ignored counts{suffix}")
        _quality(record, "", suffix, expected_frames, scored, scored_gt)
        _quality(record, "secondary_all_objects_", suffix, expected_frames, raw_predictions, raw_gt)


def summarize_candidate(
    video_summaries: Sequence[Mapping[str, Any]],
    expected_video_ids: Sequence[Any],
    expected_frames_per_video: int | Mapping[Any, int],
) -> dict[str, Any]:
    """Validate all 12 per-video aggregates, then average metrics equally by video.

    Each input is an ``aggregate_frame_metrics`` result augmented with
    ``configuration_id``, ``evaluation_protocol_id``, ``class_policy``,
    ``center_gate_px`` and ``sensitivity_gates_px``. Required numeric values
    are typed numbers, not CSV strings. Undefined primary F1 or incomplete
    secondary/gate counts fail.
    The explicit frame plan is the caller's pre-registered sampling contract;
    checking the actual frame identities remains the executor's responsibility.
    """
    expected_ids = _unique_ids(expected_video_ids, "expected_video_ids", count=12)
    frame_plan = _frame_plan(expected_frames_per_video, expected_ids)
    rows = list(video_summaries)
    actual_ids = _unique_ids([row.get("video_id") for row in rows], "video summaries", count=12)
    if set(actual_ids) != set(expected_ids):
        raise ValueError("video summaries must cover exactly the expected video universe")
    candidate_ids = {_id(row.get("configuration_id"), "configuration_id") for row in rows}
    if len(candidate_ids) != 1:
        raise ValueError("all video summaries must belong to the same configuration_id")
    by_video = dict(zip(actual_ids, rows))
    ordered = [by_video[video_id] for video_id in expected_ids]
    for video_id, row in zip(expected_ids, ordered):
        _validate_video(row, frame_plan[video_id])
    total_frames = sum(frame_plan.values())
    result: dict[str, Any] = {
        "configuration_id": next(iter(candidate_ids)), "complete": True,
        "evaluation_protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID,
        "class_policy": "individuals_ignore_clusters", "center_gate_px": 10,
        "sensitivity_gates_px": [15, 20],
        "interpretation": "training_screening_not_generalization_estimate",
        "video_ids": expected_ids, "n_videos": 12,
        "expected_frames_per_video": frame_plan,
        "frames_total": total_frames, "frames_annotated": total_frames,
        "frames_unannotated": 0,
    }
    for name in _RAW_COUNTS:
        result[name] = sum(row[name] for row in ordered)
    for suffix in _SUFFIXES:
        for name in _SCORED_COUNTS:
            result[name + suffix] = sum(row[name + suffix] for row in ordered)
        for prefix in _PREFIXES:
            for metric in _MACRO_METRICS:
                name = f"{prefix}{metric}{suffix}"
                result[f"macro_video_{name}"] = statistics.fmean(row[name] for row in ordered)
            for metric in _QUALITY_COUNTS:
                name = f"{prefix}{metric}{suffix}"
                result[name] = sum(row[name] for row in ordered)
    result["macro_video_f1_individuals_center_10px"] = result["macro_video_f1"]
    times = [row.get("detection_ms_mean") for row in ordered]
    result["macro_video_detection_ms_mean"] = (
        statistics.fmean(_finite(value, "detection_ms_mean", minimum=0) for value in times)
        if all(value is not None for value in times) else None
    )
    return result


def rank_candidates(
    summaries: Sequence[Mapping[str, Any]], expected_candidate_ids: Sequence[Any],
) -> list[dict[str, Any]]:
    """Rank a complete candidate universe without rounding or using runtime.

    Return all candidates, never a partial top five. Missing, duplicate,
    non-finite or incomplete summaries cannot be ranked.
    """
    expected_ids = _unique_ids(expected_candidate_ids, "expected_candidate_ids")
    rows = list(summaries)
    actual_ids = _unique_ids([row.get("configuration_id") for row in rows], "candidate summaries")
    if set(actual_ids) != set(expected_ids):
        raise ValueError("ranking requires the complete expected candidate universe")
    common_plan: tuple[Any, ...] | None = None
    for row in rows:
        if (row.get("complete") is not True or row.get("n_videos") != 12
                or row.get("status", "complete") != "complete"):
            raise ValueError("ranking requires complete summaries for all 12 videos")
        _evaluation({
            "protocol_id": row.get("evaluation_protocol_id"),
            "class_policy": row.get("class_policy"),
            "center_gate_px": row.get("center_gate_px"),
            "sensitivity_gates_px": row.get("sensitivity_gates_px"),
        })
        ids = _unique_ids(row.get("video_ids", []), "video_ids", count=12)
        frame_plan = _frame_plan(row.get("expected_frames_per_video"), ids)
        signature = tuple(sorted(frame_plan.items()))
        if common_plan is not None and signature != common_plan:
            raise ValueError("all candidates must use the identical video/frame plan")
        common_plan = signature
        total_frames = sum(frame_plan.values())
        for name in ("frames_total", "frames_annotated"):
            if _count(row, name) != total_frames:
                raise ValueError("ranking cannot include incomplete frame coverage")
        if _count(row, "frames_unannotated") != 0:
            raise ValueError("ranking cannot include unannotated frames")
        for suffix in _SUFFIXES:
            for prefix in _PREFIXES:
                if _count(row, f"{prefix}count_evaluated_frames{suffix}") != total_frames:
                    raise ValueError("ranking requires complete metrics for every analysis and gate")
                values = {metric: _finite(row.get(f"macro_video_{prefix}{metric}{suffix}"),
                                          f"macro_video_{prefix}{metric}{suffix}") for metric in _MACRO_METRICS}
                if any(not 0 <= values[metric] <= 1 for metric in ("f1", "recall", "precision")):
                    raise ValueError("macro precision/recall/F1 must lie in [0, 1]")
                if values["count_mae"] < abs(values["count_bias"]):
                    raise ValueError("macro count MAE must be >= absolute macro bias")
        _equal(_finite(row.get("macro_video_f1_individuals_center_10px"), "primary F1 alias"),
               row["macro_video_f1"], "primary F1 alias")
    ranked = sorted(rows, key=lambda row: (-row["macro_video_f1"], -row["macro_video_recall"],
                                          row["macro_video_count_mae"], str(row["configuration_id"])))
    return [copy.deepcopy(dict(row)) for row in ranked]
