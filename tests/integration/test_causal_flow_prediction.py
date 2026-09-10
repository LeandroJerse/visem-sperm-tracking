"""Synthetic causal prediction controls; no scientific data or runs are read."""
from __future__ import annotations

import numpy as np
import pytest

from src.prediction.classical.constant_velocity import ConstantVelocityPredictor
from src.prediction.hybrid.causal_constant_velocity import CausalFlowConstantVelocityPredictor


def batch(count=2, *, start=0):
    differences = np.tile(np.array([1.25, -0.5]), (count, 19, 1))
    positions = np.concatenate((np.zeros((count, 1, 2)), np.cumsum(differences, axis=1)), axis=1)
    frames = np.tile(np.arange(start, start + 20, dtype=np.int64), (count, 1))
    return dict(histories=positions, flow_history=np.zeros((count, 19, 2)),
                flow_validity=np.ones((count, 19), dtype=bool), history_frames=frames,
                flow_pairs=np.stack((frames[:, :-1], frames[:, 1:]), axis=2),
                origin_frames=frames[:, -1].copy())


def predict(inputs):
    return CausalFlowConstantVelocityPredictor().predict_batch(**inputs)


def from_displacements(displacements):
    inputs = batch(len(displacements))
    inputs["histories"] = np.concatenate((np.zeros((len(displacements), 1, 2)),
                                          np.cumsum(displacements, axis=1)), axis=1)
    return inputs


def test_constant_flow_cancels_against_componentwise_median_baseline():
    differences = np.zeros((2, 19, 2))
    differences[0, -5:] = [[1, 20], [5, 2], [3, 15], [9, -4], [-8, 7]]
    differences[1, -5:] = [[-5, 100], [8, 90], [3, -12], [0, 7], [5, 8]]
    inputs = from_displacements(differences)
    inputs["flow_history"][0] = [128.25, -31.5]
    inputs["flow_history"][1] = [-256.5, 17.25]
    expected = ConstantVelocityPredictor().predict_batch(inputs["histories"])
    actual = predict(inputs)
    np.testing.assert_array_equal(actual, expected)
    # Coordinate medians need not coincide with any observed 2-D displacement.
    np.testing.assert_array_equal(actual[:, 0] - inputs["histories"][:, -1], [[3, 7], [3, 8]])


def test_known_changing_flow_and_fixed_residual_predict_known_displacement():
    flow = np.stack((np.arange(19) * 0.5, -np.arange(19) * 0.25), axis=1)
    residual = np.array([1.5, -0.75])
    inputs = from_displacements((flow + residual)[None])
    inputs["flow_history"][0] = flow
    expected = inputs["histories"][:, -1:, :] + np.arange(1, 11)[None, :, None] * (residual + flow[-1])
    np.testing.assert_array_equal(predict(inputs), expected)


def test_last_flow_change_has_horizon_scaled_effect_when_residual_median_is_stable():
    inputs = batch(1)
    unchanged = predict(inputs)
    inputs["flow_history"][0, -1] = [8, -6]
    changed = predict(inputs)
    expected_change = np.arange(1, 11)[None, :, None] * np.array([8, -6])
    np.testing.assert_array_equal(changed - unchanged, expected_change)


def test_older_invalid_nan_flow_is_excluded_from_arithmetic_without_imputation():
    inputs = batch()
    expected = predict(inputs)
    inputs["flow_history"][:, :-5] = np.nan
    inputs["flow_validity"][:, :-5] = False
    actual = predict(inputs)
    np.testing.assert_array_equal(actual, expected)
    assert np.isnan(inputs["flow_history"][:, :-5]).all()
    assert not inputs["flow_validity"][:, :-5].any()


def test_older_valid_finite_flow_does_not_change_prediction():
    inputs = batch()
    expected = predict(inputs)
    inputs["flow_history"][:, :-5] = np.finfo(np.float64).max
    np.testing.assert_array_equal(predict(inputs), expected)


def test_float64_subpixel_steps_remain_visible_at_large_coordinates():
    inputs = batch(1)
    inputs["histories"][0, :, 0] = 2**30 + np.arange(20) / 2**16
    inputs["histories"][0, :, 1] = -2**30 - np.arange(20) / 2**17
    inputs["flow_history"][0] = [2**-18, -2**-19]
    actual = predict(inputs)
    expected = np.column_stack((2**30 + np.arange(20, 30) / 2**16,
                                -2**30 - np.arange(20, 30) / 2**17))[None]
    assert actual.dtype == np.float64
    np.testing.assert_array_equal(actual, expected)
    assert not np.array_equal(actual, actual.astype(np.float32).astype(np.float64))


def test_output_retains_positions_outside_image_bounds():
    inputs = batch(1)
    inputs["histories"][0, :, 0] += 630
    inputs["histories"][0, :, 1] -= 10
    actual = predict(inputs)
    assert (actual[0, :, 0] > 640).all()
    assert (actual[0, :, 1] < 0).all()


def test_windows_with_distinct_origins_are_not_mixed():
    inputs = batch()
    inputs["history_frames"][1] += 150
    inputs["flow_pairs"][1] += 150
    inputs["origin_frames"][1] += 150
    inputs["histories"][1] += [100.25, 201.75]
    predicted = predict(inputs)
    np.testing.assert_array_equal(predicted[1] - predicted[0], np.tile([100.25, 201.75], (10, 1)))


@pytest.mark.parametrize("index", range(14, 19))
def test_any_missing_used_flow_rejects_entire_batch_before_prediction(index):
    inputs = batch()
    inputs["flow_history"][1, index] = np.nan
    inputs["flow_validity"][1, index] = False
    with pytest.raises(ValueError, match="common eligible cohort"):
        predict(inputs)


