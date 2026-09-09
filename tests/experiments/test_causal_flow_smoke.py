"""Synthetic causal-boundary and completeness checks; never open real videos."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import cv2
import numpy as np
import pytest
import yaml

from src.experiments import causal_flow_smoke as smoke
from src.flow.base import FlowResult
from src.flow.causal import write_pair
from src.prediction.reference import HistoryBatch, VideoReference


def window_row(track="A", *, origin=19):
    start = origin - 19
    return {"window_id": f"11/{track}/{origin}", "video_id": "11", "track_id": track,
            "segment_id": f"11/{track}/0", "split": "train", "history_start": start,
            "origin_frame": origin, "future_end": origin + 10,
            "history_length": 20, "forecast_horizon": 10}


def history_batch(points=None):
    if points is None:
        points = np.zeros((1, 20, 2), dtype=np.float64)
    rows = tuple(MappingProxyType(window_row(str(i))) for i in range(len(points)))
    return HistoryBatch(np.asarray(points), rows)


@pytest.fixture
def plan_workspace(tmp_path, monkeypatch):
    root = smoke.REPOSITORY_ROOT
    plan_bytes = (root / smoke.PLAN_PATH).read_bytes()
    split_bytes = (root / "configs/protocol/splits.yaml").read_bytes()
    plan = tmp_path / smoke.PLAN_PATH
    plan.parent.mkdir(parents=True)
    plan.write_bytes(plan_bytes)
    split = tmp_path / "configs/protocol/splits.yaml"
    split.parent.mkdir(parents=True)
    split.write_bytes(split_bytes)
    monkeypatch.setattr(smoke, "REPOSITORY_ROOT", tmp_path)
    return plan


def test_plan_reads_only_plan_and_split_metadata(plan_workspace):
    plan, records = smoke.load_smoke_plan(plan_workspace)
    assert plan["protocol"]["video_ids"] == ["11", "12"]
    assert plan["sample"]["origin_frame"] == 19
    assert len(records) == 2
    assert all(record["path"].startswith("configs/") for record in records)


@pytest.mark.parametrize("section,key,value", [
    ("sample", "origin_frame", 20), ("sample", "replacement_origins", True),
    ("run", "split", "test"), ("protocol", "video_ids", ["24", "38"]),
    ("flow", "future_flow_mode", "observed"), ("flow", "mask", "ground_truth"),
    ("diagnostics", "quality_filter", True), ("params", "winsize", 31),
    ("sample", "history_length", 19), ("flow", "coordinate_dtype", "float32"),
])
def test_plan_mutation_fails_without_reading_sources(plan_workspace, monkeypatch, section, key, value):
    plan = yaml.safe_load(plan_workspace.read_text(encoding="utf-8"))
    plan[section][key] = value
    plan_workspace.write_text(yaml.safe_dump(plan), encoding="utf-8")
    monkeypatch.setattr(smoke, "sha256_file", lambda path: pytest.fail("altered plan reached other inputs"))
    with pytest.raises(ValueError, match="registered"):
        smoke.load_smoke_plan(plan_workspace)


def test_duplicate_plan_key_and_noncanonical_path_rejected(plan_workspace):
    with plan_workspace.open("a", encoding="utf-8") as stream:
        stream.write("\nmethod: farneback\n")
    with pytest.raises(ValueError, match="Duplicate"):
        smoke.load_smoke_plan(plan_workspace)
    with pytest.raises(ValueError, match="canonical"):
        smoke.load_smoke_plan(plan_workspace.parent / "other.yaml")


def test_changed_split_rejected(plan_workspace):
    split = smoke.REPOSITORY_ROOT / "configs/protocol/splits.yaml"
    split.write_bytes(split.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="splits changed"):
        smoke.load_smoke_plan(plan_workspace)


def test_reference_interface_never_slices_future_and_is_detached():
    positions = np.column_stack((np.arange(30), np.arange(30) + .123456789012345)).astype(np.float64)
    slices = []

    class HistoryOnlyPositions:
        def __getitem__(self, key):
            assert isinstance(key, slice)
            assert key.start == 0 and key.stop == 20
            slices.append(key)
            return positions[key]

    rows = [window_row(origin=19), window_row(origin=20)]
    reference = VideoReference("11", 49., "{}", {"11/A/0": HistoryOnlyPositions()},
                               {"11/A/0": 0}, tuple(tuple(row.values()) for row in rows))
    batch = reference.history_batch_at_origin(19)
    assert len(slices) == 1
    assert not hasattr(batch, "targets") and not hasattr(batch, "future")
    assert len(batch.window_rows) == 1
    np.testing.assert_array_equal(batch.histories[0], positions[:20])
    positions[:] = -999
    assert batch.histories[0, 0, 1] == .123456789012345
    with pytest.raises(ValueError):
        batch.histories.setflags(write=True)
    with pytest.raises(TypeError):
        batch.window_rows[0]["origin_frame"] = 20
    empty = reference.history_batch_at_origin(100)
    assert empty.histories.shape == (0, 20, 2) and empty.window_rows == ()
    assert len(slices) == 1


@pytest.mark.parametrize("origin", [True, 19.0, -1, "19"])
def test_history_interface_refuses_noninteger_origin(origin):
    reference = VideoReference("11", 49., "{}", {}, {}, ())
    with pytest.raises(ValueError, match="origin_frame"):
        reference.history_batch_at_origin(origin)


def test_select_histories_requests_only_fixed_origin_and_keeps_every_window():
    points = np.zeros((3, 20, 2), dtype=np.float64)
    points[1, :, 0] = -5  # Out-of-image positions are coverage, not selection.
    batch = history_batch(points)
    requested = []
    def read(origin):
        requested.append(origin)
        return batch
    assert smoke.select_histories(SimpleNamespace(video_id="11", history_batch_at_origin=read)) is batch
    assert requested == [19]


@pytest.mark.parametrize("fault", ["empty", "float32", "nonfinite", "other_video", "other_origin", "duplicate"])
def test_select_histories_rejects_ineligible_contract_without_replacement(fault):
    batch = history_batch()
    rows = [dict(row) for row in batch.window_rows]
    points = batch.histories.copy()
    if fault == "empty":
        points, rows = np.empty((0, 20, 2)), []
    elif fault == "float32":
        points = points.astype(np.float32)
    elif fault == "nonfinite":
        points[0, 0, 0] = np.nan
    elif fault == "other_video":
        rows[0]["video_id"] = "12"
    elif fault == "other_origin":
        rows[0]["origin_frame"] = 20
    elif fault == "duplicate":
        points, rows = np.repeat(points, 2, axis=0), rows * 2
    video = SimpleNamespace(video_id="11", history_batch_at_origin=lambda origin: HistoryBatch(points, tuple(rows)))
    with pytest.raises(ValueError):
        smoke.select_histories(video)


SPEC = {"width": 4, "height": 3, "fps": 49., "total_frames": 1470, "sha256": "a" * 64}


class FakeCapture:
    def __init__(self, *, fail_at=None, jump_at=None, bad_frame=None, opened=True, metadata=None):
        self.reads, self.released = 0, False
        self.fail_at, self.jump_at, self.bad_frame, self.opened = fail_at, jump_at, bad_frame, opened
        self.metadata = {cv2.CAP_PROP_FRAME_WIDTH: 4., cv2.CAP_PROP_FRAME_HEIGHT: 3.,
                         cv2.CAP_PROP_FRAME_COUNT: 1470., cv2.CAP_PROP_FPS: 49.}
        self.metadata.update(metadata or {})

    def isOpened(self):
        return self.opened

    def get(self, prop):
        if prop == cv2.CAP_PROP_POS_FRAMES:
            return self.reads + (1 if self.jump_at is not None and self.reads >= self.jump_at else 0)
        return self.metadata[prop]

    def getBackendName(self):
        return "SYNTHETIC"

    def read(self):
        frame = self.reads
        self.reads += 1
        if frame >= 20:
            pytest.fail("decoder requested future frame 20")
        if frame == self.fail_at:
            return False, None
        if frame == 2 and self.bad_frame is not None:
            return True, self.bad_frame
        return True, np.full((3, 4, 3), frame, dtype=np.uint8)

    def release(self):
        self.released = True


def decode_fake(tmp_path, capture, progress=lambda: None):
    return smoke.decode_prefix(tmp_path / "absent.mp4", SPEC, tmp_path / "frames",
                               capture_factory=lambda path: capture, check_progress=progress)


def test_prefix_exactly_twenty_reads_no_seek_or_future_frame(tmp_path):
    capture = FakeCapture()
    frames, index = decode_fake(tmp_path, capture)
    assert capture.reads == 20 and capture.released
    assert len(frames) == len(index["frames"]) == 20
    assert index["last_frame_returned"] == 19 and not index["full_video_decoding_verified"]
    assert index["backend"] == "SYNTHETIC"
    for frame, row in enumerate(index["frames"]):
        path = tmp_path / "frames" / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        np.testing.assert_array_equal(np.load(path, allow_pickle=False), np.full((3, 4), frame, np.uint8))


@pytest.mark.parametrize("failure", [0, 1, 19])
def test_early_decode_failure_preserves_partial_prefix_and_releases(tmp_path, failure):
    capture = FakeCapture(fail_at=failure)
    with pytest.raises(ValueError, match="Incomplete prefix"):
        decode_fake(tmp_path, capture)
    assert capture.released and capture.reads == failure + 1
    assert len(list((tmp_path / "frames").glob("*.npy"))) == failure


@pytest.mark.parametrize("capture", [
    FakeCapture(opened=False), FakeCapture(jump_at=3),
    FakeCapture(bad_frame=np.zeros((3, 4, 3), dtype=np.float32)),
    FakeCapture(bad_frame=np.zeros((3, 5, 3), dtype=np.uint8)),
    FakeCapture(metadata={cv2.CAP_PROP_FPS: np.nan}),
    FakeCapture(metadata={cv2.CAP_PROP_FRAME_COUNT: 100.}),
])
def test_decoder_rejects_open_metadata_positions_and_frames(tmp_path, capture):
    with pytest.raises(ValueError):
        decode_fake(tmp_path, capture)
    assert capture.released


def test_budget_stop_releases_capture_and_keeps_only_completed_frames(tmp_path):
    capture = FakeCapture()
    def budget():
        if capture.reads == 3:
            raise RuntimeError("synthetic budget exceeded")
    with pytest.raises(RuntimeError, match="budget"):
        decode_fake(tmp_path, capture, budget)
    assert capture.reads == 3 and capture.released
    assert len(list((tmp_path / "frames").glob("*.npy"))) == 3


@pytest.fixture
def pair_fixture(tmp_path):
    folder = tmp_path / "pairs"
    folder.mkdir()
    y, x = np.indices((3, 4), dtype=np.float32)
    field = np.stack((x, y), axis=-1)
    valid = np.ones((3, 4), bool)
    rows = []
    for frame in range(19):
        rows.append(write_pair(folder / f"{frame:06d}_{frame+1:06d}.npz", video_id="11",
            frame_from=frame, frame_to=frame + 1, source_sha256=SPEC["sha256"], estimator_hash="b" * 64,
            forward=FlowResult(field, valid), backward=FlowResult(-field, valid)))
    index = {"schema_version": 1, "video_id": "11", "origin_frame": 19,
             "source_sha256": SPEC["sha256"], "estimator_hash": "b" * 64, "pairs": rows}
    return folder, index


def read_index(tmp_path, index):
    path = tmp_path / "pair_index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return smoke.read_pair_index(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                                  video_id="11", source=SPEC, estimator_hash="b" * 64)


def test_index_authentication_and_expected_pairs(tmp_path, pair_fixture):
    _, index = pair_fixture
    rows = read_index(tmp_path, index)
    assert [row["frame_to"] for row in rows] == list(range(1, 20))
    with pytest.raises(ValueError, match="hash"):
        smoke.read_pair_index(tmp_path / "pair_index.json", "0" * 64,
                              video_id="11", source=SPEC, estimator_hash="b" * 64)


@pytest.mark.parametrize("fault", ["missing", "extra", "duplicate", "reordered", "future", "video", "dimensions", "estimator"])
def test_index_rejects_wrong_pair_identity_and_completeness(tmp_path, pair_fixture, fault):
    _, index = pair_fixture
    if fault == "missing":
        index["pairs"].pop()
    elif fault == "extra":
        index["pairs"].append(copy.deepcopy(index["pairs"][-1]))
    elif fault == "duplicate":
        index["pairs"][1] = copy.deepcopy(index["pairs"][0])
    elif fault == "reordered":
        index["pairs"][:2] = index["pairs"][1::-1]
    elif fault == "future":
        index["pairs"][-1]["frame_to"] = 20
    elif fault == "video":
        index["pairs"][0]["video_id"] = "12"
    elif fault == "dimensions":
        index["pairs"][0]["width"] = 5
    elif fault == "estimator":
        index["estimator_hash"] = "c" * 64
    with pytest.raises(ValueError):
        read_index(tmp_path, index)


@pytest.mark.parametrize("fault", ["boolean_schema", "float_origin", "row_extra", "missing_hash", "bad_hash"])
def test_index_schema_is_strict_before_npz_access(tmp_path, pair_fixture, fault):
    _, index = pair_fixture
    if fault == "boolean_schema":
        index["schema_version"] = True
    elif fault == "float_origin":
        index["origin_frame"] = 19.0
    elif fault == "row_extra":
        index["pairs"][0]["unexpected"] = 1
    elif fault == "missing_hash":
        del index["pairs"][0]["sha256"]
    elif fault == "bad_hash":
        index["pairs"][0]["sha256"] = "not-a-hash"
    with pytest.raises(ValueError):
        read_index(tmp_path, index)


def test_duplicate_json_index_key_rejected(tmp_path, pair_fixture):
    _, index = pair_fixture
    text = json.dumps(index).replace('"schema_version": 1', '"schema_version": 0, "schema_version": 1', 1)
    path = tmp_path / "pair_index.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        smoke.read_pair_index(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                              video_id="11", source=SPEC, estimator_hash="b" * 64)


def test_features_use_source_centers_preserve_invalids_and_float64(pair_fixture):
    folder, index = pair_fixture
    points = np.zeros((2, 20, 2), np.float64)
    points[0, :, 0] = np.linspace(.123456789012345, 2.123456789012345, 20)
    points[0, :, 1] = .234567890123456
    points[1, :, 0] = -1.
    batch = history_batch(points)
    features, coverage = smoke.sample_histories(batch, folder, index["pairs"], video_id="11",
                                                source=SPEC, estimator_hash="b" * 64)
    assert len(features) == 38 and len(coverage) == 2
    for frame in range(19):
        good, invalid = features[2 * frame:2 * frame + 2]
        assert good["sample_x"] == points[0, frame, 0]
        assert good["u"] == pytest.approx(points[0, frame, 0], abs=1e-15)
        assert good["v"] == pytest.approx(points[0, frame, 1], abs=1e-15)
        assert good["available_at"] == frame + 1 <= 19
        assert good["pair_sha256"] == index["pairs"][frame]["sha256"]
        assert invalid["valid"] is False and invalid["invalid_reason"] == "outside_image"
        assert invalid["u"] is None and invalid["v"] is None
    assert coverage[0]["valid_samples"] == 19 and coverage[0]["all_history_flow_valid"]
    assert coverage[1]["valid_samples"] == 0 and coverage[1]["invalid_samples"] == 19


def test_invalid_support_is_preserved_without_zero_or_window_removal(tmp_path, pair_fixture):
    folder, index = pair_fixture
    altered = tmp_path / "altered"
    altered.mkdir()
    field = np.ones((3, 4, 2), np.float32)
    valid = np.ones((3, 4), bool)
    valid[0, 1] = False
    records = []
    for frame in range(19):
        records.append(write_pair(altered / f"{frame:06d}_{frame+1:06d}.npz", video_id="11",
            frame_from=frame, frame_to=frame + 1, source_sha256=SPEC["sha256"], estimator_hash="b" * 64,
            forward=FlowResult(field, valid), backward=FlowResult(-field)))
    points = np.zeros((1, 20, 2), np.float64)
    points[0, :, 0] = .000001  # Tiny positive weight on invalid neighbor still invalidates.
    features, coverage = smoke.sample_histories(history_batch(points), altered, records, video_id="11",
                                                source=SPEC, estimator_hash="b" * 64)
    assert len(features) == 19 and len(coverage) == 1
    assert all(row["invalid_reason"] == "invalid_support" and row["u"] is None for row in features)
    assert coverage[0]["invalid_samples"] == 19


def test_feature_consumer_refuses_missing_future_or_corrupt_pair(pair_fixture):
    folder, index = pair_fixture
    options = {"video_id": "11", "source": SPEC, "estimator_hash": "b" * 64}
    with pytest.raises(ValueError, match="every historical pair"):
        smoke.sample_histories(history_batch(), folder, index["pairs"][:-1], **options)
    records = copy.deepcopy(index["pairs"])
    records[-1]["frame_to"] = 20
    with pytest.raises(ValueError, match="temporal/spatial"):
        smoke.sample_histories(history_batch(), folder, records, **options)
    first = folder / index["pairs"][0]["path"]
    first.write_bytes(first.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA256"):
        smoke.sample_histories(history_batch(), folder, index["pairs"], **options)


def summary_fixture():
    batch = history_batch()
    features = [{"valid": False, "invalid_reason": "invalid_support"} for _ in range(19)]
    coverage = [{"valid_samples": 0, "all_history_flow_valid": False}]
    pairs = [{"photometric_warp_mae": None, "photometric_zero_mae": None,
              "forward_backward_mae": None, "consistent_fraction": None,
              "photometric_valid_fraction": 0., "forward_backward_valid_fraction": 0.,
              "flow_finite_valid_fraction": 0., "estimate_seconds": 1., "diagnostics_seconds": .5}
             for _ in range(19)]
    temporal = [{"advected_temporal_mean_change": None, "advected_temporal_p95_change": None,
                 "advected_temporal_valid_fraction": 0.} for _ in range(18)]
    return batch, features, coverage, pairs, temporal


def test_summary_keeps_absent_metrics_and_equal_pair_means():
    values = summary_fixture()
    values[3][0]["photometric_warp_mae"] = 1.
    values[3][1]["photometric_warp_mae"] = 3.
    summary = smoke.summarize_video("11", *values)
    metric = summary["metrics"]["photometric_warp_mae"]
    assert metric == {"mean_equal_pairs_with_support": 2., "pairs_with_support": 2, "total_pairs": 19}
    assert summary["metrics"]["forward_backward_mae"]["mean_equal_pairs_with_support"] is None
    assert summary["invalid_feature_rows"] == 19 and summary["complete_valid_windows"] == 0
    assert summary["directional_fields"] == 38 and summary["temporal_comparisons"] == 18


@pytest.mark.parametrize("fault", ["missing_pair", "missing_temporal", "missing_feature", "wrong_coverage", "nan_metric"])
def test_summary_cannot_complete_partial_or_nonfinite_results(fault):
    batch, features, coverage, pairs, temporal = summary_fixture()
    if fault == "missing_pair":
        pairs.pop()
    elif fault == "missing_temporal":
        temporal.pop()
    elif fault == "missing_feature":
        features.pop()
    elif fault == "wrong_coverage":
        coverage[0]["valid_samples"] = 1
    elif fault == "nan_metric":
        pairs[0]["photometric_warp_mae"] = np.nan
    with pytest.raises(ValueError):
        smoke.summarize_video("11", batch, features, coverage, pairs, temporal)
