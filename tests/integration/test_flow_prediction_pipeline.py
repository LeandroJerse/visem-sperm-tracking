"""Fast synthetic tests for the reproducible flow/prediction CLIs."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.experiments.protocol import ProtocolViolation
from src.flow import pipeline as flow_cli
from src.flow.base import FlowEstimator, FlowResult
from src.flow.cache import FlowCache, make_cache_key
from src.integration import enrich_tracks_with_flow as enrich_cli
from src.prediction import pipeline as prediction_cli


def test_frozen_flow_prediction_and_enrichment_accept_only_operational_inputs():
    with pytest.raises(ProtocolViolation, match="overrides científicos"):
        flow_cli._assert_frozen_cli_is_operational(
            flow_cli.parse_args(["--max-pairs", "10"])
        )
    with pytest.raises(ProtocolViolation, match="parâmetros científicos"):
        flow_cli._assert_frozen_cli_is_operational(
            flow_cli.parse_args(["--set", "alpha=0.5"])
        )
    with pytest.raises(ProtocolViolation, match="overrides científicos"):
        prediction_cli._assert_frozen_cli_is_operational(
            prediction_cli.parse_args(["--horizons", "1", "5"])
        )
    with pytest.raises(ProtocolViolation, match="overrides científicos"):
        enrich_cli._assert_frozen_cli_is_operational(
            enrich_cli.parse_args(["--radius", "9"])
        )


def test_flow_cli_config_precedence_and_bare_parameter(tmp_path):
    config_path = tmp_path / "flow.yaml"
    config_path.write_text(
        """
method: horn_schunck
params:
  alpha: 0.1
run:
  stage: screen
  split: train
  seed: 42
""".strip(),
        encoding="utf-8",
    )
    config = flow_cli.resolve_cli_config(
        flow_cli.parse_args(
            [
                "--config",
                str(config_path),
                "--stage",
                "validation",
                "--seed",
                "123",
                "--set",
                "alpha=0.2",
                "--set",
                "run.seed=2026",
            ]
        )
    )
    assert config["method"] == "horn_schunck"
    assert config["params"]["alpha"] == pytest.approx(0.2)
    assert config["run"]["stage"] == "validation"
    assert config["run"]["seed"] == 2026  # --set is final precedence


def test_flow_cli_writes_immutable_real_video_metrics_without_epe(
    tmp_path, monkeypatch
):
    video = tmp_path / "synthetic.avi"
    video.write_bytes(b"synthetic-video-fingerprint")
    rng = np.random.default_rng(42)
    frames = [rng.random((16, 18), dtype=np.float32) for _ in range(3)]

    def fake_pairs(path, *, max_pairs=None):
        assert Path(path) == video
        pairs = [
            (0, 1, frames[0], frames[0].copy()),
            (1, 2, frames[1], frames[1].copy()),
        ]
        yield from pairs[:max_pairs]

    monkeypatch.setattr(flow_cli, "iter_video_pairs", fake_pairs)
    runs = tmp_path / "runs"
    argv = [
        "--method",
        "horn_schunck",
        "--input-video",
        str(video),
        "--video-id",
        "14",
        "--max-pairs",
        "2",
        "--stage",
        "validation",
        "--split",
        "val",
        "--seed",
        "123",
        "--set",
        "iterations=10",
        "--set",
        "evaluation.compute_backward=false",
        "--cache-dir",
        str(tmp_path / "flow_cache"),
        "--out-dir",
        str(runs),
    ]
    first = flow_cli.main(argv)
    second = flow_cli.main(argv)
    assert first["run_id"] != second["run_id"]
    assert first["pairs_processed"] == 2
    assert first["cache_hits"] == 0
    assert second["cache_hits"] == 2
    assert first["mean_photometric_mae"] == pytest.approx(0.0)
    assert first["epe_status"] == "not_computed_real_video_no_ground_truth"

    run_directories = sorted(path.parent for path in runs.rglob("manifest.json"))
    assert len(run_directories) == 2
    for directory in run_directories:
        assert {
            "manifest.json",
            "metadata.json",
            "pair_metrics.csv",
            "summary.json",
            "summary.csv",
            "cache_index.csv",
        } <= {path.name for path in directory.iterdir()}
        with (directory / "pair_metrics.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            assert "epe" not in (reader.fieldnames or [])
        assert len(rows) == 2
        manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
        assert manifest["status"] == "complete"


TRACK_FIELDS = (
    "video_id",
    "frame_index",
    "annotated",
    "track_id",
    "cx",
    "cy",
    "predicted",
    "flow_u",
    "flow_v",
)


def _write_tracks(
    path: Path,
    *,
    video_id: str = "11",
    velocity: tuple[float, float] = (2.0, -0.5),
    flow: tuple[float, float] | None = None,
    frames: int = 10,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACK_FIELDS)
        writer.writeheader()
        for frame in range(frames):
            writer.writerow(
                {
                    "video_id": video_id,
                    "frame_index": frame,
                    "annotated": 1,
                    "track_id": "cell-A",
                    "cx": velocity[0] * frame,
                    "cy": velocity[1] * frame,
                    "predicted": 0,
                    "flow_u": "" if flow is None else flow[0],
                    "flow_v": "" if flow is None else flow[1],
                }
            )
    return path


def test_prediction_cli_constant_velocity_has_exact_ade_fde(tmp_path):
    tracks = _write_tracks(tmp_path / "tracks.csv", video_id="14")
    summary = prediction_cli.main(
        [
            "--method",
            "constant_velocity",
            "--tracks-csv",
            str(tracks),
            "--video-id",
            "14",
            "--history-length",
            "3",
            "--horizons",
            "1",
            "2",
            "--stage",
            "validation",
            "--split",
            "val",
            "--out-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert summary["windows_evaluated"] == 6
    assert summary["prediction_rows"] == 12
    assert summary["ade"] == pytest.approx(0.0)
    assert summary["fde"] == pytest.approx(0.0)
    assert summary["uses_flow"] is False
    run_directory = next((tmp_path / "runs").rglob("summary.json")).parent
    assert {
        "predictions.csv",
        "window_metrics.csv",
        "summary.csv",
        "summary.json",
        "metadata.json",
        "manifest.json",
    } <= {path.name for path in run_directory.iterdir()}


def test_prediction_cli_config_set_has_final_precedence(tmp_path):
    config_path = tmp_path / "prediction.yaml"
    config_path.write_text(
        """
