"""Synthetic unit tests for optical flow and trajectory prediction."""
from __future__ import annotations

import numpy as np
import pytest

from src.flow import (
    FarnebackFlow,
    FlowCache,
    FlowEstimator,
    FlowResult,
    HornSchunckFlow,
    LucasKanadeFlow,
    RobustHybridFlow,
    create_flow_estimator,
    constant_translation_flow,
    endpoint_error,
    forward_backward_consistency,
    make_cache_key,
    photometric_warp_error,
    sample_background_flow,
    sample_flow,
    temporal_flow_change,
    translation_case,
)
from src.prediction import (
    ConstantVelocityPredictor,
    FlowAwareConstantVelocityPredictor,
    FlowAwareKalmanPredictor,
    FlowAwareLSTMPredictor,
    FlowAwareParticleFilterPredictor,
    KalmanPredictor,
    LSTMPredictor,
    PREDICTORS,
    ParticleFilterPredictor,
    PersistencePredictor,
    ade,
    build_windows_by_split,
    create_predictor,
    fde,
    make_trajectory_windows,
    trajectory_metrics,
)


def _constant_flow(height: int, width: int, u: float, v: float) -> FlowResult:
    flow = np.empty((height, width, 2), dtype=np.float32)
    flow[..., 0] = u
    flow[..., 1] = v
    return FlowResult(flow)


