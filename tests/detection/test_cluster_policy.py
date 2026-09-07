"""Synthetic adversarial cases for individual evaluation with GT cluster ignore."""
from __future__ import annotations

import copy
import math

import pytest

from src.detection.base import Detection
from src.evaluation.detection import (
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    aggregate_frame_metrics,
    evaluate_frame,
    match_detections,
)


def point(x, y=0, cls=0):
    return Detection(cx=x, cy=y, w=4, h=4, class_id=cls)


def cluster(x=0, y=0, w=40, h=40):
    return Detection(cx=x, cy=y, w=w, h=h, class_id=1)


def test_individual_takes_priority_and_keeps_original_gt_index():
    predictions = [point(0, cls=1)]
    gt = [cluster(), point(0, cls=2)]
    original = copy.deepcopy((predictions, gt))
    result = match_detections(predictions, gt)
    assert result.tp == 1 and result.fp == 0 and result.fn == 0
    assert result.matches[0].ground_truth_index == 1
    assert result.ignored_ground_truth == (0,)
    assert result.ignored_predictions == ()
    assert (predictions, gt) == original


@pytest.mark.parametrize("extra", [point(8), point(10), point(6, 8, cls=1)])
def test_duplicate_inside_individual_disk_remains_fp_even_inside_cluster(extra):
    row = evaluate_frame([point(0), extra], [point(0), cluster()])
    assert (row["tp"], row["fp"], row["fn"]) == (1, 1, 0)
    assert row["n_predictions_ignored"] == 0
    assert row["n_predictions_scored"] == 2


def test_radius_sensitivity_recomputes_ignore_and_can_reduce_f1():
    row = evaluate_frame([point(0), point(12)], [point(0), cluster(20, w=60)])
    assert row["f1"] == 1
    assert row["n_predictions_ignored"] == 1 and row["n_predictions_scored"] == 1
    for radius in (15, 20):
        assert row[f"n_predictions_ignored_at_{radius}px"] == 0
        assert row[f"n_predictions_scored_at_{radius}px"] == 2
        assert row[f"fp_at_{radius}px"] == 1
        assert row[f"f1_at_{radius}px"] == pytest.approx(2 / 3)


@pytest.mark.parametrize("x,y", [(-5, 0), (5, 0), (0, -5), (0, 5), (5, 5)])
def test_cluster_box_boundary_is_inclusive_without_margin(x, y):
    result = match_detections([point(x, y)], [cluster(w=10, h=10)])
    assert result.ignored_predictions == (0,)
    assert result.fp == 0
    outside = match_detections([point(5.001)], [cluster(w=10, h=10)])
    assert outside.fp == 1 and outside.ignored_predictions == ()


def test_overlapping_clusters_ignore_each_prediction_once():
    row = evaluate_frame([point(5)], [cluster(0, w=20), cluster(5, w=20)])
    assert row["n_gt_clusters"] == 2
    assert row["n_predictions_ignored"] == 1
    assert row["n_predictions_raw"] == row["n_predictions_scored"] + row["n_predictions_ignored"]
    assert row["secondary_all_objects_tp"] == 1
    assert row["secondary_all_objects_fn"] == 1


def test_cluster_does_not_hide_missing_individual_or_class_one_false_positive():
    row = evaluate_frame([point(100, cls=1)], [cluster(), point(0)])
    assert (row["tp"], row["fp"], row["fn"]) == (0, 1, 1)
    assert row["n_predictions_ignored"] == 0
    missing = evaluate_frame([], [cluster(), point(0)])
    assert missing["fn"] == 1 and missing["f1"] == 0


def test_cluster_only_has_no_perfect_primary_credit_but_exposes_outside_fp():
    for predictions in ([], [point(0)]):
        row = evaluate_frame(predictions, [cluster()])
        assert row["annotated"] and not row["primary_evaluable"]
        assert row["precision"] is row["recall"] is row["f1"] is None
        assert row["count_error"] == row["count_mae"] == 0
        summary = aggregate_frame_metrics([row])
        assert summary["f1"] is None
        assert summary["count_evaluated_frames"] == 1
        assert summary["count_mae"] == 0
    outside = evaluate_frame([point(100)], [cluster()])
    assert outside["primary_evaluable"] and outside["fp"] == 1 and outside["f1"] == 0
    assert aggregate_frame_metrics([outside])["f1"] == 0


