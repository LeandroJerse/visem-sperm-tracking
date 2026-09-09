"""Synthetic contract checks; never read a scientific video, label, or run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.flow.base import FlowResult
from src.flow.causal import (
    load_pair, pair_diagnostics, strict_sample, temporal_diagnostics, write_pair,
)


SOURCE = "a" * 64
ESTIMATOR = "b" * 64


def field(shape=(5, 7), vector=(0.0, 0.0), *, valid=True):
    result = np.empty((*shape, 2), dtype=np.float32)
    result[:] = vector
    return FlowResult(result, np.full(shape, valid, dtype=bool))


def archive(tmp_path):
    path = tmp_path / "11_000018_000019.npz"
    record = write_pair(
        path, video_id="11", frame_from=18, frame_to=19,
        source_sha256=SOURCE, estimator_hash=ESTIMATOR,
        forward=field(vector=(1.25, -0.5)), backward=field(vector=(-1.25, 0.5)),
    )
    return path, record


def read(path, record, **changes):
    arguments = dict(video_id="11", frame_from=18, frame_to=19,
                     origin_frame=19, source_sha256=SOURCE, estimator_hash=ESTIMATOR)
    arguments.update(changes)
    return load_pair(path, record, **arguments)


def rewrite(path: Path, record, change):
    """Tamper a disposable synthetic archive while renewing its outer hash."""
    with np.load(path, allow_pickle=False) as stored:
        contents = {name: stored[name].copy() for name in stored.files}
    change(contents)
    np.savez_compressed(path, **contents)
    return {**record, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def alter_metadata(contents, changes):
    metadata = json.loads(str(contents["metadata"]))
    metadata.update(changes)
    contents["metadata"] = np.asarray(json.dumps(metadata))


def test_strict_affine_interpolation_matches_analytic_equation():
    y, x = np.indices((7, 9), dtype=np.float64)
    values = np.stack((2.5 * x - 3.25 * y + 7, -0.125 * x + 4.5 * y - 2), axis=2)
    points = np.array([[0, 0], [8, 6], [1.2, 2.8], [8, 1.123456789], [3.123456789, 6]], dtype=np.float64)
    samples, good = strict_sample(values, np.ones((7, 9), dtype=bool), points)
    expected = np.column_stack((2.5 * points[:, 0] - 3.25 * points[:, 1] + 7,
                                -0.125 * points[:, 0] + 4.5 * points[:, 1] - 2))
    np.testing.assert_allclose(samples, expected, rtol=0, atol=1e-14)
    assert samples.dtype == np.float64
    assert good.tolist() == [True] * len(points)


def test_strict_scalar_empty_and_single_pixel_outputs():
    values = np.array([[42]], dtype=np.uint8)
    sampled, good = strict_sample(values, np.ones((1, 1), dtype=bool), np.array([[0, 0]], dtype=np.float64))
    assert sampled.shape == (1,) and sampled.dtype == np.float64
    assert sampled.tolist() == [42] and good.tolist() == [True]
    sampled, good = strict_sample(values[..., None], np.ones((1, 1), dtype=bool), np.empty((0, 2)))
    assert sampled.shape == (0, 1) and good.shape == (0,)


def test_zero_weight_invalid_nan_corner_does_not_poison_exact_sample():
    values = np.array([[7, 8], [9, np.nan]], dtype=np.float64)
    valid = np.array([[True, True], [True, False]])
    points = np.array([[0, 0], [0.5, 0], [0, 0.5], [1e-10, 1e-10], [0.5, 0.5]], dtype=np.float64)
    sampled, good = strict_sample(values, valid, points)
    np.testing.assert_array_equal(good, [True, True, True, False, False])
    np.testing.assert_array_equal(sampled[:3], [7, 7.5, 8])
    assert np.isnan(sampled[3:]).all()


def test_invalid_corner_with_small_positive_weight_is_rejected():
    values = np.ones((2, 2, 2), dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    valid[0, 1] = False
    sampled, good = strict_sample(values, valid, np.array([[1e-5, 0], [0, 0]]))
    assert good.tolist() == [False, True]
    assert np.isnan(sampled[0]).all()


def test_nonfinite_channel_rejects_entire_sample_even_with_true_mask():
    values = np.ones((2, 2, 2), dtype=np.float32)
    values[0, 0, 1] = np.inf
    sampled, good = strict_sample(values, np.ones((2, 2), dtype=bool), np.array([[0, 0], [1, 1]]))
    assert good.tolist() == [False, True]
    assert np.isnan(sampled[0]).all()


def test_strict_sampling_preserves_float64_coordinate_bounds():
    points = np.array([[2 + 1e-12, 1], [-1e-12, 1], [2, 1], [np.nan, 0], [np.inf, 0], [0, -np.inf]], dtype=np.float64)
    sampled, good = strict_sample(np.ones((3, 3)), np.ones((3, 3), dtype=bool), points)
    assert good.tolist() == [False, False, True, False, False, False]
    assert np.isnan(sampled[~good]).all()


@pytest.mark.parametrize("values,valid,points", [
    (np.empty((0, 2)), np.empty((0, 2), dtype=bool), np.empty((0, 2))),
    (np.ones((2, 2, 0)), np.ones((2, 2), dtype=bool), np.empty((0, 2))),
    (np.ones((2, 2)), np.ones((2, 2), dtype=np.uint8), np.empty((0, 2))),
    (np.ones((2, 2)), np.ones((1, 2), dtype=bool), np.empty((0, 2))),
    (np.ones((2, 2)), np.ones((2, 2), dtype=bool), np.array([0, 0])),
    (np.ones((2, 2), dtype=complex), np.ones((2, 2), dtype=bool), np.array([[0, 0]])),
    (np.ones((2, 2)), np.ones((2, 2), dtype=bool), np.array([["0", "0"]])),
])
def test_strict_sampling_rejects_malformed_contract(values, valid, points):
    with pytest.raises(ValueError):
        strict_sample(values, valid, points)


def test_pair_roundtrip_exact_arrays_and_direction(tmp_path):
    path, record = archive(tmp_path)
    forward, backward = read(path, record)
    assert record["path"] == path.name and record["width"] == 7 and record["height"] == 5
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    np.testing.assert_array_equal(forward.flow, field(vector=(1.25, -0.5)).flow)
    np.testing.assert_array_equal(backward.flow, field(vector=(-1.25, 0.5)).flow)
    assert forward.metadata["direction"] == "forward"
    assert backward.metadata["direction"] == "backward"
    assert forward.metadata["frame_from"] == 18
    assert forward.valid.dtype == bool and forward.flow.dtype == np.float32
    # A later origin may still read a pair already available to it.
    read(path, record, origin_frame=25)


def test_pair_write_never_overwrites(tmp_path):
    path, _ = archive(tmp_path)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        archive(tmp_path)
    assert path.read_bytes() == original


def test_hash_mismatch_is_rejected_before_numpy_parsing(tmp_path, monkeypatch):
    path, record = archive(tmp_path)
    path.write_bytes(path.read_bytes() + b"tampered")
    def forbidden(*args, **kwargs):
        pytest.fail("np.load must not run before hash authentication")
    monkeypatch.setattr(np, "load", forbidden)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        read(path, record)


@pytest.mark.parametrize("changes", [
    {"video_id": "12"}, {"video_id": ""}, {"frame_from": 17, "frame_to": 18},
    {"frame_to": 20}, {"origin_frame": 18}, {"origin_frame": -1},
    {"source_sha256": "c" * 64}, {"estimator_hash": "d" * 64},
    {"frame_from": True}, {"frame_to": 19.0}, {"origin_frame": True},
])
def test_pair_reader_rejects_other_identity_or_future(tmp_path, changes):
    path, record = archive(tmp_path)
    with pytest.raises(ValueError):
        read(path, record, **changes)


@pytest.mark.parametrize("name", ["../pair.npz", "..\\pair.npz", "C:\\pair.npz", "/pair.npz", "pair.npz:stream", "other.npz", "", "pair.npy"])
def test_pair_record_refuses_path_aliases(tmp_path, name):
    path, record = archive(tmp_path)
    with pytest.raises(ValueError):
        read(path, {**record, "path": name})


@pytest.mark.parametrize("changes", [
    {"video_id": "12"}, {"width": 8}, {"height": 6},
    {"frame_from": 17, "frame_to": 18}, {"source_sha256": "c" * 64},
    {"estimator_hash": "d" * 64}, {"schema_version": 2},
    {"schema_version": True}, {"frame_from": 18.0}, {"unregistered": "extra"},
])
def test_archive_metadata_must_match_index_even_with_new_outer_hash(tmp_path, changes):
    path, record = archive(tmp_path)
    changed = rewrite(path, record, lambda contents: alter_metadata(contents, changes))
    with pytest.raises(ValueError):
        read(path, changed)


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(forward=c["forward"].astype(np.float64)),
    lambda c: c.update(backward=c["backward"].astype(np.int16)),
    lambda c: c.update(forward_valid=c["forward_valid"].astype(np.uint8)),
    lambda c: c.update(backward_valid=c["backward_valid"][:-1]),
    lambda c: c.update(forward=c["forward"][..., :1]),
    lambda c: c.update(forward=c["forward"][:-1]),
    lambda c: c.update(metadata=np.array([c["metadata"]])),
    lambda c: c.update(metadata=np.bytes_(str(c["metadata"]))),
    lambda c: c.update(metadata=np.array({"x": 1}, dtype=object)),
    lambda c: c.update(extra=np.ones(1)),
    lambda c: c.pop("backward_valid"),
    lambda c: c["forward"].__setitem__((0, 0, 0), np.nan),
])
def test_archive_raw_dtype_shape_and_validity_are_strict(tmp_path, mutation):
    path, record = archive(tmp_path)
    changed = rewrite(path, record, mutation)
    with pytest.raises(ValueError):
        read(path, changed)


def test_duplicate_metadata_keys_are_not_silently_overridden(tmp_path):
    path, record = archive(tmp_path)
    def duplicate(contents):
        original = str(contents["metadata"])
        contents["metadata"] = np.asarray(original[:-1] + ', "video_id": "11"}')
    changed = rewrite(path, record, duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        read(path, changed)


def test_record_schema_and_types_are_strict(tmp_path):
    path, record = archive(tmp_path)
    for changed in ({**record, "score": 1}, {**record, "width": 7.0},
                    {**record, "sha256": record["sha256"].upper()},
                    {key: value for key, value in record.items() if key != "video_id"}):
        with pytest.raises(ValueError):
            read(path, changed)


def test_nonfinite_invalid_vectors_survive_serialization_without_zero_fill(tmp_path):
    path = tmp_path / "invalid.npz"
    forward, backward = field(), field()
    forward.flow[0, 0] = np.nan
    forward.valid[0, 0] = False
    record = write_pair(path, video_id="11", frame_from=18, frame_to=19,
                        source_sha256=SOURCE, estimator_hash=ESTIMATOR,
                        forward=forward, backward=backward)
    loaded, _ = read(path, record)
    assert not loaded.valid[0, 0] and np.isnan(loaded.flow[0, 0]).all()


def test_writer_rejects_invalid_mutated_flow_before_creating_file(tmp_path):
    forward = field()
    forward.flow[0, 0] = np.inf
    path = tmp_path / "bad.npz"
    with pytest.raises(ValueError, match="nonfinite"):
        write_pair(path, video_id="11", frame_from=0, frame_to=1,
                   source_sha256=SOURCE, estimator_hash=ESTIMATOR,
                   forward=forward, backward=field())
    assert not path.exists()


def test_known_translation_has_zero_warp_and_roundtrip_residual():
    y, x = np.indices((7, 8))
    previous = (5 * x + 3 * y).astype(np.uint8)
    following = np.full_like(previous, 200)
    following[:, 1:] = previous[:, :-1]
    diagnostics = pair_diagnostics(previous, following, field((7, 8), (1, 0)), field((7, 8), (-1, 0)))
    assert diagnostics["photometric_warp_mae"] == 0
    assert diagnostics["forward_backward_mae"] == 0
    assert diagnostics["consistent_fraction"] == 1
    assert diagnostics["photometric_valid_pixels"] == 49
    assert diagnostics["forward_backward_valid_pixels"] == 49
    assert diagnostics["photometric_valid_fraction"] == 7 / 8
    expected_zero = np.abs(previous[:, :-1].astype(np.float64) - following[:, :-1]).mean() / 255
    assert diagnostics["photometric_zero_mae"] == expected_zero
    assert diagnostics["flow_finite_valid_fraction"] == 1


def test_photometric_zero_motion_uses_identical_warped_support():
    previous = np.zeros((2, 3), dtype=np.uint8)
    following = np.array([[0, 0, 255], [0, 0, 255]], dtype=np.uint8)
    result = pair_diagnostics(previous, following, field((2, 3), (1, 0)), field((2, 3), (-1, 0)))
    assert result["photometric_zero_mae"] == 0
    assert result["photometric_warp_mae"] == 0.5
    assert result["photometric_valid_pixels"] == 4


def test_consistency_threshold_does_not_filter_validity_or_photometry():
    previous = np.zeros((5, 7), dtype=np.uint8)
    forward, backward = field(), field(vector=(0.25, 0))
    validity_before = forward.valid.copy(), backward.valid.copy()
    low = pair_diagnostics(previous, previous, forward, backward, threshold=0.2)
    equal = pair_diagnostics(previous, previous, forward, backward, threshold=0.25)
    assert low["consistent_fraction"] == 0 and equal["consistent_fraction"] == 1
    assert low["forward_backward_mae"] == 0.25
    assert low["forward_backward_valid_pixels"] == equal["forward_backward_valid_pixels"] == 35
    np.testing.assert_array_equal(forward.valid, validity_before[0])
    np.testing.assert_array_equal(backward.valid, validity_before[1])


def test_backward_invalid_corner_reduces_only_roundtrip_support():
    previous = np.zeros((5, 7), dtype=np.uint8)
    forward, backward = field(vector=(0.5, 0)), field(vector=(-0.5, 0))
    backward.valid[2, 2] = False
    result = pair_diagnostics(previous, previous, forward, backward)
    assert result["photometric_valid_pixels"] == 30
    assert result["forward_backward_valid_pixels"] == 28


def test_absent_support_is_none_not_zero_error():
    previous = np.zeros((5, 7), dtype=np.uint8)
    result = pair_diagnostics(previous, previous, field(valid=False), field())
    for key in ("photometric_warp_mae", "photometric_zero_mae", "forward_backward_mae", "consistent_fraction"):
        assert result[key] is None
    for key in ("photometric_valid_pixels", "photometric_valid_fraction", "forward_backward_valid_pixels", "forward_backward_valid_fraction", "flow_finite_valid_fraction"):
        assert result[key] == 0
    temporal = temporal_diagnostics(field(valid=False), field())
    assert temporal["advected_temporal_mean_change"] is None
    assert temporal["advected_temporal_p95_change"] is None
    assert temporal["advected_temporal_valid_pixels"] == 0


@pytest.mark.parametrize("threshold", [-0.1, np.inf, np.nan, True])
def test_pair_diagnostics_refuses_invalid_threshold(threshold):
    image = np.zeros((5, 7), dtype=np.uint8)
    with pytest.raises(ValueError):
        pair_diagnostics(image, image, field(), field(), threshold)


def test_pair_diagnostics_requires_exact_uint8_shape():
    image = np.zeros((5, 7), dtype=np.uint8)
    with pytest.raises(ValueError):
        pair_diagnostics(image.astype(np.float32), image, field(), field())
    with pytest.raises(ValueError):
        pair_diagnostics(image, image, field(), field((6, 7)))


def test_temporal_change_advects_second_field_at_subpixel_position():
    y, x = np.indices((5, 7), dtype=np.float32)
    first = field((5, 7), (0.5, 0.25))
    following = FlowResult(np.stack((x + 1, 2 * y - 1), axis=-1))
    result = temporal_diagnostics(first, following)
    # Independent closed-form field: q=(x+.5,y+.25), F_next(q)=(q_x+1,2*q_y-1).
    delta_x = x[:-1, :-1].astype(np.float64) + 1
    delta_y = 2 * y[:-1, :-1].astype(np.float64) - 0.75
    known_change = np.sqrt(delta_x ** 2 + delta_y ** 2)
    assert result["advected_temporal_valid_pixels"] == 24
    assert result["advected_temporal_valid_fraction"] == 24 / 35
    assert result["advected_temporal_mean_change"] == pytest.approx(known_change.mean(), abs=1e-14)
    assert result["advected_temporal_p95_change"] == pytest.approx(np.percentile(known_change, 95), abs=1e-14)


def test_temporal_constant_flow_zero_change_and_invalid_support():
    result = temporal_diagnostics(field(vector=(1, 0)), field(vector=(1, 0)))
    assert result["advected_temporal_mean_change"] == 0
    assert result["advected_temporal_p95_change"] == 0
    assert result["advected_temporal_valid_pixels"] == 30
    second = field(vector=(1, 0))
    second.valid[1, 2] = False
    result = temporal_diagnostics(field(vector=(1, 0)), second)
    assert result["advected_temporal_valid_pixels"] == 29
    with pytest.raises(ValueError):
        temporal_diagnostics(field(), field((6, 7)))
