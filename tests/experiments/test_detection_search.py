from __future__ import annotations

import copy

import pytest

from src.evaluation.detection import aggregate_frame_metrics, evaluate_frame
from src.experiments.detection_search import (
    expand_coarse_candidates,
    rank_candidates,
    summarize_candidate,
)


VIDEOS = [11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82]


def plan():
    return {
        "plan_id": "synthetic_threshold_screening", "method": "threshold",
        "params": {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
                   "min_area": 3, "max_area": 300},
        "search_space": {"threshold_value": [0, 128, 255], "morph_iterations": [0, 1, 2],
                         "close_iterations": [0, 1, 2]},
        "evaluation": {"protocol_id": "center_distance_v3_individuals_ignore_clusters_10px",
                       "center_gate_px": 10, "sensitivity_gates_px": [15, 20],
                       "class_policy": "individuals_ignore_clusters"},
        "selection": {
            "primary": "macro_video_f1_individuals_center_10px",
            "tie_breakers": ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"],
            "timing_used_for_ranking": False,
            "comparisons_require_all_candidates_and_all_planned_frames": True,
        },
        "run": {"split": "train", "seed": 42, "save_video": False},
    }


def identify(row, configuration_id):
    row.update(configuration_id=configuration_id, **plan()["evaluation"])
    row["evaluation_protocol_id"] = row.pop("protocol_id")
    return row


def video_rows(configuration_id="t128_o0_c0", frames=12):
    rows = []
    for video_id in VIDEOS:
        metrics = [evaluate_frame(
            [(0, 0, 0)], [(0, 0, 0)], video_id=str(video_id), frame=frame, detection_ms=1.0
        ) for frame in range(frames)]
        row = aggregate_frame_metrics(metrics, video_id=str(video_id))
        identify(row, configuration_id)
        rows.append(row)
    return rows


def candidate(configuration_id="t128_o0_c0"):
    return summarize_candidate(video_rows(configuration_id), VIDEOS, 12)


def test_expansion_keeps_endpoints_zero_morphology_order_and_isolation():
    original = plan()
    before = copy.deepcopy(original)
    expanded = expand_coarse_candidates(original)
    assert len(expanded) == 27
    assert expanded[0]["configuration_id"] == "t000_o0_c0"
    assert expanded[-1]["configuration_id"] == "t255_o2_c2"
    assert expanded[0]["provenance"] == {"search_plan_id": original["plan_id"]}
    assert expanded[0]["run"] == {"split": "train", "seed": 42, "save_video": False}
    expanded[0]["evaluation"]["sensitivity_gates_px"].append(99)
    expanded[0]["params"]["blur"] = 5
    assert original == before
    assert expanded[1]["evaluation"]["sensitivity_gates_px"] == [15, 20]
    assert expanded[1]["params"]["blur"] == 1


