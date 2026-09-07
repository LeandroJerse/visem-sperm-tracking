"""End-to-end tests for the reproducible tracking CSV CLI."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import numpy as np

from src.detection.io import CSV_FIELDS
from src.experiments.protocol import ProtocolViolation
from src.tracking.flow_cache import LazyFlowCacheIndex
from src.tracking.pipeline import (
    _assert_frozen_cli_is_operational,
    load_tracking_csv,
    main,
    parse_args,
    resolve_cli_config,
)


def test_frozen_tracking_cli_rejects_algorithm_and_partial_interval_overrides():
    with pytest.raises(ProtocolViolation, match="overrides científicos"):
        _assert_frozen_cli_is_operational(parse_args(["--method", "sort"]))
    with pytest.raises(ProtocolViolation, match="overrides científicos"):
        _assert_frozen_cli_is_operational(parse_args(["--frame-start", "10"]))
    with pytest.raises(ProtocolViolation, match="parâmetros científicos"):
        _assert_frozen_cli_is_operational(parse_args(["--set", "max_age=3"]))


def _row(
    *,
    video_id: str,
    frame: int,
    source: str,
    object_id: str,
    cx: float,
    score: float = 1.0,
) -> dict[str, object]:
    return {
        "video_id": video_id,
        "frame": frame,
        "source": source,
        "object_id": object_id,
        "class_id": 0,
        "class_name": "normal",
        "cx": cx,
        "cy": 20.0,
        "w": 8.0,
        "h": 8.0,
        "x": cx - 4.0,
        "y": 16.0,
        "score": score,
    }


def _write_unified_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_frame_metrics(
    path: Path, rows: list[tuple[str, int, bool]]
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("video_id", "frame", "annotated")
        )
        writer.writeheader()
        for video_id, frame, annotated in rows:
            writer.writerow(
                {"video_id": video_id, "frame": frame, "annotated": annotated}
            )
    return path


def _write_flow_cache(
    root: Path,
    *,
    previous_frame: int = 0,
    next_frame: int = 1,
    invalid_first_pixel: bool = False,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    field = np.zeros((40, 60, 2), dtype=np.float32)
    field[..., 0] = 10.0
    valid = np.ones((40, 60), dtype=np.uint8)
    if invalid_first_pixel:
        valid[0, 0] = 0
    cache_path = root / "field.npz"
    np.savez_compressed(
        cache_path,
        flow=field,
        valid=valid,
        metadata=np.asarray("{}"),
    )
    index_path = root / "cache_index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("previous_frame", "next_frame", "key", "path", "cache_hit"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "previous_frame": previous_frame,
                "next_frame": next_frame,
                "key": "synthetic",
                "path": str(cache_path.resolve()),
                "cache_hit": 0,
            }
        )
    return index_path, cache_path


def _synthetic_rows(video_id: str = "11") -> list[dict[str, object]]:
    return [
        _row(
            video_id=video_id,
            frame=0,
            source="detection",
            object_id="frame-object-0",
            cx=10,
        ),
        _row(
            video_id=video_id,
            frame=2,
            source="detection",
            object_id="frame-object-0",
            cx=12,
        ),
        _row(
            video_id=video_id,
            frame=0,
            source="manual",
            object_id="cell-A",
            cx=10,
        ),
        _row(
            video_id=video_id,
            frame=1,
            source="manual",
            object_id="cell-A",
            cx=11,
        ),
        _row(
            video_id=video_id,
            frame=2,
            source="manual",
            object_id="cell-A",
            cx=12,
        ),
    ]


def test_tracking_config_resolves_aliases_cli_precedence_and_bare_params(tmp_path):
    config_path = tmp_path / "tracking.yaml"
    config_path.write_text(
        """
method: hungarian
input_source: ground_truth
params:
  max_distance: 20
run:
  stage: screen
  split: train
  seed: 42
