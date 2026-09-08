"""Prepare the registered training-only individual reference, without predictors.

The entry point deliberately has no split, input-root or scientific overrides.
It exports raw GT beside individual observations and window indices so a second
implementation can audit eligibility without reopening the original sources.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import yaml

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT
from src.detection.io import CSV_FIELDS, detection_to_row
from src.detection.strict_inputs import prepare_full_video_input
from src.experiments.config import config_hash
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot
from src.prediction.ground_truth import build_individual_ground_truth


PLAN = "configs/protocol/individual_trajectories_v1.yaml"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
EXPECTED_FRAMES = {video: 1440 if video == "35" else 1500 if video == "82" else 1470
                   for video in TRAIN}
GAPS = {"23": [[823, 972], [1084, 1107]]}
TABLE_FIELDS = {
    "observations": "video_id frame_index annotated track_id segment_id class_id cx cy w h x y".split(),
    "segments": "video_id track_id segment_id split start_frame end_frame observation_count start_reason end_reason end_boundary_frame".split(),
    "windows": "window_id video_id track_id segment_id split history_start origin_frame future_end history_length forecast_horizon".split(),
    "frame_status": "video_id frame_index annotated raw_count individual_count cluster_count".split(),
}


class _StrictYaml(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"Duplicate plan key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def reference(path: Path) -> dict:
    return {"path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": sha256_file(path), "bytes": path.stat().st_size}


def load_plan(path: Path) -> tuple[dict, list[dict]]:
    """Fail before source access if any registered cohort/eligibility rule drifts."""
    root = REPOSITORY_ROOT.resolve()
    path = Path(path)
    path = (path if path.is_absolute() else root / path).resolve()
    if path != root / PLAN:
        raise ValueError("Only the canonical registered preparation plan may be read")
    plan = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_StrictYaml)
    expected = {
        "plan_id": "individual_trajectories_v1_20260908",
        "method": "ground_truth_individuals",
        "configuration_id": "individual_trajectories_v1",
        "purpose": "training_reference_preparation_without_model_evaluation",
        "input": {"root": "data/sources/visem_tracking/dataset/Train", "width": 640, "height": 480,
                  "expected_frames": {int(k): v for k, v in EXPECTED_FRAMES.items()},
                  "missing_label_ranges": {23: GAPS["23"]},
                  "read_mode": "label_contents_and_mp4_hash_metadata_without_pixel_decoding"},
        "eligibility": {"individual_classes": [0, 2], "cluster_class": 1,
                        "preserve_original_track_ids": True,
                        "break_on": ["annotation_absent", "class_1", "id_absent"],
                        "keep_individuals_inside_cluster_boxes": True,
                        "interpolate": False, "spatial_or_speed_filter": False},
        "windows": {"history_length": 20, "forecast_horizon": 10, "stride": 1,
                    "output": "indices_only", "future_reference_use": "offline_eligibility_and_targets_only",
                    "report_origins_excluded_incomplete_future": True},
        "run": {"stage": "preparation", "split": "train", "seed": 42,
                "order": "registered_train_id_order", "randomness": "none"},
        "output": {"root": "data/derived", "overwrite": False},
        "budget": {"soft_wall_seconds": 1200, "max_sampled_rss_mb": 2048,
                   "max_artifact_mb": 2048, "on_failure": "preserve_partial_run_without_completion"},
        "protocol": {"splits_config": "configs/protocol/splits.yaml",
                     "splits_sha256": "f147f748c58d46d39868b2717df2369f2e46efa4af3ebfef93c7821002aad101",
                     "inventory": "data/manifests/visem_tracking.csv",
                     "inventory_sha256": "d28e4f543f45d6b41add122789126eda1377a973f72f600a3bde75d6c2d8f03b",
                     "annotation_gaps": "data/manifests/annotation_gaps.csv",
                     "train_ids": [int(video) for video in TRAIN], "statistical_unit": "video"},
    }
    # Canonical JSON distinguishes booleans from numbers (False != 0 here).
    if config_hash(plan, 64) != config_hash(expected, 64):
        raise ValueError("Plan differs from the registered training-only v1 contract")
    refs = [reference(path)]
    protocol = plan["protocol"]
    for key in ("splits_config", "inventory", "annotation_gaps"):
        item = reference(REPOSITORY_ROOT / protocol[key])
        hash_key = "splits_sha256" if key == "splits_config" else f"{key}_sha256"
        if hash_key in protocol and item["sha256"] != protocol[hash_key]:
            raise ValueError(f"Changed versioned metadata: {key}")
        refs.append(item)
    if load_split_spec(REPOSITORY_ROOT / protocol["splits_config"]).train != TRAIN:
        raise ValueError("Training cohort differs from registered IDs")
    with (REPOSITORY_ROOT / protocol["annotation_gaps"]).open(encoding="utf-8-sig", newline="") as stream:
        gaps = list(csv.DictReader(stream))
    observed = [(r["video_id"], int(r["start_frame"]), int(r["end_frame"]),
                 int(r["frame_count"]), r["policy"], r["reason"]) for r in gaps]
    if observed != [("23", 823, 972, 150, "exclude", "missing_label_file"),
                    ("23", 1084, 1107, 24, "exclude", "missing_label_file")]:
        raise ValueError("Annotation-gap metadata changed")
    return plan, refs


def check_budget(plan: dict, monitor: ResourceMonitor, start: float, folder: Path) -> dict:
    resources = monitor.summary()
    artifact_bytes = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    if (time.perf_counter() - start > plan["budget"]["soft_wall_seconds"]
            or resources["ram_rss_peak_mb"] is None
            or resources["ram_rss_peak_mb"] > plan["budget"]["max_sampled_rss_mb"]
            or artifact_bytes > plan["budget"]["max_artifact_mb"] * 1024**2):
        raise RuntimeError("Preparation budget exceeded; partial output preserved")
    return {**resources, "artifact_bytes_before_final_manifest": artifact_bytes}


def prepare(path: Path) -> Path:
    plan, metadata_refs = load_plan(path)
    snapshot = RunSnapshot.capture()
    run = RunContext.create(module="prediction", method=plan["method"], stage="preparation",
                            seed=42, config=plan, output_root=REPOSITORY_ROOT / "data/derived",
                            provenance_snapshot=snapshot)
    start, monitor = time.perf_counter(), ResourceMonitor()
    inputs, summaries, artifacts = [], [], []
    try:
        for video in TRAIN:
            base = REPOSITORY_ROOT / plan["input"]["root"] / video
            source = prepare_full_video_input(base / f"{video}.mp4", base / "labels_ftid",
                                             video_id=video, expected_frame_count=EXPECTED_FRAMES[video],
                                             expected_width=plan["input"]["width"],
                                             expected_height=plan["input"]["height"])
            frames = source.gt_frames
            missing = [f.frame_idx for f in frames if not f.annotated]
            expected_missing = [i for a, b in GAPS.get(video, []) for i in range(a, b + 1)]
            if missing != expected_missing:
                raise ValueError(f"Unexpected annotation coverage in video {video}")
            result = build_individual_ground_truth(frames, video_id=video, split="train",
                         expected_frame_count=EXPECTED_FRAMES[video], history_length=20,
                         forecast_horizon=10, stride=1)
            folder = run.path / "by_video" / video
            folder.mkdir(parents=True, exist_ok=False)
            for name, fields in TABLE_FIELDS.items():
                target = write_csv_exclusive(folder / f"{name}.csv", getattr(result, name), fields)
                artifacts.append(reference(target))
            raw = (detection_to_row(video, frame.frame_idx, "manual", det)
                   for frame in frames for det in frame.detections)
            artifacts.append(reference(write_csv_exclusive(folder / "ground_truth_raw.csv", raw, CSV_FIELDS)))
            artifacts.append(reference(write_json_exclusive(folder / "summary.json", result.summary)))
            artifacts.append(reference(write_json_exclusive(folder / "input_contract.json", source.reference())))
            inputs.append(source)
            summaries.append(result.summary)
            check_budget(plan, monitor, start, run.path)
            print(f"Video {video}: {result.summary['individual_observations']} individual observations; "
                  f"{result.summary['segments_total']} segments; {result.summary['windows_total']} windows", flush=True)
            del frames, result
        checks = [source.verify_current() for source in inputs]
        for item in [*metadata_refs, *artifacts]:
            if reference(REPOSITORY_ROOT / item["path"]) != item:
                raise RuntimeError(f"Artifact or metadata changed: {item['path']}")
        repository_check = snapshot.verify_current()
        repository_check["scope"] = "preparation_end_before_completion"
        totals = {key: sum(summary[key] for summary in summaries) for key in (
            "frames_total", "frames_annotated", "frames_unannotated", "raw_observations",
            "individual_observations", "cluster_observations", "segments_total", "segments_with_windows",
            "segments_without_windows", "origins_with_complete_history", "windows_total",
            "origins_excluded_incomplete_future")}
        summary = {"status": "prepared_training_reference_not_prediction_evaluation", "video_ids": list(TRAIN),
                   "totals": totals, "videos": summaries, "statistical_unit": "video",
                   "future_reference_conditioned_eligibility": True, "model_evaluated": False,
                   "validation_sources_read": False, "test_sources_read": False, "pixels_decoded": False}
        artifacts.append(reference(write_json_exclusive(run.path / "summary.json", summary)))
        resources = check_budget(plan, monitor, start, run.path)
        run.complete(metadata=metadata_refs, artifacts=artifacts, input_rechecks=checks,
                     repository_recheck=repository_check, summary=summary, resources=resources)
        return run.path
    except BaseException as exc:
        run.fail(exc, metadata=metadata_refs, artifacts=artifacts, completed_video_summaries=summaries,
                 resources=monitor.summary())
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(prepare(REPOSITORY_ROOT / PLAN), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
