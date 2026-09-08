"""Reject equally corrupted metadata in both descriptive baseline summaries."""
from __future__ import annotations

import copy
from fractions import Fraction

import numpy as np
import pytest

from src.experiments.prediction_baselines import METRICS, METHOD_IDS, summarize_comparison


COUNTS = ("n_windows", "evaluated_original_ids", "all_original_individual_ids",
          "original_ids_without_windows", "segments_total", "segments_with_windows")
HASHES = ("window_keys_sha256", "histories_sha256", "targets_sha256")


def _rows():
    rows = []
    for method in METHOD_IDS:
        error = 3.0 if method == "persistence" else 2.0
        rows.append({"video_id": "11", "configuration_id": method, "split": "train",
                     "n_windows": 50, "evaluated_original_ids": 2,
                     "all_original_individual_ids": 3, "original_ids_without_windows": 1,
                     "segments_total": 4, "segments_with_windows": 3, "fps": 49.0,
                     "window_keys_sha256": "a" * 64, "histories_sha256": "b" * 64,
                     "targets_sha256": "c" * 64,
                     **{key: error for key in METRICS},
                     **{f"window_weighted_{key}": error + 0.5 for key in METRICS}})
    return rows


def _same_change(**changes):
    rows = _rows()
    for row in rows:
        row.update(changes)
    return rows


def test_valid_contract_preserves_api_values_and_does_not_mutate_inputs():
    rows = _rows()
    previous = copy.deepcopy(rows)
    result = summarize_comparison(rows, video_ids=("11",))
    assert rows == previous
    assert result["status"] == "complete_descriptive_training_baselines"
    assert result["methods"][0]["macro_ade_h10"] == 3.0
    assert result["methods"][1]["macro_ade_h10"] == 2.0
    assert result["methods"][0]["macro_window_weighted_ade_h10"] == 3.5
    assert result["paired_video_differences"][0]["cv_minus_persistence_fde_h10"] == -1.0
    assert result["model_selected"] is False and result["hypothesis_tests"] is False


@pytest.mark.parametrize("field", COUNTS)
@pytest.mark.parametrize("value", [True, False, np.bool_(True), 1.0, 1.5, "1", None,
                                   float("nan"), float("inf"), np.int64(1), -1])
def test_both_models_with_same_invalid_count_type_or_negative_value_are_rejected(field, value):
    with pytest.raises(ValueError, match="coverage"):
        summarize_comparison(_same_change(**{field: value}), video_ids=("11",))


@pytest.mark.parametrize("field", [key for key in COUNTS if key != "original_ids_without_windows"])
def test_required_coverage_is_positive_even_when_both_models_agree(field):
    with pytest.raises(ValueError, match="coverage"):
        summarize_comparison(_same_change(**{field: 0}), video_ids=("11",))


@pytest.mark.parametrize("field", COUNTS)
def test_missing_coverage_field_is_explicitly_rejected(field):
    rows = _rows()
    for row in rows:
        del row[field]
    with pytest.raises(ValueError, match="coverage"):
        summarize_comparison(rows, video_ids=("11",))


@pytest.mark.parametrize("changes", [
    {"all_original_individual_ids": 4},
    {"original_ids_without_windows": 0},
    {"evaluated_original_ids": 4, "all_original_individual_ids": 5},
    {"n_windows": 1},
    {"segments_total": 2},
    {"segments_with_windows": 51, "segments_total": 52},
    {"segments_total": 3, "segments_with_windows": 3},
    {"all_original_individual_ids": 10, "original_ids_without_windows": 8},
])
def test_identical_inconsistent_id_segment_and_window_relations_are_rejected(changes):
    with pytest.raises(ValueError, match="inconsistent"):
        summarize_comparison(_same_change(**changes), video_ids=("11",))


def test_no_original_ids_without_windows_is_valid_and_not_a_missing_value():
    rows = _same_change(all_original_individual_ids=2, original_ids_without_windows=0,
                        segments_total=3, segments_with_windows=3)
    assert summarize_comparison(rows, video_ids=("11",))["methods"][0]["n_windows"] == 50


def test_single_window_single_identity_single_segment_is_valid():
    rows = _same_change(n_windows=1, evaluated_original_ids=1, all_original_individual_ids=1,
                        original_ids_without_windows=0, segments_total=1, segments_with_windows=1)
    result = summarize_comparison(rows, video_ids=("11",))
    assert result["paired_video_differences"][0]["evaluated_original_ids"] == 1


@pytest.mark.parametrize("fps", [0, -1, True, False, np.bool_(True), "49", None, complex(49, 0),
                                 float("nan"), float("inf"), float("-inf"), 10 ** 1000])
def test_equal_invalid_fps_values_are_rejected(fps):
    with pytest.raises(ValueError, match="FPS"):
        summarize_comparison(_same_change(fps=fps), video_ids=("11",))


@pytest.mark.parametrize("fps", [49, 49.0, 49.95, np.float32(49.5), np.float64(49.5), Fraction(99, 2)])
def test_finite_positive_real_fps_values_are_accepted(fps):
    assert summarize_comparison(_same_change(fps=fps), video_ids=("11",))["status"] == "complete_descriptive_training_baselines"


@pytest.mark.parametrize("field", HASHES)
@pytest.mark.parametrize("value", ["", "a" * 63, "a" * 65, "g" * 64, "A" * 64,
                                   "a" * 63 + "\n", None, True, b"a" * 64, 0])
def test_equal_invalid_hashes_are_rejected(field, value):
    with pytest.raises(ValueError, match="SHA256"):
        summarize_comparison(_same_change(**{field: value}), video_ids=("11",))


@pytest.mark.parametrize("field", HASHES)
def test_well_formed_but_different_model_hashes_remain_unpaired(field):
    rows = _rows()
    rows[1][field] = "d" * 64
    with pytest.raises(ValueError, match="pairing"):
        summarize_comparison(rows, video_ids=("11",))


def test_original_false_completion_example_now_fails():
    rows = _same_change(n_windows=1, evaluated_original_ids=0, all_original_individual_ids=0,
                        original_ids_without_windows=0, segments_total=0, segments_with_windows=0,
                        fps=-1, window_keys_sha256="", histories_sha256="", targets_sha256="")
    with pytest.raises(ValueError):
        summarize_comparison(rows, video_ids=("11",))