""".strip(),
        encoding="utf-8",
    )
    yaml_only = resolve_cli_config(parse_args(["--config", str(config_path)]))
    assert yaml_only["input"]["source"] == "manual"
    assert yaml_only["input"]["configured_source"] == "ground_truth"

    args = parse_args(
        [
            "--config",
            str(config_path),
            "--input-csv",
            "objects.csv",
            "--stage",
            "validation",
            "--split",
            "val",
            "--seed",
            "123",
            "--set",
            "max_distance=9",
            "--set",
            "evaluation.center_gate_px=20",
            "--set",
            "input_source=detection",
        ]
    )
    config = resolve_cli_config(args)
    assert config["method"] == "hungarian"
    # --set is the final layer, including the legacy top-level alias.
    assert config["input"]["source"] == "detection"
    assert config["input"]["configured_source"] == "detection"
    assert config["params"]["max_distance"] == 9
    assert config["evaluation"]["center_gate_px"] == 20
    assert config["run"] == {"stage": "validation", "split": "val", "seed": 123}


def test_csv_loader_selects_video_keeps_manual_gt_and_materializes_empty_frames(
    tmp_path,
):
    rows = _synthetic_rows("11") + [
        _row(
            video_id="12",
            frame=0,
            source="detection",
            object_id="other",
            cx=100,
        )
    ]
    csv_path = _write_unified_csv(tmp_path / "objects.csv", rows)
    with pytest.raises(ValueError, match="múltiplos vídeos"):
        load_tracking_csv(csv_path, input_source="detection")

    sequence = load_tracking_csv(
        csv_path,
        input_source="detection",
        configured_input_source="frozen_detector",
        video_id="11",
        frame_start=0,
        frame_end=3,
    )
    assert sequence.video_id == "11"
    assert sequence.frames_processed == 4
    assert sequence.empty_input_frames == 2  # frames 1 and 3
    assert [len(items) for items in sequence.detections_by_frame] == [1, 0, 1, 0]
    assert set(sequence.ground_truth_by_frame) == {0, 1, 2}
    assert sequence.ground_truth_by_frame[0][0].object_id == "cell-A"
    assert sequence.manual_rows == 3
    assert sequence.configured_input_source == "frozen_detector"


def test_frame_metrics_companion_recovers_interval_and_annotated_empty_gt(tmp_path):
    rows = [
        _row(
            video_id="11", frame=0, source="detection", object_id="det-0", cx=10
        ),
        _row(
            video_id="11", frame=1, source="detection", object_id="det-0", cx=11
        ),
        _row(
            video_id="11", frame=0, source="manual", object_id="cell-A", cx=10
        ),
    ]
    csv_path = _write_unified_csv(tmp_path / "detections.csv", rows)
    _write_frame_metrics(
        tmp_path / "frame_metrics.csv",
        [("11", 0, True), ("11", 1, True), ("11", 2, False)],
    )

    summary = main(
        [
            "--method",
            "centroid_greedy",
            "--input-csv",
            str(csv_path),
            "--input-source",
            "detection",
            "--out-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert summary["frame_start"] == 0
    assert summary["frame_end"] == 2
    assert summary["frames_processed"] == 3
    assert summary["frame_universe_status"] == "frame_metrics_csv"
    assert summary["annotated_frames"] == 2
    assert summary["unannotated_frames"] == 1
    assert summary["unknown_annotation_frames"] == 0
    assert summary["identity_evaluation_status"] == (
        "computed_on_frame_metrics_universe"
    )
    # Frame 1 is explicitly annotated but empty, so the automatic object there
    # is a traceable false positive instead of silently disappearing from eval.
    assert summary["identity_false_positives"] == 1

    run_directory = next((tmp_path / "runs").rglob("manifest.json")).parent
    with (run_directory / "tracks.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        track_rows = list(csv.DictReader(handle))
    assert track_rows
    assert {row["annotated"] for row in track_rows} == {"1"}
    metadata = json.loads((run_directory / "metadata.json").read_text("utf-8"))
    assert metadata["frame_metrics"]["status"] == "auto_detected_sibling"
    assert metadata["frame_metrics"]["sha256"]


def test_flow_cache_index_is_lazy_and_converts_invalid_pixels_to_nan(tmp_path):
    index_path, _ = _write_flow_cache(
        tmp_path / "cache", invalid_first_pixel=True
    )
    index = LazyFlowCacheIndex(index_path)
    flows = index.iter_for_interval(0, 1)
    assert index.fields_loaded == 0
    assert next(flows) is None
    assert index.fields_loaded == 0
    dense = next(flows)
    assert index.fields_loaded == 1
    assert isinstance(dense, np.ndarray)
    assert np.isnan(dense[0, 0]).all()
    assert dense[20, 20].tolist() == pytest.approx([10.0, 0.0])
    with pytest.raises(StopIteration):
        next(flows)


def test_tracking_cli_feeds_previous_to_current_flow_and_records_provenance(
    tmp_path,
):
    rows = [
        _row(
            video_id="11", frame=0, source="detection", object_id="det-0", cx=10
        ),
        _row(
            video_id="11", frame=1, source="detection", object_id="det-0", cx=20
        ),
    ]
    csv_path = _write_unified_csv(tmp_path / "objects.csv", rows)
    index_path, _ = _write_flow_cache(tmp_path / "cache")
    summary = main(
        [
            "--method",
            "adaptive_flow_sort",
            "--input-csv",
            str(csv_path),
            "--input-source",
            "detection",
            "--flow-cache-index",
            str(index_path),
            "--set",
            "base_distance=3",
            "--set",
            "min_distance=2",
            "--set",
            "flow_weight=1",
            "--set",
            "min_hits=1",
            "--out-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert summary["unique_tracks"] == 1
    assert summary["flow_cache_status"] == "loaded_lazy"
    assert summary["flow_pairs_indexed_for_interval"] == 1
    assert summary["flow_fields_loaded"] == 1
    assert summary["flow_pairs_missing"] == 0

    run_directory = next((tmp_path / "runs").rglob("manifest.json")).parent
    manifest = json.loads((run_directory / "manifest.json").read_text("utf-8"))
    metadata = json.loads((run_directory / "metadata.json").read_text("utf-8"))
    assert manifest["config"]["input"]["flow_cache_index_sha256"]
    assert metadata["flow_cache_index"]["loaded_pairs"] == [[0, 1]]
    assert metadata["flow_cache_index"]["invalid_pixel_policy"] == (
        "converted_to_nan_before_tracking"
    )


def test_tracking_cli_refuses_flow_cache_for_pure_baseline(tmp_path):
    csv_path = _write_unified_csv(
        tmp_path / "objects.csv",
        [
            _row(
                video_id="11",
                frame=0,
                source="detection",
                object_id="det-0",
                cx=10,
            )
        ],
    )
    index_path, _ = _write_flow_cache(tmp_path / "cache")
    with pytest.raises(SystemExit, match="exclusivo de adaptive_flow_sort"):
        main(
            [
                "--method",
                "sort",
                "--input-csv",
                str(csv_path),
                "--flow-cache-index",
                str(index_path),
                "--out-dir",
                str(tmp_path / "runs"),
            ]
        )
    assert not (tmp_path / "runs").exists()


def test_tracking_cli_creates_immutable_artifacts_evaluates_gt_and_resets_ids(
    tmp_path,
):
    csv_path = _write_unified_csv(
        tmp_path / "detections.csv", _synthetic_rows("14")
    )
    runs_root = tmp_path / "runs"
    argv = [
        "--method",
        "centroid_greedy",
        "--input-csv",
        str(csv_path),
        "--input-source",
        "detection",
        "--video-id",
        "14",
        "--frame-start",
        "0",
        "--frame-end",
        "2",
        "--stage",
        "validation",
        "--split",
        "val",
        "--seed",
        "2026",
        "--set",
        "max_distance=5",
        "--set",
        "max_age=1",
        "--out-dir",
        str(runs_root),
    ]
    first = main(argv)
    second = main(argv)

    assert first["run_id"] != second["run_id"]
    for summary in (first, second):
        assert summary["frames_processed"] == 3
        assert summary["empty_input_frames"] == 1
        assert summary["input_detections"] == 2
        assert summary["manual_gt_rows"] == 3
        assert summary["track_rows"] == 2
        assert summary["unique_tracks"] == 1
        assert summary["id_switches"] == 0
        assert summary["fragmentations"] == 1
        assert summary["identity_evaluation_status"] == (
            "computed_on_frames_with_manual_rows"
        )
        assert summary["hota_status"] == "external_not_run_use_tracks_mot_artifact"

    run_directories = sorted(path.parent for path in runs_root.rglob("manifest.json"))
    assert len(run_directories) == 2
    for run_directory in run_directories:
        expected = {
            "tracks.csv",
            "tracks_mot.txt",
            "identity_events.csv",
            "identity_evaluation.json",
            "summary.json",
            "summary.csv",
            "metadata.json",
            "manifest.json",
        }
        assert expected <= {path.name for path in run_directory.iterdir()}

        with (run_directory / "tracks.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            tracks = list(csv.DictReader(handle))
        assert [row["frame_index"] for row in tracks] == ["0", "2"]
        # A fresh tracker/reset must restart deterministic IDs in each run.
        assert {row["track_id"] for row in tracks} == {"1"}

        manifest = json.loads(
            (run_directory / "manifest.json").read_text(encoding="utf-8")
        )
        metadata = json.loads(
            (run_directory / "metadata.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "complete"
        assert manifest["config"]["params"]["max_distance"] == 5
        assert manifest["hota"]["status"] == "external_not_run"
        assert Path(manifest["hota"]["motchallenge_predictions"]).name == (
            "tracks_mot.txt"
        )
        assert metadata["input"]["sha256"]
        assert metadata["identity_evaluation"]["metrics"]["fragmentations"] == 1


def test_cli_does_not_treat_missing_manual_ids_as_identity_ground_truth(tmp_path):
    rows = [
        _row(
            video_id="11",
            frame=0,
            source="detection",
            object_id="0",
            cx=10,
        ),
        _row(
            video_id="11",
            frame=0,
            source="manual",
            object_id="-1",
            cx=10,
        ),
    ]
    csv_path = _write_unified_csv(tmp_path / "missing_ids.csv", rows)
    summary = main(
        [
            "--method",
            "hungarian",
            "--input-csv",
            str(csv_path),
            "--out-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert summary["identity_evaluation_status"] == (
        "unavailable_missing_persistent_ids"
    )
    assert "id_switches" not in summary
