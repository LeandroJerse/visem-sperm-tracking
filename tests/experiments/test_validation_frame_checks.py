"""Per-frame export certification using synthetic points only."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from src.detection.base import Detection
from src.evaluation.detection import DEFAULT_EVALUATION_PROTOCOL_ID, evaluate_frame
from src.experiments.validation_frame_checks import validate_exported_frame


EVALUATION = {"protocol_id": DEFAULT_EVALUATION_PROTOCOL_ID, "class_policy": "individuals_ignore_clusters",
              "center_gate_px": 10, "sensitivity_gates_px": [15, 20]}
SUFFIXES = ("", "_at_15px", "_at_20px")
PREFIXES = ("", "secondary_all_objects_")


def point(x=0, y=0, cls=0):
    return Detection(x, y, 4, 4, class_id=cls)


def cluster(x=0, y=0, width=80):
    return Detection(x, y, width, 40, class_id=1)


def record(predictions=None, gt=None, *, annotated=True):
    value = evaluate_frame(predictions if predictions is not None else [point(3)],
                           (gt if gt is not None else [point()]) if annotated else None,
                           video_id="14", frame=0, detection_ms=1.234)
    value["evaluation_protocol_id"] = DEFAULT_EVALUATION_PROTOCOL_ID
    return value


@pytest.mark.parametrize("predictions,gt", [([], []), ([point()], []), ([], [point()]),
    ([point()], [cluster()]), ([], [cluster()]), ([point(100)], [cluster()]),
    ([point(), point(12)], [point(), cluster(20, width=60)]),
    ([point(), point(8), point(50)], [point(), cluster()]),
    ([point(3), point(100), point(101)], [point(), point(100), cluster(100)]),
])
def test_valid_empty_cluster_and_nonmonotonic_f1_states(predictions, gt):
    value = record(predictions, gt)
    original = copy.deepcopy(value)
    assert validate_exported_frame(value, EVALUATION) is None
    assert value == original


def test_valid_unannotated_retains_predictions_but_no_quality():
    value = record([point()], annotated=False)
    validate_exported_frame(value, EVALUATION)
    assert value["n_predictions_raw"] == 1 and value["f1"] is None


def test_integral_csv_floats_accepted_without_truncation():
    value = record()
    typed = {k: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v for k, v in value.items()}
    validate_exported_frame(typed, EVALUATION)


@pytest.mark.parametrize("key,bad", [("frame", 0.5), ("frame", -1), ("frame", True),
    ("n_predictions", 1.5), ("n_predictions_raw", True), ("n_predictions_raw", "1"),
    ("n_ground_truth_raw", float("nan")), ("n_gt_individuals", -1), ("n_gt_clusters", 0.1),
    ("has_gt_clusters", 0), ("annotated", 1), ("video_id", ""), ("video_id", 14),
    ("center_gate_px", 999), ("center_gate_px", True), ("center_gate_px", "10"),
    ("detection_ms", -0.1), ("detection_ms", float("inf")), ("class_policy", "binary"),
    ("evaluation_protocol_id", "center_distance_v1_15px"), ("count_error_raw", .5),
    ("count_abs_error_raw", -1), ("n_predictions_raw", 2**53),
])
def test_base_schema_and_types_reject_tampering(key, bad):
    value = record()
    value[key] = bad
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("field,bad", [("tp", 1.5), ("tp", True), ("fp", -1), ("fn", .1),
    ("precision", 1.01), ("recall", None), ("f1", -.25), ("f1", .5),
    ("count_error", .5), ("count_abs_error", 2), ("count_bias", None), ("count_mae", .1),
    ("center_error_sum_px", float("nan")), ("center_error_mean_px", 4),
    ("center_error_median_px", 4), ("center_error_max_px", 4),
])
def test_every_policy_gate_rejects_inconsistent_frame_metric(prefix, suffix, field, bad):
    value = record()
    value[prefix + field + suffix] = bad
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("field,bad", [("n_predictions_scored", 0), ("n_predictions_ignored", 1),
                                     ("n_ground_truth_scored", 0), ("primary_evaluable", False)])
def test_scored_and_raw_denominators_reconcile(suffix, field, bad):
    value = record()
    value[field + suffix] = bad
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_cluster_only_undefined_primary_has_count_denominator_of_one(suffix):
    value = record([point()], [cluster()])
    assert value["primary_evaluable" + suffix] is False
    assert value["count_mae" + suffix] == 0
    value["count_mae" + suffix] = None
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_cluster_only_primary_cannot_claim_perfect_prf(suffix):
    value = record([], [cluster()])
    value["f1" + suffix] = 1.0
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("key", ["n_ground_truth_raw", "has_gt_clusters", "count_error_raw", "tp", "f1_at_15px",
                                 "secondary_all_objects_count_mae_at_20px", "n_predictions_ignored_at_20px"])
def test_missing_annotation_cannot_acquire_zero_metrics(key):
    value = record(annotated=False)
    value[key] = 0
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("prefix", PREFIXES)
def test_no_matches_requires_null_spatial_statistics(prefix, suffix):
    value = record([], [point()])
    value[prefix + "center_error_mean_px" + suffix] = 0
    with pytest.raises(ValueError):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("change", ["missing", "extra_gate", "extra_field"])
def test_exact_schema_prevents_hidden_omissions_and_wrong_gates(change):
    value = record()
    if change == "missing":
        value.pop("secondary_all_objects_fp_at_20px")
    else:
        value["tp_at_25px" if change == "extra_gate" else "count_evaluated_frames"] = 1
    with pytest.raises(ValueError, match="schema"):
        validate_exported_frame(value, EVALUATION)


@pytest.mark.parametrize("field,value", [("center_gate_px", 15), ("sensitivity_gates_px", [15]),
                                       ("sensitivity_gates_px", [10, 20]), ("class_policy", "binary")])
def test_evaluation_contract_cannot_change(field, value):
    evaluation = {**EVALUATION, field: value}
    with pytest.raises(ValueError):
        validate_exported_frame(record(), evaluation)


@pytest.mark.parametrize("distances", [[2, 6], [1, 3, 9], [0, 2, 2, 9], [2, 2, 2, 9],
                                        [1, 2, 3, 4, 9], [0, 1, 2, 2, 2, 9]])
def test_feasible_median_and_sum_for_even_and_odd_match_counts(distances):
    gt = [point(index * 100) for index in range(len(distances))]
    predictions = [point(index * 100 + distance) for index, distance in enumerate(distances)]
    validate_exported_frame(record(predictions, gt), EVALUATION)


def test_multiple_match_mean_and_median_bounds_are_checked():
    value = record([point(1), point(103), point(209)], [point(), point(100), point(200)])
    value["center_error_median_px"] = 8  # sum 13, max 9 require sum >= median + max
    with pytest.raises(ValueError, match="median_sum_lower_bound"):
        validate_exported_frame(value, EVALUATION)


def test_random_synthetic_geometry_remains_valid_without_f1_monotonic_assumption():
    generator = np.random.default_rng(42)
    for _ in range(80):
        predictions = [point(*xy) for xy in generator.uniform(0, 100, (int(generator.integers(0, 10)), 2))]
        gt = [point(*xy, cls=int(cls)) for xy, cls in zip(generator.uniform(0, 100, (8, 2)),
                                                       generator.choice([0, 2], 8))]
        if generator.random() < .7:
            gt.extend([cluster(*xy) for xy in generator.uniform(0, 100, (2, 2))])
        validate_exported_frame(record(predictions, gt), EVALUATION)