method: constant_velocity
params:
  window: 5
data:
  history_length: 20
  horizons: [1, 5, 10]
run:
  stage: screen
  split: train
  seed: 42
""".strip(),
        encoding="utf-8",
    )
    config = prediction_cli.resolve_cli_config(
        prediction_cli.parse_args(
            [
                "--config",
                str(config_path),
                "--history-length",
                "8",
                "--seed",
                "123",
                "--set",
                "window=3",
                "--set",
                "data.history_length=6",
                "--set",
                "run.seed=2026",
            ]
        )
    )
    assert config["params"]["window"] == 3
    assert config["data"]["history_length"] == 6
    assert config["run"]["seed"] == 2026


def test_prediction_cli_flow_aware_uses_available_flow_columns(tmp_path):
    # Observed velocity 1.5 = intrinsic 1.0 + environmental flow 0.5.
    tracks = _write_tracks(
        tmp_path / "tracks_flow.csv", velocity=(1.5, 0.0), flow=(0.5, 0.0)
    )
    summary = prediction_cli.main(
        [
            "--method",
            "flow_aware_constant_velocity",
            "--tracks-csv",
            str(tracks),
            "--history-length",
            "3",
            "--horizons",
            "1",
            "2",
            "--out-dir",
            str(tmp_path / "runs_flow"),
        ]
    )
    assert summary["uses_flow"] is True
    assert summary["flow_columns_present"] is True
    assert summary["future_flow_mode"] == "last_observed"
    assert summary["ade"] == pytest.approx(0.0)


def test_prediction_cli_rejects_flow_method_without_flow_columns(tmp_path):
    tracks = tmp_path / "no_flow.csv"
    with tracks.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "video_id",
                "frame_index",
                "annotated",
                "track_id",
                "cx",
                "cy",
            ),
        )
        writer.writeheader()
        for frame in range(6):
            writer.writerow(
                {
                    "video_id": "11",
                    "frame_index": frame,
                    "annotated": 1,
                    "track_id": "A",
                    "cx": frame,
                    "cy": 0,
                }
            )
    with pytest.raises(SystemExit, match="flow_u e flow_v"):
        prediction_cli.main(
            [
                "--method",
                "flow_aware_kalman",
                "--tracks-csv",
                str(tracks),
                "--history-length",
                "3",
                "--horizons",
                "1",
            ]
        )


def test_prediction_loader_excludes_the_full_visem23_annotation_gap(tmp_path):
    tracks = tmp_path / "video23_gap.csv"
    with tracks.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACK_FIELDS)
        writer.writeheader()
        for frame in range(818, 978):
            writer.writerow(
                {
                    "video_id": "23",
                    "frame_index": frame,
                    "annotated": int(not 823 <= frame <= 972),
                    "track_id": "cell-A",
                    "cx": frame,
                    "cy": 0,
                    "predicted": 0,
                    "flow_u": "",
                    "flow_v": "",
                }
            )

    loaded = prediction_cli.load_tracks_csv(tracks, video_id="23")
    windows = prediction_cli._build_windows(
        loaded,
        split="train",
        history_length=3,
        forecast_horizon=2,
        stride=1,
    )

    assert loaded.annotation_policy == "explicit_frame_status"
    assert loaded.unannotated_rows == 150
    assert len(windows) == 2
    for window in windows:
        frames = np.concatenate((window.history_frames, window.future_frames))
        assert not np.any((823 <= frames) & (frames <= 972))


def test_prediction_requires_annotated_except_for_unlabeled_application(
    tmp_path, monkeypatch
):
    legacy = tmp_path / "legacy_without_annotated.csv"
    fields = ("video_id", "frame_index", "track_id", "cx", "cy", "predicted")
    with legacy.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for frame in range(6):
            writer.writerow(
                {
                    "video_id": "65",
                    "frame_index": frame,
                    "track_id": "cell-A",
                    "cx": frame,
                    "cy": 0,
                    "predicted": 0,
                }
            )

    with pytest.raises(ValueError, match="sem coluna annotated"):
        prediction_cli.load_tracks_csv(legacy)
    with pytest.raises(SystemExit, match="sem coluna annotated"):
        prediction_cli.main(
            [
                "--method",
                "persistence",
                "--tracks-csv",
                str(legacy),
                "--history-length",
                "3",
                "--horizons",
                "1",
                "--stage",
                "screen",
                "--split",
                "train",
                "--out-dir",
                str(tmp_path / "strict_runs"),
            ]
        )
    assert not (tmp_path / "strict_runs").exists()

    frozen_config = tmp_path / "frozen_persistence.yaml"
    frozen_config.write_text(
        """
