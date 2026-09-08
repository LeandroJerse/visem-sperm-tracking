"""Analytical, source-free tests of individual GT segmentation and eligibility."""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import pytest

from src.detection.base import Detection
from src.detection.io import GroundTruthFrame
from src.prediction.ground_truth import build_individual_ground_truth


def _det(identity="A", class_id=0, *, cx=50.1234567890123, cy=40.0, w=4.0, h=6.0):
    return Detection(cx, cy, w, h, class_id=class_id, object_id=identity)


def _frame(index, *detections, annotated=True):
    return GroundTruthFrame(index, annotated, tuple(detections))


def _build(frames, **kwargs):
    options = {"video_id": "11", "split": "train", "expected_frame_count": len(frames)}
    options.update(kwargs)
    return build_individual_ground_truth(iter(frames), **options)


def _continuous(count, identity="A"):
    return [_frame(index, _det(identity, 0 if index % 2 else 2)) for index in range(count)]


@pytest.mark.parametrize("length,window_count,history_count", [(1, 0, 0), (19, 0, 0),
                                                            (20, 0, 1), (29, 0, 10),
                                                            (30, 1, 11), (31, 2, 12), (40, 11, 21)])
def test_analytic_default_window_boundary(length, window_count, history_count):
    result = _build(_continuous(length))
    assert len(result.segments) == 1  # Short segments are retained.
    assert len(result.windows) == window_count
    assert result.summary["origins_with_complete_history"] == history_count
    assert result.summary["origins_excluded_incomplete_future"] == history_count - window_count
    assert result.summary["excluded_origins_by_end_reason"]["video_end"] == history_count - window_count
    assert result.segments[0] == {
        "video_id": "11", "track_id": "A", "segment_id": "11/A/0", "split": "train",
        "start_frame": 0, "end_frame": length - 1, "observation_count": length,
        "start_reason": "video_start", "end_reason": "video_end", "end_boundary_frame": length,
    }
    for index, window in enumerate(result.windows):
        assert window == {
            "window_id": f"11/A/0/{19 + index}/h20_f10", "video_id": "11", "track_id": "A",
            "segment_id": "11/A/0", "split": "train", "history_start": index,
            "origin_frame": 19 + index, "future_end": 29 + index,
            "history_length": 20, "forecast_horizon": 10,
        }
        assert "future" not in window and "positions" not in window and "flow" not in window


def test_analytic_classes_absence_gaps_and_summary():
    frames = [
        _frame(0, _det("A"), _det("B", 2), _det("C", 1)),
        _frame(1, _det("A", 2), _det("B"), _det("C", 1)),
        _frame(2, _det("A", 1), _det("B")),
        _frame(3, _det("A"), _det("C", 1)),
        _frame(4, annotated=False),
        _frame(5),
        _frame(6, _det("B", 2), _det("A"), _det("C", 1)),
        _frame(7, _det("B", 2), _det("A")),
        _frame(8, _det("A", 1), _det("B", 2)),
        _frame(9, _det("B", 2), _det("A")),
    ]
    result = _build(frames, history_length=2, forecast_horizon=1)
    assert [(s["track_id"], s["start_frame"], s["end_frame"], s["end_reason"])
            for s in result.segments] == [
                ("A", 0, 1, "class_1"), ("B", 0, 2, "id_absent"),
                ("A", 3, 3, "annotation_absent"), ("A", 6, 7, "class_1"),
                ("B", 6, 9, "video_end"), ("A", 9, 9, "video_end"),
            ]
    assert [(w["track_id"], w["origin_frame"]) for w in result.windows] == [("B", 1), ("B", 7), ("B", 8)]
    assert result.summary == {
        "schema_version": 1, "video_id": "11", "split": "train", "expected_frame_count": 10,
        "frames_total": 10, "frames_annotated": 9, "frames_unannotated": 1,
        "frames_annotated_empty": 1, "frames_with_individuals": 8, "frames_with_clusters": 6,
        "frames_cluster_only": 0, "raw_observations": 19, "individual_observations": 13,
        "cluster_observations": 6, "class_observations": {"0": 7, "1": 6, "2": 6},
        "unique_raw_track_ids": 3, "unique_individual_track_ids": 2,
        "segments_total": 6, "segments_with_windows": 2, "segments_without_windows": 4,
        "segment_start_reasons": {"video_start": 2, "annotation_absent": 0, "class_1": 2, "id_absent": 2},
        "segment_end_reasons": {"video_end": 2, "annotation_absent": 1, "class_1": 2, "id_absent": 1},
        "history_length": 2, "forecast_horizon": 1, "stride": 1,
        "origins_with_complete_history": 7, "windows_total": 3,
        "origins_excluded_incomplete_future": 4,
        "excluded_origins_by_end_reason": {"video_end": 1, "annotation_absent": 0, "class_1": 2, "id_absent": 1},
    }
    assert result.frame_status[4] == {"video_id": "11", "frame_index": 4, "annotated": False,
                                      "raw_count": 0, "individual_count": 0, "cluster_count": 0}
    assert result.frame_status[5] == {"video_id": "11", "frame_index": 5, "annotated": True,
                                      "raw_count": 0, "individual_count": 0, "cluster_count": 0}


