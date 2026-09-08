"""Analytical aggregation and failure boundaries for the registered baseline run."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import yaml

from src.experiments import prediction_baselines as pb


@pytest.fixture
def plan_workspace(tmp_path, monkeypatch):
    real_root = pb.REPOSITORY_ROOT
    plan = (real_root / pb.PLAN_PATH).read_bytes()
    splits = (real_root / "configs/protocol/splits.yaml").read_bytes()
    path = tmp_path / pb.PLAN_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(plan)
    (path.parent / "splits.yaml").write_bytes(splits)
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    return path


def test_registered_plan_and_metadata_only(plan_workspace):
    plan, refs = pb.load_baseline_plan(plan_workspace)
    assert plan["protocol"]["expected_total_windows"] == 343776
    assert [row["params"] for row in plan["models"]] == [{}, {"window": 5, "method": "median"}]
    assert len(refs) == 2
    assert all("data/sources" not in ref["path"] for ref in refs)


@pytest.mark.parametrize("section,key,value", [
    ("run", "split", "test"), ("run", "batch_size", 128),
    ("evaluation", "predicted_horizons", [1, 5, 10]),
    ("evaluation", "ranking_or_promotion", 0), ("inputs", "history_length", 19),
    ("inputs", "clip_predictions_to_image", True),
    ("protocol", "video_ids", [24]), ("reference", "manifest", "data/sources/private.txt"),
])
def test_plan_changes_fail_before_parent_access(plan_workspace, section, key, value):
    plan = yaml.safe_load(plan_workspace.read_text())
    plan[section][key] = value
    plan_workspace.write_text(yaml.safe_dump(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="registered"):
        pb.load_baseline_plan(plan_workspace)


def test_duplicate_plan_key_and_noncanonical_path(plan_workspace):
    with plan_workspace.open("a", encoding="utf-8") as stream:
        stream.write("\nmethod: prediction_baselines\n")
    with pytest.raises(ValueError, match="Duplicate"):
        pb.load_baseline_plan(plan_workspace)
    with pytest.raises(ValueError, match="canonical"):
        pb.load_baseline_plan(plan_workspace.parent / "absent.yaml")


def test_split_hash_change_rejected(plan_workspace):
    (plan_workspace.parent / "splits.yaml").write_text("changed")
    with pytest.raises(ValueError, match="split metadata"):
        pb.load_baseline_plan(plan_workspace)


def video_fixture(target_x=(1., 3., 5., 9.)):
    # Abstract batches isolate aggregation/export; source continuity is tested
    # separately in test_prediction_reference, using real reference contracts.
    identities = ("A", "A", "A", "B")
    segments = ("11/A/0", "11/A/0", "11/A/30", "11/B/0")
    rows = tuple({"window_id": f"synthetic/{i}", "video_id": "11", "track_id": identity,
                  "segment_id": segment, "split": "train", "history_start": i,
                  "origin_frame": i + 19, "future_end": i + 29}
                 for i, (identity, segment) in enumerate(zip(identities, segments)))
    histories = np.zeros((4, 20, 2), dtype=np.float64)
    targets = np.zeros((4, 10, 2), dtype=np.float64)
    targets[:, :, 0] = np.asarray(target_x)[:, None]
    histories.setflags(write=False)
    targets.setflags(write=False)
    def batches(batch_size=512):
        for start in range(0, 4, batch_size):
            end = start + batch_size
            yield SimpleNamespace(histories=histories[start:end], targets=targets[start:end],
                                  window_rows=rows[start:end])
    keys = hashlib.sha256()
    for row in rows:
        keys.update(json.dumps([row[k] for k in pb.KEY_FIELDS], ensure_ascii=True,
                               separators=(",", ":")).encode() + b"\n")
    return SimpleNamespace(video_id="11", fps=49., iter_batches=batches,
        window_keys_sha256=keys.hexdigest(), track_ids_with_windows=("A", "B"),
        summary={"windows_total": 4, "unique_individual_track_ids": 3,
                 "segments_total": 4, "segments_with_windows": 3})


def run_model(tmp_path, monkeypatch, *, batch_size=2, target_x=(1., 3., 5., 9.), method="persistence", expected=4):
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    config = {"configuration_id": method, "method": "persistence" if method == "persistence" else "constant_velocity",
              "params": {} if method == "persistence" else {"window": 5, "method": "median"}}
    return pb.evaluate_video_model(video_fixture(target_x), config, tmp_path / method,
                                  batch_size=batch_size, expected_windows=expected)


def test_original_id_weighting_differs_from_windows_and_segments(tmp_path, monkeypatch):
    row, artifacts = run_model(tmp_path, monkeypatch)
    # A has errors1,3,5 across two segments =>3; B has9 => video6.
    assert row["ade_h10"] == 6.
    assert row["window_weighted_ade_h10"] == 4.5
    assert row["evaluated_original_ids"] == 2
    assert row["original_ids_without_windows"] == 1
    assert row["history_span_seconds"] == 19 / 49
    assert row["horizon_seconds_h10"] == 10 / 49
    assert len(artifacts) == 4
    with (tmp_path / "persistence/track_metrics.csv").open(newline="") as stream:
        tracks = list(csv.DictReader(stream))
    assert tracks[0]["segments_with_windows"] == "2"
    assert tracks[0]["n_windows"] == "3"
    assert float(tracks[0]["ade_h10"]) == 3.


def test_dense_csv_has_every_step_and_matching_keys(tmp_path, monkeypatch):
    run_model(tmp_path, monkeypatch)
    tables = []
    for name in ("predictions.csv", "window_metrics.csv"):
        with (tmp_path / "persistence" / name).open(newline="") as stream:
            tables.append(list(csv.DictReader(stream)))
    predictions, metrics = tables
    assert len(predictions) == len(metrics) == 4
    assert list(predictions[0]) == pb.PREDICTION_FIELDS
    for pred, metric in zip(predictions, metrics):
        assert {k: pred[k] for k in pb.KEY_FIELDS} == {k: metric[k] for k in pb.KEY_FIELDS}
        assert all(float(pred[f"cx_h{h}"]) == 0 for h in range(1, 11))
        assert float(metric["ade_h1"]) == float(metric["fde_h1"])


def test_subpixel_csv_round_trip_keeps_processing_precision(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    video = video_fixture()
    original = video.iter_batches
    last = np.array([10.123456789012345, 20.9876543210123], dtype=np.float64)
    def batches(batch_size=512):
        for batch in original(batch_size=batch_size):
            history = np.broadcast_to(last, batch.histories.shape).copy()
            history.setflags(write=False)
            yield SimpleNamespace(histories=history, targets=batch.targets, window_rows=batch.window_rows)
    video.iter_batches = batches
    folder = tmp_path / "precision"
    pb.evaluate_video_model(video, {"configuration_id": "persistence", "method": "persistence", "params": {}},
                            folder, batch_size=2, expected_windows=4)
    with (folder / "predictions.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert all(float(row[f"cx_h{h}"]) == last[0] and float(row[f"cy_h{h}"]) == last[1]
               for row in rows for h in range(1, 11))


def test_constant_velocity_does_not_clip_to_image_bounds():
    history = np.stack([np.arange(19, -1, -1), np.arange(460, 480)], axis=1)[None].astype(np.float64)
    predicted = pb.ConstantVelocityPredictor().predict_batch(history, horizons=pb.HORIZONS)
    np.testing.assert_array_equal(predicted[0, 0], [-1., 480.])
    np.testing.assert_array_equal(predicted[0, 9], [-10., 489.])


def test_future_targets_cannot_change_exported_predictions(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    original_predict = pb.PersistencePredictor.predict_batch
    calls = []
    def spy(self, histories, *, horizons):
        assert histories.shape[1:] == (20, 2)
        assert not histories.flags.writeable
        calls.append(histories.copy())
        return original_predict(self, histories, horizons)
    monkeypatch.setattr(pb.PersistencePredictor, "predict_batch", spy)
    results = []
    for name, target in (("first", (1., 3., 5., 9.)), ("second", (100., 300., 500., 900.))):
        directory = tmp_path / name
        row, _ = pb.evaluate_video_model(video_fixture(target),
            {"configuration_id": "persistence", "method": "persistence", "params": {}},
            directory, batch_size=2, expected_windows=4)
        results.append((row, (directory / "predictions.csv").read_bytes()))
    assert results[0][1] == results[1][1]
    assert results[0][0]["histories_sha256"] == results[1][0]["histories_sha256"]
    assert results[0][0]["targets_sha256"] != results[1][0]["targets_sha256"]
    assert results[0][0]["ade_h10"] != results[1][0]["ade_h10"]
    assert len(calls) == 4


@pytest.mark.parametrize("batch_size", [1, 3, 512])
def test_batch_partition_preserves_values_and_hashes(tmp_path, monkeypatch, batch_size):
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    model = {"configuration_id": "persistence", "method": "persistence", "params": {}}
    first, _ = pb.evaluate_video_model(video_fixture(), model, tmp_path / "a", batch_size=2, expected_windows=4)
    second, _ = pb.evaluate_video_model(video_fixture(), model, tmp_path / "b", batch_size=batch_size, expected_windows=4)
    for key in (*pb.METRICS, "window_keys_sha256", "histories_sha256", "targets_sha256"):
        assert first[key] == second[key]
    assert (tmp_path / "a/predictions.csv").read_bytes() == (tmp_path / "b/predictions.csv").read_bytes()


def test_incomplete_coverage_preserves_partial_files_without_summary(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="all registered"):
        run_model(tmp_path, monkeypatch, expected=5)
    assert (tmp_path / "persistence/predictions.csv").is_file()
    assert not (tmp_path / "persistence/summary.json").exists()


@pytest.mark.parametrize("change", ["duplicate", "renamed", "reordered", "ids", "segments", "dtype"])
def test_consumption_must_match_parent_index_not_just_count(tmp_path, monkeypatch, change):
    monkeypatch.setattr(pb, "REPOSITORY_ROOT", tmp_path)
    video = video_fixture()
    original = video.iter_batches
    def altered(batch_size=512):
        for batch in original(batch_size=512):
            rows = [dict(row) for row in batch.window_rows]
            if change == "duplicate": rows[-1] = dict(rows[0])
            if change == "renamed": rows[-1]["window_id"] = "invented-but-unique"
            if change == "reordered": rows.reverse()
            histories = batch.histories.astype(np.float32) if change == "dtype" else batch.histories
            yield SimpleNamespace(window_rows=tuple(rows), histories=histories, targets=batch.targets)
    video.iter_batches = altered
    if change == "ids": video.track_ids_with_windows = ("A", "B", "C")
    if change == "segments": video.summary["segments_with_windows"] = 4
    with pytest.raises(ValueError):
        pb.evaluate_video_model(video, {"configuration_id": "persistence", "method": "persistence", "params": {}},
                                tmp_path / change, batch_size=512, expected_windows=4)
    assert not (tmp_path / change / "summary.json").exists()


def test_float32_predictor_drift_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pb.PersistencePredictor, "predict_batch",
                        lambda self, histories, horizons: np.zeros((len(histories), 10, 2), dtype=np.float32))
    with pytest.raises(ValueError, match="float64"):
        run_model(tmp_path, monkeypatch)


def test_fixed_parameters_and_existing_run_not_overwritten(tmp_path, monkeypatch):
    run_model(tmp_path, monkeypatch)
    content = (tmp_path / "persistence/predictions.csv").read_bytes()
    with pytest.raises(FileExistsError):
        run_model(tmp_path, monkeypatch)
    assert (tmp_path / "persistence/predictions.csv").read_bytes() == content
    with pytest.raises(ValueError, match="fixed"):
        pb.evaluate_video_model(video_fixture(), {"configuration_id": "cv_median5", "method": "constant_velocity",
            "params": {"window": 10, "method": "mean"}}, tmp_path / "changed", batch_size=2, expected_windows=4)
    assert not (tmp_path / "changed").exists()


def comparison_rows():
    rows = []
    for video, count, error in (("11", 1000, 1.), ("12", 10, 9.)):
        for method in pb.METHOD_IDS:
            value = error if method == "persistence" else error + 2
            rows.append({"video_id": video, "configuration_id": method, "split": "train",
                         "n_windows": count, "evaluated_original_ids": 2,
                         "all_original_individual_ids": 3, "original_ids_without_windows": 1,
                         "segments_total": 4, "segments_with_windows": 3, "fps": 49.,
                         "window_keys_sha256": "a"*64, "histories_sha256": "b"*64, "targets_sha256": "c"*64,
                         **{k: value for k in pb.METRICS}, **{f"window_weighted_{k}": value + 1 for k in pb.METRICS}})
    return rows


def test_videos_have_equal_weight_and_delta_direction_is_explicit():
    summary = pb.summarize_comparison(comparison_rows(), video_ids=("11", "12"))
    assert summary["methods"][0]["macro_ade_h10"] == 5.
    assert summary["methods"][1]["macro_ade_h10"] == 7.
    assert all(row["cv_minus_persistence_fde_h10"] == 2 for row in summary["paired_video_differences"])
    assert summary["model_selected"] is False


@pytest.mark.parametrize("field,value", [("n_windows", 1), ("histories_sha256", "z"*64),
    ("targets_sha256", "z"*64), ("window_keys_sha256", "z"*64), ("fps", 48),
    ("ade_h10", float("nan")), ("fde_h5", -1), ("ade_h1", True), ("split", "test")])
def test_misaligned_or_invalid_comparisons_rejected(field, value):
    rows = comparison_rows()
    rows[1][field] = value
    with pytest.raises(ValueError):
        pb.summarize_comparison(rows, video_ids=("11", "12"))


def test_missing_and_duplicate_comparison_rejected():
    rows = comparison_rows()
    for invalid in (rows[:-1], rows + [copy.deepcopy(rows[0])]):
        with pytest.raises(ValueError, match="exactly"):
            pb.summarize_comparison(invalid, video_ids=("11", "12"))


def test_invalid_plan_stops_before_capture_or_reference(plan_workspace, monkeypatch):
    plan_workspace.write_text("method: changed")
    monkeypatch.setattr(pb.RunSnapshot, "capture", lambda: pytest.fail("snapshot started"))
    monkeypatch.setattr(pb, "load_prediction_reference", lambda *a, **k: pytest.fail("reference read"))
    with pytest.raises(ValueError, match="registered"):
        pb.run_baselines(plan_workspace)


def test_parent_failure_is_recorded_without_comparison(plan_workspace, tmp_path, monkeypatch):
    snapshot = object()
    run = SimpleNamespace(path=tmp_path / "run", fail=Mock(), complete=Mock())
    monkeypatch.setattr(pb.RunSnapshot, "capture", lambda: snapshot)
    monkeypatch.setattr(pb.RunContext, "create", lambda **kwargs: run)
    def fail(*args, **kwargs): raise ValueError("synthetic changed parent")
    monkeypatch.setattr(pb, "load_prediction_reference", fail)
    with pytest.raises(ValueError, match="changed parent"):
        pb.run_baselines(plan_workspace)
    run.fail.assert_called_once()
    run.complete.assert_not_called()


def test_cli_rejects_split_or_parameter_override(monkeypatch):
    from script.prediction.test import evaluate_baselines
    monkeypatch.setattr(evaluate_baselines, "run_baselines", lambda: pytest.fail("run started"))
    with pytest.raises(SystemExit):
        evaluate_baselines.main(["--split", "test"])