method: persistence
data:
  history_length: 3
  horizons: [1]
run:
  stage: application
  split: application
  frozen: true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        prediction_cli,
        "assert_frozen_config_source",
        lambda _value: frozen_config.resolve(),
    )
    summary = prediction_cli.main(
        [
            "--config",
            str(frozen_config),
            "--tracks-csv",
            str(legacy),
            "--out-dir",
            str(tmp_path / "application_runs"),
        ]
    )
    assert summary["annotation_policy"] == "unavailable_application"
    assert summary["unknown_annotation_track_rows"] == 6
    assert summary["windows_evaluated"] == 3


def test_prediction_cli_blocks_test_and_never_fits_lstm_implicitly(tmp_path):
    tracks = _write_tracks(tmp_path / "tracks.csv")
    with pytest.raises(SystemExit, match="split de teste está bloqueado"):
        prediction_cli.main(
            [
                "--method",
                "persistence",
                "--tracks-csv",
                str(tracks),
                "--history-length",
                "3",
                "--horizons",
                "1",
                "--stage",
                "test",
                "--split",
                "test",
                "--out-dir",
                str(tmp_path / "blocked"),
            ]
        )
    with pytest.raises(SystemExit, match="exatamente um modo"):
        prediction_cli.main(
            [
                "--method",
                "lstm",
                "--tracks-csv",
                str(tracks),
                "--history-length",
                "3",
                "--horizons",
                "1",
            ]
        )
    assert not (tmp_path / "blocked").exists()

    overlap_runs = tmp_path / "overlap_runs"
    with pytest.raises(ValueError, match="compartilham vídeos"):
        prediction_cli.main(
            [
                "--method",
                "lstm",
                "--tracks-csv",
                str(tracks),
                "--history-length",
                "3",
                "--horizons",
                "1",
                "--train",
                "--train-csv",
                str(tracks),
                "--out-dir",
                str(overlap_runs),
            ]
        )
    failed_manifest = next(overlap_runs.rglob("manifest.json"))
    assert json.loads(failed_manifest.read_text(encoding="utf-8"))["status"] == "failed"


