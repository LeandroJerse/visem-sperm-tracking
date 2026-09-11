"""Independent, read-only QA of the registered static-detector comparison.

No detector, production evaluator, aggregation helper or cache loader is
imported. SciPy solves each matching directly from authenticated CSV geometry.
Original MP4/labels are not read and detectors are not rerun. Cache array bytes
are authenticated, but decoding provenance remains the producer's evidence.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import itertools
import json
import math
import random
import re
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment
import yaml

ROOT = Path(__file__).resolve().parents[3]
PLAN = "configs/detection/comparison/classical_v1.yaml"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
FAMILIES = ("threshold", "otsu", "adaptive_threshold", "hybrid_threshold", "blob", "watershed")
COUNTS = (1, 4, 18, 8, 6, 6)
PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"
SUFFIXES = ((10.0, ""), (15.0, "_at_15px"), (20.0, "_at_20px"))
RAW = ("n_predictions_raw", "n_ground_truth_raw", "n_gt_individuals", "n_gt_clusters")
SCORED = ("n_predictions_scored", "n_predictions_ignored", "n_ground_truth_scored")
MACRO = ("precision", "recall", "f1", "count_mae", "count_bias")
TOTALS = ("tp", "fp", "fn", "count_error", "count_abs_error", "count_evaluated_frames")
OBJECT_FIELDS = ("video_id", "frame", "source", "object_id", "class_id", "class_name",
                 "cx", "cy", "w", "h", "x", "y", "score")
ATOL, RTOL = 1e-9, 1e-12
THRESHOLD_REFERENCE = "data/tests/detection/threshold/t218_o0_c2__cfgb8676aa2/refinement/20260908T145354710511Z__da057ef__cfg436896b60741__src3847d91dfb__s42/manifest.json"
THRESHOLD_REFERENCE_SHA256 = "2fcd96562c2ccb959e4afcc6d1079967a6e8f9e38a443ac8ce0c0869a7bd0c48"


class VerificationError(ValueError):
    pass


def require(value: Any, message: str) -> None:
    if not value:
        raise VerificationError(message)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _mapping(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate mapping key: {key}")
        result[key] = value
    return result


def _json(content: bytes | str):
    return json.loads(content, object_pairs_hook=_mapping,
                      parse_constant=lambda value: (_ for _ in ()).throw(VerificationError(f"nonfinite JSON: {value}")))


class StrictYaml(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node):
    return _mapping((loader.construct_object(key, deep=True), loader.construct_object(value, deep=True))
                    for key, value in node.value)


StrictYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def number(value: Any, label: str = "number") -> float:
    require(not isinstance(value, bool), f"boolean {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid {label}: {value!r}") from exc
    require(math.isfinite(result), f"nonfinite {label}")
    return result


def integer(value: Any, label: str = "integer") -> int:
    result = number(value, label)
    require(result.is_integer(), f"noninteger {label}")
    return int(result)


def csv_rows(content: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), "missing/duplicate CSV header")
    rows = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows), "malformed CSV width")
    return rows


class Audit:
    def __init__(self):
        self.files: dict[str, dict] = {}
        self.comparisons = 0
        self.numeric_comparisons = 0
        self.matchings = 0
        self.maximum_numeric_difference = 0.0
        self.distance_tie_limits: list[dict] = []

    def read(self, path: Path, expected: str | None = None, *, retain: bool = True) -> bytes:
        path = Path(path).resolve()
        before = path.stat()
        digest, chunks = hashlib.sha256(), []
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                if retain:
                    chunks.append(chunk)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"file changed while reading: {path}")
        observed = digest.hexdigest()
        if expected is not None:
            require(observed == expected, f"SHA256 mismatch: {path}")
        record = {"sha256": observed, "bytes": after.st_size}
        require(str(path) not in self.files or self.files[str(path)] == record, f"file changed during QA: {path}")
        self.files[str(path)] = record
        return b"".join(chunks)

    def equal(self, actual: Any, expected: Any, label: str) -> None:
        self.comparisons += 1
        if expected is None:
            require(actual is None or actual == "", f"{label}: expected undefined, got {actual!r}")
        elif isinstance(expected, bool):
            require(actual is expected or isinstance(actual, str) and actual == str(expected), f"{label}: boolean mismatch")
        elif isinstance(expected, int):
            require(integer(actual, label) == expected, f"{label}: {actual!r} != {expected}")
            self.numeric_comparisons += 1
        elif isinstance(expected, float):
            observed = number(actual, label)
            difference = abs(observed - expected)
            self.maximum_numeric_difference = max(self.maximum_numeric_difference, difference)
            self.numeric_comparisons += 1
            require(math.isclose(observed, expected, rel_tol=RTOL, abs_tol=ATOL), f"{label}: {observed} != {expected}")
        elif isinstance(expected, (list, dict)):
            if isinstance(actual, str):
                try:
                    actual = ast.literal_eval(actual)
                except (ValueError, SyntaxError) as exc:
                    raise VerificationError(f"{label}: invalid structured CSV value") from exc
            require(isinstance(actual, type(expected)), f"{label}: structured type mismatch")
            if isinstance(expected, dict):
                require(set(actual) == set(expected), f"{label}: mapping keys mismatch")
                for key in expected:
                    self.equal(actual[key], expected[key], f"{label}.{key}")
            else:
                require(len(actual) == len(expected), f"{label}: sequence length mismatch")
                for index, (a, e) in enumerate(zip(actual, expected)):
                    self.equal(a, e, f"{label}[{index}]")
        else:
            require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def subset(self, actual: dict, expected: dict, label: str) -> None:
        for key, value in expected.items():
            require(key in actual, f"{label}: missing {key}")
            self.equal(actual[key], value, f"{label}.{key}")

    def summary(self):
        return {"files_checked": len(self.files), "comparisons": self.comparisons,
                "numeric_comparisons": self.numeric_comparisons, "scipy_matchings": self.matchings,
                "maximum_numeric_difference": self.maximum_numeric_difference,
                "distance_tie_limits": self.distance_tie_limits, "files": self.files,
                "numeric_tolerances": {"absolute": ATOL, "relative": RTOL}}


def under(root: Path, raw: str) -> Path:
    path = Path(raw)
    path = (path if path.is_absolute() else root / path).resolve()
    require(path.is_relative_to(root.resolve()), f"path escapes permitted root: {raw}")
    return path


def independent_candidates(plan: dict) -> list[dict]:
    require(plan["kind"] == "static_classical_detection_comparison_v1" and plan["expected_candidates"] == 43, "unsupported candidate contract")
    require(tuple(map(str, plan["train_ids"])) == TRAIN, "foreign training universe")
    require(plan["evaluation"] == {"protocol_id": PROTOCOL, "center_gate_px": 10,
            "sensitivity_gates_px": [15, 20], "class_policy": "individuals_ignore_clusters"}, "evaluation contract differs")
    require(plan["sampling"] == {"smoke_mode": "benchmark", "search_mode": "master",
            "smoke_frames_per_video": 1, "search_frames_per_video": 48}, "sampling contract differs")
    require(plan["run"] == {"split": "train", "seed": 42, "opencv_threads": 1, "save_video": False}, "run contract differs")
    require(plan["selection"]["primary"] == "macro_video_f1_individuals_center_10px"
            and plan["selection"]["tie_breakers"] == ["macro_video_recall_desc", "macro_video_count_mae_asc", "configuration_id_asc"]
            and plan["selection"]["finalists_per_family"] == 2
            and plan["selection"]["promotion_allowed"] is False
            and plan["selection"]["validation_released"] is False, "selection contract differs")
    groups = plan["families"]
    require(tuple(group["family"] for group in groups) == FAMILIES, "family order differs")
    result = []
    for group, expected_count in zip(groups, COUNTS):
        fixed, grid, family = group["params"], group["search_space"], group["family"]
        require(not set(fixed) & set(grid), "overlapping fixed and searched parameters")
        require(all(isinstance(v, list) and v for v in grid.values()), "invalid search axis")
        combinations = list(itertools.product(*grid.values()))
        require(len(combinations) == expected_count == group["expected_candidates"], "family grid size differs")
        for index, values in enumerate(combinations, 1):
            result.append({"configuration_id": "t218_o0_c2_reference_v1" if family == "threshold" else f"{family}_v1_{index:03d}",
                           "method": group["method"], "family": family,
                           "params": {**fixed, **dict(zip(grid, values))},
                           "evaluation": plan["evaluation"], "run": plan["run"]})
    require(len(result) == 43, "incomplete candidate grid")
    random.Random(42).shuffle(result)
    return result


def object_row(row: dict[str, str], audit: Audit) -> dict:
    require(set(row) == set(OBJECT_FIELDS), "raw object CSV schema differs")
    parsed = {key: row[key] for key in ("video_id", "source", "object_id", "class_name")}
    parsed.update(frame=integer(row["frame"]), class_id=integer(row["class_id"]))
    require(parsed["video_id"] in TRAIN and parsed["frame"] >= 0 and parsed["class_id"] in (0, 1, 2), "foreign/invalid object key")
    require(parsed["source"] in ("detection", "manual"), "unknown object source")
    for key in ("cx", "cy", "w", "h", "x", "y", "score"):
        parsed[key] = number(row[key], key)
    require(parsed["w"] > 0 and parsed["h"] > 0 and 0 <= parsed["score"] <= 1, "invalid size or score")
    audit.equal(parsed["class_name"], {0: "normal", 1: "cluster", 2: "pinhead"}[parsed["class_id"]], "class name")
    audit.equal(parsed["x"], parsed["cx"] - parsed["w"] / 2, "raw x")
    audit.equal(parsed["y"], parsed["cy"] - parsed["h"] / 2, "raw y")
    return parsed


def authenticated_cache(root: Path, plan: dict, audit: Audit):
    inputs = plan["input"]
    base_plan = yaml.load(audit.read(under(root, inputs["sample_plan"])), Loader=StrictYaml)
    audit.equal(canonical_hash(base_plan), inputs["sample_plan_canonical_sha256"], "sample plan hash")
    path = under(root, inputs["cache_manifest"])
    cache = _json(audit.read(path, inputs["cache_manifest_sha256"]))
    audit.subset(cache, {"schema_version": 1, "status": "complete", "kind": "canonical_training_detection_sample",
                        "video_ids": list(TRAIN), "sample_hash": inputs["sample_hash"],
                        "plan_sha256": inputs["sample_plan_canonical_sha256"]}, "cache")
    identity = {key: cache[key] for key in ("schema_version", "plan_sha256", "split", "audit", "video_ids",
                                          "sampling", "selections", "videos", "ground_truth", "frames")}
    audit.equal(canonical_hash(identity), inputs["sample_hash"], "cache sample identity")
    require(set(cache["videos"]) == set(TRAIN) and set(cache["selections"]) == set(TRAIN), "cache video universe differs")
    frame_records = {}
    for record in cache["frames"]:
        key = (str(record["video_id"]), integer(record["frame"]))
        require(key[0] in TRAIN and key not in frame_records, "duplicate/foreign cached frame")
        frame_records[key] = record
    pairs = {"smoke": [], "search": []}
    for video in TRAIN:
        record, selection = cache["videos"][video], cache["selections"][video]
        for mode, size in (("master", 48), ("coarse", 12), ("benchmark", 1)):
            frames = selection[mode]
            require(len(frames) == size and frames == sorted(set(frames)) and all(type(v) is int and v >= 0 for v in frames), "invalid cached frame selection")
        require(set(selection["coarse"]) <= set(selection["master"]) and set(selection["benchmark"]) <= set(selection["coarse"]), "nonnested cache")
        for index, frame in enumerate(selection["master"]):
            require((video, frame) in frame_records, "cached frame missing")
            audit.equal(frame_records[(video, frame)]["array_index"], index, "cache array index")
        pairs["smoke"].extend((video, f) for f in selection["benchmark"])
        pairs["search"].extend((video, f) for f in selection["master"])
        array = under(path.parent, record["array_path"])
        audit.read(array, record["array_sha256"], retain=False)
        audit.equal(array.stat().st_size, record["array_bytes"], "array bytes")
        audit.equal(record["shape"], [48, 480, 640, 3], "array shape declaration")
        audit.equal(record["dtype"], "uint8", "array dtype declaration")
        # Authenticate array bytes without loading/decoding any individual image.
    require(set(frame_records) == set(pairs["search"]), "cached frame coverage differs")
    gt_info = cache["ground_truth"]
    gt_rows = csv_rows(audit.read(under(path.parent, gt_info["path"]), gt_info["sha256"]))
    audit.equal(len(gt_rows), gt_info["rows"], "cache GT rows")
    grouped = {pair: [] for pair in pairs["search"]}
    ids = set()
    for raw in gt_rows:
        row = object_row(raw, audit)
        key = row["video_id"], row["frame"]
        require(key in grouped and row["source"] == "manual" and row["object_id"], "foreign/invalid cached GT")
        id_key = (*key, row["object_id"])
        require(id_key not in ids, "duplicate GT identity in frame")
        ids.add(id_key)
        grouped[key].append(row)
    for key, rows in grouped.items():
        audit.equal(len(rows), frame_records[key]["label"]["nonempty_lines"], "cached GT frame count")
    return pairs, grouped, {"sample_manifest_path": str(path), "sample_manifest_sha256": inputs["cache_manifest_sha256"], "sample_hash": inputs["sample_hash"]}


def solve_matching(predictions: list[dict], targets: list[dict], radius: float):
    distances = np.array([[math.hypot(p["cx"] - g["cx"], p["cy"] - g["cy"])
                           for g in targets] for p in predictions], dtype=float).reshape(len(predictions), len(targets))
    allowed = distances <= radius
    # Every extra invalid edge costs more than the sum of all possible valid distances.
    penalty = (min(distances.shape) + 1) * (radius + 1.0)
    costs = np.where(allowed, distances, penalty)
    rows, cols = linear_sum_assignment(costs)
    matches = [(int(i), int(j)) for i, j in zip(rows, cols) if allowed[i, j]]
    return matches, distances, costs


def prf(tp: int, fp: int, fn: int, evaluable: bool = True):
    if not evaluable:
        return None, None, None
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall, 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def quality(predictions, gt, radius, individual, audit: Audit):
    targets = [g for g in gt if not individual or g["class_id"] != 1]
    clusters = [g for g in gt if g["class_id"] == 1] if individual else []
    matches, distances, costs = solve_matching(predictions, targets, radius)
    audit.matchings += 1
    matched = {i for i, _ in matches}
    ignored = []
    for i, p in enumerate(predictions):
        if i in matched or not individual or (distances[i] <= radius).any():
            continue
        if any(g["cx"] - g["w"] / 2 <= p["cx"] <= g["cx"] + g["w"] / 2 and
               g["cy"] - g["h"] / 2 <= p["cy"] <= g["cy"] + g["h"] / 2 for g in clusters):
            ignored.append(i)
    tp, fp, fn = len(matches), len(predictions) - len(matches) - len(ignored), len(targets) - len(matches)
    evaluable = not (individual and clusters and not targets and not tp + fp)
    precision, recall, f1 = prf(tp, fp, fn, evaluable)
    ds = [float(distances[i, j]) for i, j in matches]
    error = fp - fn
    result = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
              "center_error_sum_px": sum(ds), "center_error_mean_px": statistics.fmean(ds) if ds else None,
              "center_error_median_px": statistics.median(ds) if ds else None, "center_error_max_px": max(ds) if ds else None,
              "count_error": error, "count_abs_error": abs(error), "count_bias": error, "count_mae": abs(error)}
    if individual:
        result.update(primary_evaluable=evaluable, n_predictions_scored=tp + fp,
                      n_predictions_ignored=len(ignored), n_ground_truth_scored=len(targets))
    return result, (matches, distances, costs, radius)


def has_cooptimal_assignment(witness) -> bool:
    matches, distances, costs, radius = witness
    original_total = sum(distances[i, j] for i, j in matches)
    for i, j in matches:
        alternative = costs.copy()
        alternative[i, j] = (sum(costs.shape) + 2) * (float(costs.max(initial=0)) + radius + 1)
        a, b = linear_sum_assignment(alternative)
        other = [(x, y) for x, y in zip(a, b) if distances[x, y] <= radius and (x, y) != (i, j)]
        if len(other) == len(matches) and math.isclose(sum(distances[x, y] for x, y in other), original_total, rel_tol=RTOL, abs_tol=ATOL):
            return True
    return False


def frame_metrics(predictions, gt, video: str, frame: int, audit: Audit):
    clusters = sum(g["class_id"] == 1 for g in gt)
    raw_error = len(predictions) - len(gt)
    result = {"video_id": video, "frame": frame, "annotated": True, "class_policy": "individuals_ignore_clusters",
              "center_gate_px": 10.0, "n_predictions": len(predictions), "n_predictions_raw": len(predictions),
              "n_ground_truth": len(gt), "n_ground_truth_raw": len(gt), "n_gt_individuals": len(gt) - clusters,
              "n_gt_clusters": clusters, "has_gt_clusters": bool(clusters),
              "count_error_raw": raw_error, "count_abs_error_raw": abs(raw_error)}
    witnesses = {}
    for radius, suffix in SUFFIXES:
        for prefix, individual in (("", True), ("secondary_all_objects_", False)):
            q, witness = quality(predictions, gt, radius, individual, audit)
            result.update({f"{prefix}{name}{suffix}": value for name, value in q.items()})
            witnesses[(prefix, suffix)] = witness
    return result, witnesses


def compare_frame(observed: dict, expected: dict, witnesses: dict, audit: Audit, label: str):
    skip = set()
    for (prefix, suffix), witness in witnesses.items():
        fields = [f"{prefix}center_error_{name}_px{suffix}" for name in ("median", "max")]
        mismatch = [key for key in fields if expected[key] is not None and
                    not math.isclose(number(observed.get(key), key), expected[key], rel_tol=RTOL, abs_tol=ATOL)]
        if mismatch and has_cooptimal_assignment(witness):
            for key in mismatch:
                require(0 <= number(observed[key]) <= witness[3] + ATOL, "cooptimal distance statistic outside gate")
            audit.distance_tie_limits.append({"frame": label, "fields": mismatch,
                "reason": "different cooptimal assignment exists; these order statistics bounded but not exactly certified"})
            skip.update(mismatch)
    audit.subset(observed, {k: v for k, v in expected.items() if k not in skip}, label)


def video_metrics(rows: list[dict], video: str) -> dict:
    n = len(rows)
    timing = [row["detection_ms"] for row in rows]
    raw_errors = [row["count_error_raw"] for row in rows]
    result = {"video_id": video, "frames_total": n, "frames_annotated": n, "frames_unannotated": 0,
              "frames_with_clusters": sum(bool(r["n_gt_clusters"]) for r in rows),
              "frames_with_individual_gt": sum(bool(r["n_gt_individuals"]) for r in rows),
              "frames_true_empty_gt": sum(r["n_ground_truth_raw"] == 0 for r in rows),
              "frames_cluster_only_gt": sum(bool(r["n_gt_clusters"]) and not r["n_gt_individuals"] for r in rows),
              "n_predictions_unannotated": 0, "detection_ms_mean": statistics.fmean(timing),
              "detection_ms_median": statistics.median(timing), "detection_ms_max": max(timing),
              "count_error_raw": sum(raw_errors), "count_abs_error_raw": sum(map(abs, raw_errors)),
              "count_bias_raw": statistics.fmean(raw_errors), "count_mae_raw": statistics.fmean(map(abs, raw_errors))}
    result.update({key: sum(r[key] for r in rows) for key in RAW})
    for _, suffix in SUFFIXES:
        effective = sum(r["primary_evaluable" + suffix] for r in rows)
        result.update({"frames_primary_evaluable" + suffix: effective, "frames_primary_unevaluable" + suffix: n - effective,
                       "frames_with_ignored_predictions" + suffix: sum(bool(r["n_predictions_ignored" + suffix]) for r in rows)})
        result.update({key + suffix: sum(r[key + suffix] for r in rows) for key in SCORED})
        for prefix in ("", "secondary_all_objects_"):
            def value(row, key):
                return row[prefix + key + suffix]
            tp, fp, fn = (sum(value(r, k) for r in rows) for k in ("tp", "fp", "fn"))
            precision, recall, f1 = prf(tp, fp, fn, bool(prefix or effective or tp + fp + fn))
            errors = [value(r, "count_error") for r in rows]
            distance = sum(value(r, "center_error_sum_px") for r in rows)
            q = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
                 "center_error_mean_px": distance / tp if tp else None, "center_error_sum_px": distance,
                 "count_error": sum(errors), "count_abs_error": sum(map(abs, errors)),
                 "count_mae": statistics.fmean(map(abs, errors)), "count_bias": statistics.fmean(errors),
                 "count_evaluated_frames": n}
            result.update({prefix + k + suffix: v for k, v in q.items()})
    return result


def candidate_metrics(videos: list[dict], identifier: str, frames_each: int) -> dict:
    require([r["video_id"] for r in videos] == list(TRAIN), "candidate video order differs")
    result = {"configuration_id": identifier, "complete": True, "evaluation_protocol_id": PROTOCOL,
              "class_policy": "individuals_ignore_clusters", "center_gate_px": 10, "sensitivity_gates_px": [15, 20],
              "interpretation": "training_screening_not_generalization_estimate", "video_ids": list(TRAIN), "n_videos": 12,
              "expected_frames_per_video": {v: frames_each for v in TRAIN}, "frames_total": 12 * frames_each,
              "frames_annotated": 12 * frames_each, "frames_unannotated": 0}
    result.update({key: sum(r[key] for r in videos) for key in RAW})
    for _, suffix in SUFFIXES:
        result.update({key + suffix: sum(r[key + suffix] for r in videos) for key in SCORED})
        for prefix in ("", "secondary_all_objects_"):
            for metric in MACRO:
                name = prefix + metric + suffix
                require(all(r[name] is not None for r in videos), f"undefined video ranking metric: {name}")
                result["macro_video_" + name] = statistics.fmean(r[name] for r in videos)
            for metric in TOTALS:
                name = prefix + metric + suffix
                result[name] = sum(r[name] for r in videos)
    result["macro_video_f1_individuals_center_10px"] = result["macro_video_f1"]
    result["macro_video_detection_ms_mean"] = statistics.fmean(r["detection_ms_mean"] for r in videos)
    return result


def authenticated_artifacts(manifest: dict, directory: Path, audit: Audit) -> dict[str, bytes]:
    paths, hashes = manifest["artifacts"], manifest["artifact_hashes"]
    require(paths and set(paths) == set(hashes), "artifact/hash set mismatch")
    result = {}
    for key, raw in paths.items():
        path = under(directory, raw)
        require(path.parent == directory.resolve() and path.name != "manifest.json" and path.name not in result,
                "foreign/duplicate artifact")
        result[path.name] = audit.read(path, hashes[key])
    actual = {p.name for p in directory.iterdir() if p.is_file() and p.name != "manifest.json"}
    require(actual == set(result), "undeclared or missing artifact in run directory")
    return result


def provenance(manifest: dict, audit: Audit, *, mode: str, parent: dict | None = None):
    audit.subset(manifest, {"status": "complete", "git_dirty": False, "seed": 42, "stage": mode, "module": "detection"}, "provenance")
    require(re.fullmatch(r"[0-9a-f]{7,40}", manifest.get("git_sha", "")) is not None, "missing commit")
    require(re.fullmatch(r"[0-9a-f]{64}", manifest.get("source_hash", "")) is not None, "missing source hash")
    require(isinstance(manifest.get("environment"), dict) and manifest["environment"], "missing environment")
    capture = manifest.get("provenance_capture", {})
    require(capture.get("mode") == "shared_batch" and capture.get("recheck_policy") == "batch_end_before_ranking", "missing snapshot capture")
    require(re.fullmatch(r"[0-9a-f]{64}", capture.get("snapshot_sha256", "")) is not None, "missing snapshot hash")
    audit.equal(manifest["config_hash"], canonical_hash(manifest["config"])[:12], "run config hash")
    if parent:
        for key in ("git_sha", "source_hash", "environment"):
            audit.equal(manifest[key], parent[key], "child." + key)
        for key in ("snapshot_sha256", "process_id", "captured_at"):
            audit.equal(capture[key], parent["provenance_capture"][key], "child snapshot." + key)
    else:
        verification = manifest.get("provenance_verification", {})
        audit.subset(verification, {"status": "verified", "scope": "batch_end_before_ranking",
                                   "snapshot_sha256": capture["snapshot_sha256"]}, "final provenance")


def historical_reference(root: Path, audit: Audit, planned_master: list[tuple[str, int]]):
    path = under(root, THRESHOLD_REFERENCE)
    manifest = _json(audit.read(path, THRESHOLD_REFERENCE_SHA256))
    audit.subset(manifest, {"status": "complete", "git_dirty": False}, "historical T218")
    files = authenticated_artifacts(manifest, path.parent, audit)
    require({"detections.csv", "frame_metrics.csv"} <= set(files), "historical reference lacks raw outputs")
    objects = {pair: [] for pair in planned_master}
    for raw in csv_rows(files["detections.csv"]):
        row = object_row(raw, audit)
        key = row["video_id"], row["frame"]
        require(key in objects, "historical T218 contains a foreign frame")
        objects[key].append(row)
    frames = csv_rows(files["frame_metrics.csv"])
    require([(r["video_id"], integer(r["frame"])) for r in frames] == planned_master, "historical T218 frame coverage differs")
    return objects, dict(zip(planned_master, frames))


def verify_ranking(files: dict[str, bytes], summaries: list[dict], audit: Audit) -> list[str]:
    """Check the exact unrounded ordering of already independently checked summaries."""
    require(len(summaries) == 43 and len({r["configuration_id"] for r in summaries}) == 43,
            "ranking requires 43 unique candidates")
    ranked = sorted(summaries, key=lambda r: (-r["macro_video_f1"], -r["macro_video_recall"],
                                            r["macro_video_count_mae"], r["configuration_id"]))
    ranked = [{**row, "rank": i} for i, row in enumerate(ranked, 1)]
    observed = csv_rows(files["ranking.csv"])
    require(len(observed) == 43, "ranking row count differs")
    for actual, expected in zip(observed, ranked):
        audit.equal(actual, {key: "" if value is None else str(value) for key, value in expected.items()},
                    "ranking serialization and order")
    finalists = [row for family in FAMILIES for row in [r for r in ranked if r["family"] == family][:2]]
    require(len(finalists) == 11, "family finalist count differs")
    audit.equal(_json(files["family_finalists.json"]), finalists, "family finalists")
    return [row["configuration_id"] for row in finalists]


def verify_batch(manifest_path: Path, *, root: Path = ROOT, plan_path: Path | None = None,
                 audit: Audit | None = None) -> dict:
    audit = audit or Audit()
    root = Path(root).resolve()
    manifest_path = under(root, str(manifest_path))
    plan_path = under(root, str(plan_path or root / PLAN))
    require(plan_path == root / PLAN, "only the canonical comparison plan is accepted")
    plan = yaml.load(audit.read(plan_path), Loader=StrictYaml)
    candidates = independent_candidates(plan)
    batch_bytes = audit.read(manifest_path)
    batch = _json(batch_bytes)
    mode = batch.get("summary", {}).get("mode")
    require(mode in ("smoke", "search"), "only complete smoke/search supported")
    provenance(batch, audit, mode=mode)
    pairs_by_mode, cached_gt, input_reference = authenticated_cache(root, plan, audit)
    historical_objects, historical_frames = historical_reference(root, audit, pairs_by_mode["search"])
    pairs = pairs_by_mode[mode]
    frames_each = 1 if mode == "smoke" else 48
    plan_hash = canonical_hash(plan)
    audit.subset(batch["config"], {"plan": plan, "mode": mode, "input": input_reference}, "batch config")
    summary = batch["summary"]
    audit.subset(summary, {"complete": True, "mode": mode, "plan_hash": plan_hash, "sample_hash": plan["input"]["sample_hash"],
                          "completed_candidates": 43, "frames_per_candidate": len(pairs), "frame_evaluations": 43 * len(pairs),
                          "selection_allowed": mode == "search", "promotion_allowed": False,
                          "validation_released": False, "wall_seconds_limit": None}, "batch summary")
    for key in ("cache_validation_seconds", "candidate_loop_seconds", "ram_rss_peak_mb"):
        require(number(summary[key], key) >= 0, "negative resource/timing value")
    require(number(summary["ram_rss_peak_mb"]) <= plan["budget"]["max_rss_mb"], "batch RSS exceeded")
    require(integer(summary["resource_samples"]) > 0, "no RSS samples")
    files = authenticated_artifacts(batch, manifest_path.parent, audit)
    expected_files = {"planned_candidates.json", "planned_frames.json", "candidate_metrics.csv"} | {f"candidate_{i:03d}.json" for i in range(1, 44)}
    if mode == "search":
        expected_files |= {"ranking.csv", "family_finalists.json"}
    require(set(files) == expected_files, "batch artifact schema differs")
    audit.equal(_json(files["planned_candidates.json"]), candidates, "planned candidates")
    audit.equal(_json(files["planned_frames.json"]), [list(pair) for pair in pairs], "planned frames")
    candidate_records = batch["candidate_manifests"]
    require(len(candidate_records) == 43, "candidate manifest count differs")
    summaries, child_bytes_total, child_paths = [], 0, set()
    for index, (record, expected_config) in enumerate(zip(candidate_records, candidates), 1):
        path = under(root, record["path"])
        require(path not in child_paths and path != manifest_path, "duplicate child manifest")
        child_paths.add(path)
        child = _json(audit.read(path, record["sha256"]))
        provenance(child, audit, mode=mode, parent=batch)
        config = child["config"]
        candidate = dict(expected_config)
        candidate["run"] = {**candidate["run"], "stage": mode}
        audit.subset(config, candidate, "candidate config")
        audit.subset(config["provenance"], {"plan_id": plan["plan_id"], "plan_hash": plan_hash,
                     **input_reference, "sample_mode": "benchmark" if mode == "smoke" else "master",
                     "batch_manifest_path": str(manifest_path)}, "candidate input provenance")
        audit.equal(child["provenance_capture"]["origin_batch_manifest"], str(manifest_path), "child origin")
        child_files = authenticated_artifacts(child, path.parent, audit)
        require(set(child_files) == {"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"}, "candidate artifact schema differs")
        child_bytes_total += sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())
        identifier = expected_config["configuration_id"]
        detections = {pair: [] for pair in pairs}
        gt = {pair: [] for pair in pairs}
        for raw in csv_rows(child_files["detections.csv"]):
            row = object_row(raw, audit)
            pair = row["video_id"], row["frame"]
            require(pair in gt, "exported object outside frame plan")
            (gt if row["source"] == "manual" else detections)[pair].append(row)
        for pair in pairs:
            audit.equal(gt[pair], cached_gt[pair], f"{identifier}/{pair}: raw GT")
            require(len(detections[pair]) <= plan["budget"]["max_predictions_per_frame"], "prediction ceiling exceeded")
            if expected_config["family"] == "threshold":
                audit.equal(detections[pair] + gt[pair], historical_objects[pair], f"T218 historical raw parity/{pair}")
        observed_frames = csv_rows(child_files["frame_metrics.csv"])
        require([(r["video_id"], integer(r["frame"])) for r in observed_frames] == pairs, "frame metric universe differs")
        reconstructed = []
        for observed, pair in zip(observed_frames, pairs):
            row, witness = frame_metrics(detections[pair], gt[pair], *pair, audit)
            row.update(configuration_id=identifier, family=expected_config["family"], evaluation_protocol_id=PROTOCOL,
                       sample_hash=plan["input"]["sample_hash"])
            compare_frame(observed, row, witness, audit, f"{identifier}/{pair}")
            if expected_config["family"] == "threshold":
                scientific = {key: value for key, value in row.items()
                              if key not in {"configuration_id", "family", "evaluation_protocol_id", "sample_hash"}}
                compare_frame(historical_frames[pair], scientific, witness, audit, f"T218 historical metrics/{pair}")
            row["detection_ms"] = number(observed["detection_ms"], "detection time")
            require(row["detection_ms"] >= 0, "negative detection time")
            reconstructed.append(row)
        observed_videos = csv_rows(child_files["video_summary.csv"])
        require([r["video_id"] for r in observed_videos] == list(TRAIN), "video summary universe differs")
        videos = []
        for observed, video in zip(observed_videos, TRAIN):
            row = video_metrics([r for r in reconstructed if r["video_id"] == video], video)
            row.update(configuration_id=identifier, family=expected_config["family"], evaluation_protocol_id=PROTOCOL,
                       class_policy="individuals_ignore_clusters", center_gate_px=10,
                       sensitivity_gates_px=[15, 20], sample_hash=plan["input"]["sample_hash"])
            audit.subset(observed, row, f"{identifier}/{video}: aggregate")
            videos.append(row)
        expected_summary = candidate_metrics(videos, identifier, frames_each)
        expected_summary.update(mode=mode, family=expected_config["family"], method=expected_config["method"],
                                run_id=child["run_id"], manifest_path=str(path), plan_hash=plan_hash, sample_hash=plan["input"]["sample_hash"])
        observed_summary = _json(child_files["summary.json"])
        audit.subset(observed_summary, expected_summary, f"{identifier}: summary")
        audit.equal(observed_summary, child["summary"], "summary vs child manifest")
        audit.equal(_json(files[f"candidate_{index:03d}.json"]), observed_summary, "candidate checkpoint")
        audit.equal(sum(r["detection_ms"] for r in reconstructed) / 1000, observed_summary["detector_seconds"], "detector timing sum")
        for key in ("evaluation_seconds", "export_seconds", "ram_rss_peak_mb"):
            require(number(observed_summary[key], key) >= 0, "negative candidate timing/resource")
        require(number(observed_summary["ram_rss_peak_mb"]) <= plan["budget"]["max_rss_mb"], "candidate RSS exceeded")
        summaries.append(observed_summary)
        print(json.dumps({"verification_candidate": index, "planned": 43, "configuration_id": identifier}), flush=True)
    audit.equal(child_bytes_total, summary["candidate_artifact_bytes"], "candidate artifact bytes")
    batch_bytes_total = sum(p.stat().st_size for p in manifest_path.parent.iterdir() if p.is_file())
    require(child_bytes_total + batch_bytes_total <= plan["budget"]["max_batch_artifact_mb"] * 1024**2, "final artifact budget exceeded")
    observed_candidates = csv_rows(files["candidate_metrics.csv"])
    require(len(observed_candidates) == 43, "candidate metric row count differs")
    for observed, expected in zip(observed_candidates, summaries):
        audit.equal(observed, {key: "" if value is None else str(value) for key, value in expected.items()}, "batch candidate metrics serialization")
    finalists_ids = []
    if mode == "search":
        finalists_ids = verify_ranking(files, summaries, audit)
        smoke = batch["config"]["provenance"]["smoke"]
        require(isinstance(smoke, dict), "search missing smoke parent")
        smoke_manifest = _json(audit.read(under(root, smoke["path"]), smoke["sha256"]))
        audit.subset(smoke_manifest["summary"], {"mode": "smoke", "complete": True, "selection_allowed": False,
                    "plan_hash": plan_hash, "sample_hash": plan["input"]["sample_hash"], "frame_evaluations": 516}, "smoke prerequisite")
        audit.equal(smoke_manifest["source_hash"], batch["source_hash"], "smoke source compatibility")
    else:
        require(batch["config"]["provenance"]["smoke"] is None, "smoke has unexpected parent")
    audit.read(manifest_path, hashlib.sha256(batch_bytes).hexdigest())
    return {"status": "passed", "mode": mode, "manifest": str(manifest_path),
            "manifest_sha256": hashlib.sha256(batch_bytes).hexdigest(), "plan_hash": plan_hash,
            "candidates": 43, "frames_per_candidate": len(pairs), "frame_evaluations": 43 * len(pairs),
            "family_finalist_ids": finalists_ids, "new_detector_runs": 0,
            "historical_t218_parity": {"status": "passed", "manifest": THRESHOLD_REFERENCE,
                "manifest_sha256": THRESHOLD_REFERENCE_SHA256, "frames_compared": len(pairs),
                "excluded_fields": ["timing", "configuration_id", "family", "evaluation_protocol_id", "sample_hash", "run_metadata"]},
            "limitations": ["Original videos and labels are not reread; source decoding is not reproduced.",
                "Detector inference and wall-clock measurements are not reproduced; timings are checked for consistency only.",
                "CSV association identities are not exported. Counts and optimal total distance are reconstructed; any cooptimal median/max exception is listed explicitly.",
                "The independent smoke QA receipt is separate evidence; during search this verifier authenticates the smoke manifest link and recomputes the complete search itself."],
            **audit.summary()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "data/sources"), "QA output outside derived workspace")
    require(not output.exists(), "QA output already exists; preserve previous attempts")
    started, audit = time.perf_counter(), Audit()
    result = {"started_at": datetime.now(timezone.utc).isoformat(), "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "numpy_version": np.__version__, "scipy_version": scipy.__version__}
    exit_code = 0
    try:
        result.update(verify_batch(args.manifest, audit=audit))
    except Exception as exc:
        result.update(status="failed", error=str(exc), error_type=type(exc).__name__, **audit.summary())
        exit_code = 1
    result["elapsed_seconds"] = time.perf_counter() - started
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"status": result["status"], "output": str(output), "comparisons": audit.comparisons,
                      "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
