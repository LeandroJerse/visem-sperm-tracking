"""Independent verification of a completed, registered threshold validation.

This verifier imports no src/script implementation. It reuses only pure audit
and SciPy-matching helpers from the earlier independent refinement verifier.
All experiment inputs read here are exported CSV/JSON artifacts: no original
labels, MP4, cache arrays, live source-code/environment checks or YAML reads.
The embedded registered plan is checked against its fixed prospective rules.
Run only after an explicit complete batch manifest is supplied. Reports are
exclusive new files; failures remain recorded. --self-test uses synthetic
in-memory objects only and reads no experiment artifacts.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import platform
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

import verify_threshold_refinement as independent


ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ("14", "19", "36", "52")
FRAME_COUNTS = {"14": 1470, "19": 1470, "36": 1470, "52": 1440}
CANDIDATES = ("t219_o0_c2", "t218_o0_c2")
PARAMETER_HASHES = {
    "t219_o0_c2": "2bee065ae23c3a63f2f03888d933fed7e2d2b0c67ffd6d05e243195efc9b78a9",
    "t218_o0_c2": "5b9dacca7e53b226fe90c42f1cb98d673193f0b43d0af8e2952677bc733acfa3",
}
PROTOCOL = independent.PROTOCOL
GATES, PREFIXES = independent.GATES, independent.PREFIXES
RAW, SCORED = independent.RAW, independent.SCORED
INTERPRETATION = "validation_selection_not_independent_test_not_frozen"
EVALUATION = {"protocol_id": PROTOCOL, "class_policy": "individuals_ignore_clusters",
              "center_gate_px": 10, "sensitivity_gates_px": [15, 20]}
RUN = {"split": "val", "seed": 42, "opencv_threads": 1, "save_video": False,
       "order": "seeded_shuffle_of_eight_candidate_video_pairs", "reset_detector_per_video": True}
BUDGET = {"batch_soft_wall_seconds": 1800, "max_rss_mb": 2048,
          "max_batch_artifact_mb": 2048, "max_predictions_per_frame": 2000,
          "on_failure": "preserve_partial_runs_without_selection"}
CSV_FIELDS = ("video_id", "frame", "source", "object_id", "class_id", "class_name",
              "cx", "cy", "w", "h", "x", "y", "score")
MATCH_PAIRS = {(video, frame) for video, count in FRAME_COUNTS.items()
               for frame in (0, (count - 1) // 2, count - 1)}
require, number, integer = independent.require, independent.number, independent.integer
boolean, digest_json = independent.boolean, independent.digest_json


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def forbidden_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def structured(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value, object_pairs_hook=strict_object, parse_constant=forbidden_constant)
    except json.JSONDecodeError:
        # csv.DictWriter writes nested mappings/lists with Python repr.
        return ast.literal_eval(value)


def utf8_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def valid_sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"Invalid SHA256: {value!r}")
    return value


def lexical_path(value):
    """Compare recorded Windows source paths without dereferencing them."""
    require(isinstance(value, str) and value, "Missing recorded path")
    return value.replace("/", "\\").rstrip("\\").casefold()


class Audit(independent.Audit):
    def path(self, value, base=None):
        path = super().path(value, base)
        require(path.suffix.lower() in {".csv", ".json"}, "This verifier reads exported CSV/JSON only")
        return path

    def json(self, path):
        return self._stable_read(path, lambda stream: json.load(
            stream, object_pairs_hook=strict_object, parse_constant=forbidden_constant))

    def csv(self, path):
        def read(stream):
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            require(fields and len(fields) == len(set(fields)), f"Missing/duplicate CSV header: {path}")
            rows = list(reader)
            require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
                    f"Malformed CSV row: {path}")
            return rows
        return self._stable_read(path, read)

    def equal(self, observed, expected, label, *, spatial=False):
        if isinstance(expected, (dict, list, tuple)):
            self.comparisons += 1
            observed = structured(observed)
            if isinstance(expected, dict):
                require(isinstance(observed, dict) and set(observed) == set(expected), f"{label}: mapping keys differ")
                for key, value in expected.items():
                    self.equal(observed[key], value, f"{label}.{key}", spatial=spatial)
            else:
                require(isinstance(observed, (list, tuple)) and len(observed) == len(expected),
                        f"{label}: sequence shape differs")
                for index, value in enumerate(expected):
                    self.equal(observed[index], value, f"{label}[{index}]", spatial=spatial)
        elif isinstance(expected, int) and not isinstance(expected, bool):
            self.comparisons += 1
            require(integer(observed) == expected, f"{label}: count/index mismatch")
        elif spatial and expected is not None:
            self.comparisons += 1
            require(math.isclose(number(observed), expected, rel_tol=1e-12, abs_tol=1e-9),
                    f"{label}: spatial mismatch {observed!r} != {expected!r}")
        else:
            super().equal(observed, expected, label, spatial=spatial)

    def reference(self, reference):
        require(isinstance(reference, dict), "Expected metadata reference mapping")
        path = self.hash(reference["path"], valid_sha(reference["sha256"]))
        if "bytes" in reference:
            self.equal(self.files[str(path)]["bytes"], integer(reference["bytes"]), "reference byte size")
        return path


def parameters(candidate):
    require(candidate in CANDIDATES, "Unknown validation finalist")
    return {"adaptive": False, "invert": False, "blur": 1, "morph_kernel": 3,
            "min_area": 3, "max_area": 300, "threshold_value": int(candidate[1:4]),
            "morph_iterations": 0, "close_iterations": 2}


def validate_plan(plan):
    require(plan["plan_id"] == "threshold_validation_v3_20260908" and plan["method"] == "threshold"
            and plan["stage"] == "validation"
            and plan["purpose"] == "select_between_two_training_finalists_on_complete_validation_videos",
            "Wrong validation plan identity")
    require(plan["evaluation"] == EVALUATION and plan["run"] == RUN and plan["budget"] == BUDGET,
            "Prospective evaluation/run/budget rules changed")
    require(plan["selection"] == {
        "primary": "macro_video_f1_individuals_center_10px",
        "tie_breakers": ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"],
        "video_weighting": "equal_after_within_video_aggregation", "require_all_candidates_and_full_videos": True,
        "timing_used_for_ranking": False, "sensitivity_used_for_ranking": False,
        "interpretation": INTERPRETATION, "hypothesis_tests": False, "confidence_intervals": False},
        "Selection rule changed")
    require(plan["input"] == {
        "root": "data/sources/visem_tracking/dataset/Train", "label_format": "tracked_yolo",
        "width": 640, "height": 480, "expected_frames": FRAME_COUNTS,
        "expected_annotation_coverage": "complete_per_versioned_inventory",
        "read_mode": "sequential_full_video_with_extra_eof_check",
        "on_missing_or_malformed_label": "fail_without_selection", "resize": False,
        "ground_truth_available_to_detector": False}, "Full-video input rule changed")
    protocol = plan["protocol"]
    require(protocol["validation_ids"] == list(map(int, VIDEOS))
            and protocol["test_ids_blocked"] == [24, 38, 47, 54]
            and protocol["splits_config"] == "configs/protocol/splits.yaml"
            and protocol["inventory"] == "data/manifests/visem_tracking.csv", "Split rule changed")
    for key in ("splits_sha256", "inventory_sha256"):
        valid_sha(protocol[key])
    require(plan["refinement"]["candidate_ids"] == list(CANDIDATES)
            and plan["refinement"]["parameter_hashes"] == PARAMETER_HASHES,
            "Registered finalists or parameter hashes changed")
    for candidate in CANDIDATES:
        require(digest_json(parameters(candidate)) == PARAMETER_HASHES[candidate], "Parameter reconstruction differs")


def validate_source_record(record, video, frames):
    """Inspect the exported source identity only. Never hash/open source paths."""
    require(record["contract"] == "full_video_input_v1" and record["schema_version"] == 1
            and record["video_id"] == video and record["expected_frame_count"] == frames
            and record["expected_width"] == 640 and record["expected_height"] == 480,
            "Input contract differs from complete registered video")
    require(utf8_digest({k: v for k, v in record.items() if k != "input_hash"}) == record["input_hash"],
            "Input contract hash cannot be reconstructed")
    source = ROOT / "data/sources/visem_tracking/dataset/Train" / video
    require(lexical_path(record["source_video"]["path"]) == lexical_path(str(source / f"{video}.mp4")),
            "Recorded MP4 path differs from canonical video")
    valid_sha(record["source_video"]["sha256"])
    require(integer(record["source_video"]["bytes"]) > 0, "Empty recorded source video")
    metadata = record["video_metadata"]
    require(metadata["width"] == 640 and metadata["height"] == 480 and metadata["frame_count"] == frames
            and number(metadata["fps"]) > 0, "Recorded source header differs")
    gt = record["ground_truth"]
    require(lexical_path(gt["directory"]) == lexical_path(str(source / "labels_ftid"))
            and gt["layout"] == "track_id class cx cy w h" and gt["annotated_frames"] == frames
            and gt["unannotated_frames"] == 0 and gt["unannotated_indices"] == [],
            "Input contract is not completely annotated")
    files = gt["files"]
    require(len(files) == frames and [item["frame"] for item in files] == list(range(frames)),
            "Recorded label universe has gaps, duplicates or extras")
    inventory = record["inventory"]
    require(utf8_digest(inventory["entries"]) == inventory["sha256"], "Recorded directory inventory hash differs")
    entries = {name: kind for name, kind in inventory["entries"]}
    require(len(entries) == len(inventory["entries"]), "Duplicate directory entry in source contract")
    empty = 0
    for index, item in enumerate(files):
        match = re.fullmatch(rf"{video}_frame_([0-9]+)_with_ftid\.txt", item["name"])
        require(match is not None and int(match.group(1)) == index and entries.get(item["name"]) == "file",
                "Noncanonical or missing recorded label entry")
        require(lexical_path(item["path"]) == lexical_path(str(source / "labels_ftid" / item["name"])),
                "Recorded label path belongs to another input")
        valid_sha(item["sha256"])
        require(integer(item["bytes"]) >= 0 and integer(item["rows"]) >= 0, "Invalid label metadata count")
        empty += integer(item["rows"]) == 0
    require({name for name in entries if name.lower().endswith(".txt")} == {item["name"] for item in files},
            "Extra or unaccounted TXT label in recorded inventory")
    require(gt["annotated_empty_frames"] == empty, "Recorded empty-label count differs")


def check_source_verification(check, record, lower_time, upper_time):
    require(check["status"] == "verified" and check["input_hash"] == record["input_hash"]
            and check["checks"] == ["canonical_paths", "mp4_sha256", "label_sha256", "directory_inventory"]
            and check["files_verified"] == 1 + record["expected_frame_count"],
            "Missing recorded source recheck")
    require(independent.recorded_time(lower_time) <= independent.recorded_time(check["checked_at"])
            <= independent.recorded_time(upper_time), "Source verification chronology differs")


def validate_provenance(audit, batch, batch_path):
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False
            and batch.get("stage") == "validation" and batch.get("seed") == 42
            and batch.get("method") == "threshold_validation", "Batch is incomplete or from another stage")
    require(batch["config_hash"] == digest_json(batch["config"])[:12], "Batch config hash differs")
    capture = independent.verify_batch_snapshot(audit, batch, batch_path)
    config = batch["config"]
    plan, provenance = config["plan"], config["provenance"]
    validate_plan(plan)
    plan_hash = digest_json(plan)
    require(config["run"] == RUN and provenance["plan_hash"] == plan_hash
            and batch["summary"]["plan_hash"] == plan_hash
            and provenance["expected_frames_per_video"] == FRAME_COUNTS
            and provenance["candidate_parameters_hashes"] == PARAMETER_HASHES
            and provenance["interpretation"] == INTERPRETATION, "Batch plan provenance differs")
    require(provenance["exact_frame_plan"] == [[v, f] for v in VIDEOS for f in range(FRAME_COUNTS[v])],
            "Resolved exact frame plan differs")
    # YAML and original-source hashes are recorded evidence, not reopened here.
    for reference in provenance["validated_inputs"]:
        valid_sha(reference["sha256"])
        if "bytes" in reference:
            require(integer(reference["bytes"]) >= 0, "Invalid prerequisite metadata byte count")
    for key, digest in (("splits", plan["protocol"]["splits_sha256"]),
                        ("inventory", plan["protocol"]["inventory_sha256"]),
                        ("refinement_manifest", plan["refinement"]["manifest_sha256"]),
                        ("finalists", plan["refinement"]["finalists_sha256"]),
                        ("refinement_verification", plan["refinement"]["verification_sha256"])):
        require(provenance[key]["sha256"] == digest, f"Prerequisite reference hash differs: {key}")
    refinement_path = audit.reference(provenance["refinement_manifest"])
    refinement = audit.json(refinement_path)
    require(refinement["status"] == "complete" and refinement["summary"]["mode"] == "refine"
            and refinement["summary"]["frame_evaluations"] == 67392, "Wrong training refinement parent")
    finalists_path = audit.reference(provenance["finalists"])
    require(refinement["artifact_hashes"]["finalists.json"] == provenance["finalists"]["sha256"]
            and audit.path(refinement["artifacts"]["finalists.json"]) == finalists_path,
            "Finalists do not belong to the referenced refinement")
    finalists = audit.json(finalists_path)
    require([row["configuration_id"] for row in finalists] == list(CANDIDATES), "Training final order differs")
    qa = audit.json(audit.reference(provenance["refinement_verification"]))
    require(qa["status"] == "passed" and qa["ranking_complete_match"] is True
            and qa["batch_manifest_sha256"] == provenance["refinement_manifest"]["sha256"]
            and qa["independent_top2"] == list(CANDIDATES), "Previous independent QA differs")
    require(set(provenance["training_finalist_manifests"]) == set(CANDIDATES), "Wrong finalist references")
    children = {audit.path(item["path"]): item["sha256"] for item in refinement["candidate_manifests"]}
    for candidate in CANDIDATES:
        reference = provenance["training_finalist_manifests"][candidate]
        child_path = audit.reference(reference)
        require(children.get(child_path) == reference["sha256"], "Finalist child is outside training parent")
        child = audit.json(child_path)
        require(child["status"] == "complete" and child["config"]["configuration_id"] == candidate
                and child["config"]["params"] == parameters(candidate)
                and child["config"]["evaluation"] == EVALUATION
                and child["config"]["run"]["split"] == "train", "Finalist parameters/identity differ")
    return plan, provenance, capture


def extended_frame_counts(audit, frame):
    independent.frame_counts(audit, frame)
    audit.fields(frame, {
        "n_predictions": integer(frame["n_predictions_raw"]),
        "n_ground_truth": integer(frame["n_ground_truth_raw"]),
        "has_gt_clusters": integer(frame["n_gt_clusters"]) > 0,
        "count_abs_error_raw": abs(integer(frame["count_error_raw"])),
    }, "frame raw aliases/diagnostics")
    require(number(frame["detection_ms"]) >= 0, "Negative detection time")
    require(integer(frame["n_predictions_raw"]) <= BUDGET["max_predictions_per_frame"],
            "Saved frame exceeds the prospective prediction limit")


def aggregate_video(audit, frames, video):
    result = independent.aggregate_video(audit, frames)
    errors = [integer(row["count_error_raw"]) for row in frames]
    times = [number(row["detection_ms"]) for row in frames]
    raw_counts = [integer(row["n_predictions_raw"]) for row in frames]
    ordered = sorted(times)
    position = (len(times) - 1) * 0.95
    low, high = math.floor(position), math.ceil(position)
    p95 = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    result.update(video_id=video, n_predictions_unannotated=0,
        frames_with_clusters=sum(integer(row["n_gt_clusters"]) > 0 for row in frames),
        frames_with_individual_gt=sum(integer(row["n_gt_individuals"]) > 0 for row in frames),
        frames_true_empty_gt=sum(integer(row["n_ground_truth_raw"]) == 0 for row in frames),
        frames_cluster_only_gt=sum(integer(row["n_gt_clusters"]) > 0 and integer(row["n_gt_individuals"]) == 0 for row in frames),
        count_error_raw=sum(errors), count_abs_error_raw=sum(map(abs, errors)),
        count_bias_raw=statistics.fmean(errors), count_mae_raw=statistics.fmean(map(abs, errors)),
        frames=len(frames), scored_frames=len(frames), warmup_frames=0,
        detections=sum(raw_counts), rows=sum(raw_counts) + result["n_ground_truth_raw"],
        det_per_frame_mean=round(statistics.fmean(raw_counts), 2),
        det_per_frame_median=round(float(statistics.median(raw_counts)), 2), det_per_frame_max=max(raw_counts),
        annotated_frames=len(frames), unannotated_frames=0,
        detection_ms_mean=round(statistics.fmean(times), 4),
        detection_ms_median=round(float(statistics.median(times)), 4),
        detection_ms_max=round(max(times), 4), detection_ms_p95=round(p95, 4))
    for _, suffix in GATES:
        n = sum(boolean(row["primary_evaluable" + suffix]) for row in frames)
        result.update({"frames_primary_evaluable" + suffix: n,
                       "frames_primary_unevaluable" + suffix: len(frames) - n,
                       "frames_with_ignored_predictions" + suffix: sum(integer(row["n_predictions_ignored" + suffix]) > 0 for row in frames)})
    return result


def aggregate_candidate(videos, candidate):
    result = independent.aggregate_candidate(videos)
    result.update(configuration_id=candidate, complete=True, split="val", frame_coverage_verified=True,
                  evaluation_protocol_id=PROTOCOL, class_policy="individuals_ignore_clusters",
                  center_gate_px=10, sensitivity_gates_px=[15, 20], interpretation=INTERPRETATION,
                  video_ids=list(VIDEOS), n_videos=4, expected_frames_per_video=FRAME_COUNTS,
                  macro_video_detection_ms_mean=statistics.fmean(row["detection_ms_mean"] for row in videos))
    return result


def object_rows(audit, rows, video, count):
    grouped = defaultdict(lambda: {"detection": [], "manual": []})
    for row in rows:
        require(set(row) == set(CSV_FIELDS), "Unexpected raw detection header")
        frame = integer(row["frame"])
        require(row["video_id"] == video and 0 <= frame < count and row["source"] in {"manual", "detection"},
                "Raw object belongs to another frame/video/source")
        item = {key: number(row[key]) for key in ("cx", "cy", "w", "h", "x", "y", "score")}
        item.update(object_id=row["object_id"], class_id=integer(row["class_id"]), class_name=row["class_name"])
        require(item["class_id"] in (0, 1, 2) and item["w"] > 0 and item["h"] > 0
                and row["object_id"] != "" and item["class_name"] == {0: "normal", 1: "cluster", 2: "pinhead"}[item["class_id"]],
                "Invalid raw object identity/class/geometry")
        audit.equal(item["x"], item["cx"] - item["w"] / 2, "raw x", spatial=True)
        audit.equal(item["y"], item["cy"] - item["h"] / 2, "raw y", spatial=True)
        if row["source"] == "manual":
            require(0 <= item["cx"] <= 640 and 0 <= item["cy"] <= 480
                    and item["w"] <= 640 and item["h"] <= 480 and item["score"] == 1.0,
                    "Manual CSV violates recorded normalized GT contract")
        grouped[frame][row["source"]].append(item)
    return grouped


def gt_fingerprint(items):
    # Include every exported object field and retain duplicate rows.
    return digest_json(sorted(items, key=lambda item: digest_json(item)))


def verify(batch_path, audit):
    require(not any(name == "src" or name.startswith("src.") or name == "script" or name.startswith("script.")
                    for name in sys.modules), "Project scientific implementation imported")
    batch_path = audit.hash(batch_path)
    batch = audit.json(batch_path)
    plan, provenance, capture = validate_provenance(audit, batch, batch_path)
    artifacts = audit.artifacts(batch, batch_path)
    require({"planned_pairs.json", "planned_frames.json", "planned_candidates.json", "input_contracts.json",
             "video_metrics.csv", "candidate_metrics.csv", "ranking.csv", "selection.json"} == set(artifacts),
            "Incomplete or unexpected validation batch artifacts")
    planned_pairs = [[candidate, video] for candidate in CANDIDATES for video in VIDEOS]
    random.Random(42).shuffle(planned_pairs)
    require(audit.json(artifacts["planned_pairs.json"]) == planned_pairs, "Actual pair order differs from seed 42")
    require(audit.json(artifacts["planned_frames.json"]) == provenance["exact_frame_plan"], "Planned frame artifact differs")
    candidates = audit.json(artifacts["planned_candidates.json"])
    require([row["configuration_id"] for row in candidates] == list(CANDIDATES), "Planned candidate order differs")
    candidate_by_id = {row["configuration_id"]: row for row in candidates}
    for candidate, row in candidate_by_id.items():
        require(row == {"configuration_id": candidate, "method": "threshold", "params": parameters(candidate),
                "evaluation": EVALUATION, "provenance": {
                    "training_finalist_manifest": provenance["training_finalist_manifests"][candidate],
                    "validation_plan_hash": provenance["plan_hash"], "candidate_parameters_hash": PARAMETER_HASHES[candidate]}},
                "Planned candidate contract differs from fixed training finalist")
    inputs = audit.json(artifacts["input_contracts.json"])
    require(set(inputs) == set(VIDEOS), "Input contract includes foreign/missing video")
    for video, record in inputs.items():
        validate_source_record(record, video, FRAME_COUNTS[video])
        check_source_verification(batch["input_verification"][video], record, batch["started_at"],
                                  batch["provenance_verification"]["checked_at"])
    require(set(batch["input_verification"]) == set(VIDEOS), "Batch source checks differ from the four videos")
    refs = batch["candidate_manifests"]
    require(len(refs) == len({ref["path"] for ref in refs}) == 8, "Eight distinct complete child runs required")
    reference_gt, summaries, rebuilt, child_paths = {}, {}, {}, []
    all_frame_records = 0
    for index, (reference, pair) in enumerate(zip(refs, planned_pairs), 1):
        candidate, video = pair
        child_path = audit.reference(reference)
        child_paths.append(child_path)
        child = audit.json(child_path)
        require(child["status"] == "complete" and child["stage"] == "validation" and child["method"] == "threshold"
                and child["seed"] == 42 and child["config_hash"] == digest_json(child["config"])[:12],
                "Child status/stage/seed/config hash differs")
        require(child["provenance_capture"] == capture and all(child[key] == batch[key]
                for key in ("git_sha", "git_dirty", "source_hash", "environment")), "Child differs from shared batch snapshot")
        require(independent.recorded_time(capture["captured_at"]) <= independent.recorded_time(child["started_at"])
                <= independent.recorded_time(child["finished_at"])
                <= independent.recorded_time(batch["provenance_verification"]["checked_at"]), "Child snapshot chronology differs")
        expected_config = {**candidate_by_id[candidate], "run": RUN,
            "input": {"video_id": video, "video": inputs[video]["source_video"]["path"],
                      "gt_dir": inputs[video]["ground_truth"]["directory"], "input_hash": inputs[video]["input_hash"]},
            "provenance": {**candidate_by_id[candidate]["provenance"], "batch_manifest": str(batch_path)}}
        require(child["config"] == expected_config, "Child candidate/input/provenance differs from planned pair")
        files = audit.artifacts(child, child_path)
        require(set(files) == {"detections.csv", "frame_metrics.csv", "summary.json"}, "Unexpected/missing child artifact")
        frames = audit.csv(files["frame_metrics.csv"])
        count = FRAME_COUNTS[video]
        require(len(frames) == count and [integer(row["frame"]) for row in frames] == list(range(count)),
                "Full-video frame universe has missing, extra, duplicate or reordered records")
        raw = object_rows(audit, audit.csv(files["detections.csv"]), video, count)
        for frame_number, frame in enumerate(frames):
            require(frame["video_id"] == video and frame["evaluation_protocol_id"] == PROTOCOL
                    and frame["class_policy"] == EVALUATION["class_policy"] and number(frame["center_gate_px"]) == 10
                    and boolean(frame["annotated"]), "Frame identity/protocol or GT availability differs")
            pred, gt = raw[frame_number]["detection"], raw[frame_number]["manual"]
            audit.fields(frame, {"n_predictions_raw": len(pred), "n_ground_truth_raw": len(gt),
                "n_gt_individuals": sum(item["class_id"] in (0, 2) for item in gt),
                "n_gt_clusters": sum(item["class_id"] == 1 for item in gt)}, "exported raw object counts")
            require(inputs[video]["ground_truth"]["files"][frame_number]["rows"] == len(gt),
                    "Exported GT row count differs from recorded strict-label input")
            key, fingerprint = (video, frame_number), gt_fingerprint(gt)
            require(key not in reference_gt or reference_gt[key] == fingerprint, "Exported GT differs between candidates")
            reference_gt[key] = fingerprint
            extended_frame_counts(audit, frame)
            if key in MATCH_PAIRS:
                independent.compare_matching(audit, candidate, key, pred, gt, frame)
        aggregate = aggregate_video(audit, frames, video)
        summary = audit.json(files["summary.json"])
        require(summary == child["summary"], "Child summary JSON differs from manifest")
        audit.fields(summary, aggregate, f"video summary {candidate}/{video}")
        audit.fields(summary, {"configuration_id": candidate, "split": "val", "status": "complete",
            "frame_coverage_verified": True, "input_hash": inputs[video]["input_hash"],
            "evaluation_protocol_id": PROTOCOL, "class_policy": EVALUATION["class_policy"],
            "center_gate_px": 10, "sensitivity_gates_px": [15, 20], "metric_primary": "f1_individuals_center_10px",
            "count_scope": "scored_predictions_minus_individually_annotated_gt", "video": None}, "video metadata")
        require(summary["completeness"] == {"status": "complete", "expected_frames": count,
                "decoded_frames": count, "frame_metric_rows": count, "extra_read_eof": True,
                "input_hash_verification": "required_before_batch_completion"}, "Missing recorded EOF/completeness evidence")
        certificate = child["frame_coverage_verification"]
        require(certificate["status"] == "verified" and certificate["video_id"] == video
                and certificate["expected_frames"] == certificate["frame_rows"] == count
                and audit.reference(certificate["frame_metrics"]) == files["frame_metrics.csv"], "Frame export certificate differs")
        check_source_verification(child["input_verification"], inputs[video], child["started_at"], child["finished_at"])
        require(number(summary["ram_rss_peak_mb"]) <= BUDGET["max_rss_mb"], "Child exceeds recorded RSS limit")
        require((candidate, video) not in summaries, "Duplicate candidate/video result")
        summaries[candidate, video] = summary
        rebuilt[candidate, video] = aggregate
        all_frame_records += count
        print(json.dumps({"verified_video_runs": index, "planned_runs": 8,
                          "verified_frame_records": all_frame_records}), flush=True)
    require(all_frame_records == 11700 and len(reference_gt) == 5850 and len(audit.match_checks) == 144,
            "Independent verification did not cover the full predetermined universe")
    saved_videos = audit.csv(artifacts["video_metrics.csv"])
    require([(row["configuration_id"], row["video_id"]) for row in saved_videos] == [tuple(pair) for pair in planned_pairs],
            "Batch video table order/universe differs")
    for row in saved_videos:
        audit.fields(row, summaries[row["configuration_id"], row["video_id"]], "batch video table")
    candidates_rebuilt = {candidate: aggregate_candidate([rebuilt[candidate, video] for video in VIDEOS], candidate)
                          for candidate in CANDIDATES}
    ranked_ids = sorted(CANDIDATES, key=lambda candidate: (-candidates_rebuilt[candidate]["macro_video_f1"],
        -candidates_rebuilt[candidate]["macro_video_recall"], candidates_rebuilt[candidate]["macro_video_count_mae"], candidate))
    for name in ("candidate_metrics.csv", "ranking.csv"):
        rows = audit.csv(artifacts[name])
        expected_order = list(CANDIDATES) if name == "candidate_metrics.csv" else ranked_ids
        require([row["configuration_id"] for row in rows] == expected_order, f"Wrong {name} order/universe")
        for index, row in enumerate(rows, 1):
            audit.fields(row, candidates_rebuilt[row["configuration_id"]], name)
            if name == "ranking.csv":
                audit.equal(row["rank"], index, "rank")
    selection = audit.json(artifacts["selection.json"])
    winner = ranked_ids[0]
    audit.fields(selection, {"status": "validation_selected_not_frozen", "interpretation": INTERPRETATION,
        "configuration_id": winner, "params": parameters(winner), "evaluation": EVALUATION,
        "plan_hash": provenance["plan_hash"], "test_executed": False, "five_fold_executed": False}, "selection")
    require([row["configuration_id"] for row in selection["ranking"]] == ranked_ids, "Selection ranking differs")
    for index, row in enumerate(selection["ranking"], 1):
        audit.fields(row, {**candidates_rebuilt[row["configuration_id"]], "rank": index}, "selection ranking")
    audit.fields(batch["summary"], {"complete": True, "split": "val", "interpretation": INTERPRETATION,
        "n_candidates": 2, "n_videos": 4, "n_runs": 8, "frames_per_candidate": 5850, "frame_evaluations": 11700,
        "selected_configuration_id": winner}, "batch completeness")
    require(number(batch["summary"]["total_wall_seconds"]) <= BUDGET["batch_soft_wall_seconds"]
            and number(batch["summary"]["ram_rss_peak_mb"]) <= BUDGET["max_rss_mb"]
            and integer(batch["summary"]["artifact_bytes_before_final_manifest"]) <= BUDGET["max_batch_artifact_mb"] * 1024**2,
            "Completed batch records exceeded its prospective budget")
    return {"status": "passed", "batch_manifest": str(batch_path),
        "batch_manifest_sha256": audit.files[str(batch_path)]["sha256"],
        "git_sha_of_verified_runs": batch["git_sha"], "source_hash_of_verified_runs": batch["source_hash"],
        "plan_hash": provenance["plan_hash"], "input_hashes": {v: inputs[v]["input_hash"] for v in VIDEOS},
        "candidates": list(CANDIDATES), "videos": list(VIDEOS), "expected_frames_per_video": FRAME_COUNTS,
        "runs": 8, "frames_per_candidate": 5850, "frame_evaluations": all_frame_records,
        "distinct_physical_frames": len(reference_gt), "independent_ranking": ranked_ids,
        "independent_selected_configuration_id": winner, "ranking_complete_match": True,
        "candidate_metrics_rebuilt": candidates_rebuilt,
        "predetermined_matching_frames": sorted([list(key) for key in MATCH_PAIRS]),
        "matching_checks": audit.match_checks, "shared_snapshot_sha256": capture["snapshot_sha256"],
        "test_executed": False, "five_fold_executed": False, "frozen": False,
        "limits": ["Validation selection, not independent generalization or automatic freezing.",
            "All 11700 frame records and aggregates reconstructed; SciPy matching only at the 24 predetermined candidate/frame combinations (144 checks).",
            "GT came from exported CSVs; source pixels, labels and cached arrays were not reopened.",
            "Original-source hashes and EOF are the executor's recorded evidence, not independently rerun checks.",
            "The embedded plan and recorded prerequisites were checked; registered YAML/current code/environment were not reopened.",
            "Training finalist provenance was checked against prior QA; the 117-candidate refinement was not re-evaluated."]}


def synthetic_self_test():
    audit = Audit()
    def item(cx, cy=0.0, cls=0, width=2.0):
        return {"cx": cx, "cy": cy, "w": width, "h": width, "class_id": cls, "object_id": "id"}
    boundary = independent.independent_match([item(10.004)], [item(0.0)], 10, individuals=True)
    require((boundary["tp"], boundary["fp"], boundary["fn"]) == (0, 1, 1), "Boundary float was rounded")
    cases = [
        ([item(0), item(1)], [item(0), item(0, cls=1, width=30)], (1, 1, 0, 0)),
        ([item(12)], [item(0), item(12, cls=1, width=10)], (0, 0, 1, 1)),
        ([], [], (0, 0, 0, 0)),
        ([item(0)], [item(0, cls=1, width=20)], (0, 0, 0, 1)),
    ]
    frames = []
    for index, (pred, gt, expected) in enumerate(cases):
        row = {"video_id": "synthetic", "frame": index, "annotated": True,
               "n_predictions": len(pred), "n_predictions_raw": len(pred),
               "n_ground_truth": len(gt), "n_ground_truth_raw": len(gt),
               "n_gt_individuals": sum(obj["class_id"] in (0, 2) for obj in gt),
               "n_gt_clusters": sum(obj["class_id"] == 1 for obj in gt),
               "has_gt_clusters": any(obj["class_id"] == 1 for obj in gt),
               "count_error_raw": len(pred)-len(gt), "count_abs_error_raw": abs(len(pred)-len(gt)), "detection_ms": 1.0}
        for gate, suffix in GATES:
            for prefix in PREFIXES:
                metrics = independent.independent_match(pred, gt, gate, individuals=not bool(prefix))
                row.update({f"{prefix}{key}{suffix}": value for key, value in metrics.items()})
        require(tuple(row[key] for key in ("tp", "fp", "fn", "n_predictions_ignored")) == expected,
                "Synthetic protected cluster result differs")
        extended_frame_counts(audit, row)
        frames.append(row)
    require(frames[1]["n_predictions_ignored"] == 1 and frames[1]["n_predictions_ignored_at_15px"] == 0
            and frames[1]["tp_at_15px"] == 1, "12px sensitivity policy was not recalculated")
    aggregate = aggregate_video(audit, frames, "synthetic")
    require(aggregate["frames_cluster_only_gt"] == 1 and aggregate["count_evaluated_frames"] == 4
            and aggregate["frames_primary_unevaluable"] == 1 and aggregate["count_mae"] == 0.5,
            "Fixed annotated universe aggregation differs")
    bad = {**frames[0], "count_abs_error_raw": 999}
    try:
        extended_frame_counts(audit, bad)
    except ValueError:
        pass
    else:
        raise ValueError("Corrupt frame arithmetic was accepted")
    require(len(MATCH_PAIRS) == 12 and len(MATCH_PAIRS)*2*3*2 == 144
            and ("14", 734) in MATCH_PAIRS and ("52", 719) in MATCH_PAIRS, "Wrong prospective matching universe")
    require(gt_fingerprint([item(0), item(0)]) != gt_fingerprint([item(0)]), "GT fingerprint lost multiplicity")
    audit.equal("[15.0, 20.0]", [15, 20], "numeric sensitivity serialization")
    unequal_videos = [aggregate_video(audit, chosen, video) for video, chosen in zip(
        VIDEOS, ([frames[0]], [frames[1]] * 2, [frames[2]] * 3, [frames[0], frames[1]]))]
    macro = aggregate_candidate(unequal_videos, CANDIDATES[0])
    require(macro["n_videos"] == 4 and macro["macro_video_f1"] == statistics.fmean(row["f1"] for row in unequal_videos),
            "Candidate aggregation does not assign equal weight to all four videos")
    pooled = independent.prf(macro["tp"], macro["fp"], macro["fn"])["f1"]
    require(not math.isclose(macro["macro_video_f1"], pooled), "Synthetic case failed to distinguish pooled from macro F1")
    try:
        json.loads('{"x": 1, "x": 2}', object_pairs_hook=strict_object)
    except ValueError:
        pass
    else:
        raise ValueError("Duplicate JSON key was accepted")
    try:
        audit.path(ROOT / "data/sources/forbidden.json")
    except ValueError:
        pass
    else:
        raise ValueError("Source access guard failed")
    require(not any(name == "src" or name.startswith("src.") or name == "script" or name.startswith("script.")
                    for name in sys.modules), "Project scientific implementation imported")
    return {"status": "passed", "mode": "synthetic_self_test", "experiment_artifacts_read": False,
            "checks": ["unrounded 10.004px boundary", "individual priority and duplicate protection",
                       "12px primary/sensitivity recomputation", "cluster-only undefined PRF with count coverage",
                       "empty GT", "arithmetic corruption rejected", "144 predefined checks", "GT multiplicity",
                       "equal-video macro versus pooled F1", "duplicate JSON key rejected", "source guard"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest")
    parser.add_argument("--output", help="New JSON outside the batch run; existing records are refused")
    parser.add_argument("--self-test", action="store_true", help="Synthetic in-memory checks; no experiment data")
    args = parser.parse_args()
    if args.self_test:
        require(args.batch_manifest is None and args.output is None, "Self-test does not accept experiment paths")
        print(json.dumps(synthetic_self_test()), flush=True)
        return 0
    require(args.batch_manifest is not None and args.output is not None, "Explicit batch manifest and new report are required")
    output, requested_batch = Path(args.output).resolve(), Path(args.batch_manifest).resolve()
    require(output.is_relative_to(ROOT) and output.suffix.lower() == ".json"
            and not output.is_relative_to(ROOT / "data/sources")
            and not output.is_relative_to(requested_batch.parent), "Report must be a new JSON outside sources and batch run")
    require(output.parent.is_dir(), "Report parent must already exist")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        started, audit = time.perf_counter(), Audit()
        try:
            report = verify(args.batch_manifest, audit)
            code = 0
        except Exception as error:
            report = {"status": "failed", "error_type": type(error).__name__, "error": str(error),
                      "batch_manifest_requested": args.batch_manifest, "completed_matching_checks": audit.match_checks}
            code = 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-started,
            comparisons=audit.comparisons, files_verified=len(audit.files), input_files=list(audit.files.values()),
            verifier_script=str(Path(__file__).resolve()), verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            reused_independent_helpers={"path": str(Path(independent.__file__).resolve()),
                "sha256": hashlib.sha256(Path(independent.__file__).read_bytes()).hexdigest()},
            runtime={"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()},
            tolerances={"counts": "exact", "scalar_absolute": 1e-12,
                        "spatial_absolute_px": 1e-9, "spatial_relative_for_accumulated_roundoff": 1e-12},
            project_implementation_imported=False, original_sources_opened=False, seed=None)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