@pytest.mark.parametrize("break_frame,reason", [(_frame(2), "id_absent"),
                                               (_frame(2, _det("other")), "id_absent"),
                                               (_frame(2, _det("A", 1)), "class_1"),
                                               (_frame(2, annotated=False), "annotation_absent")])
def test_reappearing_id_never_stitches_and_retains_original_identity(break_frame, reason):
    result = _build([_frame(0, _det()), _frame(1, _det()), break_frame,
                     _frame(3, _det()), _frame(4, _det())], history_length=2, forecast_horizon=1)
    segments = [s for s in result.segments if s["track_id"] == "A"]
    assert [(s["segment_id"], s["observation_count"]) for s in segments] == [("11/A/0", 2), ("11/A/3", 2)]
    assert segments[0]["end_reason"] == reason
    assert segments[0]["end_boundary_frame"] == 2
    assert segments[1]["start_reason"] == reason
    assert not result.windows
    assert [r["frame_index"] for r in result.observations if r["track_id"] == "A"] == [0, 1, 3, 4]


def test_initial_missing_annotation_and_cluster_only_frames_are_explicit():
    result = _build([_frame(0, annotated=False), _frame(1, _det()),
                     _frame(2, _det("A", 1)), _frame(3, _det("C", 1)), _frame(4)])
    assert result.segments[0]["start_reason"] == "annotation_absent"
    assert result.summary["frames_cluster_only"] == 2
    assert result.summary["frames_annotated_empty"] == 1
    assert result.summary["raw_observations"] == 3
    assert result.summary["individual_observations"] == 1


def test_individual_inside_another_cluster_is_not_removed():
    frames = [_frame(i, _det("cluster", 1, cx=50, cy=40, w=80, h=60), _det("cell")) for i in range(30)]
    result = _build(frames)
    assert len(result.observations) == 30
    assert len(result.segments) == 1 and len(result.windows) == 1
    assert result.summary["cluster_observations"] == 30
    assert result.summary["unique_raw_track_ids"] == 2


@pytest.mark.parametrize("rows", [[], [_frame(i) for i in range(3)],
                                  [_frame(i, annotated=False) for i in range(3)],
                                  [_frame(i, _det("C", 1)) for i in range(3)]])
def test_no_individuals_never_fabricates_trajectories(rows):
    if not rows:
        with pytest.raises(ValueError, match="complete expected universe"):
            _build(rows, expected_frame_count=1)
        return
    result = _build(rows)
    assert not result.observations and not result.segments and not result.windows
    assert len(result.frame_status) == 3
    assert result.summary["origins_with_complete_history"] == 0
    assert result.summary["origins_excluded_incomplete_future"] == 0


