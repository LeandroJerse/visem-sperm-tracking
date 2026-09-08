"""Analytical tests of position-only batch baselines and dense future metrics."""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from src.prediction.classical.constant_velocity import ConstantVelocityPredictor
from src.prediction.classical.persistence import PersistencePredictor
from src.prediction.metrics import dense_trajectory_metrics, trajectory_metrics


BASELINES = (PersistencePredictor, ConstantVelocityPredictor)
DENSE = range(1, 11)


def _stationary(n=2, time=20):
    centers = np.array([[30.125, 80.25], [41.75, 72.5]], dtype=np.float64)[:n]
    return np.repeat(centers[:, None, :], time, axis=1)


def _linear():
    start = np.array([[30.0, 80.0], [50.0, 20.0]])
    velocity = np.array([[2.0, -0.5], [-0.25, 1.5]])
    positions = start[:, None, :] + np.arange(30)[None, :, None] * velocity[:, None, :]
    return positions[:, :20, :], positions[:, 20:, :], velocity


@pytest.mark.parametrize("baseline", BASELINES)
def test_stationary_baselines_have_exact_zero_dense_error(baseline):
    histories = _stationary()
    predicted = baseline().predict_batch(histories)
    targets = np.repeat(histories[:, -1:, :], 10, axis=1)
    assert predicted.shape == (2, 10, 2) and predicted.dtype == np.float64
    np.testing.assert_array_equal(predicted, targets)
    metrics = dense_trajectory_metrics(predicted, targets, horizons=DENSE)
    assert list(metrics) == ["ade_h1", "fde_h1", "ade_h5", "fde_h5", "ade_h10", "fde_h10"]
    for values in metrics.values():
        assert values.shape == (2,) and values.dtype == np.float64
        np.testing.assert_array_equal(values, [0, 0])


def test_constant_motion_is_exact_and_persistence_error_has_analytic_horizon_mean():
    histories, targets, velocities = _linear()
    constant = ConstantVelocityPredictor().predict_batch(histories)
    np.testing.assert_array_equal(constant, targets)
    constant_metrics = dense_trajectory_metrics(constant, targets, horizons=DENSE)
    assert all(np.array_equal(values, np.zeros(2)) for values in constant_metrics.values())
    persistent = PersistencePredictor().predict_batch(histories)
    metrics = dense_trajectory_metrics(persistent, targets, horizons=DENSE)
    speed = np.hypot(velocities[:, 0], velocities[:, 1])
    for horizon in (1, 5, 10):
        np.testing.assert_allclose(metrics[f"ade_h{horizon}"], speed * (horizon + 1) / 2, rtol=1e-15)
        np.testing.assert_allclose(metrics[f"fde_h{horizon}"], speed * horizon, rtol=1e-15)


def test_acceleration_distinguishes_dense_ade_from_three_sparse_endpoint_errors():
    positions = np.stack([np.arange(30, dtype=np.float64) ** 2, np.zeros(30)], axis=1)[None, :, :]
    predicted = ConstantVelocityPredictor().predict_batch(positions[:, :20, :])
    # Last five observed differences are 29,31,33,35,37: component-wise median 33.
    np.testing.assert_array_equal(predicted[0, :, 0], 361 + 33 * np.arange(1, 11))
    targets = positions[:, 20:, :]
    metrics = dense_trajectory_metrics(predicted, targets, horizons=DENSE)
    assert {name: values.item() for name, values in metrics.items()} == {
        "ade_h1": 6, "fde_h1": 6, "ade_h5": 26, "fde_h5": 50, "ade_h10": 66, "fde_h10": 150,
    }
    sparse = trajectory_metrics(predicted[0, [0, 4, 9]], targets[0, [0, 4, 9]], horizons=(1, 5, 10))
    assert sparse["ade"] == pytest.approx((6 + 50 + 150) / 3)
    assert metrics["ade_h10"].item() != pytest.approx(sparse["ade"])