def test_true_empty_retains_negative_evidence_and_fixed_count_denominator():
    ignored = evaluate_frame([point(0)], [cluster()])
    false_positive = evaluate_frame([point(100)], [])
    summary = aggregate_frame_metrics([ignored, false_positive])
    assert summary["frames_annotated"] == summary["count_evaluated_frames"] == 2
    assert summary["frames_primary_evaluable"] == 1
    assert summary["count_mae"] == summary["count_bias"] == .5
    empty = evaluate_frame([], [])
    assert empty["primary_evaluable"] and empty["f1"] == 1
    with_empty = aggregate_frame_metrics([ignored, empty])
    assert with_empty["f1"] == 1
    assert with_empty["frames_true_empty_gt"] == 1


def test_raw_scored_and_secondary_counts_reconcile_without_unlabeled_leakage():
    rows = [
        evaluate_frame([point(0), point(100)], [point(0), cluster(100)]),
        evaluate_frame([point(100)], [cluster(100)]),
        evaluate_frame([], []),
        evaluate_frame([point(200)], None),
    ]
    row = rows[0]
    assert row["n_predictions"] == row["n_predictions_raw"] == 2
    assert row["n_ground_truth"] == row["n_ground_truth_raw"] == 2
    assert row["n_ground_truth_scored"] == row["n_gt_individuals"] == 1
    assert row["n_gt_clusters"] == 1
    assert row["secondary_all_objects_tp"] == 2
    assert row["tp"] == 1
    summary = aggregate_frame_metrics(rows)
    assert summary["n_predictions_raw"] == 4
    assert summary["n_predictions_raw"] == (
        summary["n_predictions_scored"] + summary["n_predictions_ignored"] + summary["n_predictions_unannotated"]
    )
    assert summary["n_ground_truth_raw"] == summary["n_gt_individuals"] + summary["n_gt_clusters"] == 3
    assert summary["frames_annotated"] == summary["count_evaluated_frames"] == 3
    assert summary["frames_with_clusters"] == summary["frames_with_ignored_predictions"] == 2
    assert summary["frames_with_individual_gt"] == summary["frames_cluster_only_gt"] == 1
    assert summary["secondary_all_objects_tp"] == 3 and summary["secondary_all_objects_f1"] == 1
    for radius in (15, 20):
        assert summary[f"secondary_all_objects_tp_at_{radius}px"] == 3
    unannotated = aggregate_frame_metrics([rows[-1]])
    assert unannotated["f1"] is unannotated["f1_at_15px"] is None
    assert unannotated["secondary_all_objects_f1"] is None
    assert unannotated["count_evaluated_frames"] == 0


def test_evaluated_count_and_raw_annotation_count_have_distinct_meanings():
    row = evaluate_frame([], [point(0), cluster(100)])
    assert row["count_error"] == -1
    assert row["count_error_raw"] == row["secondary_all_objects_count_error"] == -2


def test_explicit_historical_binary_fifteen_preserves_cluster_as_target():
    row = evaluate_frame([point(12)], [(0, 0, 1)], center_gate_px=15,
                         sensitivity_gates_px=(10, 20), class_policy="binary")
    assert row["tp"] == 1 and row["n_predictions_ignored"] == 0
    assert row["n_ground_truth_scored"] == 1
    assert row["tp_at_10px"] == 0 and row["tp_at_20px"] == 1
    assert DEFAULT_CLASS_POLICY == "individuals_ignore_clusters"
    assert DEFAULT_EVALUATION_PROTOCOL_ID == "center_distance_v3_individuals_ignore_clusters_10px"


@pytest.mark.parametrize("bad", [point(math.nan), point(math.inf), point(0, math.inf), point(0, cls=3), point(0, cls=1.5)])
@pytest.mark.parametrize("side", ["predictions", "ground_truth"])
def test_invalid_centers_and_unknown_classes_fail_clearly(bad, side):
    arguments = {"predictions": [point(0)], "ground_truth": [point(0)], side: [bad]}
    with pytest.raises(ValueError, match="finite|class id"):
        evaluate_frame(**arguments)


@pytest.mark.parametrize("bad", [cluster(w=0), cluster(w=-1), cluster(w=math.nan), cluster(h=math.inf), (0, 0, 1)])
def test_cluster_boxes_require_finite_positive_dimensions_even_without_predictions(bad):
    with pytest.raises(ValueError, match="cluster box"):
        evaluate_frame([], [bad])


@pytest.mark.parametrize("gate", [-1, math.nan, math.inf])
def test_invalid_radii_fail_even_without_labels(gate):
    with pytest.raises(ValueError, match="finite and non-negative"):
        evaluate_frame([], None, center_gate_px=gate)
    with pytest.raises(ValueError, match="finite and non-negative"):
        evaluate_frame([], None, sensitivity_gates_px=(gate,))


def test_missing_annotation_cannot_be_recast_as_explicit_negative():
    with pytest.raises(ValueError, match="explicit ground truth"):
        evaluate_frame([], None, annotated=True)