def test_flow_cli_protocol_guard_runs_before_video_decode(tmp_path):
    video = tmp_path / "blocked.avi"
    video.write_bytes(b"not-decoded")
    with pytest.raises(SystemExit, match="split de teste está bloqueado"):
        flow_cli.main(
            [
                "--method",
                "horn_schunck",
                "--input-video",
                str(video),
                "--stage",
                "test",
                "--split",
                "test",
                "--out-dir",
                str(tmp_path / "blocked_flow"),
            ]
        )
    assert not (tmp_path / "blocked_flow").exists()


def _write_mask_csv(path: Path) -> Path:
    fields = ("video_id", "frame", "source", "x", "y", "w", "h")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "video_id": "11",
                    "frame": 0,
                    "source": "detection",
                    "x": 4,
                    "y": 4,
                    "w": 2,
                    "h": 2,
                },
                {
                    "video_id": "11",
                    "frame": 1,
                    "source": "detection",
                    "x": 8,
                    "y": 8,
                    "w": 2,
                    "h": 2,
                },
                {
                    "video_id": "11",
                    "frame": 0,
                    "source": "manual",
                    "x": 0,
                    "y": 0,
                    "w": 2,
                    "h": 2,
                },
                {
                    "video_id": "12",
                    "frame": 0,
                    "source": "detection",
                    "x": 0,
                    "y": 0,
                    "w": 2,
                    "h": 2,
                },
            ]
        )
    return path


def test_exclusion_boxes_filter_source_video_and_union_both_frames(tmp_path):
    boxes = flow_cli.load_exclusion_boxes(
        _write_mask_csv(tmp_path / "boxes.csv"), source="detection", video_id="11"
    )
    assert boxes.boxes_used == 2
    assert set(boxes.by_frame) == {0, 1}
    include, count = flow_cli.build_pair_include_mask(
        (12, 12), boxes, 0, 1, margin_px=1
    )
    assert count == 2
    assert not include[3:7, 3:7].any()
    assert not include[7:11, 7:11].any()
    assert include[0, 0]  # manual box was filtered out


class _RecordingFlow(FlowEstimator):
    name = "recording"

    def __init__(self) -> None:
        self.masks: list[np.ndarray] = []

    def estimate(self, previous_frame, next_frame, mask=None):
        assert mask is not None
        self.masks.append(np.asarray(mask, dtype=bool).copy())
        return FlowResult(
            np.zeros((*previous_frame.shape[:2], 2), dtype=np.float32),
            valid=mask,
        )