def test_velocity_uses_five_differences_six_positions_and_component_wise_median():
    differences = np.array([[100, -100]] * 14 + [[1, 10], [2, 50], [3, 40], [4, 30], [5, 20]], dtype=np.float64)
    histories = np.concatenate([np.zeros((1, 2)), np.cumsum(differences, axis=0)])[None, :, :]
    predictor = ConstantVelocityPredictor()
    assert predictor.window == 5 and predictor.method == "median"
    predicted = predictor.predict_batch(histories, (1, 5))
    np.testing.assert_array_equal(predicted[0] - histories[0, -1], [[3, 30], [15, 150]])
    assert not any(np.array_equal(row, [3, 30]) for row in differences[-5:])
    # Earlier finite positions outside the registered window are never differenced.
    changed = histories.copy()
    changed[0, :14, 0] = np.resize([1e308, -1e308], 14)
    np.testing.assert_array_equal(predictor.predict_batch(changed, (1, 5)), predicted)


@pytest.mark.parametrize("method,window,velocity", [("median", None, [3, 4]),
                                                    ("mean", None, [3, 4]),
                                                    ("last", None, [5, 6]),
                                                    ("mean", 2, [4, 5]),
                                                    ("median", 1, [5, 6])])
def test_existing_velocity_options_have_explicit_batch_semantics(method, window, velocity):
    history = np.array([[[0, 0], [1, 2], [4, 6], [9, 12]]], dtype=np.float64)
    prediction = ConstantVelocityPredictor(method=method, window=window).predict_batch(history, (1,))
    np.testing.assert_array_equal(prediction[0, 0], history[0, -1] + velocity)


@pytest.mark.parametrize("baseline", BASELINES)
def test_causal_prefix_ignores_changes_to_future_targets(baseline):
    histories, targets, _ = _linear()
    complete = np.concatenate([histories, targets], axis=1)
    original = baseline().predict_batch(complete[:, :20, :])
    changed = complete.copy()
    changed[:, 20:, :] = -1e100
    np.testing.assert_array_equal(baseline().predict_batch(changed[:, :20, :]), original)
    assert list(inspect.signature(baseline.predict_batch).parameters) == ["self", "histories", "horizons"]
    with pytest.raises(TypeError):
        baseline().predict_batch(histories, future_flow=np.zeros((2, 10, 2)))
    with pytest.raises(TypeError):
        baseline().predict_batch(histories, target=targets)


@pytest.mark.parametrize("baseline", BASELINES)
def test_legacy_float32_api_matches_batch_for_representable_cases(baseline):
    histories, _, _ = _linear()
    requested = (1, 5, 10)
    batch = baseline().predict_batch(histories, requested)
    for index, history in enumerate(histories):
        legacy = baseline().predict(history, requested)
        assert legacy.positions.dtype == np.float32
        np.testing.assert_array_equal(legacy.positions.astype(np.float64), batch[index])


def test_float64_batch_preserves_subpixel_positions_lost_in_legacy_float32():
    base = float(2 ** 25)
    histories = np.stack([base + np.arange(20) * 0.125, np.full(20, base + 0.25)], axis=1)[None, :, :]
    expected_cv = np.stack([base + np.arange(20, 30) * 0.125, np.full(10, base + 0.25)], axis=1)
    batch = ConstantVelocityPredictor().predict_batch(histories)
    np.testing.assert_array_equal(batch[0], expected_cv)
    persistent = PersistencePredictor().predict_batch(histories)
    assert persistent[0, 0, 0] == base + 19 * 0.125
    legacy = ConstantVelocityPredictor().predict(histories[0], tuple(DENSE))
    assert legacy.positions.dtype == np.float32 and batch.dtype == np.float64
    assert not np.array_equal(batch[0], legacy.positions.astype(np.float64))
    target = batch.copy()
    target[:, :, 0] += 0.125
    metrics = dense_trajectory_metrics(batch, target, horizons=DENSE)
    assert all(values.item() == 0.125 for values in metrics.values())


@pytest.mark.parametrize("baseline", BASELINES)
@pytest.mark.parametrize("dtype", [np.int32, np.uint16, np.float32, np.float64])
def test_numeric_arrays_convert_directly_to_float64_and_do_not_mutate_input(baseline, dtype):
    histories = np.arange(2 * 20 * 2).reshape(2, 20, 2).astype(dtype)
    before = histories.copy()
    prediction = baseline().predict_batch(histories)
    assert prediction.dtype == np.float64
    np.testing.assert_array_equal(histories, before)
    assert not np.shares_memory(prediction, histories)


