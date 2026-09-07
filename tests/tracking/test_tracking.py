"""Synthetic, deterministic tests for the tracking baselines and hybrid."""
from __future__ import annotations

import csv

import numpy as np
import pytest

from src.tracking import (
    TRACKERS,
    AdaptiveFlowSortTracker,
    ByteTrackStyleTracker,
    CentroidGreedyTracker,
    HungarianTracker,
    SortTracker,
    TrackDetection,
    create_tracker,
)
from src.tracking.assignment import _hungarian_numpy, match_cost_matrix
from src.evaluation.tracking import TrackEvalHOTAAdapter
from src.tracking.io import export_motchallenge, export_tracks_csv
from src.tracking.metrics import evaluate_identity_events
from src.tracking.runner import track_sequence


def detection(
    x: float,
    y: float = 20.0,
    *,
    score: float = 1.0,
    object_id: str | None = None,
) -> TrackDetection:
    return TrackDetection(x, y, 8.0, 8.0, score=score, object_id=object_id)


def test_public_factory_contains_every_baseline_and_hybrid():
    assert set(TRACKERS) == {
        "centroid_greedy",
        "hungarian",
        "sort",
        "bytetrack_style",
        "adaptive_flow_sort",
    }
    assert isinstance(create_tracker("hungarian"), HungarianTracker)
    with pytest.raises(ValueError, match="Unknown tracker"):
        create_tracker("not-a-tracker")


def test_detection_validation_and_consecutive_frame_contract():
    with pytest.raises(ValueError):
        TrackDetection(1, 1, 0, 5)
    with pytest.raises(ValueError):
        TrackDetection(1, 1, 5, 5, score=1.2)
    tracker = CentroidGreedyTracker()
    tracker.update([detection(10)], frame_index=0)
    with pytest.raises(ValueError, match="consecutive"):
        tracker.update([detection(11)], frame_index=2)


def test_numpy_hungarian_fallback_solves_rectangular_assignment():
    cost = np.asarray([[4.0, 1.0, 3.0], [2.0, 0.0, 5.0]])
    rows, columns = _hungarian_numpy(cost)
    assert list(zip(rows, columns)) == [(0, 1), (1, 0)]
    matches, unmatched_rows, unmatched_columns = match_cost_matrix(
        np.asarray([[1.0, np.inf], [np.inf, np.inf]]), max_cost=2.0
    )
    assert matches == [(0, 0)]
    assert unmatched_rows == [1]
    assert unmatched_columns == [1]


def test_centroid_greedy_persists_id_across_one_missing_frame_and_resets():
    tracker = CentroidGreedyTracker(max_distance=10, max_age=1)
    first = tracker.update([detection(10)], frame_index=0)
    assert [item.track_id for item in first] == [1]
    assert tracker.update([], frame_index=1) == []
    recovered = tracker.update([detection(13)], frame_index=2)
    assert [item.track_id for item in recovered] == [1]
    tracker.reset()
    restarted = tracker.update([detection(50)], frame_index=0)
    assert [item.track_id for item in restarted] == [1]


def test_centroid_greedy_birth_assigns_new_id_without_changing_existing_id():
    tracker = CentroidGreedyTracker(max_distance=10, max_age=1)
    first = tracker.update([detection(10)], frame_index=0)
    assert [(item.track_id, item.cx) for item in first] == [(1, 10.0)]

    after_birth = tracker.update(
        [detection(11), detection(50)], frame_index=1
    )
    assert {item.track_id: item.cx for item in after_birth} == {1: 11.0, 2: 50.0}


def test_hungarian_is_global_while_centroid_baseline_is_greedy():
    greedy = CentroidGreedyTracker(max_distance=10)
    global_assignment = HungarianTracker(max_distance=10)
    initial = [detection(0), detection(5)]
    greedy.update(initial, frame_index=0)
    global_assignment.update(initial, frame_index=0)
    ambiguous = [detection(4), detection(6)]
    greedy_result = greedy.update(ambiguous, frame_index=1)
    hungarian_result = global_assignment.update(ambiguous, frame_index=1)
    assert {item.track_id: item.cx for item in greedy_result} == {1: 6.0, 2: 4.0}
    assert {item.track_id: item.cx for item in hungarian_result} == {1: 4.0, 2: 6.0}


def test_sort_velocity_model_preserves_ids_through_crossing():
    tracker = SortTracker(
        iou_threshold=0.01,
        max_age=2,
        min_hits=1,
        process_noise=0.2,
        measurement_noise=0.5,
    )
    frames = [(10, 20), (12, 18), (14, 16), (16, 14), (18, 12)]
    result = []
    for frame_index, (rightward, leftward) in enumerate(frames):
        result = tracker.update(
            [detection(rightward), detection(leftward)], frame_index=frame_index
        )
    final_positions = {item.track_id: item.cx for item in result}
    assert final_positions[1] == pytest.approx(18.0, abs=0.2)
    assert final_positions[2] == pytest.approx(12.0, abs=0.2)