def test_flow_cli_passes_same_union_mask_forward_backward_and_records_provenance(
    tmp_path, monkeypatch
):
    video = tmp_path / "11.avi"
    video.write_bytes(b"masked-video")
    boxes = _write_mask_csv(tmp_path / "boxes.csv")
    frame = np.zeros((12, 12), dtype=np.float32)

    def fake_pairs(path, *, max_pairs=None):
        yield 0, 1, frame, frame.copy()

    estimator = _RecordingFlow()
    monkeypatch.setattr(flow_cli, "iter_video_pairs", fake_pairs)
    monkeypatch.setattr(flow_cli, "_create_estimator", lambda config: estimator)
    cache_root = tmp_path / "masked_cache"
    argv = [
        "--method",
        "horn_schunck",
        "--input-video",
        str(video),
        "--mask-csv",
        str(boxes),
        "--mask-source",
        "detection",
        "--mask-margin",
        "1",
        "--max-pairs",
        "1",
        "--cache-dir",
        str(cache_root),
        "--out-dir",
        str(tmp_path / "runs_mask"),
    ]
    summary = flow_cli.main(argv)
    assert len(estimator.masks) == 2  # forward + backward metric
    assert np.array_equal(estimator.masks[0], estimator.masks[1])
    assert summary["mask_enabled"] is True
    assert summary["mask_source"] == "detection"
    assert summary["mean_mask_excluded_fraction"] > 0
    run = next((tmp_path / "runs_mask").rglob("manifest.json")).parent
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["mask"]["sha256"]
    assert manifest["exclusion_mask"]["pair_policy"] == (
        "union_previous_and_next_frame_boxes"
    )
    with (run / "cache_index.csv").open(encoding="utf-8", newline="") as handle:
        first_index_row = next(csv.DictReader(handle))
    cached = FlowCache(cache_root).load(first_index_row["key"])
    assert cached is not None
    cache_provenance = cached.metadata["cache_provenance"]
    assert cache_provenance["exclusion_mask"]["sha256"] == (
        manifest["config"]["mask"]["sha256"]
    )
    assert cache_provenance["exclusion_mask"]["boxes_in_pair"] == 2

    changed_boxes = _write_mask_csv(tmp_path / "boxes_changed.csv")
    with changed_boxes.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("video_id", "frame", "source", "x", "y", "w", "h"),
        )
        writer.writerow(
            {
                "video_id": "11",
                "frame": 0,
                "source": "detection",
                "x": 2,
                "y": 8,
                "w": 1,
                "h": 1,
            }
        )
    changed_argv = list(argv)
    changed_argv[changed_argv.index(str(boxes))] = str(changed_boxes)
    changed_summary = flow_cli.main(changed_argv)
    assert changed_summary["cache_hits"] == 0
    changed_run = next(
        path.parent
        for path in (tmp_path / "runs_mask").rglob("manifest.json")
        if path.parent.name == changed_summary["run_id"]
    )
    with (changed_run / "cache_index.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        changed_index_row = next(csv.DictReader(handle))
    assert changed_index_row["key"] != first_index_row["key"]


def _flow_cache_fixture(tmp_path: Path) -> tuple[Path, Path]:
    cache = FlowCache(tmp_path / "cache")
    key = make_cache_key("video11", 0, 1, config={"method": "synthetic"})
    field = np.empty((15, 15, 2), dtype=np.float32)
    field[...] = (2.0, -3.0)
    valid = np.ones((15, 15), dtype=bool)
    valid[5:10, 5:10] = False
    result = FlowResult(
        field,
        valid=valid,
        confidence=np.full((15, 15), 0.8, dtype=np.float32),
        metadata={"algorithm": "synthetic"},
    )
    artifact = cache.save(key, result)
    index = tmp_path / "cache_index.csv"
    with index.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("video_id", "previous_frame", "next_frame", "key", "path"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "video_id": "11",
                "previous_frame": 0,
                "next_frame": 1,
                "key": key,
                "path": artifact,
            }
        )
    tracks = tmp_path / "tracks_for_flow.csv"
    with tracks.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("video_id", "frame_index", "track_id", "cx", "cy"),
        )
        writer.writeheader()
        writer.writerow(
            {"video_id": "11", "frame_index": 0, "track_id": "A", "cx": 7, "cy": 7}
        )
        writer.writerow(
            {"video_id": "11", "frame_index": 1, "track_id": "A", "cx": 9, "cy": 4}
        )
    return tracks, index


def test_enrich_tracks_direct_invalid_background_recovers_and_never_overwrites(
    tmp_path,
):
    tracks, index_path = _flow_cache_fixture(tmp_path)
    index = enrich_cli.load_cache_index(index_path)
    _, original_rows = enrich_cli._read_track_rows(tracks)
    direct, direct_counts = enrich_cli.enrich_track_rows(
        original_rows, index, sampling="direct"
    )
    assert direct_counts == {
        "rows": 2,
        "valid": 0,
        "missing_cache": 1,
        "invalid_sampling": 1,
        "fields_loaded": 1,
    }
    assert direct[0]["flow_valid"] == 0

    external = tmp_path / "export" / "tracks_with_flow.csv"
    summary = enrich_cli.main(
        [
            "--tracks-csv",
            str(tracks),
            "--cache-index",
            str(index_path),
            "--sampling",
            "background",
            "--radius",
            "6",
            "--inner-radius",
            "3",
            "--min-samples",
            "8",
            "--output",
            str(external),
            "--out-dir",
            str(tmp_path / "enrich_runs"),
        ]
    )
    assert summary["rows_with_valid_flow"] == 1
    assert summary["rows_without_cache_pair"] == 1
    with external.open(encoding="utf-8", newline="") as handle:
        enriched = list(csv.DictReader(handle))
    assert enriched[0]["flow_valid"] == "1"
    assert float(enriched[0]["flow_u"]) == pytest.approx(2.0)
    assert float(enriched[0]["flow_v"]) == pytest.approx(-3.0)
    assert float(enriched[0]["flow_magnitude"]) == pytest.approx(np.sqrt(13.0))
    assert float(enriched[0]["flow_direction"]) == pytest.approx(np.arctan2(-3.0, 2.0))
    assert float(enriched[0]["flow_confidence"]) == pytest.approx(0.8)
    assert enriched[1]["flow_valid"] == "0"
    with pytest.raises(SystemExit, match="recuso sobrescrever"):
        enrich_cli.main(
            [
                "--tracks-csv",
                str(tracks),
                "--cache-index",
                str(index_path),
                "--output",
                str(external),
            ]
        )
