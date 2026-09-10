"""Synthetic causal deduplication, coverage and bilinear witness checks."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest

from src.flow.causal import strict_sample
from src.flow.compact import (
    SampleValue, attach_samples, build_compact_requests, sampling_witness,
)
from src.prediction.reference import HistoryBatch, WindowBatch


def batch(origin=19, *, video="11", track="a", segment="a/0", shift=0.0):
    frames = np.arange(origin - 19, origin + 1, dtype=np.float64)
    history = np.stack((frames * 0.123456789012345 + shift, frames * -2.5), axis=1)
    row = {
        "window_id": f"{video}/{track}/{segment}/{origin}", "video_id": video,
        "track_id": track, "segment_id": segment, "split": "train",
        "history_start": origin - 19, "origin_frame": origin,
        "future_end": origin + 10, "history_length": 20, "forecast_horizon": 10,
    }
    return HistoryBatch(history[None], (row,))


def alter_window(original, **changes):
    return HistoryBatch(original.histories, ({**original.window_rows[0], **changes},))


def valid_samples(requests, vector=(0.0, 0.0)):
    return {row["sample_id"]: SampleValue(*vector, True, "") for row in requests.samples}


def test_adjacent_windows_deduplicate_sources_but_preserve_all_uses():
    requests = build_compact_requests([batch(), batch(20)], video_id="11")
    assert len(requests.windows) == 2
    assert len(requests.samples) == 20
    assert sum(len(row["sample_ids"]) for row in requests.links) == 38
    assert requests.links[0]["sample_ids"][1:] == requests.links[1]["sample_ids"][:-1]
    assert [row["frame_from"] for row in requests.samples] == list(range(20))
    assert [row["frame_to"] for row in requests.samples] == list(range(1, 21))
    by_id = {row["sample_id"]: row for row in requests.samples}
    assert max(by_id[key]["frame_to"] for key in requests.links[0]["sample_ids"]) == 19
    assert max(by_id[key]["frame_to"] for key in requests.links[1]["sample_ids"]) == 20
    for row in requests.samples:
        key = ["11", "a", "a/0", row["frame_from"]]
        assert row["sample_id"] == hashlib.sha256(json.dumps(
            key, ensure_ascii=True, separators=(",", ":"),
        ).encode()).hexdigest()
        assert row["cx"] == float(row["frame_from"] * 0.123456789012345)


def test_stable_order_does_not_depend_on_batch_iteration_order():
    forward = build_compact_requests([batch(), batch(20)], video_id="11")
    reverse = build_compact_requests([batch(20), batch()], video_id="11")
    assert forward == reverse
    together = HistoryBatch(np.concatenate((batch(track="z", segment="z/0").histories,
                                            batch().histories)),
                            (batch(track="z", segment="z/0").window_rows[0], batch().window_rows[0]))
    requests = build_compact_requests([together], video_id="11")
    assert [row["track_id"] for row in requests.windows] == ["a", "z"]
    assert [(row["frame_from"], row["track_id"]) for row in requests.samples[:4]] == [
        (0, "a"), (0, "z"), (1, "a"), (1, "z"),
    ]


def test_segments_never_join_even_for_same_original_id_and_coordinates():
    requests = build_compact_requests([batch(), batch(segment="a/1")], video_id="11")
    assert len(requests.samples) == 38
    assert not set(requests.links[0]["sample_ids"]) & set(requests.links[1]["sample_ids"])


def test_empty_batches_keep_explicit_video_and_do_not_replace_origin():
    empty = HistoryBatch(np.empty((0, 20, 2), dtype=np.float64), ())
    result = build_compact_requests([empty], video_id="11")
    assert result.video_id == "11" and result.samples == result.windows == result.links == ()
    assert attach_samples(result, {}).samples == ()
    assert attach_samples(result, {}).coverage == ()


def test_detached_output_cannot_be_changed_by_mutating_inputs():
    original = batch()
    result = build_compact_requests([original], video_id="11")
    original.histories[:] = 100
    original.window_rows[0]["track_id"] = "changed"
    assert result.samples[0]["cx"] == 0
    assert result.windows[0]["track_id"] == "a"
    with pytest.raises(TypeError):
        result.samples[0]["cx"] = 10
    with pytest.raises(TypeError):
        result.links[0]["sample_ids"][0] = "changed"


@pytest.mark.parametrize("change", [
    {"video_id": "12"}, {"split": "val"}, {"split": "test"},
    {"history_length": 19}, {"history_length": True}, {"forecast_horizon": 9},
    {"history_start": 1}, {"history_start": -1}, {"origin_frame": 20},
    {"future_end": 30}, {"origin_frame": 19.0}, {"track_id": ""},
    {"segment_id": "has spaces"}, {"window_id": "-1"}, {"origin_frame": "19"},
])
def test_rejects_inconsistent_window_metadata(change):
    with pytest.raises(ValueError):
        build_compact_requests([alter_window(batch(), **change)], video_id="11")


@pytest.mark.parametrize("change", ["float32", "shape", "nan", "inf", "not_array"])
def test_rejects_non_float64_or_malformed_histories(change):
    original = batch()
    histories = original.histories.copy()
    if change == "float32":
        histories = histories.astype(np.float32)
    elif change == "shape":
        histories = histories[:, :19]
    elif change == "nan":
        histories[0, 2, 0] = np.nan
    elif change == "inf":
        histories[0, 19, 1] = np.inf
    elif change == "not_array":
        histories = histories.tolist()
    with pytest.raises(ValueError):
        build_compact_requests([HistoryBatch(histories, original.window_rows)], video_id="11")


def test_rejects_target_bearing_batch_and_unexpected_schema():
    original = batch()
    with pytest.raises(ValueError, match="without targets"):
        build_compact_requests([WindowBatch(original.histories, np.zeros((1, 10, 2)),
                                            original.window_rows)], video_id="11")
    with pytest.raises(ValueError, match="schema"):
        build_compact_requests([alter_window(original, future_x=999)], video_id="11")
    row = dict(original.window_rows[0])
    del row["future_end"]
    with pytest.raises(ValueError, match="schema"):
        build_compact_requests([HistoryBatch(original.histories, (row,))], video_id="11")


def test_streaming_batches_may_mix_origins_without_changing_the_union():
    mixed = HistoryBatch(np.concatenate((batch().histories, batch(20).histories)),
                         (batch().window_rows[0], batch(20).window_rows[0]))
    assert build_compact_requests([mixed], video_id="11") == build_compact_requests(
        [batch(), batch(20)], video_id="11",
    )


def test_rejects_duplicate_ids_and_renamed_duplicate_windows():
    with pytest.raises(ValueError, match="Duplicate window_id"):
        build_compact_requests([batch(), batch()], video_id="11")
    with pytest.raises(ValueError, match="another name"):
        build_compact_requests([batch(), alter_window(batch(), window_id="renamed")], video_id="11")


def test_rejects_conflicting_segment_owner():
    with pytest.raises(ValueError, match="conflicting original IDs"):
        build_compact_requests([batch(), batch(track="b")], video_id="11")


@pytest.mark.parametrize("offset", [0, 18])
def test_conflicting_overlap_including_previous_origin_is_rejected(offset):
    latter = batch(20)
    latter.histories[0, offset, 0] = np.nextafter(latter.histories[0, offset, 0], np.inf)
    with pytest.raises(ValueError, match="Conflicting source coordinates"):
        build_compact_requests([batch(), latter], video_id="11")


def test_valid_zero_remains_valid_zero_and_all_windows_remain_present():
    requests = build_compact_requests([batch(), batch(20)], video_id="11")
    result = attach_samples(requests, valid_samples(requests))
    assert len(result.samples) == 20 and len(result.coverage) == 2
    assert all(row["u"] == row["v"] == 0 and row["valid"] and row["reason"] == ""
               for row in result.samples)
    assert all(row["valid_history19"] == 19 and row["valid_last5"] == 5
               and row["eligible_last5"] for row in result.coverage)


def test_invalid_older_history_does_not_exclude_last_five_predictor():
    requests = build_compact_requests([batch()], video_id="11")
    sampled = valid_samples(requests)
    sampled[requests.samples[13]["sample_id"]] = SampleValue(np.nan, np.nan, False, "outside_image")
    result = attach_samples(requests, sampled)
    assert len(result.samples) == 19
    assert np.isnan(result.samples[13]["u"]) and not result.samples[13]["valid"]
    row = result.coverage[0]
    assert row["valid_history19"] == 18 and row["valid_last5"] == 5 and row["eligible_last5"]
    assert row["invalid_reasons_history19"] == (("outside_image", 1),)
    assert row["invalid_reasons_last5"] == ()


@pytest.mark.parametrize("offset", [14, 15, 16, 17, 18])
def test_any_invalid_last_five_sample_excludes_window_but_keeps_it(offset):
    requests = build_compact_requests([batch()], video_id="11")
    sampled = valid_samples(requests)
    sampled[requests.samples[offset]["sample_id"]] = SampleValue(np.nan, np.nan, False, "invalid_corner")
    result = attach_samples(requests, sampled)
    row = result.coverage[0]
    assert row["valid_history19"] == 18 and row["valid_last5"] == 4 and not row["eligible_last5"]
    assert row["invalid_reasons_last5"] == (("invalid_corner", 1),)


@pytest.mark.parametrize("value", [
    SampleValue(np.nan, 0, True, ""), SampleValue(0, np.inf, True, ""),
    SampleValue(0, 0, True, "invalid"), SampleValue(0, 0, False, "absent"),
    SampleValue(np.nan, np.nan, False, ""), SampleValue(np.nan, np.inf, False, "absent"),
    SampleValue(np.nan, np.nan, False, "line\nbreak"), SampleValue(0, 0, 1, ""),
    SampleValue(True, 0, True, ""), SampleValue("0", 0, True, ""),
])
def test_rejects_imputed_or_ambiguous_sample_validity(value):
    requests = build_compact_requests([batch()], video_id="11")
    sampled = valid_samples(requests)
    sampled[requests.samples[0]["sample_id"]] = value
    with pytest.raises(ValueError):
        attach_samples(requests, sampled)


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_exact_sample_id_coverage_required(change):
    requests = build_compact_requests([batch()], video_id="11")
    sampled = valid_samples(requests)
    if change == "missing":
        sampled.pop(requests.samples[0]["sample_id"])
    else:
        sampled["unknown"] = SampleValue(0, 0, True, "")
    with pytest.raises(ValueError, match="missing or extra"):
        attach_samples(requests, sampled)


def test_forged_link_cannot_shift_or_mix_causal_pairs():
    requests = build_compact_requests([batch(), batch(20)], video_id="11")
    shifted = replace(requests, links=(
        {"window_id": requests.windows[0]["window_id"], "sample_ids": requests.links[1]["sample_ids"]},
        requests.links[1],
    ))
    with pytest.raises(ValueError, match="consecutive causal pairs"):
        attach_samples(shifted, valid_samples(requests))


def test_witness_preserves_order_borders_and_float32_corner_values():
    field = np.arange(3 * 4 * 2, dtype=np.float32).reshape(3, 4, 2)
    valid = np.ones((3, 4), dtype=bool)
    points = np.array([[1.25, 0.5], [3, 2], [3, 0.25], [0, 0]], dtype=np.float64)
    result = sampling_witness(field, valid, points)
    assert result["corners_xy"].dtype == np.int64
    assert result["corner_uv"].dtype == np.float32
    assert result["corner_valid"].dtype == result["inside"].dtype == bool
    assert result["inside"].tolist() == [True] * 4
    np.testing.assert_array_equal(result["corners_xy"], [
        [[1, 0], [2, 0], [1, 1], [2, 1]], [[3, 2]] * 4,
        [[3, 0], [3, 0], [3, 1], [3, 1]], [[0, 0], [1, 0], [0, 1], [1, 1]],
    ])
    for i in range(len(points)):
        for k, (x, y) in enumerate(result["corners_xy"][i]):
            np.testing.assert_array_equal(result["corner_uv"][i, k], field[y, x])
    field[:] = -10
    valid[:] = False
    assert result["corner_uv"][0, 0, 0] == 2 and result["corner_valid"].all()


def test_witness_keeps_nan_zero_weight_corners_for_independent_review():
    field = np.full((2, 2, 2), np.nan, dtype=np.float32)
    field[0, 0] = [3, -2]
    valid = np.array([[True, False], [False, False]])
    points = np.array([[0, 0], [0.5, 0.5]], dtype=np.float64)
    result = sampling_witness(field, valid, points)
    assert result["corner_valid"].tolist() == [[True, False, False, False]] * 2
    assert np.isnan(result["corner_uv"][:, 1:]).all()
    vectors, good = strict_sample(field, valid, points)
    assert good.tolist() == [True, False]
    assert vectors[0].tolist() == [3, -2]


def test_witness_outside_nonfinite_and_empty_points_have_explicit_sentinels():
    field = np.ones((2, 2, 2), dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    points = np.array([[-0.01, 0], [0, -1], [1.01, 1], [1, 1.01], [np.nan, 0],
                       [0, np.inf]], dtype=np.float64)
    result = sampling_witness(field, valid, points)
    assert not result["inside"].any() and not result["corner_valid"].any()
    assert (result["corners_xy"] == -1).all() and np.isnan(result["corner_uv"]).all()
    result = sampling_witness(field, valid, np.empty((0, 2), dtype=np.float64))
    assert result["corners_xy"].shape == result["corner_uv"].shape == (0, 4, 2)
    assert result["corner_valid"].shape == (0, 4) and result["inside"].shape == (0,)


def test_witness_single_pixel_has_four_repeated_coordinates():
    result = sampling_witness(np.array([[[4, 5]]], dtype=np.float32), np.ones((1, 1), dtype=bool),
                              np.array([[0, 0]], dtype=np.float64))
    assert result["corners_xy"].tolist() == [[[0, 0]] * 4]
    assert result["corner_uv"].tolist() == [[[4, 5]] * 4]


def test_witness_retains_nonfinite_corner_even_when_mask_declares_valid():
    field = np.ones((2, 2, 2), dtype=np.float32)
    field[1, 1, 1] = np.nan
    valid = np.ones((2, 2), dtype=bool)
    points = np.array([[0.5, 0.5], [0, 0]], dtype=np.float64)
    result = sampling_witness(field, valid, points)
    assert result["corner_valid"].all() and np.isnan(result["corner_uv"][:, 3, 1]).all()
    _, good = strict_sample(field, valid, points)
    assert good.tolist() == [False, True]


def test_witness_can_reconstruct_every_sample_without_dense_field():
    random = np.random.default_rng(42)
    field = random.normal(size=(8, 9, 2)).astype(np.float32)
    valid = np.ones((8, 9), dtype=bool)
    valid[2:4, 2:4] = False
    points = np.vstack((random.uniform([0, 0], [8, 7], size=(40, 2)),
                        [[8, 7], [0, 0], [8, 1.25], [2, 1], [0, 7]]))
    witness = sampling_witness(field, valid, points)
    actual, good = strict_sample(field, valid, points)
    for i, point in enumerate(points):
        x, y = point
        wx, wy = x - np.floor(x), y - np.floor(y)
        weights = np.array([(1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy])
        active = weights > 0
        expected_valid = witness["corner_valid"][i, active].all()
        assert bool(good[i]) == bool(expected_valid)
        if expected_valid:
            recovered = weights[active] @ witness["corner_uv"][i, active].astype(np.float64)
            np.testing.assert_allclose(actual[i], recovered, rtol=0, atol=5e-16)
        else:
            assert np.isnan(actual[i]).all()


@pytest.mark.parametrize("change", ["field_dtype", "field_shape", "field_empty", "valid_dtype",
                                    "valid_shape", "points_dtype", "points_shape"])
def test_witness_rejects_ambiguous_shapes_and_dtypes(change):
    field = np.ones((2, 2, 2), dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    points = np.zeros((1, 2), dtype=np.float64)
    if change == "field_dtype":
        field = field.astype(np.float64)
    elif change == "field_shape":
        field = field[:, :, 0]
    elif change == "field_empty":
        field = field[:0]
    elif change == "valid_dtype":
        valid = valid.astype(np.uint8)
    elif change == "valid_shape":
        valid = valid[:1]
    elif change == "points_dtype":
        points = points.astype(np.float32)
    elif change == "points_shape":
        points = points[:, 0]
    with pytest.raises(ValueError):
        sampling_witness(field, valid, points)