def test_sort_can_emit_predicted_lost_state_during_short_disappearance():
    tracker = SortTracker(
        iou_threshold=0.01, max_age=2, min_hits=1, emit_predictions=True
    )
    tracker.update([detection(10)], frame_index=0)
    tracker.update([detection(12)], frame_index=1)
    missing = tracker.update([], frame_index=2)
    assert len(missing) == 1
    assert missing[0].track_id == 1
    assert missing[0].predicted is True
    assert missing[0].state == "lost"
    recovered = tracker.update([detection(16)], frame_index=3)
    assert recovered[0].track_id == 1
    assert recovered[0].predicted is False


def test_bytetrack_low_score_detection_recovers_but_does_not_spawn():
    tracker = ByteTrackStyleTracker(
        high_threshold=0.6,
        low_threshold=0.1,
        iou_threshold=0.1,
        second_iou_threshold=0.05,
        min_hits=1,
    )
    first = tracker.update([detection(10, score=0.9)], frame_index=0)
    assert [item.track_id for item in first] == [1]
    second = tracker.update(
        [detection(11, score=0.3), detection(60, score=0.3)], frame_index=1
    )
    assert [item.track_id for item in second] == [1]
    assert second[0].score == pytest.approx(0.3)
    assert tracker.active_track_ids == (1,)


def test_adaptive_flow_sort_uses_uniform_and_dense_flow_prior():
    uniform = AdaptiveFlowSortTracker(
        base_distance=3,
        min_distance=2,
        min_hits=1,
        flow_weight=1.0,
    )
    uniform.update([detection(10)], frame_index=0)
    moved = uniform.update([detection(20)], frame_index=1, flow=(10.0, 0.0))
    assert [item.track_id for item in moved] == [1]

    dense = AdaptiveFlowSortTracker(
        base_distance=3,
        min_distance=2,
        min_hits=1,
        flow_weight=1.0,
    )
    dense.update([detection(10)], frame_index=0)
    field = np.zeros((50, 50, 2), dtype=float)
    field[..., 0] = 10.0
    moved_dense = dense.update([detection(20)], frame_index=1, flow=field)
    assert [item.track_id for item in moved_dense] == [1]


def test_sequence_runner_requires_one_flow_per_frame():
    tracker = CentroidGreedyTracker()
    results = track_sequence(tracker, [[detection(1)], [], [detection(3)]])
    assert [item.frame_index for item in results] == [0, 2]
    with pytest.raises(ValueError, match="flows ended"):
        track_sequence(tracker, [[detection(1)], [detection(2)]], flows=[None])


def test_identity_metrics_record_switch_and_fragmentation_events():
    ground_truth = {
        frame: [detection(10 + frame, object_id="cell-A")] for frame in range(4)
    }
    predictions = {
        0: [detection(10, object_id="track-1")],
        1: [],
        2: [detection(12, object_id="track-2")],
        3: [detection(13, object_id="track-2")],
    }
    metrics = evaluate_identity_events(ground_truth, predictions)
    assert metrics.matches == 3
    assert metrics.false_negatives == 1
    assert metrics.id_switches == 1
    assert metrics.fragmentations == 1
    assert [event.event for event in metrics.events] == ["id_switch", "fragmentation"]


def test_exports_are_explicit_and_do_not_overwrite(tmp_path):
    tracker = CentroidGreedyTracker()
    results = track_sequence(tracker, [[detection(10)], [detection(11)]])
    csv_path = export_tracks_csv(
        results,
        tmp_path / "tracks.csv",
        video_id="v11",
        annotated_by_frame={0: True, 1: False},
    )
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["video_id"] == "v11"
    assert rows[0]["track_id"] == "1"
    assert [row["annotated"] for row in rows] == ["1", "0"]
    with pytest.raises(FileExistsError):
        export_tracks_csv(results, csv_path, video_id="v11")

    mot_path = export_motchallenge(results, tmp_path / "mot.txt")
    first_columns = mot_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert first_columns[:2] == ["1", "1"]
    assert len(first_columns) == 10


def test_hota_adapter_never_fabricates_internal_hota(tmp_path):
    adapter = TrackEvalHOTAAdapter(tmp_path / "missing-trackeval")
    with pytest.raises(FileNotFoundError, match="TrackEval"):
        adapter.build_command(
            ground_truth_folder=tmp_path / "gt",
            trackers_folder=tmp_path / "trackers",
            benchmark="VISEM",
            split="test",
            tracker_name="sort",
        )
    summary = tmp_path / "summary.txt"
    summary.write_text("HOTA DetA AssA\n0.42 0.5 0.4\n", encoding="utf-8")
    assert TrackEvalHOTAAdapter.parse_summary(summary) == pytest.approx(0.42)