def test_stride_is_anchored_to_each_segment_and_counts_excluded_origins():
    frames = [_frame(0), _frame(1), *[_frame(i, _det()) for i in range(2, 10)]]
    result = _build(frames, history_length=3, forecast_horizon=2, stride=2)
    assert [w["origin_frame"] for w in result.windows] == [4, 6]
    assert [w["history_start"] for w in result.windows] == [2, 4]
    assert result.summary["origins_with_complete_history"] == 3  # 4, 6, 8.
    assert result.summary["origins_excluded_incomplete_future"] == 1


def test_escaped_segment_ids_preserve_distinct_original_ids_and_videos():
    ids = ("a/b", "a%2Fb", "café", "007", 0)
    frames = [_frame(0, *[_det(identity) for identity in ids])]
    first = _build(frames)
    second = _build(frames, video_id="12", split="val")
    assert {s["segment_id"] for s in first.segments} == {
        "11/a%2Fb/0", "11/a%252Fb/0", "11/caf%C3%A9/0", "11/007/0", "11/0/0"}
    assert {s["track_id"] for s in first.segments} == {"a/b", "a%2Fb", "café", "007", "0"}
    assert not ({s["segment_id"] for s in first.segments} & {s["segment_id"] for s in second.segments})
    assert first.summary["unique_individual_track_ids"] == second.summary["unique_individual_track_ids"] == 5


def test_within_frame_order_has_no_effect_on_any_export():
    frames = [_frame(i, _det("Z", i % 3), _det("A"), _det("M", 2)) for i in range(34)]
    reversed_rows = [replace(frame, detections=tuple(reversed(frame.detections))) for frame in frames]
    assert asdict(_build(frames)) == asdict(_build(reversed_rows))


def test_future_extension_preserves_prefix_observations_and_segment_identity():
    prefix = _continuous(23)
    extended = [*prefix, *[_frame(i, _det()) for i in range(23, 34)], _frame(34, _det("A", 1))]
    before = _build(prefix)
    after = _build(extended)
    assert tuple(r for r in after.observations if r["frame_index"] < 23) == before.observations
    assert after.frame_status[:23] == before.frame_status
    for key in ("track_id", "segment_id", "start_frame", "start_reason"):
        assert before.segments[0][key] == after.segments[0][key]
    assert before.segments[0]["end_reason"] == "video_end"
    assert after.segments[0]["end_reason"] == "class_1"
    assert before.summary["windows_total"] == 0
    assert after.summary["windows_total"] == 5


def test_future_geometry_does_not_change_history_or_window_indices():
    frames = _continuous(30)
    changed = [*frames[:20], *[_frame(i, _det(class_id=0 if i % 2 else 2, cx=100 + i * 3, cy=100))
                             for i in range(20, 30)]]
    before, after = _build(frames), _build(changed)
    assert before.observations[:20] == after.observations[:20]
    assert before.windows == after.windows
    assert before.summary == after.summary
    # Losing future eligibility may remove the offline window, never change its past.
    lost = _build([*frames[:20], *[_frame(i, _det("A", 1)) for i in range(20, 30)]])
    assert lost.observations == before.observations[:20]
    assert not lost.windows
    assert lost.summary["origins_excluded_incomplete_future"] == 1


def test_full_precision_detachment_and_no_area_or_speed_filter():
    tiny = _det(w=1e-10, h=1e-10)
    fast = _det(cx=10000.123456789012, cy=9000, w=1000, h=1000)
    frames = [_frame(0, tiny), _frame(1, fast), _frame(2, _det())]
    result = _build(frames, history_length=2, forecast_horizon=1)
    assert len(result.observations) == 3 and len(result.windows) == 1
    assert result.observations[0]["cx"] == tiny.cx
    assert result.observations[1]["cx"] == fast.cx
    assert result.observations[1]["x"] == fast.x
    assert all(type(row[key]) is float for row in result.observations for key in ("cx", "cy", "w", "h", "x", "y"))
    tiny.cx = 999
    assert result.observations[0]["cx"] == 50.1234567890123
    result.observations[1]["cy"] = 1.0
    assert fast.cy == 9000
    json.dumps(asdict(result), allow_nan=False)