@pytest.mark.parametrize(("field", "value"), [
    ("threshold_value", [None]), ("threshold_value", [-1]), ("threshold_value", [256]),
    ("threshold_value", [10.5]), ("threshold_value", [True]), ("threshold_value", []),
    ("threshold_value", [0, 0]), ("threshold_value", "0"),
    ("morph_iterations", [-1]), ("close_iterations", [False]),
])
def test_expansion_rejects_invalid_or_duplicate_grid(field, value):
    invalid = plan()
    invalid["search_space"][field] = value
    with pytest.raises(ValueError):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize(("field", "value"), [
    ("adaptive", True), ("invert", True), ("invert", 0), ("blur", 2),
    ("morph_kernel", 0), ("min_area", 0), ("min_area", 301),
    ("max_area", float("inf")), ("unknown", 1), ("threshold_value", 200),
])
def test_expansion_rejects_invalid_fixed_parameters(field, value):
    invalid = plan()
    invalid["params"][field] = value
    with pytest.raises(ValueError):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize(("field", "value"), [
    ("protocol_id", "center_distance_v2_10px"), ("center_gate_px", 15),
    ("center_gate_px", True), ("sensitivity_gates_px", [15]),
    ("sensitivity_gates_px", [15, 15, 20]), ("class_policy", "binary"),
])
def test_expansion_rejects_contract_drift(field, value):
    invalid = plan()
    invalid["evaluation"][field] = value
    with pytest.raises(ValueError):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize(("field", "value"), [
    ("primary", "pooled_f1"), ("primary", None),
    ("tie_breakers", ["macro_video_count_mae_asc", "macro_video_recall_desc", "configuration_id_asc"]),
    ("tie_breakers", ["macro_video_recall_desc", "macro_video_count_mae_asc"]),
    ("tie_breakers", ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc", "runtime_asc"]),
    ("tie_breakers", None), ("timing_used_for_ranking", True),
    ("timing_used_for_ranking", 0), ("timing_used_for_ranking", None),
    ("comparisons_require_all_candidates_and_all_planned_frames", False),
    ("comparisons_require_all_candidates_and_all_planned_frames", 1),
    ("comparisons_require_all_candidates_and_all_planned_frames", None),
])
def test_expansion_rejects_declared_selection_drift_before_building_grid(monkeypatch, field, value):
    invalid = plan()
    invalid["selection"][field] = value

    def forbidden_grid(_):
        raise AssertionError("selection must be validated before expanding any candidate")

    monkeypatch.setattr("src.experiments.detection_search.parameter_grid", forbidden_grid)
    with pytest.raises(ValueError, match="selection"):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize("field", [
    "primary", "tie_breakers", "timing_used_for_ranking",
    "comparisons_require_all_candidates_and_all_planned_frames",
])
def test_expansion_requires_every_selection_rule_to_be_explicit(field):
    invalid = plan()
    del invalid["selection"][field]
    with pytest.raises(ValueError, match="selection"):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize("selection", [None, [], "macro_video_f1", {}])
def test_expansion_rejects_missing_or_malformed_selection(selection):
    invalid = plan()
    invalid["selection"] = selection
    with pytest.raises(ValueError, match="selection"):
        expand_coarse_candidates(invalid)
    del invalid["selection"]
    with pytest.raises(ValueError, match="selection"):
        expand_coarse_candidates(invalid)


@pytest.mark.parametrize(("field", "value"), [("split", "val"), ("save_video", True), ("seed", None)])
def test_expansion_rejects_invalid_run(field, value):
    invalid = plan()
    invalid["run"][field] = value
    with pytest.raises(ValueError):
        expand_coarse_candidates(invalid)


def test_summary_preserves_counts_all_analyses_and_video_weight():
    result = candidate()
    assert result["complete"] is True
    assert result["n_videos"] == 12
    assert result["frames_total"] == result["count_evaluated_frames"] == 144
    assert result["n_predictions_raw"] == result["n_predictions_scored"] == result["tp"] == 144
    assert result["n_predictions_ignored"] == result["fp"] == result["fn"] == 0
    assert result["macro_video_f1_individuals_center_10px"] == 1
    assert result["macro_video_secondary_all_objects_f1_at_20px"] == 1
    assert result["macro_video_detection_ms_mean"] == 1


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "unexpected", "mixed_config"])
def test_summary_rejects_inexact_video_universe(change):
    rows = video_rows()
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif change == "extra":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "unexpected":
        rows[-1]["video_id"] = "24"
    else:
        rows[-1]["configuration_id"] = "other"
    with pytest.raises(ValueError):
        summarize_candidate(rows, VIDEOS, 12)


@pytest.mark.parametrize("field", [
    "frames_total", "frames_annotated", "count_evaluated_frames",
    "count_evaluated_frames_at_15px", "secondary_all_objects_count_evaluated_frames_at_20px",
])
def test_summary_rejects_incomplete_frames_at_any_gate(field):
    rows = video_rows()
    rows[0][field] = 11
    with pytest.raises(ValueError):
        summarize_candidate(rows, VIDEOS, 12)


@pytest.mark.parametrize(("field", "value"), [
    ("f1", None), ("f1", float("nan")), ("recall", float("inf")),
    ("precision", .5), ("count_mae", 1), ("count_bias", 1),
    ("count_abs_error", -1), ("tp", 11), ("n_predictions_raw", 13),
    ("n_predictions_ignored", 1), ("n_ground_truth_raw", 13),
    ("n_ground_truth_scored_at_20px", 11), ("secondary_all_objects_tp_at_15px", 11),
    ("frames_unannotated", 1), ("status", "partial"),
])
def test_summary_rejects_invalid_metrics_and_inconsistent_counts(field, value):
    rows = video_rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        summarize_candidate(rows, VIDEOS, 12)


@pytest.mark.parametrize(("field", "value"), [
    ("evaluation_protocol_id", "center_distance_v2_10px"), ("class_policy", "binary"),
    ("center_gate_px", 15), ("sensitivity_gates_px", [15]), ("evaluation_protocol_id", None),
])
def test_summary_rejects_mixed_or_missing_evaluation_contract(field, value):
    rows = video_rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        summarize_candidate(rows, VIDEOS, 12)


def test_summary_rejects_fractional_or_impossible_absolute_count_error():
    for absolute_error in (.5, 1):
        rows = video_rows()
        rows[0]["count_abs_error"] = absolute_error
        rows[0]["count_mae"] = absolute_error / 12
        with pytest.raises(ValueError):
            summarize_candidate(rows, VIDEOS, 12)