def _translated_pair(
    height: int = 64, width: int = 72, dx: int = 3, dy: int = -2
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y, x = np.mgrid[:height, :width]
    previous = ((13 * x + 7 * y + (x * y) % 31) % 256).astype(np.uint8)
    following = np.zeros_like(previous)
    source_x0, source_x1 = max(0, -dx), min(width, width - dx)
    source_y0, source_y1 = max(0, -dy), min(height, height - dy)
    target_x0, target_x1 = source_x0 + dx, source_x1 + dx
    target_y0, target_y1 = source_y0 + dy, source_y1 + dy
    following[target_y0:target_y1, target_x0:target_x1] = previous[
        source_y0:source_y1, source_x0:source_x1
    ]
    valid = np.zeros((height, width), dtype=bool)
    valid[source_y0:source_y1, source_x0:source_x1] = True
    return previous, following, valid


def test_flow_result_rejects_invalid_shape():
    with pytest.raises(ValueError):
        FlowResult(np.zeros((10, 10), dtype=np.float32))


def test_endpoint_error_known_translation():
    predicted = _constant_flow(8, 9, 2.0, -1.0)
    target = _constant_flow(8, 9, 3.0, -1.0)
    assert endpoint_error(predicted, target) == pytest.approx(1.0)


def test_reusable_synthetic_translation_has_exact_ground_truth():
    frame = np.arange(12 * 14, dtype=np.uint8).reshape(12, 14)
    previous, following, truth = translation_case(frame, (2.0, -1.0))
    assert previous.shape == following.shape
    assert np.allclose(truth.flow[truth.valid], [2.0, -1.0])
    assert endpoint_error(truth, constant_translation_flow(frame.shape, (2.0, -1.0))) == 0.0


def test_photometric_warp_known_integer_translation():
    previous, following, valid = _translated_pair()
    truth = _constant_flow(*previous.shape, 3.0, -2.0)
    assert photometric_warp_error(previous, following, truth, valid) < 1e-6


def test_forward_backward_constant_fields_are_consistent_inside_image():
    forward = _constant_flow(12, 14, 2.0, -1.0)
    backward = _constant_flow(12, 14, -2.0, 1.0)
    result = forward_backward_consistency(forward, backward, threshold=1e-5)
    assert result.valid.sum() == (12 - 1) * (14 - 2)
    assert result.fraction_consistent == pytest.approx(1.0)
    assert result.mean_error == pytest.approx(0.0)


def test_temporal_change_is_zero_for_stable_constant_flow():
    first = _constant_flow(12, 14, 1.0, 0.0)
    following = _constant_flow(12, 14, 1.0, 0.0)
    stability = temporal_flow_change(first, following)
    assert stability["mean_change"] == pytest.approx(0.0)
    assert stability["p95_change"] == pytest.approx(0.0)


def test_horn_schunck_identical_frames_return_zero():
    rng = np.random.default_rng(7)
    image = rng.random((24, 28), dtype=np.float32)
    result = HornSchunckFlow(alpha=0.1, iterations=30).estimate(image, image)
    assert np.max(np.abs(result.flow)) < 1e-7
    assert result.valid.all()


def test_horn_schunck_recovers_small_single_scale_translation():
    previous, following, interior = _translated_pair(96, 104, dx=1, dy=1)
    interior[:10] = False
    interior[-10:] = False
    interior[:, :10] = False
    interior[:, -10:] = False
    result = HornSchunckFlow(
        alpha=0.08, iterations=300, tolerance=0.0
    ).estimate(previous, following)
    median = np.median(result.flow[interior], axis=0)
    assert np.allclose(median, [1.0, 1.0], atol=0.3)


def test_flow_sampling_and_features():
    result = _constant_flow(6, 7, 3.0, 4.0)
    sampled = sample_flow(result, np.array([[1.25, 2.5], [-1.0, 0.0]]))
    assert sampled.valid.tolist() == [True, False]
    assert np.allclose(sampled.vectors[0], [3.0, 4.0])
    assert sampled.features[0, 2] == pytest.approx(5.0)


def test_background_sampling_uses_valid_annulus_not_zero_fallback():
    result = _constant_flow(15, 15, 2.0, -3.0)
    result.valid[5:10, 5:10] = False
    sampled = sample_background_flow(
        result, np.array([[7.0, 7.0]]), radius=6, inner_radius=3, min_samples=8
    )
    assert sampled.valid[0]
    assert np.allclose(sampled.vectors[0], [2.0, -3.0])


def test_flow_cache_roundtrip_is_content_addressed(tmp_path):
    cache = FlowCache(tmp_path)
    key = make_cache_key("video11", 10, 11, config={"method": "hs", "alpha": 0.1})
    original = FlowResult(
        _constant_flow(4, 5, 1.0, 2.0).flow,
        confidence=np.full((4, 5), 0.75, dtype=np.float32),
        metadata={"algorithm": "synthetic"},
    )
    path = cache.save(key, original)
    loaded = cache.load(key)
    assert path.is_file() and loaded is not None
    assert np.array_equal(loaded.flow, original.flow)
    assert np.array_equal(loaded.valid, original.valid)
    assert np.allclose(loaded.confidence, original.confidence)
    assert loaded.metadata == original.metadata


class _ConstantEstimator(FlowEstimator):
    def __init__(self, value: tuple[float, float], name: str) -> None:
        self.value = value
        self.name = name

    def estimate(self, previous_frame, next_frame, mask=None):
        result = _constant_flow(*previous_frame.shape[:2], *self.value)
        if mask is not None:
            result.valid &= np.asarray(mask, dtype=bool)
        return result


def test_hybrid_fuses_estimators_without_altering_pure_baselines():
    previous = np.zeros((8, 9), dtype=np.uint8)
    hybrid = RobustHybridFlow(
        base=_ConstantEstimator((1.0, 0.0), "base"),
        refiner=_ConstantEstimator((3.0, 0.0), "refiner"),
        refiner_weight=0.25,
        compensate_global=False,
        reject_inconsistent=False,
    )
    result = hybrid.estimate(previous, previous)
    assert np.allclose(result.flow[..., 0], 1.5)
    assert result.metadata["base"] == "base"
    assert result.metadata["refiner"] == "refiner"


def test_classical_hybrid_recovers_translation_when_compensation_is_disabled():
    pytest.importorskip("cv2")
    previous, following, interior = _translated_pair(96, 104, dx=2, dy=1)
    interior[:10] = False
    interior[-10:] = False
    interior[:, :10] = False
    interior[:, -10:] = False
    estimator = RobustHybridFlow(
        base=FarnebackFlow(levels=3, winsize=25, iterations=7),
        compensate_global=False,
        reject_inconsistent=False,
    )
    result = estimator.estimate(previous, following)
    median = np.median(result.flow[interior], axis=0)
    assert np.allclose(median, [2.0, 1.0], atol=0.75)


def test_flow_registry_keeps_heavy_dependencies_lazy():
    assert isinstance(create_flow_estimator("horn-schunck"), HornSchunckFlow)
    assert create_flow_estimator("raft").name == "raft"
    assert create_predictor("flow-aware-lstm").name == "flow_aware_lstm"


def test_prediction_registry_exposes_each_pure_and_hybrid_algorithm():
    expected = {
        "persistence",
        "constant_velocity",
        "flow_aware_constant_velocity",
        "kalman",
        "flow_aware_kalman",
        "particle_filter",
        "flow_aware_particle_filter",
        "lstm",
        "flow_aware_lstm",
    }
    assert set(PREDICTORS) == expected
    assert LSTMPredictor().uses_flow is False
    assert FlowAwareLSTMPredictor().uses_flow is True


def test_opencv_dense_and_sparse_flows_recover_small_translation():
    pytest.importorskip("cv2")
    previous, following, interior = _translated_pair(96, 104, dx=2, dy=1)
    interior[:10] = False
    interior[-10:] = False
    interior[:, :10] = False
    interior[:, -10:] = False

    dense = FarnebackFlow(levels=3, winsize=25, iterations=7).estimate(
        previous, following
    )
    dense_median = np.median(dense.flow[interior], axis=0)
    assert np.allclose(dense_median, [2.0, 1.0], atol=0.75)

    sparse = LucasKanadeFlow(
        max_corners=500, quality_level=0.001, forward_backward_threshold=2.0
    ).estimate(previous, following)
    assert sparse.valid.sum() >= 10
    sparse_median = np.median(sparse.flow[sparse.valid], axis=0)
    assert np.allclose(sparse_median, [2.0, 1.0], atol=0.75)


def _linear_history(length: int = 20, velocity: tuple[float, float] = (2.0, -0.5)):
    steps = np.arange(length, dtype=np.float32)[:, None]
    return steps * np.asarray(velocity, dtype=np.float32)


def test_persistence_and_constant_velocity_baselines():
    history = _linear_history()
    horizons = (1, 5, 10)
    persistence = PersistencePredictor().predict(history, horizons)
    assert np.allclose(persistence.positions, history[-1])
    constant = ConstantVelocityPredictor().predict(history, horizons)
    expected = history[-1] + np.asarray(horizons)[:, None] * np.array([2.0, -0.5])
    assert np.allclose(constant.positions, expected)


def test_flow_aware_velocity_separates_intrinsic_and_environmental_motion():
    # Observed motion = intrinsic (1, 0) + past flow (0.5, 0).
    history = _linear_history(8, velocity=(1.5, 0.0))
    observed_flow = np.repeat([[0.5, 0.0]], len(history) - 1, axis=0)
    future_flow = np.repeat([[2.0, 0.0]], 4, axis=0)
    prediction = FlowAwareConstantVelocityPredictor().predict(
        history,
        (1, 4),
        flow_history=observed_flow,
        future_flow=future_flow,
    )
    expected = np.stack((history[-1] + [3.0, 0.0], history[-1] + [12.0, 0.0]))
    assert np.allclose(prediction.positions, expected)
    with pytest.raises(ValueError, match="requires flow_history"):
        FlowAwareConstantVelocityPredictor().predict(history, (1,))


def test_kalman_and_flow_aware_kalman_follow_linear_motion():
    history = _linear_history(25, velocity=(1.25, -0.75))
    horizons = (1, 5)
    expected = history[-1] + np.asarray(horizons)[:, None] * [1.25, -0.75]
    prediction = KalmanPredictor(
        process_variance=1e-4, measurement_variance=1e-3
    ).predict(history, horizons)
    assert np.allclose(prediction.positions, expected, atol=0.05)
    assert prediction.covariance.shape == (2, 2, 2)

    flow = np.repeat([[0.25, -0.25]], len(history) - 1, axis=0)
    aware = FlowAwareKalmanPredictor(
        process_variance=1e-4, measurement_variance=1e-3
    ).predict(history, horizons, flow_history=flow, future_flow=flow[:5])
    assert np.allclose(aware.positions, expected, atol=0.05)


def test_particle_filter_is_seeded_and_tracks_linear_motion():
    history = _linear_history(18, velocity=(1.0, 0.25))
    predictor = ParticleFilterPredictor(
        num_particles=600,
        position_process_std=0.03,
        velocity_process_std=0.02,
        measurement_std=0.15,
        initial_position_std=0.2,
        initial_velocity_std=0.2,
        seed=123,
    )
    first = predictor.predict(history, (1, 3))
    second = predictor.predict(history, (1, 3))
    expected = history[-1] + np.asarray([1, 3])[:, None] * [1.0, 0.25]
    assert np.array_equal(first.positions, second.positions)
    assert np.allclose(first.positions, expected, atol=0.35)


def test_flow_aware_particle_filter_requires_and_compensates_flow():
    history = _linear_history(18, velocity=(1.5, 0.0))
    observed_flow = np.repeat([[0.5, 0.0]], len(history) - 1, axis=0)
    future_flow = np.repeat([[2.0, 0.0]], 3, axis=0)
    predictor = FlowAwareParticleFilterPredictor(
        num_particles=800,
        position_process_std=0.02,
        velocity_process_std=0.01,
        measurement_std=0.1,
        initial_position_std=0.1,
        initial_velocity_std=0.1,
        seed=123,
    )
    prediction = predictor.predict(
        history,
        (1, 3),
        flow_history=observed_flow,
        future_flow=future_flow,
    )
    expected = history[-1] + np.asarray([1, 3])[:, None] * [3.0, 0.0]
    assert np.allclose(prediction.positions, expected, atol=0.25)
    with pytest.raises(ValueError, match="requires flow_history"):
        predictor.predict(history, (1,))


def test_windows_never_cross_frame_gaps_or_unannotated_frames():
    frames = np.array([0, 1, 2, 3, 4, 10, 11, 12, 13, 14, 15])
    positions = np.stack((frames, np.zeros_like(frames)), axis=1)
    annotated = np.ones(len(frames), dtype=bool)
    annotated[-1] = False
    windows = make_trajectory_windows(
        positions,
        frames,
        video_id="23",
        track_id="cell-a",
        split="train",
        history_length=3,
        forecast_horizon=2,
        annotated=annotated,
    )
    assert len(windows) == 2
    assert np.array_equal(windows[0].history_frames, [0, 1, 2])
    assert np.array_equal(windows[0].future_frames, [3, 4])
    assert np.array_equal(windows[1].history_frames, [10, 11, 12])
    assert np.array_equal(windows[1].future_frames, [13, 14])
    assert all(15 not in window.future_frames for window in windows)


def test_video_splits_are_exclusive_and_windows_keep_video_split():
    record = {
        "video_id": "11",
        "track_id": "a",
        "frame_ids": np.arange(7),
        "positions": _linear_history(7),
    }
    split_windows = build_windows_by_split(
        [record],
        {"train": ["11"], "validation": ["14"], "test": ["24"]},
        history_length=3,
        forecast_horizon=2,
    )
    assert len(split_windows["train"]) == 3
    assert not split_windows["validation"] and not split_windows["test"]
    assert {window.video_id for window in split_windows["train"]} == {"11"}
    with pytest.raises(ValueError, match="both"):
        build_windows_by_split(
            [record],
            {"train": ["11"], "test": ["11"]},
            history_length=3,
            forecast_horizon=2,
        )


def test_ade_fde_and_horizon_metrics_are_analytically_correct():
    predicted = np.array([[0.0, 0.0], [3.0, 4.0]], dtype=np.float32)
    target = np.zeros_like(predicted)
    assert ade(predicted, target) == pytest.approx(2.5)
    assert fde(predicted, target) == pytest.approx(5.0)
    metrics = trajectory_metrics(predicted, target, horizons=(1, 5))
    assert metrics == {
        "ade": pytest.approx(2.5),
        "fde": pytest.approx(5.0),
        "error_h1": pytest.approx(0.0),
        "error_h5": pytest.approx(5.0),
    }