def test_independent_rows_and_chunk_sizes_produce_identical_results():
    histories, targets, _ = _linear()
    for baseline in BASELINES:
        predicted = baseline().predict_batch(histories)
        chunked = np.concatenate([baseline().predict_batch(histories[index:index + 1]) for index in range(2)])
        np.testing.assert_array_equal(chunked, predicted)
        metrics = dense_trajectory_metrics(predicted, targets, horizons=DENSE)
        for index in range(2):
            singleton = dense_trajectory_metrics(predicted[index:index + 1], targets[index:index + 1], horizons=DENSE)
            for name in metrics:
                assert singleton[name].item() == metrics[name][index]


def test_short_history_contract_and_sparse_prediction_horizons():
    one = np.array([[[3.5, 2.0]]], dtype=np.float64)
    np.testing.assert_array_equal(PersistencePredictor().predict_batch(one, (2, 7)), [[[3.5, 2], [3.5, 2]]])
    with pytest.raises(ValueError, match="T>=2"):
        ConstantVelocityPredictor().predict_batch(one)
    two = np.array([[[3.5, 2.0], [4.0, 3.0]]])
    np.testing.assert_array_equal(ConstantVelocityPredictor().predict_batch(two, (2, 7)), [[[5, 5], [7.5, 10]]])


@pytest.mark.parametrize("histories", [None, [[[1, 2], [3, 4]]], np.zeros((0, 20, 2)),
                                       np.zeros((1, 0, 2)), np.zeros((20, 2)), np.zeros((1, 20, 3)),
                                       np.zeros((1, 20, 2, 1)), np.ones((1, 20, 2), dtype=bool),
                                       np.ones((1, 20, 2), dtype=complex), np.ones((1, 20, 2), dtype=object),
                                       np.full((1, 20, 2), "1"), np.full((1, 20, 2), np.nan),
                                       np.full((1, 20, 2), np.inf)])
def test_invalid_history_batches_fail_in_both_baselines(histories):
    for baseline in BASELINES:
        with pytest.raises(ValueError):
            baseline().predict_batch(histories)


def test_masked_positions_are_missing_data_not_silently_usable_coordinates():
    histories = np.ma.array(_stationary(), mask=False)
    histories.mask[0, 0, 0] = True
    for baseline in BASELINES:
        with pytest.raises(ValueError):
            baseline().predict_batch(histories)
    masked_future = np.ma.array(np.zeros((1, 10, 2)), mask=False)
    masked_future.mask[0, 3, 0] = True
    for predicted, targets in ((masked_future, np.zeros((1, 10, 2))),
                               (np.zeros((1, 10, 2)), masked_future)):
        with pytest.raises(ValueError):
            dense_trajectory_metrics(predicted, targets, horizons=DENSE)


@pytest.mark.parametrize("horizons", [None, 1, [], [0], [-1], [1, 1], [5, 1], [1.0],
                                      [1, 2.5], [True], [np.bool_(True)], ["1"], [[1]],
                                      [float("nan")], [2 ** 80]])
def test_batch_horizons_never_silently_sort_deduplicate_or_coerce(horizons):
    for baseline in BASELINES:
        with pytest.raises(ValueError):
            baseline().predict_batch(_stationary(), horizons)


@pytest.mark.parametrize("options", [{"window": 0}, {"window": -1}, {"window": 1.0}, {"window": True},
                                      {"window": "5"}, {"method": "average"}, {"method": None},
                                      {"method": ["median"]}])
def test_invalid_velocity_settings_fail_before_batch_calculation(options):
    with pytest.raises(ValueError):
        ConstantVelocityPredictor(**options).predict_batch(_stationary())


@pytest.mark.parametrize("history", [np.array([[[-1e308, 0], [1e308, 0]]]),
                                     np.array([[[0, 0], [1e308, 0]]])])
def test_velocity_arithmetic_overflow_is_an_error(history):
    with pytest.raises(ValueError, match="overflowed"):
        ConstantVelocityPredictor().predict_batch(history)