def test_does_not_read_even_when_label_paths_are_present(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("GT eligibility must not read files")
    frames = [replace(frame, label_path=Path("nonexistent/label.txt")) for frame in _continuous(30)]
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    result = _build(frames)
    assert result.summary["windows_total"] == 1


@pytest.mark.parametrize("frames,expected", [([_frame(0), _frame(2)], 3),
                                            ([_frame(1), _frame(0)], 2),
                                            ([_frame(0), _frame(0)], 2),
                                            ([_frame(0)], 2),
                                            ([_frame(0), _frame(1)], 1),
                                            ([_frame(-1)], 1),
                                            ([_frame(0.0)], 1),
                                            ([_frame(True)], 1),
                                            ([{"frame_idx": 0}], 1)])
def test_frame_universe_is_explicit_ordered_and_integral(frames, expected):
    with pytest.raises(ValueError):
        _build(frames, expected_frame_count=expected)


@pytest.mark.parametrize("value", [None, 0, 1, "True", "False", np.bool_(True)])
def test_annotation_status_must_be_a_true_bool(value):
    with pytest.raises(ValueError, match="explicit bool"):
        _build([_frame(0, annotated=value)])


def test_unannotated_frame_cannot_contain_objects():
    with pytest.raises(ValueError, match="unannotated frame"):
        _build([_frame(0, _det(), annotated=False)])


@pytest.mark.parametrize("identities", [("A", "A"), (0, "0")])
def test_duplicate_ids_are_rejected_even_across_classes(identities):
    with pytest.raises(ValueError, match="Duplicate GT track_id"):
        _build([_frame(0, _det(identities[0], 0), _det(identities[1], 1))])


@pytest.mark.parametrize("identity", [None, -1, "-1", True, False, 1.0, "", " A", "A B", "A\n", "A\x00"])
def test_invalid_original_identity_is_not_fabricated(identity):
    with pytest.raises(ValueError, match="track_id"):
        _build([_frame(0, _det(identity))])


@pytest.mark.parametrize("class_id", [-1, 3, 0.0, 1.5, "0", None, True, float("nan")])
def test_class_is_strictly_validated(class_id):
    with pytest.raises(ValueError, match="class_id"):
        _build([_frame(0, _det("A", class_id))])


@pytest.mark.parametrize("field,value", [("cx", float("nan")), ("cy", float("inf")),
                                         ("w", float("-inf")), ("h", 0), ("w", -1),
                                         ("cx", -1), ("cy", 1), ("cx", "50"),
                                         ("w", True), ("h", None), ("w", 10000)])
def test_invalid_geometry_fails_for_individuals_and_clusters(field, value):
    for class_id in (0, 1, 2):
        with pytest.raises(ValueError):
            _build([_frame(0, _det(class_id=class_id, **{field: value}))])


@pytest.mark.parametrize("name,value", [("expected_frame_count", 0), ("expected_frame_count", 1.0),
                                        ("expected_frame_count", True), ("history_length", 1),
                                        ("history_length", 2.0), ("forecast_horizon", 0),
                                        ("forecast_horizon", True), ("stride", 0), ("stride", 1.5),
                                        ("video_id", ""), ("video_id", 11), ("video_id", "11/12"),
                                        ("video_id", "11\\12"), ("split", ""), ("split", " train")])
def test_configuration_values_do_not_silently_coerce(name, value):
    with pytest.raises(ValueError):
        _build([_frame(0)], **{name: value})
