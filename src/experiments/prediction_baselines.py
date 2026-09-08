"""Registered, causal baseline evaluation on the audited training reference.

This stage fixes both models prospectively. It neither selects parameters nor
opens original sources, validation or test data. Dense predictions use a wide
CSV row per parent window; every predicted step remains available for audit.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import config_hash
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot
from src.prediction.classical.constant_velocity import ConstantVelocityPredictor
from src.prediction.classical.persistence import PersistencePredictor
from src.prediction.metrics import dense_trajectory_metrics
from src.prediction.reference import load_prediction_reference


PLAN_PATH = "configs/protocol/prediction_baselines_v1.yaml"
PLAN_HASH = "11aeec0be9f32f8905288c7118ce8b723180e7afb1ef8e7111d404a033e67ec9"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
METHOD_IDS = ("persistence", "cv_median5")
HORIZONS = tuple(range(1, 11))
REPORT_HORIZONS = (1, 5, 10)
KEY_FIELDS = "window_id video_id track_id segment_id split history_start origin_frame future_end".split()
METRICS = tuple(f"{name}_h{h}" for h in REPORT_HORIZONS for name in ("ade", "fde"))
PREDICTION_FIELDS = KEY_FIELDS + [f"{axis}_h{h}" for h in HORIZONS for axis in ("cx", "cy")]
WINDOW_METRIC_FIELDS = KEY_FIELDS + list(METRICS)


class _StrictYaml(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"Duplicate baseline plan key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def artifact_reference(path: Path) -> dict:
    return {"path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": sha256_file(path), "bytes": path.stat().st_size}


def load_baseline_plan(path: Path) -> tuple[dict, list[dict]]:
    root = REPOSITORY_ROOT.resolve()
    path = (path if path.is_absolute() else root / path).resolve()
    if path != root / PLAN_PATH:
        raise ValueError("Only the canonical registered baseline plan may be read")
    plan = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_StrictYaml)
    if not isinstance(plan, dict) or config_hash(plan, 64) != PLAN_HASH:
        raise ValueError("Baseline plan differs from the registered training-only v1 contract")
    split_path = root / plan["protocol"]["splits_config"]
    if sha256_file(split_path) != plan["protocol"]["splits_sha256"]:
        raise ValueError("Registered split metadata changed")
    if load_split_spec(split_path).train != TRAIN:
        raise ValueError("Baseline cohort differs from the registered training IDs")
    return plan, [artifact_reference(path), artifact_reference(split_path)]


def _check_budget(plan: dict, monitor: ResourceMonitor, start: float, path: Path,
                  *, inspect_files: bool = False) -> dict:
    resources = monitor.summary()
    if (time.perf_counter() - start > plan["budget"]["soft_wall_seconds"]
            or resources["ram_rss_peak_mb"] is None
            or resources["ram_rss_peak_mb"] > plan["budget"]["max_sampled_rss_mb"]):
        raise RuntimeError("Baseline time/RSS budget exceeded; partial run preserved")
    if inspect_files:
        size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        resources["artifact_bytes_before_final_manifest"] = size
        if size > plan["budget"]["max_artifact_mb"] * 1024**2:
            raise RuntimeError("Baseline artifact budget exceeded; partial run preserved")
    return resources


def evaluate_video_model(video, model_config: dict, folder: Path, *, batch_size: int,
                         expected_windows: int, check_progress=lambda: None) -> tuple[dict, list[dict]]:
    """Call the predictor with past positions only; targets go only to metrics."""
    method_id = model_config["configuration_id"]
    if (method_id, model_config["method"], model_config["params"]) == ("persistence", "persistence", {}):
        predictor = PersistencePredictor()
    elif (method_id, model_config["method"], model_config["params"]) == (
            "cv_median5", "constant_velocity", {"window": 5, "method": "median"}):
        predictor = ConstantVelocityPredictor(window=5, method="median")
    else:
        raise ValueError("Only the two prospectively fixed baselines are supported")
    folder.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    rows_written, prediction_seconds = 0, 0.0
    seen_windows, seen_segments = set(), set()
    windows_hash, histories_hash, targets_hash = (hashlib.sha256() for _ in range(3))
    tracks = defaultdict(lambda: {"count": 0, "sum": np.zeros(len(METRICS), dtype=np.float64), "segments": set()})
    predictions_path, metrics_path = folder / "predictions.csv", folder / "window_metrics.csv"
    with predictions_path.open("x", encoding="utf-8", newline="") as pred_stream, \
            metrics_path.open("x", encoding="utf-8", newline="") as metric_stream:
        pred_writer = csv.writer(pred_stream)
        metric_writer = csv.writer(metric_stream)
        pred_writer.writerow(PREDICTION_FIELDS)
        metric_writer.writerow(WINDOW_METRIC_FIELDS)
        for batch in video.iter_batches(batch_size=batch_size):
            if batch.histories.shape != (len(batch.window_rows), 20, 2) or batch.targets.shape != (len(batch.window_rows), 10, 2):
                raise ValueError("Reference batch differs from the fixed 20+10 contract")
            if len(batch.window_rows) == 0:
                raise ValueError("Empty reference batches are invalid")
            if batch.histories.dtype != np.dtype("float64") or batch.targets.dtype != np.dtype("float64"):
                raise ValueError("The registered scientific path requires float64 histories and targets")
            histories_hash.update(np.asarray(batch.histories, dtype="<f8").tobytes())
            targets_hash.update(np.asarray(batch.targets, dtype="<f8").tobytes())
            t0 = time.perf_counter()
            # No target, GT identity, future image/flow or annotation mask is
            # passed across this prediction boundary.
            predicted = predictor.predict_batch(batch.histories, horizons=HORIZONS)
            prediction_seconds += time.perf_counter() - t0
            if not isinstance(predicted, np.ndarray) or predicted.dtype != np.dtype("float64"):
                raise ValueError("The registered batch predictor must return float64 positions")
            metrics = dense_trajectory_metrics(predicted, batch.targets, horizons=HORIZONS,
                                               report_horizons=REPORT_HORIZONS)
            values = np.column_stack([metrics[name] for name in METRICS])
            coordinates = predicted.reshape(len(batch.window_rows), -1).tolist()
            ids = np.asarray([row["track_id"] for row in batch.window_rows])
            for identity in np.unique(ids):
                selected = ids == identity
                tracks[str(identity)]["count"] += int(selected.sum())
                tracks[str(identity)]["sum"] += values[selected].sum(axis=0)
            for row, positions, errors in zip(batch.window_rows, coordinates, values.tolist(), strict=True):
                if row["video_id"] != video.video_id or row["split"] != "train":
                    raise ValueError("Reference window belongs to another video or split")
                if row["window_id"] in seen_windows:
                    raise ValueError("Duplicate window consumed by a baseline")
                seen_windows.add(row["window_id"])
                seen_segments.add(row["segment_id"])
                keys = [row[name] for name in KEY_FIELDS]
                windows_hash.update(json.dumps(keys, ensure_ascii=True, separators=(",", ":")).encode() + b"\n")
                pred_writer.writerow(keys + positions)
                metric_writer.writerow(keys + errors)
                tracks[row["track_id"]]["segments"].add(row["segment_id"])
            rows_written += len(batch.window_rows)
            check_progress()
    if rows_written != expected_windows or rows_written != video.summary["windows_total"]:
        raise ValueError("Baseline did not evaluate all registered parent windows")
    if windows_hash.hexdigest() != video.window_keys_sha256:
        raise ValueError("Consumed window index differs from the audited parent order/identity")
    if (tuple(sorted(tracks)) != tuple(video.track_ids_with_windows)
            or len(seen_segments) != video.summary["segments_with_windows"]):
        raise ValueError("Evaluated original IDs/segments differ from the complete parent index")
    track_rows = []
    for identity, stats in sorted(tracks.items()):
        means = stats["sum"] / stats["count"]
        track_rows.append({"video_id": video.video_id, "configuration_id": method_id,
                           "track_id": identity, "n_windows": stats["count"],
                           "segments_with_windows": len(stats["segments"]),
                           **dict(zip(METRICS, means.tolist(), strict=True))})
    if not track_rows:
        raise ValueError("No original identity has an evaluated window")
    track_path = write_csv_exclusive(folder / "track_metrics.csv", track_rows)
    flat = {"video_id": video.video_id, "configuration_id": method_id, "method": model_config["method"],
            "split": "train", "n_windows": rows_written, "evaluated_original_ids": len(track_rows),
            "all_original_individual_ids": video.summary["unique_individual_track_ids"],
            "original_ids_without_windows": video.summary["unique_individual_track_ids"] - len(track_rows),
            "segments_total": video.summary["segments_total"],
            "segments_with_windows": video.summary["segments_with_windows"],
            "fps": video.fps, "history_span_seconds": 19 / video.fps,
            **{f"horizon_seconds_h{h}": h / video.fps for h in REPORT_HORIZONS},
            "window_keys_sha256": windows_hash.hexdigest(), "histories_sha256": histories_hash.hexdigest(),
            "targets_sha256": targets_hash.hexdigest(), "prediction_seconds": prediction_seconds,
            "prediction_ms_per_window": prediction_seconds * 1000 / rows_written}
    for key in METRICS:
        flat[key] = math.fsum(row[key] for row in track_rows) / len(track_rows)
        flat[f"window_weighted_{key}"] = math.fsum(row[key] * row["n_windows"] for row in track_rows) / rows_written
    files = [artifact_reference(p) for p in (predictions_path, metrics_path, track_path)]
    summary_path = write_json_exclusive(folder / "summary.json", {
        "status": "complete", "metrics": flat, "params": model_config["params"],
        "prediction_schema": "wide_dense_positions_v1", "dtype": "float64",
        "predictor_input": "history_positions_only", "future_targets_passed_to_predictor": False,
        "clipped_to_image": False, "artifacts": files, "elapsed_seconds": time.perf_counter() - start})
    return flat, files + [artifact_reference(summary_path)]


def summarize_comparison(rows: list[dict], *, video_ids: tuple[str, ...] = TRAIN) -> dict:
    """Equal original-ID weights within video, then equal video weights; no ranking."""
    from numbers import Real

    expected = {(v, method) for v in video_ids for method in METHOD_IDS}
    by_pair = {(row["video_id"], row["configuration_id"]): row for row in rows}
    if len(by_pair) != len(rows) or set(by_pair) != expected or not video_ids or len(set(video_ids)) != len(video_ids):
        raise ValueError("Baseline comparison requires exactly both methods on every video")
    names = (*METRICS, *(f"window_weighted_{key}" for key in METRICS))
    coverage_minimums = {"n_windows": 1, "evaluated_original_ids": 1,
                         "all_original_individual_ids": 1, "original_ids_without_windows": 0,
                         "segments_total": 1, "segments_with_windows": 1}
    hash_names = ("window_keys_sha256", "histories_sha256", "targets_sha256")
    paired = []
    for video in video_ids:
        left, right = (by_pair[(video, method)] for method in METHOD_IDS)
        for row in (left, right):
            if row.get("split") != "train":
                raise ValueError("Baseline summary must represent positive training coverage")
            for key, minimum in coverage_minimums.items():
                value = row.get(key)
                if type(value) is not int or value < minimum:
                    raise ValueError(f"Baseline coverage {key} must be an integer >= {minimum}")
            evaluated = row["evaluated_original_ids"]
            all_ids, without_windows = row["all_original_individual_ids"], row["original_ids_without_windows"]
            total_segments, window_segments = row["segments_total"], row["segments_with_windows"]
            if (all_ids != evaluated + without_windows
                    or not evaluated <= window_segments <= row["n_windows"]
                    or total_segments < max(window_segments, all_ids)
                    or total_segments - window_segments < without_windows):
                raise ValueError("Baseline ID/segment/window coverage counts are inconsistent")
            fps = row.get("fps")
            if isinstance(fps, bool) or not isinstance(fps, Real):
                raise ValueError("Baseline FPS must be a finite positive real number")
            try:
                valid_fps = math.isfinite(fps) and fps > 0
            except (OverflowError, TypeError, ValueError):
                valid_fps = False
            if not valid_fps:
                raise ValueError("Baseline FPS must be a finite positive real number")
            for key in hash_names:
                value = row.get(key)
                if (not isinstance(value, str) or len(value) != 64
                        or any(character not in "0123456789abcdef" for character in value)):
                    raise ValueError(f"Baseline {key} must be a canonical lowercase SHA256")
            for key in names:
                value = row[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid baseline metric {key}")
        for name in (*coverage_minimums, "fps", *hash_names):
            if left[name] != right[name]:
                raise ValueError(f"Baseline pairing differs in {name} for video {video}")
        paired.append({"video_id": video, "n_windows": left["n_windows"],
                       "evaluated_original_ids": left["evaluated_original_ids"],
                       **{f"cv_minus_persistence_{key}": right[key] - left[key] for key in names}})
    methods = []
    for method in METHOD_IDS:
        selected = [by_pair[(video, method)] for video in video_ids]
        methods.append({"configuration_id": method, "n_videos": len(video_ids),
                        "n_windows": sum(row["n_windows"] for row in selected),
                        **{f"macro_{key}": math.fsum(row[key] for row in selected) / len(video_ids) for key in names}})
    return {"status": "complete_descriptive_training_baselines", "video_ids": list(video_ids),
            "methods": methods, "paired_video_differences": paired,
            "hypothesis_tests": False, "confidence_intervals": False, "model_selected": False,
            "test_executed": False, "flow_evaluated": False, "end_to_end_evaluated": False}


def run_baselines(path: Path = REPOSITORY_ROOT / PLAN_PATH) -> Path:
    plan, metadata = load_baseline_plan(path)
    snapshot = RunSnapshot.capture()
    run = RunContext.create(module="prediction", method="prediction_baselines", algorithm="baselines",
                            stage="development", seed=42, config=plan, provenance_snapshot=snapshot)
    start, monitor = time.perf_counter(), ResourceMonitor()
    artifacts, video_rows = [], []
    try:
        parent = plan["reference"]
        reference = load_prediction_reference(REPOSITORY_ROOT / parent["manifest"],
            expected_manifest_sha256=parent["manifest_sha256"],
            verification_path=REPOSITORY_ROOT / parent["verification"],
            expected_verification_sha256=parent["verification_sha256"])
        if tuple(reference.video_ids) != TRAIN:
            raise ValueError("Reference cohort differs from the baseline plan")
        for video_id in TRAIN:
            video = reference.load_video(video_id)
            expected_windows = plan["protocol"]["expected_windows"][int(video_id)]
            for model in plan["models"]:
                folder = run.path / "by_video" / video_id / model["configuration_id"]
                row, files = evaluate_video_model(video, model, folder, batch_size=plan["run"]["batch_size"],
                    expected_windows=expected_windows,
                    check_progress=lambda: _check_budget(plan, monitor, start, run.path))
                artifacts.extend(files)
                video_rows.append(row)
                _check_budget(plan, monitor, start, run.path, inspect_files=True)
                print(f"Video {video_id}, {model['configuration_id']}: {row['n_windows']} windows complete", flush=True)
            del video
        reference_check = reference.verify_current()
        for item in [*metadata, *artifacts]:
            if artifact_reference(REPOSITORY_ROOT / item["path"]) != item:
                raise RuntimeError(f"Changed baseline metadata or output: {item['path']}")
        repo_check = snapshot.verify_current()
        repo_check["scope"] = "baseline_end_before_comparison"
        comparison = summarize_comparison(video_rows)
        if any(row["n_windows"] != plan["protocol"]["expected_total_windows"] for row in comparison["methods"]):
            raise ValueError("Baseline comparison does not cover all registered windows")
        artifacts.append(artifact_reference(write_csv_exclusive(run.path / "video_metrics.csv", video_rows)))
        artifacts.append(artifact_reference(write_csv_exclusive(run.path / "paired_video_metrics.csv", comparison["paired_video_differences"])))
        artifacts.append(artifact_reference(write_json_exclusive(run.path / "summary.json", comparison)))
        resources = _check_budget(plan, monitor, start, run.path, inspect_files=True)
        run.complete(metadata=metadata, reference_provenance=reference.provenance, reference_recheck=reference_check,
                     repository_recheck=repo_check, artifacts=artifacts, summary=comparison, resources=resources)
        return run.path
    except BaseException as exc:
        run.fail(exc, metadata=metadata, artifacts=artifacts, completed_video_models=video_rows,
                 resources=monitor.summary())
        raise