@pytest.mark.parametrize("field,change", [
    ("history_frames", lambda x: x.__setitem__((0, 4), 3)),
    ("history_frames", lambda x: x.__setitem__((0, 10), 11)),
    ("flow_pairs", lambda x: x.__setitem__((0, 18), [19, 20])),
    ("flow_pairs", lambda x: x.__setitem__((0, 10), [11, 10])),
    ("flow_pairs", lambda x: x.__setitem__((0, 10), [9, 11])),
    ("origin_frames", lambda x: x.__setitem__(0, 20)),
    ("origin_frames", lambda x: x.__setitem__(0, 18)),
])
def test_sparse_or_misaligned_or_future_frames_are_rejected(field, change):
    inputs = batch()
    change(inputs[field])
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("field", ["histories", "flow_history"])
@pytest.mark.parametrize("dtype", [bool, complex, object, str])
def test_positions_and_flow_reject_bool_complex_or_coercible_nonnumeric(field, dtype):
    inputs = batch()
    inputs[field] = inputs[field].astype(dtype)
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("field", ["history_frames", "flow_pairs", "origin_frames"])
@pytest.mark.parametrize("dtype", [bool, float, complex, object])
def test_frame_metadata_requires_actual_integers_without_coercion(field, dtype):
    inputs = batch()
    inputs[field] = inputs[field].astype(dtype)
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("field", ["histories", "flow_history", "flow_validity", "history_frames", "flow_pairs", "origin_frames"])
@pytest.mark.parametrize("mutation", ["shape", "list", "masked"])
def test_inputs_reject_shape_mismatch_lists_and_masked_arrays(field, mutation):
    inputs = batch()
    if mutation == "shape":
        inputs[field] = inputs[field][:1]
    elif mutation == "list":
        inputs[field] = inputs[field].tolist()
    else:
        inputs[field] = np.ma.array(inputs[field], mask=False)
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("field,index", [("histories", (0, 0, 0)), ("histories", (0, -1, 1)),
                                          ("flow_history", (0, 0, 0)), ("flow_history", (0, -1, 1))])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_positions_or_declared_valid_flow_are_rejected(field, index, value):
    inputs = batch()
    inputs[field][index] = value
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("values", [[0, 0], [np.inf, np.nan], [np.nan, -np.inf], [np.nan, 0]])
def test_invalid_old_flow_must_be_two_nans_never_zero_or_infinite(values):
    inputs = batch()
    inputs["flow_history"][0, 0] = values
    inputs["flow_validity"][0, 0] = False
    with pytest.raises(ValueError, match="two NaNs"):
        predict(inputs)


@pytest.mark.parametrize("dtype", [int, float, object])
def test_validity_mask_must_be_boolean(dtype):
    inputs = batch()
    inputs["flow_validity"] = inputs["flow_validity"].astype(dtype)
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("field", ["history_frames", "flow_pairs", "origin_frames"])
def test_unsigned_frame_metadata_cannot_wrap_past_int64(field):
    inputs = batch()
    inputs[field] = inputs[field].astype(np.uint64)
    inputs[field].flat[0] = np.uint64(2**63)
    with pytest.raises(ValueError, match="fitting int64"):
        predict(inputs)


def test_frame_indices_at_int64_limit_do_not_overflow_alignment_check():
    inputs = batch(1)
    inputs["history_frames"][0] = np.iinfo(np.int64).max - np.arange(19, -1, -1)
    inputs["flow_pairs"] = np.stack((inputs["history_frames"][:, :-1], inputs["history_frames"][:, 1:]), axis=2)
    inputs["origin_frames"] = inputs["history_frames"][:, -1].copy()
    assert predict(inputs).shape == (1, 10, 2)


def test_empty_batch_rejected():
    with pytest.raises(ValueError):
        predict(batch(0))


def test_only_five_flow_vectors_cannot_replace_the_full_historical_contract():
    inputs = batch()
    inputs["flow_history"] = inputs["flow_history"][:, -5:]
    inputs["flow_validity"] = inputs["flow_validity"][:, -5:]
    with pytest.raises(ValueError):
        predict(inputs)


@pytest.mark.parametrize("argument,value", [("future_flow", np.zeros((2, 10, 2))),
                                            ("future_flow_mode", "observed"),
                                            ("horizons", [1, 5, 10])])
def test_future_oracle_and_sparse_output_modes_have_no_api(argument, value):
    inputs = batch()
    inputs[argument] = value
    with pytest.raises(TypeError):
        predict(inputs)


@pytest.mark.parametrize("case", ["difference", "residual", "prediction"])
def test_arithmetic_overflow_cannot_produce_a_partial_prediction(case):
    inputs = batch(1)
    maximum = np.finfo(np.float64).max
    if case == "difference":
        inputs["histories"][0, -2:] = [[-maximum, 0], [maximum, 0]]
    elif case == "residual":
        inputs["histories"][0, -1, 0] = maximum
        inputs["flow_history"][0, -1, 0] = -maximum
    else:
        inputs["flow_history"][0, -1] = [maximum, 0]
    with pytest.raises(ValueError, match="overflowed"):
        predict(inputs)


def test_inputs_are_not_modified_by_successful_prediction():
    inputs = batch()
    originals = {key: value.copy() for key, value in inputs.items()}
    predict(inputs)
    for name, original in originals.items():
        np.testing.assert_array_equal(inputs[name], original)
