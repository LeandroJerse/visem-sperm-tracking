"""Fixed training-prefix benchmark for compact causal flow features.

This entry measures engineering cost and coverage, not prediction errors.
Full extraction needs a separate operational plan after independent audit.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import yaml

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT
from src.experiments.causal_flow_smoke import _StrictYaml
from src.experiments.config import config_hash
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot
from src.flow.base import as_gray_u8
from src.flow.causal import pair_diagnostics, strict_sample, write_pair
from src.flow.classical.farneback import FarnebackFlow
from src.flow.compact import SampleValue, attach_samples, build_compact_requests, sampling_witness
from src.prediction.reference import TRAIN_IDS, load_prediction_reference

PLAN_PATH = "configs/flow/farneback/compact_benchmark_v1.yaml"
PLAN_HASH = "f794175a7060b687099cfc391a02f71e8ba95bf2b18dc736a0e91be741eee0e1"
FRAMES, PAIRS, CHECKPOINTS = 60, 59, (0, 58)
SAVED_FRAMES = (0, 1, 58, 59)


def artifact_reference(path: Path) -> dict:
    return {"path": path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix(),
            "sha256": sha256_file(path), "bytes": path.stat().st_size}


def load_benchmark_plan(path: Path) -> tuple[dict, list[dict]]:
    root = REPOSITORY_ROOT.resolve()
    path = (path if path.is_absolute() else root / path).resolve()
    if path != root / PLAN_PATH:
        raise ValueError("Only the canonical compact benchmark plan is accepted")
    plan = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_StrictYaml)
    if not isinstance(plan, dict) or config_hash(plan, 64) != PLAN_HASH:
        raise ValueError("Compact benchmark differs from its registered plan")
    split = root / plan["protocol"]["splits_config"]
    if sha256_file(split) != plan["protocol"]["splits_sha256"] or load_split_spec(split).train != TRAIN_IDS:
        raise ValueError("Registered training split changed")
    metadata = [artifact_reference(path), artifact_reference(split)]
    for key, hash_key in (("manifest", "manifest_sha256"), ("verification", "verification_sha256")):
        p = root / plan["causal_smoke"][key]
        record = artifact_reference(p)
        if record["sha256"] != plan["causal_smoke"][hash_key]:
            raise ValueError("Audited causal smoke metadata changed")
        value = json.loads(p.read_bytes())
        if value.get("status") != ("complete" if key == "manifest" else "passed"):
            raise ValueError("Causal smoke was not completed and audited")
        metadata.append(record)
    return plan, metadata


def projection(plan: dict, videos: list[dict], elapsed_seconds: float) -> dict:
    """A conservative planning indicator; never auto-releases a full run."""
    if [v["video_id"] for v in videos] != list(TRAIN_IDS):
        raise ValueError("Projection needs every registered training video in order")
    terms = []
    observed_variable = 0.0
    for row in videos:
        if row["windows"] <= 0 or row["unique_samples"] <= 0:
            raise ValueError("Projection unavailable: zero benchmark denominator")
        spec = plan["sources"][row["video_id"]]
        loop_scale = max((spec["total_frames"] - 1) / PAIRS,
                         spec["full_unique_samples"] / row["unique_samples"])
        table_scale = max(spec["full_windows"] / row["windows"],
                          spec["full_unique_samples"] / row["unique_samples"],
                          spec["total_frames"] / FRAMES, (spec["total_frames"] - 1) / PAIRS)
        seconds = [row[k] for k in ("loop_seconds", "table_seconds", "checkpoint_seconds")]
        if not all(np.isfinite(s) and s >= 0 for s in seconds):
            raise ValueError("Invalid recorded cost")
        observed_variable += sum(seconds)
        terms.append({"video_id": row["video_id"], "loop_scale": loop_scale, "table_scale": table_scale,
            "variable_seconds": seconds[0] * loop_scale + seconds[1] * table_scale + seconds[2],
            "artifact_bytes": row["compact_bytes"] * table_scale + row["checkpoint_bytes"]})
    if not np.isfinite(elapsed_seconds) or elapsed_seconds < observed_variable:
        raise ValueError("Recorded cost scopes exceed total elapsed time")
    fixed = elapsed_seconds - observed_variable
    factor = plan["projection"]["safety_factor"]
    seconds = factor * (fixed + sum(t["variable_seconds"] for t in terms))
    size = factor * sum(t["artifact_bytes"] for t in terms) + plan["projection"]["metadata_reserve_mb"] * 1024**2
    within = (seconds <= plan["projection"]["max_projected_seconds"]
              and size <= plan["projection"]["max_projected_artifact_mb"] * 1024**2)
    return {"status": "provisional_within_budget" if within else "exceeds_planning_budget",
        "fixed_seconds": fixed, "observed_variable_seconds": observed_variable,
        "safety_factor": factor, "metadata_reserve_mb": plan["projection"]["metadata_reserve_mb"],
        "projected_seconds": seconds, "projected_artifact_bytes": size,
        "terms": terms, "full_extraction_released": False, "full_rss_certified": False,
        "requires": "independent_qa_and_registered_full_operational_plan",
        "limitation": "prefix_density_and_motion_may_not_represent_full_videos"}


def stream_prefix(source_path: Path, spec: dict, requests, folder: Path, *, params: dict,
                  estimator_hash: str, check_progress=lambda: None, capture_factory=None,
                  estimator_factory=FarnebackFlow) -> tuple[dict, list[dict]]:
    """Hold two images and one forward field; export all interpolation witnesses."""
    import cv2

    video_id = requests.video_id
    checkpoint_folder = folder / "checkpoints"
    checkpoint_folder.mkdir(exist_ok=False)
    gray_folder = folder / "frames"
    gray_folder.mkdir(exist_ok=False)
    groups = defaultdict(list)
    for i, sample in enumerate(requests.samples):
        if sample["frame_from"] not in range(PAIRS) or sample["frame_to"] != sample["frame_from"] + 1:
            raise ValueError("Sample lies outside registered prefix")
        groups[sample["frame_from"]].append(i)
    n = len(requests.samples)
    witness_arrays = {"sample_ids": np.asarray([r["sample_id"] for r in requests.samples], dtype="U64"),
        "points_xy": np.asarray([[r["cx"], r["cy"]] for r in requests.samples], dtype=np.float64).reshape(n, 2),
        "corners_xy": np.full((n, 4, 2), -1, dtype=np.int64),
        "corner_uv": np.full((n, 4, 2), np.nan, dtype=np.float32),
        "corner_valid": np.zeros((n, 4), dtype=bool), "inside": np.zeros(n, dtype=bool)}
    artifact_paths, frame_records, pairs, diagnostic_rows = [], [], [], []
    sampled = {}
    checkpoint_seconds = 0.0
    start_loop = time.perf_counter()
    capture = (capture_factory or cv2.VideoCapture)(str(source_path))
    try:
        if not capture.isOpened():
            raise ValueError("Video could not be opened")
        for prop, expected in ((cv2.CAP_PROP_FRAME_COUNT, spec["total_frames"]),
                              (cv2.CAP_PROP_FPS, spec["fps"]), (cv2.CAP_PROP_FRAME_WIDTH, spec["width"]),
                              (cv2.CAP_PROP_FRAME_HEIGHT, spec["height"])):
            got = float(capture.get(prop))
            if not np.isfinite(got) or abs(got - expected) > 1e-6:
                raise ValueError("Video metadata differs from registered source")
        if capture.get(cv2.CAP_PROP_POS_FRAMES) != 0:
            raise ValueError("Decoder must start at frame zero")
        backend = capture.getBackendName()
        estimator = estimator_factory(**params)
        estimator.reset()
        previous = None
        for frame_index in range(FRAMES):
            check_progress()
            ok, bgr = capture.read()
            if not ok or bgr is None:
                raise ValueError(f"Incomplete prefix at frame {frame_index}; partial files preserved")
            if bgr.dtype != np.uint8 or bgr.shape != (spec["height"], spec["width"], 3):
                raise ValueError("Unexpected decoded frame shape/dtype")
            if capture.get(cv2.CAP_PROP_POS_FRAMES) != frame_index + 1:
                raise ValueError("Nonsequential decoder position")
            gray = as_gray_u8(bgr)
            frame_record = {"frame_index": frame_index, "gray_sha256": hashlib.sha256(gray.tobytes()).hexdigest()}
            if frame_index in SAVED_FRAMES:
                before = time.perf_counter()
                frame_path = gray_folder / f"{frame_index:06d}.npy"
                with frame_path.open("xb") as stream:
                    np.save(stream, gray, allow_pickle=False)
                frame_record["artifact"] = artifact_reference(frame_path)
                artifact_paths.append(frame_path)
                checkpoint_seconds += time.perf_counter() - before
            frame_records.append(frame_record)
            if previous is not None:
                s = frame_index - 1
                forward = estimator.estimate(previous, gray)
                # The strict sampler checks validity of contributing corners;
                # dtype, shape and global declared-valid finiteness remain required.
                if (forward.flow.dtype != np.float32 or forward.flow.shape != (spec["height"], spec["width"], 2)
                        or forward.valid.dtype != bool or forward.valid.shape != (spec["height"], spec["width"])
                        or not np.isfinite(forward.flow[forward.valid]).all()):
                    raise ValueError("Invalid forward field contract")
                pair_record = {"frame_from": s, "frame_to": frame_index,
                    "forward_sha256": hashlib.sha256(forward.flow.tobytes() + forward.valid.tobytes()).hexdigest()}
                indices = np.asarray(groups[s], dtype=np.int64)
                points = witness_arrays["points_xy"][indices]
                vectors, good = strict_sample(forward.flow, forward.valid, points)
                witnesses = sampling_witness(forward.flow, forward.valid, points)
                for key in ("corners_xy", "corner_uv", "corner_valid", "inside"):
                    witness_arrays[key][indices] = witnesses[key]
                for local, index in enumerate(indices):
                    key = requests.samples[index]["sample_id"]
                    reason = "" if good[local] else ("outside_image" if not witnesses["inside"][local] else "invalid_contributor")
                    sampled[key] = SampleValue(float(vectors[local, 0]), float(vectors[local, 1]), bool(good[local]), reason)
                if s in CHECKPOINTS:
                    before = time.perf_counter()
                    backward = estimator.estimate(gray, previous)
                    pair_path = checkpoint_folder / f"{s:06d}_{frame_index:06d}.npz"
                    pair_record["checkpoint"] = write_pair(pair_path, video_id=video_id, frame_from=s, frame_to=frame_index,
                        source_sha256=spec["sha256"], estimator_hash=estimator_hash, forward=forward, backward=backward)
                    artifact_paths.append(pair_path)
                    diagnostic_rows.append({"video_id": video_id, "frame_from": s, "frame_to": frame_index,
                                           **pair_diagnostics(previous, gray, forward, backward, threshold=1.5)})
                    checkpoint_seconds += time.perf_counter() - before
                pairs.append(pair_record)
            previous = gray
        if len(pairs) != PAIRS or len(frame_records) != FRAMES or len(sampled) != n:
            raise ValueError("Incomplete prefix or sampling")
    finally:
        capture.release()
    loop_seconds = time.perf_counter() - start_loop - checkpoint_seconds
    before_tables = time.perf_counter()
    features = attach_samples(requests, sampled)
    identity = {"schema_version": 1, "video_id": video_id, "source_sha256": spec["sha256"],
                "estimator_hash": estimator_hash, "width": spec["width"], "height": spec["height"]}
    path = folder / "witnesses.npz"
    with path.open("xb") as stream:
        np.savez_compressed(stream, metadata=np.asarray(json.dumps(identity, sort_keys=True)), **witness_arrays)
    artifact_paths.append(path)
    for name, value in (("frame_index.json", {**identity, "backend": backend, "frames": frame_records,
                                           "last_frame_returned": 59, "full_video_decoding_verified": False}),
                        ("pair_index.json", {**identity, "pairs": pairs})):
        artifact_paths.append(write_json_exclusive(folder / name, value))
    feature_rows = [{**r, "u": r["u"] if r["valid"] else None,
                    "v": r["v"] if r["valid"] else None} for r in features.samples]
    coverage_rows = [{**r, "invalid_reasons_history19": json.dumps(dict(r["invalid_reasons_history19"]), sort_keys=True),
                     "invalid_reasons_last5": json.dumps(dict(r["invalid_reasons_last5"]), sort_keys=True)} for r in features.coverage]
    for name, rows in (("features.csv", feature_rows), ("window_coverage.csv", coverage_rows),
                       ("checkpoint_metrics.csv", diagnostic_rows)):
        artifact_paths.append(write_csv_exclusive(folder / name, rows))
    checkpoint_bytes = sum(p.stat().st_size for p in artifact_paths if p.parent in (checkpoint_folder, gray_folder))
    artifacts = [artifact_reference(p) for p in artifact_paths]
    table_seconds = time.perf_counter() - before_tables
    return {"video_id": video_id, "frames": FRAMES, "forward_fields": PAIRS,
        "backward_fields": len(CHECKPOINTS), "windows": len(requests.windows), "unique_samples": n,
        "historical_uses": len(requests.windows) * 19, "valid_samples": sum(r["valid"] for r in features.samples),
        "eligible_last5_windows": sum(r["eligible_last5"] for r in features.coverage),
        "loop_seconds": loop_seconds, "checkpoint_seconds": checkpoint_seconds,
        "table_seconds": table_seconds, "checkpoint_bytes": checkpoint_bytes}, artifacts


def run_compact_benchmark(path: Path = REPOSITORY_ROOT / PLAN_PATH) -> Path:
    import cv2

    plan, metadata = load_benchmark_plan(path)
    snapshot = RunSnapshot.capture()
    run = RunContext.create(module="flow", method="farneback", algorithm="farneback", stage="benchmark",
                            seed=42, config=plan, provenance_snapshot=snapshot)
    start, monitor = time.perf_counter(), ResourceMonitor()
    artifacts, summaries, sources = [], [], []
    old_threads, old_opencl = cv2.getNumThreads(), cv2.ocl.useOpenCL()

    def check_budget():
        resources = monitor.summary()
        size = sum(p.stat().st_size for p in run.path.rglob("*") if p.is_file())
        if (time.perf_counter() - start > plan["budget"]["soft_wall_seconds"]
                or resources["ram_rss_peak_mb"] is None
                or resources["ram_rss_peak_mb"] > plan["budget"]["max_sampled_rss_mb"]
                or size > plan["budget"]["max_artifact_mb"] * 1024**2):
            raise RuntimeError("Compact benchmark budget exceeded; partial run preserved")
        return {**resources, "artifact_bytes_before_final_manifest": size}

    try:
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        cv2.setRNGSeed(42)
        parent = plan["reference"]
        reference = load_prediction_reference(REPOSITORY_ROOT / parent["manifest"],
            expected_manifest_sha256=parent["manifest_sha256"], verification_path=REPOSITORY_ROOT / parent["verification"],
            expected_verification_sha256=parent["verification_sha256"])
        # Fix every request before opening the first MP4. The reference loader
        # parses only exported metadata; history iteration never returns targets.
        requests_by_video, preparation_seconds = {}, {}
        for video_id in TRAIN_IDS:
            check_budget()
            video = reference.load_video(video_id)
            spec = plan["sources"][video_id]
            if (video.n_windows != spec["full_windows"] or video.fps != spec["fps"]
                    or video.summary["segments_with_windows"] != spec["full_segments_with_windows"]):
                raise ValueError("Full-reference counts or FPS changed")
            cpath = (REPOSITORY_ROOT / parent["manifest"]).parent / "by_video" / video_id / "input_contract.json"
            cref = next(r for r in reference.provenance["validated_inputs"] if Path(r["path"]).resolve() == cpath.resolve())
            if sha256_file(cpath) != cref["sha256"]:
                raise ValueError("Reference input contract changed")
            expected = {"path": str((REPOSITORY_ROOT / spec["path"]).resolve()), "sha256": spec["sha256"], "bytes": spec["bytes"]}
            if json.loads(cpath.read_bytes())["source_video"] != expected:
                raise ValueError("Source does not match parent")
            before = time.perf_counter()
            requests = build_compact_requests(video.iter_history_batches(first_origin=19, last_origin=59), video_id=video_id)
            if not requests.windows or not requests.samples:
                raise ValueError("Empty prefix: do not replace origin or video")
            folder = run.path / "by_video" / video_id
            folder.mkdir(parents=True, exist_ok=False)
            for name, rows in (("selected_windows.csv", requests.windows), ("requests.csv", requests.samples),
                ("links.csv", [{"window_id": r["window_id"], "sample_ids": json.dumps(list(r["sample_ids"]), separators=(",", ":"))}
                               for r in requests.links])):
                artifacts.append(artifact_reference(write_csv_exclusive(folder / name, rows)))
            preparation_seconds[video_id] = time.perf_counter() - before
            requests_by_video[video_id] = requests
        estimator_hash = config_hash({"method": "farneback", "params": plan["params"], "input": plan["flow"]["input"], "mask": "none"}, 64)
        for video_id in TRAIN_IDS:
            spec = plan["sources"][video_id]
            source_path = REPOSITORY_ROOT / spec["path"]
            src = artifact_reference(source_path)
            if src["sha256"] != spec["sha256"] or src["bytes"] != spec["bytes"]:
                raise ValueError("MP4 hash differs from registered source")
            sources.append(src)
            folder = run.path / "by_video" / video_id
            result, outputs = stream_prefix(source_path, spec, requests_by_video[video_id], folder,
                params=plan["params"], estimator_hash=estimator_hash, check_progress=check_budget)
            artifacts.extend(outputs)
            result["table_seconds"] += preparation_seconds[video_id]
            result["compact_bytes"] = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) - result["checkpoint_bytes"]
            summaries.append(result)
            print(f"Video {video_id}: 60 frames, 59 forward fields, {result['windows']} windows, {result['unique_samples']} unique samples", flush=True)
        ref_check = reference.verify_current()
        for r in [*metadata, *sources]:
            if artifact_reference(REPOSITORY_ROOT / r["path"]) != r:
                raise RuntimeError("Input/output changed during benchmark")
        for result in summaries:
            folder = run.path / "by_video" / result["video_id"]
            before = time.perf_counter()
            refs = [r for r in artifacts if (REPOSITORY_ROOT / r["path"]).is_relative_to(folder)]
            for r in refs:
                if artifact_reference(REPOSITORY_ROOT / r["path"]) != r:
                    raise RuntimeError("Output changed during benchmark")
            result["table_seconds"] += time.perf_counter() - before
            artifacts.append(artifact_reference(write_json_exclusive(folder / "summary.json", result)))
        repository_check = snapshot.verify_current()
        repository_check["scope"] = "compact_benchmark_end_before_certification"
        measured_elapsed = time.perf_counter() - start
        cost_projection = projection(plan, summaries, measured_elapsed)
        summary = {"status": "complete_compact_engineering_benchmark", "video_ids": list(TRAIN_IDS), "videos": summaries,
            **{key: sum(v[key] for v in summaries) for key in ("frames", "forward_fields", "backward_fields", "windows", "unique_samples", "historical_uses", "valid_samples", "eligible_last5_windows")},
            "projection_elapsed_seconds": measured_elapsed, "projection": cost_projection,
            "prediction_evaluated": False, "hypothesis_evaluated": False, "parameters_selected": False,
            "validation_test_sources_read": False, "physical_fluid_velocity_measured": False,
            "full_extraction_released": False}
        if (summary["frames"], summary["forward_fields"], summary["backward_fields"]) != (720, 708, 24):
            raise ValueError("Incomplete benchmark frame/pair coverage")
        artifacts.append(artifact_reference(write_json_exclusive(run.path / "summary.json", summary)))
        resources = check_budget()
        run.complete(metadata=metadata, source_videos=sources, reference_provenance=reference.provenance,
            reference_recheck=ref_check, repository_recheck=repository_check, artifacts=artifacts,
            summary=summary, resources=resources, runtime_settings={"opencv_threads": cv2.getNumThreads(),
                "opencl": cv2.ocl.useOpenCL(), "rng_seed": 42, "estimator_hash": estimator_hash})
        return run.path
    except BaseException as exc:
        run.fail(exc, metadata=metadata, source_videos=sources, artifacts=artifacts,
                 completed_videos=summaries, resources=monitor.summary())
        raise
    finally:
        cv2.setNumThreads(old_threads)
        cv2.ocl.setUseOpenCL(old_opencl)


def main() -> None:
    argparse.ArgumentParser(description="Benchmark compacto causal registrado, somente prefixos dos 12 treinos.").parse_args()
    print(run_compact_benchmark(), flush=True)


if __name__ == "__main__":
    main()
