"""Execute the registered two-finalist validation on four complete videos.

No parameter, frame or video overrides are accepted. Selection requires eight
complete runs, unchanged sources and reproducible exported frame metrics.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import random
import time
from pathlib import Path
from typing import Any

import cv2

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT, resolve_from_repository
from src.detection.registry import build_detector
from src.detection.runner import run_on_video
from src.detection.strict_inputs import prepare_full_video_input
from src.evaluation.detection import aggregate_frame_metrics
from src.experiments.detection_validation import (
    VALIDATION_IDS, VALIDATION_INTERPRETATION, load_validation_plan,
    rank_validation_candidates, summarize_validation_candidate,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot, _git_dirty
from src.experiments.validation_frame_checks import validate_exported_frame

DEFAULT_PLAN = "configs/detection/threshold/validation_v3.yaml"


def _reference(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def certify_frame_export(path: Path, summary: dict, video_id: str, expected: int,
                         evaluation: dict) -> dict:
    """Read the export back and verify identity, coverage and every aggregate."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicated frame metric columns")
        raw = list(reader)
    if len(raw) != expected or summary.get("video_id") != video_id:
        raise ValueError("Frame export or video identity is incomplete")
    completeness = summary.get("completeness", {})
    required = {"status": "complete", "expected_frames": expected, "decoded_frames": expected,
                "frame_metric_rows": expected, "extra_read_eof": True}
    if any(completeness.get(k) != v for k, v in required.items()):
        raise ValueError("Missing strict full-video completeness evidence")
    strings = {"video_id", "class_policy", "evaluation_protocol_id"}
    rows = []
    for index, row in enumerate(raw):
        if (row.get("video_id") != video_id or row.get("frame") != str(index)
                or row.get("annotated") != "True"
                or row.get("evaluation_protocol_id") != evaluation["protocol_id"]
                or row.get("class_policy") != evaluation["class_policy"]):
            raise ValueError("Frame export has missing, reordered or foreign frames/annotations")
        converted = {}
        for key, value in row.items():
            if key is None or value is None:
                raise ValueError("Malformed frame metrics CSV")
            if key in strings:
                converted[key] = value
            elif value == "":
                converted[key] = None
            elif value in {"True", "False"}:
                converted[key] = value == "True"
            else:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"Nonfinite exported frame metric: {key}")
                converted[key] = number
        validate_exported_frame(converted, evaluation)
        rows.append(converted)
    rebuilt = aggregate_frame_metrics(rows, video_id=video_id)
    for key, expected_value in rebuilt.items():
        if key.startswith("detection_ms_"):
            continue  # The runner intentionally rounds descriptive timing to four decimals.
        observed = summary.get(key)
        if isinstance(expected_value, (int, float)):
            if (isinstance(observed, bool) or not isinstance(observed, (int, float))
                    or not math.isfinite(observed)
                    or not math.isclose(observed, expected_value, rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError(f"Exported metrics disagree with video summary: {key}")
        elif observed != expected_value:
            raise ValueError(f"Exported metrics disagree with video summary: {key}")
    return {"status": "verified", "video_id": video_id, "expected_frames": expected,
            "frame_rows": len(rows), "aggregate_fields_checked": len(rebuilt) - 3,
            "frame_metrics": _reference(path)}


class _Budget:
    def __init__(self, rules: dict, started: float, monitor: ResourceMonitor):
        self.rules, self.started, self.monitor = rules, started, monitor
        self.paths: list[Path] = []

    def check(self, frame: int | None = None, predictions: list | None = None) -> None:
        self.monitor.sample()
        if predictions is not None and len(predictions) > self.rules["max_predictions_per_frame"]:
            raise RuntimeError(f"Prediction budget exceeded at frame {frame}; no truncation allowed")
        if time.perf_counter() - self.started > self.rules["batch_soft_wall_seconds"]:
            raise RuntimeError("Validation wall-clock budget exceeded")
        rss = self.monitor.summary()["ram_rss_peak_mb"]
        if rss is None or rss > self.rules["max_rss_mb"]:
            raise RuntimeError("Validation RAM budget exceeded or unavailable")
        if frame is None and self.artifact_bytes() > self.rules["max_batch_artifact_mb"] * 1024**2:
            raise RuntimeError("Validation artifact budget exceeded")

    def artifact_bytes(self) -> int:
        return sum(p.stat().st_size for folder in self.paths for p in folder.rglob("*") if p.is_file())


def run_validation(plan_path: str | Path = DEFAULT_PLAN, *, output_root: str | Path | None = None) -> Path:
    started = time.perf_counter()
    if output_root is not None:
        output_root = resolve_from_repository(output_root).resolve()
        if output_root.is_relative_to((REPOSITORY_ROOT / "data/sources").resolve()):
            raise ValueError("Validation output must not be written inside data/sources")
    if _git_dirty(REPOSITORY_ROOT) is not False:
        raise RuntimeError("Commit the validation protocol and executor before opening validation inputs")
    snapshot = RunSnapshot.capture(REPOSITORY_ROOT)
    if snapshot.git_dirty is not False:
        raise RuntimeError("Validation requires a clean Git snapshot")
    plan, candidates, provenance = load_validation_plan(resolve_from_repository(plan_path))
    cv2.setNumThreads(plan["run"]["opencv_threads"])
    monitor = ResourceMonitor()
    budget = _Budget(plan["budget"], started, monitor)
    config = {"configuration_id": plan["plan_id"] + "_batch", "method": "threshold",
              "plan": plan, "provenance": provenance, "run": plan["run"]}
    batch = RunContext.create(module="detection", method="threshold_validation", algorithm="threshold",
                              stage="validation", seed=plan["run"]["seed"], config=config,
                              output_root=output_root, provenance_snapshot=snapshot)
    budget.paths.append(batch.path)
    children, summaries, inputs = [], [], {}
    try:
        pairs = [[c["configuration_id"], v] for c in candidates for v in VALIDATION_IDS]
        random.Random(plan["run"]["seed"]).shuffle(pairs)
        write_json_exclusive(batch.path / "planned_pairs.json", pairs)
        write_json_exclusive(batch.path / "planned_frames.json", provenance["exact_frame_plan"])
        write_json_exclusive(batch.path / "planned_candidates.json", candidates)
        expected_frames = provenance["expected_frames_per_video"]
        source_root = resolve_from_repository(plan["input"]["root"])
        for video_id in VALIDATION_IDS:
            budget.check()
            folder = source_root / video_id
            prepared = prepare_full_video_input(
                folder / f"{video_id}.mp4", folder / "labels_ftid", video_id=video_id,
                expected_width=plan["input"]["width"], expected_height=plan["input"]["height"],
                expected_frame_count=expected_frames[video_id])
            if not all(frame.annotated for frame in prepared.gt_frames):
                raise ValueError(f"Video {video_id} no longer has complete annotation coverage")
            inputs[video_id] = prepared
        write_json_exclusive(batch.path / "input_contracts.json", {v: p.reference() for v, p in inputs.items()})
        registered_artifacts = {p.name: _reference(p) for p in batch.path.iterdir()
                                if p.is_file() and p.name != "manifest.json"}
        by_id = {c["configuration_id"]: c for c in candidates}
        for number, (candidate_id, video_id) in enumerate(pairs, 1):
            budget.check()
            prepared = inputs[video_id]
            candidate = copy.deepcopy(by_id[candidate_id])
            candidate.update(run=copy.deepcopy(plan["run"]), input={"video_id": video_id,
                             "video": str(prepared.video_path), "gt_dir": str(prepared.gt_dir),
                             "input_hash": prepared.input_hash})
            candidate["provenance"].update(batch_manifest=str(batch.path / "manifest.json"))
            child = RunContext.create(module="detection", method="threshold", stage="validation",
                seed=plan["run"]["seed"], config=candidate, output_root=output_root,
                provenance_snapshot=snapshot, snapshot_origin_batch_manifest=batch.path / "manifest.json")
            budget.paths.append(child.path)
            try:
                detector = build_detector("threshold", params=candidate["params"])
                summary = run_on_video(detector, prepared.video_path, child.path / "detections.csv",
                    video_id=video_id, gt_dir=prepared.gt_dir, out_frames_csv=child.path / "frame_metrics.csv",
                    center_gate_px=plan["evaluation"]["center_gate_px"], class_policy=plan["evaluation"]["class_policy"],
                    sensitivity_gates_px=plan["evaluation"]["sensitivity_gates_px"], verbose=False,
                    full_video_input=prepared, progress_callback=budget.check)
                certificate = certify_frame_export(child.path / "frame_metrics.csv", summary, video_id,
                                                  expected_frames[video_id], plan["evaluation"])
                source_check = prepared.verify_current()
                summary.update(configuration_id=candidate_id, split="val", status="complete",
                               frame_coverage_verified=True, input_hash=prepared.input_hash)
                # The complete input reference is already in a hashed batch artifact.
                summary.pop("full_video_input", None)
                write_json_exclusive(child.path / "summary.json", summary)
                budget.check()
                artifacts = {name: str(child.path / name) for name in ("detections.csv", "frame_metrics.csv", "summary.json")}
                child.complete(summary=summary, artifacts=artifacts,
                               artifact_hashes={name: sha256_file(Path(p)) for name, p in artifacts.items()},
                               frame_coverage_verification=certificate, input_verification=source_check)
                children.append(_reference(child.path / "manifest.json"))
                summaries.append(summary)
                print(f"{number}/8: {candidate_id}, video {video_id}, {summary['frames_total']} frames completos", flush=True)
            except BaseException as exc:
                child.fail(exc, input_hash=prepared.input_hash)
                raise
        budget.check()
        input_checks = {v: p.verify_current() for v, p in inputs.items()}
        # Revalidate the complete parent chain, including the coarse-search
        # artifacts owned by the nested refinement loader, outside Git.
        current = load_validation_plan(resolve_from_repository(plan_path))
        if current != (plan, candidates, provenance):
            raise ValueError("Validation prerequisite metadata changed during execution")
        for reference in registered_artifacts.values():
            if sha256_file(Path(reference["path"])) != reference["sha256"]:
                raise ValueError("Registered validation batch artifact changed during execution")
        for reference, expected_summary in zip(children, summaries):
            path = Path(reference["path"])
            if sha256_file(path) != reference["sha256"]:
                raise ValueError("Validation child manifest changed before ranking")
            child_manifest = json.loads(path.read_text(encoding="utf-8"))
            if child_manifest.get("status") != "complete" or child_manifest.get("summary") != expected_summary:
                raise ValueError("Validation child summary changed before ranking")
            for name, digest in child_manifest["artifact_hashes"].items():
                if sha256_file(Path(child_manifest["artifacts"][name])) != digest:
                    raise ValueError("Validation child artifact changed before ranking")
        snapshot_check = snapshot.verify_current()
        candidate_summaries = [summarize_validation_candidate(
            [s for s in summaries if s["configuration_id"] == c["configuration_id"]], expected_frames)
            for c in candidates]
        ranking = rank_validation_candidates(candidate_summaries, list(by_id))
        for rank, row in enumerate(ranking, 1):
            row["rank"] = rank
        budget.check()
        write_csv_exclusive(batch.path / "video_metrics.csv", summaries)
        write_csv_exclusive(batch.path / "candidate_metrics.csv", candidate_summaries)
        write_csv_exclusive(batch.path / "ranking.csv", ranking)
        winner = ranking[0]["configuration_id"]
        selection = {"status": "validation_selected_not_frozen", "interpretation": VALIDATION_INTERPRETATION,
                     "configuration_id": winner, "params": by_id[winner]["params"], "evaluation": plan["evaluation"],
                     "plan_hash": provenance["plan_hash"], "ranking": ranking,
                     "test_executed": False, "five_fold_executed": False}
        write_json_exclusive(batch.path / "selection.json", selection)
        summary = {"complete": True, "split": "val", "interpretation": VALIDATION_INTERPRETATION,
                   "plan_hash": provenance["plan_hash"], "n_candidates": 2, "n_videos": 4, "n_runs": len(children),
                   "frames_per_candidate": sum(expected_frames.values()),
                   "frame_evaluations": sum(s["frames_total"] for s in summaries),
                   "selected_configuration_id": winner, "artifact_bytes_before_final_manifest": budget.artifact_bytes(),
                   "total_wall_seconds": time.perf_counter() - started, **monitor.summary()}
        artifacts = {p.name: str(p) for p in batch.path.iterdir() if p.is_file() and p.name != "manifest.json"}
        budget.check()
        batch.complete(summary=summary, candidate_manifests=children, artifacts=artifacts,
                       artifact_hashes={name: sha256_file(Path(p)) for name, p in artifacts.items()},
                       input_verification=input_checks, provenance_verification=snapshot_check)
        return batch.path
    except BaseException as exc:
        # A failed manifest always invalidates any selection artifact written just before failure.
        batch.fail(exc, candidate_manifests=children, selection_valid=False,
                   summary={"complete": False, "completed_video_runs": len(children), **monitor.summary()})
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--out-dir")
    parser.add_argument("--dry-run", action="store_true", help="Verify metadata only; do not open validation videos or labels")
    args = parser.parse_args(argv)
    if args.dry_run:
        _, candidates, provenance = load_validation_plan(resolve_from_repository(args.plan))
        print(json.dumps({"status": "metadata_verified_no_validation_input_opened", "plan_hash": provenance["plan_hash"],
                          "candidate_ids": [c["configuration_id"] for c in candidates],
                          "expected_frames_per_video": provenance["expected_frames_per_video"],
                          "frame_evaluations": 2 * len(provenance["exact_frame_plan"])}))
    else:
        print(json.dumps({"batch": str(run_validation(args.plan, output_root=args.out_dir))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
