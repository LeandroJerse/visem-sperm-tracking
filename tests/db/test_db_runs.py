"""Integration tests for immutable-run ingestion into SQLite."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from src.core.relocation import PathMigrationMap
from src.db.build_db import build_database
from src.db.run_ingest import load_run_tables


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_runs(results_dir: Path) -> None:
    detection = results_dir / "runs/validation/detection/threshold/run-detection"
    detection.mkdir(parents=True)
    frame_metrics = detection / "frame_metrics.csv"
    summary = detection / "summary.csv"
    costs = detection / "costs.csv"
    pd.DataFrame(
        [
            {"video_id": "11", "frame": 0, "annotated": True, "tp": 2, "fp": 0, "fn": 0, "f1": 1.0},
            {"video_id": "11", "frame": 1, "annotated": False, "tp": None, "fp": None, "fn": None, "f1": None},
        ]
    ).to_csv(frame_metrics, index=False)
    pd.DataFrame(
        [{"video_id": "11", "frames": 2, "f1": 1.0, "detection_ms_mean": 3.5}]
    ).to_csv(summary, index=False)
    pd.DataFrame([{"ram_peak_mb": 128.0, "vram_peak_mb": 0.0}]).to_csv(costs, index=False)
    _write_json(detection / "metadata.json", {"note": "test"})
    _write_json(
        detection / "manifest.json",
        {
            "run_id": "run-detection",
            "status": "complete",
            "module": "detection",
            "method": "threshold",
            "stage": "validation",
            "seed": 42,
            "started_at": "2026-08-29T10:00:00+00:00",
            "finished_at": "2026-08-29T10:00:02+00:00",
            "elapsed_seconds": 2.0,
            "git_sha": "abc1234",
            "config_hash": "deadbeef1234",
            "config": {"run": {"split": "val"}, "params": {"threshold_value": 200}},
            "environment": {"python": "3.11.9", "cuda_available": False},
            # Absolute paths are normalised during ingestion.
            "artifacts": {
                "frame_metrics_csv": str(frame_metrics.resolve()),
                "summary_csv": str(summary.resolve()),
            },
            "summary": {"f1": 1.0, "detection_ms_mean": 3.5},
        },
    )

    # A failed module still belongs in runs and contributes its elapsed cost,
    # despite not having frame/video artifacts.
    tracking = results_dir / "runs/test/tracking/sort/run-tracking"
    _write_json(
        tracking / "manifest.json",
        {
            "run_id": "run-tracking",
            "status": "failed",
            "module": "tracking",
            "method": "sort",
            "stage": "test",
            "seed": 123,
            "started_at": "2026-08-29T11:00:00+00:00",
            "finished_at": "2026-08-29T11:00:01+00:00",
            "elapsed_seconds": 1.0,
            "config_hash": "feedface1234",
            "config": {"run": {"split": "test"}},
            "error": "synthetic failure",
        },
    )

    # A module under development may only have its running manifest.
    flow = results_dir / "runs/smoke/flow/farneback/run-flow"
    flow.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "video_id": "14",
                "previous_frame": 0,
                "next_frame": 1,
                "photometric_mae": 0.1,
            }
        ]
    ).to_csv(flow / "pair_metrics.csv", index=False)
    _write_json(
        flow / "manifest.json",
        {
            "run_id": "run-flow",
            "status": "running",
            "module": "flow",
            "method": "farneback",
            "stage": "smoke",
            "seed": 2026,
            "started_at": "2026-08-29T12:00:00+00:00",
            "config_hash": "cafebabe1234",
            "config": {},
        },
    )

    # Corrupt/incomplete external output is ignored rather than aborting all ingestion.
    broken = results_dir / "runs/smoke/prediction/kalman/broken"
    broken.mkdir(parents=True)
    (broken / "manifest.json").write_text("{not-json", encoding="utf-8")


def _make_legacy_result(results_dir: Path) -> None:
    legacy = results_dir / "legacy"
    legacy.mkdir(parents=True)
    pd.DataFrame(
        [{"video_id": "11", "frame": 0, "source": "detection", "cx": 10, "cy": 20}]
    ).to_csv(legacy / "11_threshold.csv", index=False)
    pd.DataFrame([{"video_id": "11", "method": "threshold", "frames": 1}]).to_csv(
        legacy / "11_threshold_summary.csv", index=False
    )


def test_load_run_tables_is_resilient_and_uses_relative_paths(tmp_path):
    results = tmp_path / "results"
    _make_runs(results)

    tables = load_run_tables(results)
    assert len(tables["runs"]) == 3
    assert len(tables["metrics_frame"]) == 3
    assert len(tables["metrics_video"]) == 1
    assert len(tables["costs"]) == 2

    run = tables["runs"].set_index("run_id").loc["run-detection"]
    assert run["status"] == "complete"
    assert run["config_hash"] == "deadbeef1234"
    assert run["split"] == "val"
    assert run["run_path"] == "runs/validation/detection/threshold/run-detection"
    assert not Path(run["manifest_path"]).is_absolute()
    assert not Path(run["metadata_path"]).is_absolute()
    artifact_paths = json.loads(run["artifacts_json"])
    assert artifact_paths["frame_metrics_csv"].startswith("runs/")
    assert not Path(artifact_paths["frame_metrics_csv"]).is_absolute()

    frame = tables["metrics_frame"].query("run_id == 'run-detection'").iloc[0]
    assert frame["run_id"] == "run-detection"
    assert frame["source_path"].endswith("/frame_metrics.csv")
    assert frame["f1"] == 1.0
    flow_metric = tables["metrics_frame"].query("run_id == 'run-flow'").iloc[0]
    assert flow_metric["metric_unit"] == "frame_pair"
    assert flow_metric["frame"] == 0
    assert flow_metric["photometric_mae"] == 0.1

    detection_cost = tables["costs"].set_index("run_id").loc["run-detection"]
    assert detection_cost["elapsed_seconds"] == 2.0
    assert detection_cost["detection_ms_mean"] == 3.5
    assert detection_cost["ram_peak_mb"] == 128.0


def test_build_database_keeps_legacy_tables_and_is_idempotent(tmp_path):
    results = tmp_path / "results"
    _make_runs(results)
    _make_legacy_result(results)
    db_path = results / "visem.db"

    kwargs = {
        "db_path": db_path,
        "results_dir": results,
        "raw_dir": tmp_path / "raw",
        "tracked_dir": tmp_path / "tracked",
        "verbose": False,
    }
    first = build_database(**kwargs)
    second = build_database(**kwargs)
    assert first == second
    assert second["detections"] == 1
    assert second["summaries"] == 1
    assert second["runs"] == 3
    assert second["metrics_frame"] == 3
    assert second["metrics_video"] == 1
    assert second["costs"] == 2

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "detections", "summaries", "runs", "metrics_frame", "metrics_video", "costs"
        } <= table_names
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 3
        assert conn.execute(
            "SELECT status FROM runs WHERE run_id='run-tracking'"
        ).fetchone()[0] == "failed"
        assert conn.execute(
            "SELECT f1 FROM metrics_video WHERE run_id='run-detection'"
        ).fetchone()[0] == 1.0


def test_empty_results_still_create_stable_run_tables(tmp_path):
    db_path = tmp_path / "empty.db"
    counts = build_database(
        db_path=db_path,
        results_dir=tmp_path / "no-results",
        raw_dir=tmp_path / "no-raw",
        tracked_dir=tmp_path / "no-tracked",
        verbose=False,
    )
    assert {name: counts[name] for name in ("runs", "metrics_frame", "metrics_video", "costs")} == {
        "runs": 0,
        "metrics_frame": 0,
        "metrics_video": 0,
        "costs": 0,
    }
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"runs", "metrics_frame", "metrics_video", "costs"} <= tables


def test_path_migration_map_resolves_files_and_tree_children(tmp_path):
    repository = tmp_path / "repository"
    manifest = tmp_path / "layout.csv"
    manifest.write_text(
        "original_path,new_path,action,bytes,file_count,sha256,verified\n"
        "old/file.csv,new/file.csv,move_file,1,1,abc,True\n"
        "old/tree,new/tree,move_tree,2,2,,True\n",
        encoding="utf-8",
    )
    mapping = PathMigrationMap.from_csv(manifest, repository_root=repository)
    assert mapping.resolve(r"old\file.csv") == (repository / "new/file.csv").resolve()
    assert mapping.resolve(r"old\tree\nested\x.json") == (
        repository / "new/tree/nested/x.json"
    ).resolve()
    assert mapping.resolve("unknown/file.csv") is None


def test_migrated_legacy_run_paths_resolve_to_canonical_artifacts(tmp_path):
    data_root = tmp_path / "data"
    run_dir = (
        data_root
        / "tests/detection/threshold/t200_o1_c2__cfg3276cf65/validation/run-legacy"
    )
    run_dir.mkdir(parents=True)
    (run_dir / "detections.csv").write_text(
        "video_id,frame\n14,0\n", encoding="utf-8"
    )
    (run_dir / "summary.csv").write_text("video_id,f1\n14,0.5\n", encoding="utf-8")
    legacy_prefix = r"results\runs\validation\detection\threshold\run-legacy"
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "run-legacy",
            "status": "complete",
            "module": "detection",
            "method": "threshold",
            "stage": "validation",
            "seed": 42,
            "config": {
                "run": {"split": "val"},
                "input": {"video": r"unknown\source\14.mp4"},
            },
            "artifacts": {
                "detections_csv": legacy_prefix + r"\detections.csv",
                "summary_csv": legacy_prefix + r"\summary.csv",
            },
        },
    )

    tables = load_run_tables(data_root)
    run = tables["runs"].iloc[0]
    artifacts = json.loads(run["artifacts_json"])
    for value in artifacts.values():
        assert (data_root / value).is_file()
    assert run["configuration_id"] == "t200_o1_c2"
    assert run["configuration_hash"] == "3276cf65"
    config = json.loads(run["config_json"])
    assert config["input"]["video"] == "unknown/source/14.mp4"