def test_dense_metric_horizons_are_explicit_and_complete_not_sparse():
    predicted = np.zeros((1, 10, 2))
    with pytest.raises(TypeError):
        dense_trajectory_metrics(predicted, predicted)
    with pytest.raises(ValueError, match="dense future"):
        dense_trajectory_metrics(predicted[:, [0, 4, 9]], predicted[:, [0, 4, 9]], horizons=(1, 5, 10))
    with pytest.raises(ValueError, match="dense future"):
        dense_trajectory_metrics(predicted, predicted, horizons=range(2, 12))
    with pytest.raises(ValueError, match="dense future"):
        dense_trajectory_metrics(predicted, predicted, horizons=range(1, 10))
    short = dense_trajectory_metrics(predicted[:, :3], predicted[:, :3], horizons=(1, 2, 3), report_horizons=(1, 3))
    assert list(short) == ["ade_h1", "fde_h1", "ade_h3", "fde_h3"]


@pytest.mark.parametrize("name,bad", [("horizons", None), ("horizons", [True] + list(range(2, 11))),
                                     ("horizons", np.arange(1, 11, dtype=float)),
                                     ("horizons", [1, 2, 3, 4, 5, 6, 7, 8, 9, 9]),
                                     ("report_horizons", []), ("report_horizons", [0]),
                                     ("report_horizons", [1, 11]), ("report_horizons", [5, 1]),
                                     ("report_horizons", [1, 1]), ("report_horizons", [True]),
                                     ("report_horizons", [1.0]), ("report_horizons", ["1"]),
                                     ("report_horizons", [float("nan")])])
def test_dense_metric_horizon_types_and_reporting_universe_are_strict(name, bad):
    options = {"horizons": DENSE, "report_horizons": (1, 5, 10), name: bad}
    with pytest.raises(ValueError):
        dense_trajectory_metrics(np.zeros((1, 10, 2)), np.zeros((1, 10, 2)), **options)


@pytest.mark.parametrize("bad", [None, [], np.zeros((0, 10, 2)), np.zeros((1, 0, 2)), np.zeros((10, 2)),
                                 np.zeros((1, 10, 3)), np.ones((1, 10, 2), dtype=bool),
                                 np.ones((1, 10, 2), dtype=complex), np.ones((1, 10, 2), dtype=object),
                                 np.full((1, 10, 2), "0"), np.full((1, 10, 2), np.nan),
                                 np.full((1, 10, 2), np.inf), np.zeros((2, 10, 2))])
def test_dense_metric_inputs_must_be_aligned_finite_real_batches(bad):
    good = np.zeros((1, 10, 2))
    for predicted, targets in ((bad, good), (good, bad)):
        with pytest.raises(ValueError):
            dense_trajectory_metrics(predicted, targets, horizons=DENSE)


def test_dense_metrics_reject_overflow_but_hypot_handles_large_finite_errors():
    with pytest.raises(ValueError, match="overflowed"):
        dense_trajectory_metrics(np.full((1, 10, 2), 1e308), np.full((1, 10, 2), -1e308), horizons=DENSE)
    with pytest.raises(ValueError, match="overflowed"):
        dense_trajectory_metrics(np.full((1, 10, 2), 1e308), np.zeros((1, 10, 2)), horizons=DENSE)
    metrics = dense_trajectory_metrics(np.full((1, 1, 2), 1e200), np.zeros((1, 1, 2)),
                                       horizons=(1,), report_horizons=(1,))
    assert metrics["ade_h1"].item() == pytest.approx(np.sqrt(2) * 1e200)
    assert metrics["fde_h1"].item() == pytest.approx(np.sqrt(2) * 1e200)


def test_dense_metrics_do_not_mutate_or_aggregate_the_input_batch():
    predicted = np.zeros((2, 10, 2), dtype=np.float64)
    targets = np.zeros_like(predicted)
    targets[0, :, 0], targets[1, :, 0] = 1, 9
    before = targets.copy()
    metrics = dense_trajectory_metrics(predicted, targets, horizons=np.arange(1, 11, dtype=np.int64))
    for values in metrics.values():
        np.testing.assert_array_equal(values, [1, 9])
        assert values.dtype == np.float64 and not np.shares_memory(values, targets)
    np.testing.assert_array_equal(targets, before)
    np.testing.assert_array_equal(predicted, np.zeros_like(predicted))