def test_expected_frame_mapping_and_normalized_duplicate_ids():
    result = summarize_candidate(video_rows(), list(map(str, VIDEOS)), dict.fromkeys(VIDEOS, 12))
    assert result["frames_total"] == 144
    with pytest.raises(ValueError):
        summarize_candidate(video_rows(), VIDEOS[:-1], 12)
    with pytest.raises(ValueError):
        summarize_candidate(video_rows(), VIDEOS, {**dict.fromkeys(VIDEOS, 12), "11": 12})


def test_ignored_predictions_remain_in_raw_counts_but_not_primary_scores():
    rows = []
    gt = [{"cx": 0, "cy": 0, "class_id": 0},
          {"cx": 100, "cy": 100, "w": 20, "h": 20, "class_id": 1}]
    for video_id in VIDEOS:
        metrics = [evaluate_frame([(0, 0, 0), (100, 100, 0)], gt,
                                  video_id=str(video_id), frame=i) for i in range(12)]
        row = aggregate_frame_metrics(metrics, video_id=str(video_id))
        identify(row, "synthetic")
        rows.append(row)
    result = summarize_candidate(rows, VIDEOS, 12)
    assert result["n_predictions_raw"] == 288
    assert result["n_predictions_scored"] == result["n_predictions_ignored"] == 144
    assert result["secondary_all_objects_tp"] == 288
    assert result["macro_video_detection_ms_mean"] is None


def test_144_frames_pooled_f1_and_macro_video_f1_rank_differently():
    # The first video is dense. A fits it; B fits the eleven sparse videos.
    # Equal frame counts do not justify pooling objects across videos.
    all_rows = {"a": [], "b": []}
    for video_index, video_id in enumerate(VIDEOS):
        count = 100 if video_index == 0 else 1
        gt = [(i * 50, 0, 0) for i in range(count)]
        for config_id in all_rows:
            correct = (config_id == "a") == (video_index == 0)
            pred = gt if correct else []
            metrics = [evaluate_frame(pred, gt, video_id=str(video_id), frame=i) for i in range(12)]
            row = aggregate_frame_metrics(metrics, video_id=str(video_id))
            identify(row, config_id)
            all_rows[config_id].append(row)
    a, b = (summarize_candidate(all_rows[key], VIDEOS, 12) for key in ("a", "b"))
    pooled_a = 2 * a["tp"] / (2 * a["tp"] + a["fp"] + a["fn"])
    pooled_b = 2 * b["tp"] / (2 * b["tp"] + b["fp"] + b["fn"])
    assert a["frames_total"] == b["frames_total"] == 144
    assert pooled_a > pooled_b
    assert a["macro_video_f1"] < b["macro_video_f1"]
    assert [row["configuration_id"] for row in rank_candidates([a, b], ["a", "b"])] == ["b", "a"]


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "partial", "frames", "nan", "gate", "plan"])
def test_rank_requires_every_candidate_complete(change):
    rows = [candidate("a"), candidate("b")]
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif change == "extra":
        rows.append(candidate("c"))
    elif change == "partial":
        rows[0]["complete"] = False
    elif change == "frames":
        rows[0]["frames_total"] = 143
    elif change == "nan":
        rows[0]["macro_video_f1"] = float("nan")
    elif change == "gate":
        rows[0]["secondary_all_objects_count_evaluated_frames_at_20px"] = 143
    else:
        rows[0]["video_ids"][-1] = "24"
    with pytest.raises(ValueError):
        rank_candidates(rows, ["a", "b"])


def test_no_empty_or_partial_top_five_and_expected_ids_must_be_unique():
    for summaries, expected in (([], []), ([], ["a"]), ([candidate("a")], ["a", "a"]),
                                ([candidate("a")], ["a", "b", "c", "d", "e"])):
        with pytest.raises(ValueError):
            rank_candidates(summaries, expected)


def test_ranking_ties_use_unrounded_metrics_then_recall_mae_and_id_not_time():
    rows = [candidate(key) for key in ("d", "c", "b", "a", "z")]
    for row in rows:
        row["macro_video_f1"] = row["macro_video_f1_individuals_center_10px"] = .8
        row["macro_video_recall"] = .7
        row["macro_video_count_mae"] = 1
    rows[0]["macro_video_recall"] = .6
    rows[1]["macro_video_count_mae"] = 2
    rows[2]["macro_video_detection_ms_mean"] = 0
    rows[3]["macro_video_detection_ms_mean"] = 100000
    rows[4]["macro_video_f1"] = rows[4]["macro_video_f1_individuals_center_10px"] = .8 + 1e-14
    ranked = rank_candidates(rows, ["a", "b", "c", "d", "z"])
    assert [row["configuration_id"] for row in ranked] == ["z", "a", "b", "c", "d"]
    ranked[0]["video_ids"].append("extra")
    assert len(rows[4]["video_ids"]) == 12
