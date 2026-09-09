"""Prospectively fixed Farneback smoke: causal fields, history-only features.

This executor cannot open another split, origin or cache through overrides.
It tests engineering integrity, not prediction performance or model selection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

import numpy as np
import yaml

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT
from src.experiments.config import config_hash
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot
from src.flow.base import as_gray_u8
from src.flow.causal import load_pair, pair_diagnostics, strict_sample, temporal_diagnostics, write_pair
from src.flow.classical.farneback import FarnebackFlow
from src.prediction.reference import HistoryBatch, load_prediction_reference

PLAN_PATH = "configs/flow/farneback/causal_smoke_v1.yaml"
PLAN_HASH = "f7e0afa345b3774127bb622a03ab21d1100dd9655dbd7bb0c6c3eaaa4f13708f"
VIDEOS = ("11", "12")
ORIGIN, HISTORY_LENGTH, PAIRS = 19, 20, 19


class _StrictYaml(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    value = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in value:
            raise ValueError(f"Duplicate flow plan key: {key}")
        value[key] = loader.construct_object(value_node, deep=True)
    return value


_StrictYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def artifact_reference(path: Path) -> dict:
    return {"path": path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix(),
            "sha256": sha256_file(path), "bytes": path.stat().st_size}


def load_smoke_plan(path: Path) -> tuple[dict, list[dict]]:
    root = REPOSITORY_ROOT.resolve()
    path = (path if path.is_absolute() else root / path).resolve()
    if path != root / PLAN_PATH:
        raise ValueError("Only the canonical registered causal smoke plan is accepted")
    plan = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_StrictYaml)
    if not isinstance(plan, dict) or config_hash(plan, 64) != PLAN_HASH:
        raise ValueError("Causal smoke plan differs from its registered contract")
    split = root / plan["protocol"]["splits_config"]
    if sha256_file(split) != plan["protocol"]["splits_sha256"]:
        raise ValueError("Registered splits changed")
    if not set(VIDEOS).issubset(load_split_spec(split).train):
        raise ValueError("Smoke videos must belong to train")
    return plan, [artifact_reference(path), artifact_reference(split)]


def select_histories(video) -> HistoryBatch:
    batch = video.history_batch_at_origin(ORIGIN)
    if not batch.window_rows or batch.histories.shape != (len(batch.window_rows), HISTORY_LENGTH, 2):
        raise ValueError("No complete histories at the fixed origin; do not replace it")
    if batch.histories.dtype != np.float64 or not np.isfinite(batch.histories).all():
        raise ValueError("History coordinates must remain finite float64")
    keys = set()
    for row in batch.window_rows:
        if (row["video_id"] != video.video_id or row["split"] != "train"
                or row["history_start"] != 0 or row["origin_frame"] != ORIGIN
                or row["history_length"] != HISTORY_LENGTH or row["forecast_horizon"] != 10
                or row["future_end"] != 29 or row["window_id"] in keys):
            raise ValueError("History batch contains unexpected or repeated windows")
        keys.add(row["window_id"])
    return batch


def decode_prefix(source_path: Path, spec: dict, folder: Path, *, check_progress=lambda: None,
                  capture_factory=None) -> tuple[list[np.ndarray], dict]:
    """Request exactly frames 0..19; early EOF is failure, not completion."""
    import cv2

    capture = (capture_factory or cv2.VideoCapture)(str(source_path))
    try:
        if not capture.isOpened():
            raise ValueError("Video could not be opened")
        expected = {cv2.CAP_PROP_FRAME_COUNT: spec["total_frames"],
                    cv2.CAP_PROP_FRAME_WIDTH: spec["width"], cv2.CAP_PROP_FRAME_HEIGHT: spec["height"],
                    cv2.CAP_PROP_FPS: spec["fps"]}
        for prop, value in expected.items():
            measured = float(capture.get(prop))
            if not np.isfinite(measured) or abs(measured - value) > 1e-6:
                raise ValueError(f"Video metadata differs from registered source: property {prop}")
        if float(capture.get(cv2.CAP_PROP_POS_FRAMES)) != 0:
            raise ValueError("Decoder did not start at frame zero")
        folder.mkdir(parents=True, exist_ok=False)
        frames, records = [], []
        for frame_index in range(HISTORY_LENGTH):
            check_progress()
            ok, image = capture.read()
            if not ok or image is None:
                raise ValueError(f"Incomplete prefix: decoder failed at frame {frame_index}")
            if image.dtype != np.uint8 or image.shape != (spec["height"], spec["width"], 3):
                raise ValueError(f"Decoded frame {frame_index} has unexpected shape/dtype")
            position = float(capture.get(cv2.CAP_PROP_POS_FRAMES))
            if position != frame_index + 1:
                raise ValueError("Decoder frame position is not sequential")
            gray = as_gray_u8(image)
            path = folder / f"{frame_index:06d}.npy"
            with path.open("xb") as stream:
                np.save(stream, gray, allow_pickle=False)
            frames.append(gray)
            records.append({"frame_index": frame_index, "path": path.name,
                            "sha256": sha256_file(path), "bytes": path.stat().st_size,
                            "decoded_position_after_read": position})
        return frames, {"schema_version": 1, "source_sha256": spec["sha256"],
                        "width": spec["width"], "height": spec["height"], "fps": spec["fps"],
                        "backend": capture.getBackendName(), "frames": records,
                        "frames_requested": HISTORY_LENGTH, "last_frame_returned": ORIGIN,
                        "full_video_decoding_verified": False}
    finally:
        capture.release()


def read_pair_index(path: Path, expected_sha256: str, *, video_id: str,
                    source: dict, estimator_hash: str) -> list[dict]:
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != expected_sha256:
        raise ValueError("Pair index hash changed")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate pair-index JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Nonfinite pair-index constant: {value}")

    index = json.loads(blob, object_pairs_hook=unique_object, parse_constant=reject_constant)
    expected = {"schema_version": 1, "video_id": video_id, "origin_frame": ORIGIN,
                "source_sha256": source["sha256"], "estimator_hash": estimator_hash}
    if (not isinstance(index, dict) or set(index) != set(expected) | {"pairs"}
            or any(type(index.get(k)) is not type(v) or index.get(k) != v for k, v in expected.items())):
        raise ValueError("Pair index identity mismatch")
    rows = index["pairs"]
    if not isinstance(rows, list) or len(rows) != PAIRS:
        raise ValueError("Pair index must cover exactly 19 pairs")
    for frame, row in enumerate(rows):
        required = {"path": f"{frame:06d}_{frame+1:06d}.npz", "video_id": video_id,
                    "frame_from": frame, "frame_to": frame + 1, "source_sha256": source["sha256"],
                    "estimator_hash": estimator_hash, "width": source["width"], "height": source["height"]}
        if (not isinstance(row, dict) or set(row) != set(required) | {"sha256"}
                or any(type(row.get(k)) is not type(v) or row.get(k) != v for k, v in required.items())
                or not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Missing, repeated, reordered or incompatible pair")
    return rows


def sample_histories(batch: HistoryBatch, pair_folder: Path, records: list[dict], *, video_id: str,
                     source: dict, estimator_hash: str, check_progress=lambda: None) -> tuple[list[dict], list[dict]]:
    """The flow consumer gets no future position array and loads no future pair."""
    if len(records) != PAIRS:
        raise ValueError("Features require every historical pair")
    features, valid_counts = [], Counter()
    for frame_from, record in enumerate(records):
        if (record["frame_from"] != frame_from or record["frame_to"] != frame_from + 1
                or record["width"] != source["width"] or record["height"] != source["height"]):
            raise ValueError("Feature pair differs from expected temporal/spatial support")
        forward, _ = load_pair(pair_folder / record["path"], record, video_id=video_id,
                               frame_from=frame_from, frame_to=frame_from + 1, origin_frame=ORIGIN,
                               source_sha256=source["sha256"], estimator_hash=estimator_hash)
        points = batch.histories[:, frame_from, :]
        sampled, good = strict_sample(forward.flow, forward.valid, points)
        for i, row in enumerate(batch.window_rows):
            x, y = map(float, points[i])
            valid = bool(good[i])
            inside = 0 <= x <= source["width"] - 1 and 0 <= y <= source["height"] - 1
            reason = "" if valid else "outside_image" if not inside else "invalid_support"
            features.append({"window_id": row["window_id"], "video_id": video_id,
                "track_id": row["track_id"], "segment_id": row["segment_id"], "origin_frame": ORIGIN,
                "frame_from": frame_from, "frame_to": frame_from + 1, "available_at": frame_from + 1,
                "sample_x": x, "sample_y": y, "u": float(sampled[i, 0]) if valid else None,
                "v": float(sampled[i, 1]) if valid else None, "valid": valid, "invalid_reason": reason,
                "pair_sha256": record["sha256"]})
            valid_counts[row["window_id"]] += valid
        check_progress()
    coverage = [{"window_id": row["window_id"], "video_id": video_id, "origin_frame": ORIGIN,
                 "track_id": row["track_id"], "segment_id": row["segment_id"], "expected_samples": PAIRS,
                 "valid_samples": valid_counts[row["window_id"]],
                 "invalid_samples": PAIRS - valid_counts[row["window_id"]],
                 "all_history_flow_valid": valid_counts[row["window_id"]] == PAIRS}
                for row in batch.window_rows]
    return features, coverage


def summarize_video(video_id: str, batch: HistoryBatch, features: list[dict], coverage: list[dict],
                    pairs: list[dict], temporal: list[dict]) -> dict:
    windows = len(batch.window_rows)
    if len(pairs) != PAIRS or len(temporal) != PAIRS - 1 or len(features) != windows * PAIRS or len(coverage) != windows:
        raise ValueError("Incomplete output counts")
    valid = sum(row["valid"] for row in features)
    if sum(row["valid_samples"] for row in coverage) != valid:
        raise ValueError("Coverage does not reconcile")
    metrics = {}
    for rows, keys in ((pairs, ("photometric_warp_mae", "photometric_zero_mae", "forward_backward_mae", "consistent_fraction",
                               "photometric_valid_fraction", "forward_backward_valid_fraction", "flow_finite_valid_fraction")),
                       (temporal, ("advected_temporal_mean_change", "advected_temporal_p95_change", "advected_temporal_valid_fraction"))):
        for key in keys:
            values = [float(row[key]) for row in rows if row[key] is not None]
            if not all(np.isfinite(values)):
                raise ValueError("Nonfinite diagnostic escaped explicit absence handling")
            metrics[key] = {"mean_equal_pairs_with_support": float(np.mean(values)) if values else None,
                            "pairs_with_support": len(values), "total_pairs": len(rows)}
    return {"video_id": video_id, "split": "train", "origin_frame": ORIGIN,
            "decoded_frames": HISTORY_LENGTH, "pairs": PAIRS, "directional_fields": 2 * PAIRS,
            "temporal_comparisons": len(temporal), "selected_windows": windows,
            "feature_rows": len(features), "valid_feature_rows": valid, "invalid_feature_rows": len(features) - valid,
            "complete_valid_windows": sum(row["all_history_flow_valid"] for row in coverage),
            "invalid_reasons": dict(Counter(row["invalid_reason"] for row in features if not row["valid"])),
            "metrics": metrics, "estimate_both_directions_seconds": sum(row["estimate_seconds"] for row in pairs),
            "diagnostics_seconds": sum(row["diagnostics_seconds"] for row in pairs),
            "interpretation": "causal_engineering_smoke_not_flow_accuracy_or_prediction_improvement"}


def run_causal_smoke(path: Path = REPOSITORY_ROOT / PLAN_PATH) -> Path:
    import cv2

    plan, metadata = load_smoke_plan(path)
    snapshot = RunSnapshot.capture()
    run = RunContext.create(module="flow", method="farneback", algorithm="farneback", stage="smoke",
                            seed=42, config=plan, provenance_snapshot=snapshot)
    start, monitor = time.perf_counter(), ResourceMonitor()
    artifacts, source_records, summaries = [], [], []
    previous_threads, previous_opencl = cv2.getNumThreads(), cv2.ocl.useOpenCL()

    def check_budget():
        resources = monitor.summary()
        size = sum(p.stat().st_size for p in run.path.rglob("*") if p.is_file())
        if (time.perf_counter() - start > plan["budget"]["soft_wall_seconds"]
                or resources["ram_rss_peak_mb"] is None
                or resources["ram_rss_peak_mb"] > plan["budget"]["max_sampled_rss_mb"]
                or size > plan["budget"]["max_artifact_mb"] * 1024**2):
            raise RuntimeError("Causal smoke budget exceeded; partial run preserved")
        return {**resources, "artifact_bytes_before_final_manifest": size}

    try:
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        cv2.setRNGSeed(42)
        parent = plan["reference"]
        reference = load_prediction_reference(REPOSITORY_ROOT / parent["manifest"],
            expected_manifest_sha256=parent["manifest_sha256"],
            verification_path=REPOSITORY_ROOT / parent["verification"],
            expected_verification_sha256=parent["verification_sha256"])
        batches = {}
        for video_id in VIDEOS:
            video = reference.load_video(video_id)
            batch = select_histories(video)
            batches[video_id] = batch
            folder = run.path / "by_video" / video_id
            folder.mkdir(parents=True, exist_ok=False)
            artifacts.append(artifact_reference(write_csv_exclusive(folder / "selected_windows.csv", batch.window_rows)))
            histories = [{"window_id": row["window_id"], "video_id": video_id, "track_id": row["track_id"],
                          "segment_id": row["segment_id"], "origin_frame": ORIGIN, "frame_index": frame,
                          "cx": float(batch.histories[i, frame, 0]), "cy": float(batch.histories[i, frame, 1])}
                         for i, row in enumerate(batch.window_rows) for frame in range(HISTORY_LENGTH)]
            artifacts.append(artifact_reference(write_csv_exclusive(folder / "histories.csv", histories)))
            # Match the MP4 identity already certified by the parent before
            # opening that MP4. Only exported contract JSON is read here.
            contract_path = REPOSITORY_ROOT / parent["manifest"]
            contract_path = contract_path.parent / "by_video" / video_id / "input_contract.json"
            contract_record = next(item for item in reference.provenance["validated_inputs"]
                                   if Path(item["path"]).resolve() == contract_path.resolve())
            if sha256_file(contract_path) != contract_record["sha256"]:
                raise ValueError("Parent input contract changed")
            contract = json.loads(contract_path.read_bytes())
            spec = plan["sources"][video_id]
            source_path = (REPOSITORY_ROOT / spec["path"]).resolve()
            expected_source = {"path": str(source_path), "sha256": spec["sha256"], "bytes": spec["bytes"]}
            if contract["source_video"] != expected_source or video.fps != spec["fps"]:
                raise ValueError("Source identity differs from audited individual reference")
            check_budget()
        estimator_hash = config_hash({"method": "farneback", "params": plan["params"],
                                      "input": plan["flow"]["input"], "mask": "none"}, 64)
        for video_id in VIDEOS:
            folder, spec = run.path / "by_video" / video_id, plan["sources"][video_id]
            source_path = REPOSITORY_ROOT / spec["path"]
            src = artifact_reference(source_path)
            if src["sha256"] != spec["sha256"] or src["bytes"] != spec["bytes"]:
                raise ValueError("Original MP4 does not match the registered source")
            source_records.append(src)
            frames, frame_index = decode_prefix(source_path, spec, folder / "frames", check_progress=check_budget)
            frame_index["video_id"] = video_id
            artifacts.extend(artifact_reference(folder / "frames" / row["path"]) for row in frame_index["frames"])
            artifacts.append(artifact_reference(write_json_exclusive(folder / "frames.json", frame_index)))
            pair_folder = folder / "pairs"
            pair_folder.mkdir(exist_ok=False)
            estimator = FarnebackFlow(**plan["params"])
            estimator.reset()
            pair_records, pair_rows, temporal_rows = [], [], []
            previous_forward = None
            for frame_from in range(PAIRS):
                check_budget()
                a, b = frames[frame_from:frame_from + 2]
                before = time.perf_counter()
                forward, backward = estimator.estimate(a, b), estimator.estimate(b, a)
                estimate_seconds = time.perf_counter() - before
                monitor.sample()
                pair_path = pair_folder / f"{frame_from:06d}_{frame_from+1:06d}.npz"
                record = write_pair(pair_path, video_id=video_id, frame_from=frame_from, frame_to=frame_from + 1,
                                    source_sha256=spec["sha256"], estimator_hash=estimator_hash,
                                    forward=forward, backward=backward)
                pair_records.append(record)
                artifacts.append(artifact_reference(pair_path))
                before = time.perf_counter()
                metrics = pair_diagnostics(a, b, forward, backward, threshold=1.5)
                if previous_forward is not None:
                    temporal_rows.append({"video_id": video_id, "first_frame": frame_from - 1,
                        "middle_frame": frame_from, "last_frame": frame_from + 1,
                        **temporal_diagnostics(previous_forward, forward)})
                pair_rows.append({"video_id": video_id, "frame_from": frame_from, "frame_to": frame_from + 1,
                                  "estimate_seconds": estimate_seconds, "diagnostics_seconds": time.perf_counter() - before,
                                  **metrics})
                previous_forward = forward
                check_budget()
            index_path = write_json_exclusive(folder / "pair_index.json", {
                "schema_version": 1, "video_id": video_id, "origin_frame": ORIGIN,
                "source_sha256": spec["sha256"], "estimator_hash": estimator_hash, "pairs": pair_records})
            index_ref = artifact_reference(index_path)
            artifacts.append(index_ref)
            authenticated = read_pair_index(index_path, index_ref["sha256"], video_id=video_id,
                                            source=spec, estimator_hash=estimator_hash)
            features, coverage = sample_histories(batches[video_id], pair_folder, authenticated, video_id=video_id,
                source=spec, estimator_hash=estimator_hash, check_progress=check_budget)
            summary = summarize_video(video_id, batches[video_id], features, coverage, pair_rows, temporal_rows)
            for name, rows in (("features", features), ("window_coverage", coverage),
                               ("pair_metrics", pair_rows), ("temporal_metrics", temporal_rows)):
                artifacts.append(artifact_reference(write_csv_exclusive(folder / f"{name}.csv", rows)))
            artifacts.append(artifact_reference(write_json_exclusive(folder / "summary.json", summary)))
            summaries.append(summary)
            print(f"Video {video_id}: 20 frames, 19 pairs, {summary['feature_rows']} feature rows complete", flush=True)
        reference_check = reference.verify_current()
        for item in [*metadata, *artifacts, *source_records]:
            if artifact_reference(REPOSITORY_ROOT / item["path"]) != item:
                raise RuntimeError(f"Input/output changed before completion: {item['path']}")
        repository_check = snapshot.verify_current()
        repository_check["scope"] = "causal_smoke_end_before_certification"
        summary = {"status": "complete_causal_engineering_smoke", "video_ids": list(VIDEOS),
            "decoded_frames": sum(row["decoded_frames"] for row in summaries), "pairs": sum(row["pairs"] for row in summaries),
            "directional_fields": sum(row["directional_fields"] for row in summaries),
            "selected_windows": sum(row["selected_windows"] for row in summaries),
            "feature_rows": sum(row["feature_rows"] for row in summaries),
            "valid_feature_rows": sum(row["valid_feature_rows"] for row in summaries),
            "invalid_feature_rows": sum(row["invalid_feature_rows"] for row in summaries),
            "videos": summaries, "hypothesis_evaluated": False, "prediction_evaluated": False,
            "parameters_selected": False, "validation_test_sources_read": False,
            "future_images_returned_to_estimator": False, "physical_fluid_velocity_measured": False}
        if summary["decoded_frames"] != 40 or summary["pairs"] != 38 or summary["directional_fields"] != 76:
            raise ValueError("Smoke coverage is incomplete")
        artifacts.append(artifact_reference(write_json_exclusive(run.path / "summary.json", summary)))
        resources = check_budget()
        run.complete(metadata=metadata, source_videos=source_records, reference_provenance=reference.provenance,
            reference_recheck=reference_check, repository_recheck=repository_check, artifacts=artifacts, summary=summary,
            resources=resources, runtime_settings={"opencv_threads": cv2.getNumThreads(), "opencl": cv2.ocl.useOpenCL(),
                                                   "rng_seed": 42, "estimator_hash": estimator_hash})
        return run.path
    except BaseException as exc:
        run.fail(exc, metadata=metadata, source_videos=source_records, artifacts=artifacts,
                 completed_videos=summaries, resources=monitor.summary())
        raise
    finally:
        cv2.setNumThreads(previous_threads)
        cv2.ocl.setUseOpenCL(previous_opencl)


def main() -> None:
    argparse.ArgumentParser(description="Executa o smoke causal registrado de Farneback, somente treino11/12.").parse_args()
    print(run_causal_smoke(), flush=True)


if __name__ == "__main__":
    main()
