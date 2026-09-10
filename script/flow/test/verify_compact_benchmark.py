"""Independent audit of the compact causal Farneback benchmark derivatives.

Only this standalone module, the standard library, NumPy and SciPy are used.
No project implementation is imported; no source MP4 or original annotation
is opened. The decoder and Farneback are not rerun. Every stored witness is
reconstructed with float64 weights and accurate scalar sums. Dense-checkpoint
samples and diagnostics use SciPy as a second interpolation formulation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import sys
import time

import numpy as np
import scipy
from scipy.ndimage import map_coordinates


ROOT = Path(__file__).resolve().parents[3]
PLAN_HASH = "f794175a7060b687099cfc391a02f71e8ba95bf2b18dc736a0e91be741eee0e1"
PARENT_HASH = "88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35"
PARENT_QA_HASH = "f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9"
VIDEOS = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
TOLERANCE = 1e-9
WINDOW_FIELDS = "window_id video_id track_id segment_id split history_start origin_frame future_end history_length forecast_horizon".split()
PHOTO_FB_FIELDS = "photometric_warp_mae photometric_zero_mae photometric_valid_pixels photometric_valid_fraction forward_backward_mae consistent_fraction forward_backward_valid_pixels forward_backward_valid_fraction flow_finite_valid_fraction".split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(type(value) is int or isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value) is not None,
            f"Invalid nonnegative integer {value!r}")
    result = int(value)
    require(result >= 0, "Negative count/index")
    return result


def number(value):
    require(not isinstance(value, bool) and value not in (None, ""), f"Invalid number {value!r}")
    result = float(value)
    require(math.isfinite(result), "Nonfinite numeric value")
    return result


def boolean(value):
    require(type(value) is bool or isinstance(value, str) and value in ("True", "False"), "Invalid Boolean")
    return value if type(value) is bool else value == "True"


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "Malformed SHA256")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def parse_json(blob):
    return json.loads(blob.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_constant=bad_constant)


class Audit:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.allowed = set()
        self.files = {}
        self.comparisons = 0
        self.numeric_comparisons = 0
        self.coordinate_comparisons = 0
        self.max_absolute_difference = 0.0
        self.max_difference_label = None
        self.pair_pixels_diagnosed = 0
        self.directional_field_pixels_validated = 0

    def path(self, value):
        candidate = Path(value)
        path = (candidate if candidate.is_absolute() else self.root / candidate).resolve()
        require(path.is_relative_to(self.root) and not path.is_relative_to(self.root / "data/sources"),
                f"Read outside derived/local metadata scope: {path}")
        require(path.suffix.lower() in {".json", ".csv", ".npy", ".npz", ".yaml", ".yml"},
                f"Forbidden input suffix: {path}")
        return path

    def allow(self, paths):
        self.allowed.update(self.path(path) for path in paths)

    def read(self, value, expected_sha=None, expected_bytes=None):
        path = self.path(value)
        require(path in self.allowed, f"Unregistered read: {path}")
        blob = path.read_bytes()
        actual_sha = hashlib.sha256(blob).hexdigest()
        require(expected_sha is None or actual_sha == sha(expected_sha), f"SHA256 mismatch: {path}")
        require(expected_bytes is None or len(blob) == integer(expected_bytes), f"Byte count mismatch: {path}")
        previous = self.files.get(str(path))
        require(previous is None or (previous["sha256"], previous["bytes"]) == (actual_sha, len(blob)),
                f"Input changed during verification: {path}")
        self.files[str(path)] = {"path": str(path), "sha256": actual_sha, "bytes": len(blob)}
        return blob

    def reference(self, record):
        require(isinstance(record, dict) and set(record) == {"path", "sha256", "bytes"}, "Invalid file-reference schema")
        return self.read(record["path"], record["sha256"], record["bytes"])

    def json(self, value):
        return parse_json(self.read(value))

    def rows(self, value, fields=None):
        reader = csv.DictReader(io.StringIO(self.read(value).decode("utf-8-sig")))
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "Missing/duplicate CSV columns")
        require(fields is None or reader.fieldnames == list(fields), f"Unexpected CSV schema: {value}")
        rows = list(reader)
        require(all(None not in row and all(item is not None for item in row.values()) for row in rows), "Malformed CSV row")
        return rows

    def near(self, actual, expected, label):
        self.comparisons += 1
        self.numeric_comparisons += 1
        difference = abs(number(actual) - number(expected))
        if difference > self.max_absolute_difference:
            self.max_absolute_difference, self.max_difference_label = difference, label
        require(difference <= TOLERANCE, f"{label}: absolute difference {difference} > {TOLERANCE}")

    def coordinate(self, actual, expected, label):
        self.comparisons += 1
        self.numeric_comparisons += 1
        self.coordinate_comparisons += 1
        require(number(actual).hex() == number(expected).hex(), f"{label}: coordinate changed")

    def equal(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, dict):
            require(isinstance(actual, dict) and set(actual) == set(expected), f"{label}: mapping keys differ")
            for key in expected:
                self.equal(actual[key], expected[key], f"{label}.{key}")
        elif isinstance(expected, (list, tuple)):
            require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), f"{label}: sequence length differs")
            for index, value in enumerate(expected):
                self.equal(actual[index], value, f"{label}[{index}]")
        elif type(expected) is bool:
            require(boolean(actual) is expected, f"{label}: Boolean differs")
        elif type(expected) is int:
            require(integer(actual) == expected, f"{label}: integer differs")
        elif type(expected) is float:
            self.near(actual, expected, label)
        elif expected is None:
            require(actual is None or actual == "", f"{label}: missing value imputed")
        else:
            require(actual == expected, f"{label}: value differs ({actual!r} != {expected!r})")


def independent_sample(values, validity, points):
    """SciPy order-1 interpolation; strict corner support is assessed separately."""
    values, validity, points = np.asarray(values), np.asarray(validity), np.asarray(points, dtype=np.float64)
    require(values.ndim in (2, 3) and min(values.shape[:2]) > 0, "Invalid sampling field")
    require(validity.dtype == bool and validity.shape == values.shape[:2], "Invalid sampling mask")
    require(points.ndim == 2 and points.shape[1] == 2, "Invalid sampling coordinates")
    height, width = values.shape[:2]
    scalar = values.ndim == 2
    arrays = values[..., None] if scalar else values
    result = np.full((len(points), arrays.shape[2]), np.nan, dtype=np.float64)
    good = np.isfinite(points).all(axis=1) & (points[:, 0] >= 0) & (points[:, 0] <= width - 1) & (points[:, 1] >= 0) & (points[:, 1] <= height - 1)
    ids = np.flatnonzero(good)
    if len(ids):
        chosen = points[ids]
        left, top = np.floor(chosen).astype(np.int64).T
        right, bottom = np.minimum(left + 1, width - 1), np.minimum(top + 1, height - 1)
        dx, dy = chosen[:, 0] - left, chosen[:, 1] - top
        support = validity & np.isfinite(arrays).all(axis=2)
        supported = np.ones(len(ids), dtype=bool)
        for col, row, positive in ((left, top, (1 - dx) * (1 - dy) > 0),
                                    (right, top, dx * (1 - dy) > 0),
                                    (left, bottom, (1 - dx) * dy > 0),
                                    (right, bottom, dx * dy > 0)):
            supported &= ~positive | support[row, col]
        good[ids] = supported
        ids = ids[supported]
        # Zeroing unusable cells is only an internal numerical safeguard. The
        # support gate above guarantees that no retained sample uses them.
        for channel in range(arrays.shape[2]):
            clean = np.where(support, arrays[..., channel], 0).astype(np.float64)
            result[ids, channel] = map_coordinates(clean, points[ids, ::-1].T,
                order=1, mode="constant", cval=np.nan, prefilter=False, output=np.float64)
        require(np.isfinite(result[good]).all(), "Nonfinite interpolated value")
    return (result[:, 0] if scalar else result), good


def diagnostics(previous, following, forward, backward, forward_valid, backward_valid):
    height, width = previous.shape
    yy, xx = np.indices((height, width), dtype=np.float64)
    points = np.column_stack((xx.ravel(), yy.ravel())) + forward.reshape(-1, 2).astype(np.float64)
    sampled_gray, good_gray = independent_sample(following, np.ones(previous.shape, dtype=bool), points)
    supported = forward_valid.ravel() & good_gray
    n_photo, n_total = int(supported.sum()), previous.size
    zero = following.astype(np.float64).ravel() - previous.astype(np.float64).ravel()
    residual_gray = sampled_gray - previous.astype(np.float64).ravel()
    sampled_back, good_back = independent_sample(backward, backward_valid, points)
    roundtrip = forward_valid.ravel() & good_back
    n_fb = int(roundtrip.sum())
    f = forward.reshape(-1, 2)[roundtrip].astype(np.float64)
    b = sampled_back[roundtrip]
    residual = np.hypot(f[:, 0] + b[:, 0], f[:, 1] + b[:, 1])
    return {
        "photometric_warp_mae": float(np.mean(np.abs(residual_gray[supported]), dtype=np.float64) / 255) if n_photo else None,
        "photometric_zero_mae": float(np.mean(np.abs(zero[supported]), dtype=np.float64) / 255) if n_photo else None,
        "photometric_valid_pixels": n_photo, "photometric_valid_fraction": n_photo / n_total,
        "forward_backward_mae": float(np.mean(residual, dtype=np.float64)) if n_fb else None,
        "consistent_fraction": int(np.count_nonzero(residual <= 1.5)) / n_fb if n_fb else None,
        "forward_backward_valid_pixels": n_fb, "forward_backward_valid_fraction": n_fb / n_total,
        "flow_finite_valid_fraction": int(np.count_nonzero(forward_valid)) / n_total,
    }


def reference_map(audit, records, expected_paths, label):
    require(isinstance(records, list), f"{label}: references must be a list")
    actual = [audit.path(row["path"]) for row in records]
    require(len(actual) == len(set(actual)) and set(actual) == set(expected_paths), f"{label}: file set differs")
    audit.allow(actual)
    for row in records:
        audit.reference(row)
    return dict(zip(actual, records))


def parent_qa_references(audit, records, parent_path):
    """Normalize the pinned older QA's exact five-field evidence schema.

    The parent's own digest was discovered by that audit, while its 85
    artifacts had expected hashes. We authenticate the parent separately by
    the prospectively pinned digest; historical mtime is not a content hash.
    """
    require(isinstance(records, list), "Parent QA input files must be a list")
    output = []
    for record in records:
        require(isinstance(record, dict) and set(record) == {
            "path", "sha256", "bytes", "mtime_ns", "expected_hash_verified"},
            "Unexpected parent QA input-file schema")
        integer(record["mtime_ns"])
        expected_flag = audit.path(record["path"]) != parent_path
        require(type(record["expected_hash_verified"]) is bool
                and record["expected_hash_verified"] is expected_flag,
                "Parent QA expected-hash evidence differs from pinned format")
        output.append({key: record[key] for key in ("path", "sha256", "bytes")})
    return output


def read_parent(audit, plan, manifest):
    parent_path = audit.path(plan["reference"]["manifest"])
    qa_path = audit.path(plan["reference"]["verification"])
    require(parent_path.is_relative_to(audit.root / "data/derived/prediction/ground_truth_individuals")
            and qa_path.parent == parent_path.parent.parent, "Invalid parent/QA location")
    audit.allow((parent_path, qa_path))
    parent = parse_json(audit.read(parent_path, PARENT_HASH))
    qa = parse_json(audit.read(qa_path, PARENT_QA_HASH))
    audit.equal(plan["reference"]["manifest_sha256"], PARENT_HASH, "registered parent hash")
    audit.equal(plan["reference"]["verification_sha256"], PARENT_QA_HASH, "registered parent QA hash")
    require(parent.get("status") == "complete" and parent.get("stage") == "preparation"
            and parent.get("module") == "prediction" and parent.get("method") == "ground_truth_individuals"
            and parent.get("git_dirty") is False and qa.get("status") == "passed", "Parent/QA not certified")
    audit.equal(qa["run_manifest_sha256"], PARENT_HASH, "QA parent binding")
    require(audit.path(qa["run_manifest"]) == parent_path, "QA path differs from parent")
    require(qa.get("all_observations_segments_windows_compared") is True
            and qa.get("coordinates_compared_as_exact_binary_floats") is True
            and qa.get("original_sources_opened") is False and qa.get("project_implementation_imported") is False,
            "Pinned parent QA does not certify full derived reference")
    train = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
    names = ("observations.csv", "segments.csv", "windows.csv", "frame_status.csv",
             "ground_truth_raw.csv", "summary.json", "input_contract.json")
    expected = {parent_path.parent / "summary.json"}
    expected.update(parent_path.parent / "by_video" / video / name for video in train for name in names)
    parents = reference_map(audit, parent["artifacts"], expected, "parent artifacts")
    meta_paths = [audit.root / name for name in ("configs/protocol/individual_trajectories_v1.yaml",
        "configs/protocol/splits.yaml", "data/manifests/visem_tracking.csv", "data/manifests/annotation_gaps.csv")]
    reference_map(audit, parent["metadata"], meta_paths, "parent metadata")
    provenance = manifest["reference_provenance"]
    for name, path, expected_hash in (("parent_manifest", parent_path, PARENT_HASH), ("verification", qa_path, PARENT_QA_HASH)):
        record = provenance[name]
        require(audit.path(record["path"]) == path and record["sha256"] == expected_hash, f"Wrong {name} provenance")
        audit.reference(record)
    expected_inputs = expected | {parent_path, qa_path} | set(meta_paths)
    reference_map(audit, provenance["validated_inputs"], expected_inputs, "validated parent inputs")
    require(provenance.get("original_sources_read") is False
            and provenance.get("scope") == "individual_reference_v1_training_only", "Unexpected reference scope")
    recheck = manifest["reference_recheck"]
    require(recheck.get("status") == "verified" and recheck.get("files_verified") == len(expected_inputs)
            and recheck.get("scope") == "exported_reference_end_of_batch_no_original_source_recheck",
            "Derived reference not fully rechecked")
    # Compare the earlier audit's complete input identity against pinned files.
    qa_expected = expected | {parent_path}
    reference_map(audit, parent_qa_references(audit, qa["input_files"], parent_path),
                  qa_expected, "parent QA input files")
    for video in VIDEOS:
        contract = audit.json(parent_path.parent / "by_video" / video / "input_contract.json")
        source = plan["sources"][video]
        audit.equal(contract["source_video"], {"path": str(audit.root / source["path"]),
                    "sha256": source["sha256"], "bytes": source["bytes"]}, "declared original source identity")
        audit.equal(contract["expected_width"], 640, "parent width")
        audit.equal(contract["expected_height"], 480, "parent height")
        audit.near(contract["video_metadata"]["fps"], source["fps"], "parent fps")
    return parent_path.parent, parents


REQUEST_FIELDS = "sample_id video_id track_id segment_id frame_from frame_to cx cy".split()
LINK_FIELDS = ["window_id", "sample_ids"]
COMPACT_COVERAGE_FIELDS = "window_id video_id track_id segment_id origin_frame sample_count valid_history19 valid_last5 eligible_last5 invalid_reasons_history19 invalid_reasons_last5".split()


def canonical_sample_id(video, track, segment, frame):
    require(all(isinstance(value, str) and value for value in (video, track, segment)),
            "Sampling identity tokens must be nonempty strings")
    return digest([video, track, segment, integer(frame)])


def reconstruct_requests(audit, parent_folder, folder, video):
    """Rebuild source identities and coordinates solely from pinned derivatives."""
    windows = audit.rows(parent_folder / "by_video" / video / "windows.csv", WINDOW_FIELDS)
    grouped = {}
    for row in windows:
        grouped.setdefault((row["track_id"], row["segment_id"]), []).append(integer(row["origin_frame"]))
    for origins in grouped.values():
        ordered = sorted(origins)
        require(ordered == list(range(ordered[0], ordered[-1] + 1)), "Full-reference segment window origins are not contiguous")
    full_counts = {"full_windows": len(windows), "full_segments_with_windows": len(grouped),
                   "full_unique_samples": sum(len(origins) + 18 for origins in grouped.values())}
    selected = [row for row in windows if 19 <= integer(row["origin_frame"]) <= 59]
    selected.sort(key=lambda row: (integer(row["origin_frame"]), row["track_id"], row["segment_id"], row["window_id"]))
    require(selected and len({row["window_id"] for row in selected}) == len(selected), "No unique fixed-prefix cohort")
    selected_keys = {(row["track_id"], row["segment_id"]) for row in selected}
    positions = {}
    for row in audit.rows(parent_folder / "by_video" / video / "observations.csv"):
        frame = integer(row["frame_index"])
        key = (row["track_id"], row["segment_id"])
        if frame > 59 or key not in selected_keys:
            continue
        require(row["video_id"] == video and row["annotated"] == "True" and row["class_id"] in ("0", "2"),
                "Invalid historical individual observation")
        full_key = (*key, frame)
        require(full_key not in positions, "Duplicate parent historical observation")
        positions[full_key] = number(row["cx"]), number(row["cy"])
    exported = audit.rows(folder / "selected_windows.csv", WINDOW_FIELDS)
    audit.equal(exported, selected, "selected parent window sequence")
    requests, links = {}, []
    signatures = set()
    history_coordinate_uses = 0
    for row in selected:
        origin = integer(row["origin_frame"])
        for key, value in {"video_id": video, "split": "train", "history_start": origin - 19,
                           "future_end": origin + 10, "history_length": 20, "forecast_horizon": 10}.items():
            audit.equal(row[key], value, f"window {key}")
        signature = row["track_id"], row["segment_id"], origin
        require(signature not in signatures, "Same window history has multiple names")
        signatures.add(signature)
        samples = []
        for frame in range(origin - 19, origin + 1):
            key = row["track_id"], row["segment_id"], frame
            require(key in positions, "Missing contiguous historical observation")
            xy = positions[key]
            history_coordinate_uses += 2
            if frame == origin:
                continue
            sample_id = canonical_sample_id(video, *key)
            requested = {"sample_id": sample_id, "video_id": video, "track_id": key[0],
                "segment_id": key[1], "frame_from": frame, "frame_to": frame + 1,
                "cx": xy[0], "cy": xy[1]}
            require(sample_id not in requests or requests[sample_id] == requested, "Conflicting duplicate source sample")
            requests[sample_id] = requested
            samples.append(sample_id)
        links.append({"window_id": row["window_id"], "sample_ids": samples})
    requests = sorted(requests.values(), key=lambda row: (row["frame_from"], row["track_id"], row["segment_id"]))
    exported = audit.rows(folder / "requests.csv", REQUEST_FIELDS)
    require(len(exported) == len(requests), "Deduplicated request count differs")
    for index, (actual, expected) in enumerate(zip(exported, requests)):
        for key, value in expected.items():
            if key in ("cx", "cy"):
                audit.coordinate(actual[key], value, f"request {index} {key}")
            else:
                audit.equal(actual[key], value, f"request {index} {key}")
    actual_links = audit.rows(folder / "links.csv", LINK_FIELDS)
    require(len(actual_links) == len(links), "Window linkage row count differs")
    for original, expected in zip(actual_links, links):
        audit.equal(original["window_id"], expected["window_id"], "linked window identity")
        ids = parse_json(original["sample_ids"].encode("utf-8"))
        audit.equal(ids, expected["sample_ids"], "nineteen ordered causal source links")
    return selected, requests, links, history_coordinate_uses, full_counts


def independent_witness(points, corners_xy, corner_uv, corner_valid, inside, *, width, height):
    """Rebuild strict bilinear values with scalar weights and accurate sums.

    Stored corner geometry is checked independently from source coordinates.
    All positively weighted neighbours must be marked valid and finite. A
    zero-weight invalid/NaN neighbour cannot poison an exact boundary sample.
    Outside rows must retain the registered -1/NaN/false witness sentinels.
    """
    n = len(points)
    require(isinstance(points, np.ndarray) and points.dtype == np.float64 and points.shape == (n, 2)
            and np.isfinite(points).all(), "Witness source points must be finite float64 N,2")
    require(corners_xy.dtype == np.int64 and corners_xy.shape == (n, 4, 2), "Witness corner geometry must be int64 N,4,2")
    require(corner_uv.dtype == np.float32 and corner_uv.shape == (n, 4, 2), "Witness vectors must be float32 N,4,2")
    require(corner_valid.dtype == bool and corner_valid.shape == (n, 4), "Witness corner validity must be bool N,4")
    require(inside.dtype == bool and inside.shape == (n,), "Witness inside flags must be bool N")
    require(type(width) is int and type(height) is int and min(width, height) > 0, "Invalid witness image dimensions")
    values = np.full((n, 2), np.nan, dtype=np.float64)
    supported = np.zeros(n, dtype=bool)
    reasons = []
    for index, (x, y) in enumerate(points):
        is_inside = 0 <= x <= width - 1 and 0 <= y <= height - 1
        require(bool(inside[index]) == is_inside, "Witness inside flag differs from float64 bounds")
        if not is_inside:
            require((corners_xy[index] == -1).all() and np.isnan(corner_uv[index]).all()
                    and not corner_valid[index].any(), "Outside witness must preserve -1/NaN/false sentinels")
            reasons.append("outside_image")
            continue
        left, top = math.floor(x), math.floor(y)
        right, bottom = min(left + 1, width - 1), min(top + 1, height - 1)
        expected = np.asarray(((left, top), (right, top), (left, bottom), (right, bottom)), dtype=np.int64)
        require(np.array_equal(corners_xy[index], expected), "Witness corner order or origin geometry differs")
        dx, dy = float(x - left), float(y - top)
        weights = ((1 - dx) * (1 - dy), dx * (1 - dy), (1 - dx) * dy, dx * dy)
        active = [corner for corner, weight in enumerate(weights) if weight > 0]
        good = all(corner_valid[index, corner] and np.isfinite(corner_uv[index, corner]).all() for corner in active)
        supported[index] = good
        reasons.append("" if good else "invalid_contributor")
        if good:
            for channel in range(2):
                values[index, channel] = math.fsum(weights[corner] * float(corner_uv[index, corner, channel]) for corner in active)
    require(np.isfinite(values[supported]).all(), "Witness interpolation yielded a nonfinite retained vector")
    return values, supported, reasons


def rebuild_coverage(audit, windows, requests, links, features, rows):
    require(len(features) == len(requests) and len(rows) == len(windows), "Coverage must preserve all samples and windows")
    values = {row["sample_id"]: row for row in features}
    require(len(values) == len(features), "Feature rows contain duplicate IDs")
    valid_uses = eligible = 0
    for window, link, original in zip(windows, links, rows):
        samples = [values[sample_id] for sample_id in link["sample_ids"]]
        good19 = sum(boolean(row["valid"]) for row in samples)
        good5 = sum(boolean(row["valid"]) for row in samples[-5:])
        expected = {"window_id": window["window_id"], "video_id": window["video_id"],
            "track_id": window["track_id"], "segment_id": window["segment_id"],
            "origin_frame": integer(window["origin_frame"]), "sample_count": 19,
            "valid_history19": good19, "valid_last5": good5, "eligible_last5": good5 == 5}
        for key, value in expected.items():
            audit.equal(original[key], value, f"coverage {key}")
        for suffix, subset in (("history19", samples), ("last5", samples[-5:])):
            reasons = sorted(Counter(row["reason"] for row in subset if not boolean(row["valid"])).items())
            parsed = parse_json(original[f"invalid_reasons_{suffix}"].encode("utf-8"))
            audit.equal(parsed, dict(reasons), f"coverage reasons {suffix}")
        valid_uses += good19
        eligible += good5 == 5
    return {"historical_uses": len(windows) * 19, "valid_historical_uses": valid_uses,
            "invalid_historical_uses": len(windows) * 19 - valid_uses,
            "eligible_last5_windows": eligible, "ineligible_last5_windows": len(windows) - eligible}


def projection(plan, videos, elapsed_seconds):
    """Recompute the registered estimate from measured, disjoint cost scopes."""
    require(len(videos) == len(VIDEOS) and [row["video_id"] for row in videos] == list(VIDEOS), "Projection cohort differs")
    observed_variable = 0.0
    contributions = []
    for row in videos:
        source = plan["sources"][row["video_id"]]
        unique, windows = integer(row["unique_samples"]), integer(row["windows"])
        require(unique > 0 and windows > 0, "Zero denominator: no projection or gate is available")
        ratio_samples = integer(source["full_unique_samples"]) / unique
        loop_scale = max((integer(source["total_frames"]) - 1) / 59, ratio_samples)
        table_scale = max(integer(source["full_windows"]) / windows, ratio_samples,
                          integer(source["total_frames"]) / 60, (integer(source["total_frames"]) - 1) / 59)
        times = [number(row[key]) for key in ("loop_seconds", "table_seconds", "checkpoint_seconds")]
        require(min(times) >= 0, "Negative component timing")
        observed_variable += sum(times)
        projected = times[0] * loop_scale + times[1] * table_scale + times[2]
        storage = integer(row["compact_bytes"]) * table_scale + integer(row["checkpoint_bytes"])
        contributions.append({"video_id": row["video_id"], "loop_scale": loop_scale, "table_scale": table_scale,
            "variable_seconds": projected, "artifact_bytes": storage})
    elapsed = number(elapsed_seconds)
    require(elapsed >= observed_variable, "Recorded cost scopes exceed measured elapsed time")
    fixed = elapsed - observed_variable
    # Preserve the registered order of floating-point additions. No observed
    # projection term is trusted or used as a computational input.
    seconds = 2 * (fixed + sum(row["variable_seconds"] for row in contributions))
    size = 2 * sum(row["artifact_bytes"] for row in contributions) + 16 * 1024**2
    passed = seconds <= number(plan["projection"]["max_projected_seconds"]) and size <= number(plan["projection"]["max_projected_artifact_mb"]) * 1024**2
    return {"status": "provisional_within_budget" if passed else "exceeds_planning_budget",
            "fixed_seconds": fixed, "observed_variable_seconds": observed_variable,
            "safety_factor": 2.0, "metadata_reserve_mb": 16,
            "projected_seconds": seconds, "projected_artifact_bytes": size, "terms": contributions,
            "full_extraction_released": False, "full_rss_certified": False,
            "requires": "independent_qa_and_registered_full_operational_plan",
            "limitation": "prefix_density_and_motion_may_not_represent_full_videos"}


SMOKE_HASH = "fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98"
SMOKE_QA_HASH = "b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652"
COMPACT_FEATURE_FIELDS = REQUEST_FIELDS + ["u", "v", "valid", "reason"]
COMPACT_TABLES = ("selected_windows.csv", "requests.csv", "links.csv", "witnesses.npz",
    "frame_index.json", "pair_index.json", "features.csv", "window_coverage.csv",
    "checkpoint_metrics.csv", "summary.json")


def authenticate_checkpoint(audit, path, record, identity, frame):
    expected_identity = {key: value for key, value in identity.items() if key != "schema_version"}
    expected_identity.update(frame_from=frame, frame_to=frame + 1)
    expected = {"path": f"{frame:06d}_{frame + 1:06d}.npz", "sha256": sha(record["sha256"]), **expected_identity}
    audit.equal(record, expected, "checkpoint index identity")
    require(frame in (0, 58), "Dense checkpoint outside prospectively fixed pairs")
    with np.load(io.BytesIO(audit.read(path, record["sha256"])), allow_pickle=False) as archive:
        names = {"metadata", "forward", "backward", "forward_valid", "backward_valid"}
        require(len(archive.files) == len(names) and set(archive.files) == names, "Checkpoint NPZ schema differs")
        metadata = archive["metadata"]
        require(metadata.dtype.kind == "U" and metadata.shape == (), "Checkpoint metadata must be Unicode scalar")
        audit.equal(parse_json(str(metadata.item()).encode()), {"schema_version": 1, **expected_identity}, "checkpoint metadata")
        arrays = [archive[name] for name in ("forward", "backward", "forward_valid", "backward_valid")]
    for field, valid in ((arrays[0], arrays[2]), (arrays[1], arrays[3])):
        require(field.dtype == np.float32 and field.shape == (identity["height"], identity["width"], 2), "Checkpoint field dtype/shape differs")
        require(valid.dtype == bool and valid.shape == field.shape[:2], "Checkpoint validity dtype/shape differs")
        require(np.isfinite(field[valid]).all(), "Checkpoint marks nonfinite vectors as valid")
        audit.directional_field_pixels_validated += valid.size
    return arrays


def read_witness(audit, folder, identity, requests):
    path = folder / "witnesses.npz"
    with np.load(io.BytesIO(audit.read(path)), allow_pickle=False) as archive:
        names = {"metadata", "sample_ids", "points_xy", "corners_xy", "corner_uv", "corner_valid", "inside"}
        require(len(archive.files) == len(names) and set(archive.files) == names, "Witness NPZ schema differs")
        arrays = {name: archive[name] for name in archive.files}
    metadata = arrays.pop("metadata")
    require(metadata.dtype.kind == "U" and metadata.shape == (), "Witness metadata must be Unicode scalar")
    audit.equal(parse_json(str(metadata.item()).encode()), identity, "witness metadata")
    ids = arrays.pop("sample_ids")
    require(ids.dtype == np.dtype("U64") and ids.shape == (len(requests),), "Witness ID dtype or shape differs")
    audit.equal(ids.tolist(), [row["sample_id"] for row in requests], "witness request order")
    points = arrays["points_xy"]
    require(points.dtype == np.float64 and points.shape == (len(requests), 2), "Witness source points dtype/shape differs")
    for index, requested in enumerate(requests):
        audit.coordinate(points[index, 0], requested["cx"], "witness source-center x")
        audit.coordinate(points[index, 1], requested["cy"], "witness source-center y")
    rebuilt = independent_witness(points, arrays["corners_xy"], arrays["corner_uv"],
        arrays["corner_valid"], arrays["inside"], width=identity["width"], height=identity["height"])
    return arrays, rebuilt


def verify_video(audit, parent_folder, run, video, plan, estimator_hash, artifacts):
    folder = run / "by_video" / video
    source = plan["sources"][video]
    identity = {"schema_version": 1, "video_id": video, "source_sha256": source["sha256"],
                "estimator_hash": estimator_hash, "width": 640, "height": 480}
    windows, requests, links, history_uses, full_counts = reconstruct_requests(audit, parent_folder, folder, video)
    for key, value in full_counts.items():
        audit.equal(source[key], value, f"registered full-reference count {key}")
    witness_arrays, (vectors, valid, reasons) = read_witness(audit, folder, identity, requests)
    feature_rows = audit.rows(folder / "features.csv", COMPACT_FEATURE_FIELDS)
    require(len(feature_rows) == len(requests), "Features must preserve every unique request")
    for index, (row, request) in enumerate(zip(feature_rows, requests)):
        expected = {**request, "u": float(vectors[index, 0]) if valid[index] else None,
                    "v": float(vectors[index, 1]) if valid[index] else None,
                    "valid": bool(valid[index]), "reason": reasons[index]}
        for key, value in expected.items():
            if key in ("cx", "cy"):
                audit.coordinate(row[key], value, f"feature {index} {key}")
            else:
                audit.equal(row[key], value, f"feature {index} {key}")
    coverage = rebuild_coverage(audit, windows, requests, links, feature_rows,
        audit.rows(folder / "window_coverage.csv", COMPACT_COVERAGE_FIELDS))
    frame_index = audit.json(folder / "frame_index.json")
    require(set(frame_index) == set(identity) | {"backend", "frames", "last_frame_returned", "full_video_decoding_verified"}, "Frame index schema differs")
    for key, value in {**identity, "last_frame_returned": 59, "full_video_decoding_verified": False}.items():
        audit.equal(frame_index[key], value, f"frame index {key}")
    require(isinstance(frame_index["backend"], str) and frame_index["backend"], "Decoder backend missing")
    require(len(frame_index["frames"]) == 60, "Frame hash inventory is incomplete")
    frames = {}
    checkpoint_paths = set()
    for frame, row in enumerate(frame_index["frames"]):
        expected = {"frame_index": frame, "gray_sha256": sha(row["gray_sha256"])}
        if frame in (0, 1, 58, 59):
            path = folder / "frames" / f"{frame:06d}.npy"
            checkpoint_paths.add(path)
            require(audit.path(row["artifact"]["path"]) == path, "Saved gray artifact path differs")
            audit.equal(row["artifact"], artifacts[path], "saved gray artifact binding")
            expected["artifact"] = row["artifact"]
            gray = np.load(io.BytesIO(audit.reference(row["artifact"])), allow_pickle=False)
            require(gray.dtype == np.uint8 and gray.shape == (480, 640), "Gray checkpoint must be original uint8 image")
            audit.equal(hashlib.sha256(gray.tobytes(order="C")).hexdigest(), row["gray_sha256"], "raw grayscale hash")
            frames[frame] = gray
        audit.equal(row, expected, "frame hash inventory row")
    pair_index = audit.json(folder / "pair_index.json")
    require(set(pair_index) == set(identity) | {"pairs"}, "Pair index schema differs")
    for key, value in identity.items():
        audit.equal(pair_index[key], value, f"pair index {key}")
    require(len(pair_index["pairs"]) == 59, "Forward pair hash inventory incomplete")
    metrics = audit.rows(folder / "checkpoint_metrics.csv", ["video_id", "frame_from", "frame_to", *PHOTO_FB_FIELDS])
    require(len(metrics) == 2, "Exactly two checkpoint diagnostics per video are required")
    checkpoint_sample_count = 0
    for frame, row in enumerate(pair_index["pairs"]):
        expected = {"frame_from": frame, "frame_to": frame + 1, "forward_sha256": sha(row["forward_sha256"])}
        if frame in (0, 58):
            path = folder / "checkpoints" / f"{frame:06d}_{frame + 1:06d}.npz"
            checkpoint_paths.add(path)
            expected["checkpoint"] = row["checkpoint"]
            forward, backward, fv, bv = authenticate_checkpoint(audit, path, row["checkpoint"], identity, frame)
            raw_hash = hashlib.sha256(forward.tobytes(order="C") + fv.tobytes(order="C")).hexdigest()
            audit.equal(row["forward_sha256"], raw_hash, "checkpoint raw forward hash")
            actual_metrics = metrics[0 if frame == 0 else 1]
            rebuilt = diagnostics(frames[frame], frames[frame + 1], forward, backward, fv, bv)
            audit.equal(actual_metrics, {"video_id": video, "frame_from": frame, "frame_to": frame + 1, **rebuilt}, "checkpoint diagnostic metrics")
            audit.pair_pixels_diagnosed += 480 * 640
            selected = np.asarray([i for i, requested in enumerate(requests) if requested["frame_from"] == frame], dtype=np.int64)
            for index in selected:
                if not witness_arrays["inside"][index]:
                    continue
                points = witness_arrays["corners_xy"][index]
                expected_uv = forward[points[:, 1], points[:, 0]]
                expected_valid = fv[points[:, 1], points[:, 0]]
                require(np.array_equal(witness_arrays["corner_uv"][index].view(np.uint32), expected_uv.view(np.uint32)), "Checkpoint witness corner vectors differ bitwise from dense field")
                require(np.array_equal(witness_arrays["corner_valid"][index], expected_valid), "Checkpoint witness corner validity differs")
            if len(selected):
                independently_sampled, supported = independent_sample(forward, fv, witness_arrays["points_xy"][selected])
                require(np.array_equal(supported, valid[selected]), "Checkpoint witness validity differs from dense interpolation")
                for local, index in enumerate(selected):
                    if supported[local]:
                        for channel in range(2):
                            audit.near(vectors[index, channel], independently_sampled[local, channel], "checkpoint dense-versus-witness sample")
            checkpoint_sample_count += len(selected)
        audit.equal(row, expected, "forward pair hash inventory row")
    summary = audit.json(folder / "summary.json")
    expected_keys = {"video_id", "frames", "forward_fields", "backward_fields", "windows", "unique_samples",
        "historical_uses", "valid_samples", "eligible_last5_windows", "loop_seconds", "checkpoint_seconds",
        "table_seconds", "checkpoint_bytes", "compact_bytes"}
    require(set(summary) == expected_keys, "Video summary schema differs")
    checkpoint_bytes = sum(integer(artifacts[path]["bytes"]) for path in checkpoint_paths)
    compact_paths = {path for path in artifacts if path.parent == folder and path.name != "summary.json"}
    compact_bytes = sum(integer(artifacts[path]["bytes"]) for path in compact_paths)
    rebuilt_summary = {"video_id": video, "frames": 60, "forward_fields": 59, "backward_fields": 2,
        "windows": len(windows), "unique_samples": len(requests), "historical_uses": len(windows) * 19,
        "valid_samples": int(valid.sum()), "eligible_last5_windows": coverage["eligible_last5_windows"],
        "checkpoint_bytes": checkpoint_bytes, "compact_bytes": compact_bytes}
    for key, value in rebuilt_summary.items():
        audit.equal(summary[key], value, f"video summary {key}")
    for name in ("loop_seconds", "checkpoint_seconds", "table_seconds"):
        require(number(summary[name]) >= 0, "Negative measured cost scope")
    return summary, {"video_id": video, **coverage, "invalid_unique_samples": len(valid) - int(valid.sum()),
                    "checkpoint_samples_compared_to_dense_fields": checkpoint_sample_count,
                    "historical_coordinate_uses_reconstructed": history_uses,
                    "witness_corners_verified": len(requests) * 4}


def verify(manifest_path, audit):
    manifest_path = Path(manifest_path).resolve()
    run = manifest_path.parent
    require(manifest_path.name == "manifest.json" and run.is_relative_to(audit.root / "data/tests/flow/farneback")
            and run.parent.name == "benchmark", "Expected the manifest of one compact Farneback benchmark")
    audit.allow((manifest_path,))
    manifest = audit.json(manifest_path)
    for key, expected in {"status": "complete", "module": "flow", "method": "farneback", "algorithm": "farneback",
                          "stage": "benchmark", "seed": 42, "git_dirty": False, "storage_class": "tests", "run_id": run.name}.items():
        audit.equal(manifest[key], expected, f"run {key}")
    require(manifest["git_dirty"] is False, "Scientific run must record clean Git")
    plan = manifest["config"]
    require(digest(plan) == PLAN_HASH and manifest["config_hash"] == PLAN_HASH[:12], "Resolved benchmark plan was not prospectively registered")
    audit.equal(plan["protocol"]["video_ids"], list(VIDEOS), "registered training cohort")
    require(re.fullmatch(r"[0-9a-f]{7,40}", manifest["git_sha"]) is not None, "Invalid scientific commit")
    sha(manifest["source_hash"])
    capture = manifest["provenance_capture"]
    require(capture["mode"] == "shared_batch" and capture["per_candidate_recheck"] is False, "Missing shared provenance snapshot")
    expected_snapshot = digest({"repo_root": str(audit.root), "captured_at": capture["captured_at"],
        "process_id": capture["process_id"], "git_sha": manifest["git_sha"], "git_dirty": False,
        "source_hash": manifest["source_hash"], "environment": manifest["environment"]})
    audit.equal(capture["snapshot_sha256"], expected_snapshot, "snapshot digest")
    require(audit.path(capture["origin_batch_manifest"]) == manifest_path, "Snapshot origin differs")
    recheck = manifest["repository_recheck"]
    require(recheck["status"] == "verified" and recheck["scope"] == "compact_benchmark_end_before_certification", "Missing final repository recheck")
    audit.equal(recheck["snapshot_sha256"], expected_snapshot, "rechecked snapshot digest")
    audit.equal(recheck["checks"], ["git_sha", "git_dirty", "source_hash", "environment"], "repository check fields")
    timestamps = [datetime.fromisoformat(value) for value in (capture["captured_at"], manifest["started_at"],
                  recheck["checked_at"], manifest["finished_at"])]
    require(all(value.tzinfo is not None for value in timestamps) and timestamps == sorted(timestamps), "Invalid provenance chronology")
    require(f"__{manifest['git_sha']}__cfg{PLAN_HASH[:12]}__src{manifest['source_hash'][:10]}__s42" in run.name, "Run path does not bind code/configuration")
    expected_artifacts = {run / "summary.json"}
    for video in VIDEOS:
        folder = run / "by_video" / video
        expected_artifacts.update(folder / name for name in COMPACT_TABLES)
        expected_artifacts.update(folder / "frames" / f"{frame:06d}.npy" for frame in (0, 1, 58, 59))
        expected_artifacts.update(folder / "checkpoints" / f"{frame:06d}_{frame + 1:06d}.npz" for frame in (0, 58))
    artifacts = reference_map(audit, manifest["artifacts"], expected_artifacts, "compact benchmark artifacts")
    require({path.resolve() for path in run.rglob("*") if path.is_file()} == expected_artifacts | {manifest_path}, "Missing or unindexed file in immutable run")
    metadata_paths = [audit.root / "configs/flow/farneback/compact_benchmark_v1.yaml", audit.root / "configs/protocol/splits.yaml",
                      audit.path(plan["causal_smoke"]["manifest"]), audit.path(plan["causal_smoke"]["verification"])]
    metadata = reference_map(audit, manifest["metadata"], metadata_paths, "compact benchmark metadata")
    audit.equal(metadata[metadata_paths[1]]["sha256"], plan["protocol"]["splits_sha256"], "split hash")
    for index, registered, expected_hash in ((2, "manifest_sha256", SMOKE_HASH), (3, "verification_sha256", SMOKE_QA_HASH)):
        audit.equal(plan["causal_smoke"][registered], expected_hash, "registered causal smoke binding")
        audit.equal(metadata[metadata_paths[index]]["sha256"], expected_hash, "authenticated causal smoke binding")
    smoke, smoke_qa = audit.json(metadata_paths[2]), audit.json(metadata_paths[3])
    require(smoke["status"] == "complete" and smoke_qa["status"] == "passed", "Pinned causal smoke was not complete and audited")
    audit.equal(smoke_qa["run_manifest_sha256"], SMOKE_HASH, "smoke QA manifest binding")
    require(audit.path(smoke_qa["run_manifest"]) == metadata_paths[2], "Smoke QA identifies another run")
    sources = [{"path": plan["sources"][video]["path"], "sha256": plan["sources"][video]["sha256"],
                "bytes": plan["sources"][video]["bytes"]} for video in VIDEOS]
    # Never resolve/stat/open/hash source paths here. These are recorded identities.
    audit.equal(manifest["source_videos"], sources, "declared source video identities")
    parent_folder, _ = read_parent(audit, plan, manifest)
    estimator_hash = digest({"method": "farneback", "params": plan["params"], "input": plan["flow"]["input"], "mask": "none"})
    audit.equal(manifest["runtime_settings"], {"opencv_threads": 1, "opencl": False, "rng_seed": 42,
                                             "estimator_hash": estimator_hash}, "runtime settings")
    videos, coverage_reports = [], []
    for video in VIDEOS:
        result, coverage = verify_video(audit, parent_folder, run, video, plan, estimator_hash, artifacts)
        videos.append(result)
        coverage_reports.append(coverage)
        print(f"Verified video {video}: 60 frame hashes, 59 pair hashes, {result['unique_samples']} independent witness samples", flush=True)
    recorded = audit.json(run / "summary.json")
    measured_elapsed = number(recorded["projection_elapsed_seconds"])
    require(0 < measured_elapsed <= number(manifest["elapsed_seconds"]), "Projection timing is outside the recorded run")
    cost_projection = projection(plan, videos, measured_elapsed)
    summary = {"status": "complete_compact_engineering_benchmark", "video_ids": list(VIDEOS), "videos": videos,
        **{key: sum(video[key] for video in videos) for key in ("frames", "forward_fields", "backward_fields", "windows",
            "unique_samples", "historical_uses", "valid_samples", "eligible_last5_windows")},
        "projection_elapsed_seconds": measured_elapsed, "projection": cost_projection,
        **{key: False for key in ("prediction_evaluated", "hypothesis_evaluated", "parameters_selected",
            "validation_test_sources_read", "physical_fluid_velocity_measured", "full_extraction_released")}}
    audit.equal(recorded, summary, "rebuilt root summary")
    audit.equal(manifest["summary"], summary, "manifest summary")
    require((summary["frames"], summary["forward_fields"], summary["backward_fields"]) == (720, 708, 24), "Incomplete benchmark universe")
    resources = manifest["resources"]
    require(0 < number(resources["ram_rss_peak_mb"]) <= 2048 and 0 < number(manifest["elapsed_seconds"]) <= 900, "Registered runtime resource limits exceeded")
    artifact_bytes = sum(integer(record["bytes"]) for record in artifacts.values())
    total_bytes = artifact_bytes + audit.files[str(manifest_path)]["bytes"]
    require(artifact_bytes <= integer(resources["artifact_bytes_before_final_manifest"]) <= 512 * 1024**2
            and total_bytes <= 512 * 1024**2, "Registered artifact budget exceeded")
    for record in list(audit.files.values()):
        audit.reference(record)
    return {"status": "passed", "run_manifest": str(manifest_path),
        "run_manifest_sha256": audit.files[str(manifest_path)]["sha256"], "plan_hash": PLAN_HASH,
        "parent_manifest_sha256": PARENT_HASH, "parent_verification_sha256": PARENT_QA_HASH,
        "git_sha_of_verified_run": manifest["git_sha"], "source_hash_of_verified_run": manifest["source_hash"],
        "shared_snapshot_sha256": expected_snapshot, "video_ids": list(VIDEOS),
        "frame_hash_records_verified": 720, "saved_gray_frames_verified": 48,
        "forward_hash_records_verified": 708, "dense_pair_archives_verified": 24,
        "saved_directional_fields_verified": 48, "unique_samples_rebuilt": summary["unique_samples"],
        "windows_rebuilt": summary["windows"], "historical_uses_rebuilt": summary["historical_uses"],
        "coverage_reports": coverage_reports, "all_witness_interpolations_reconstructed": True,
        "sampling_at_source_history_center_confirmed": True, "coordinates_compared_as_exact_binary_floats": True,
        "new_artifacts_verified": len(artifacts), "new_run_bytes_including_manifest": total_bytes,
        "summary_rebuilt": summary, "recorded_resources": resources,
        "recorded_elapsed_seconds": manifest["elapsed_seconds"],
        "limitations": [
            "No MP4, original annotation, validation/test source, project implementation or estimator was opened/imported/executed.",
            "All compact samples were reconstructed from stored corner witnesses. Only the two registered dense checkpoints per video independently bind those corners to saved full fields; noncheckpoint corner provenance relies on the registered producer.",
            "The 720 gray and 708 forward raw hashes are inventories; only 48 saved gray arrays and 24 saved forward/backward archives can be independently rehashed from retained arrays. Unsaved arrays cannot be reconstructed from their hashes.",
            "Correspondence of saved gray arrays to source decoding and equality of saved fields to Farneback output remain producer evidence. This verifier does not rerun the decoder or estimator.",
            "All selected histories, source coordinates, deduplicated identities, ordered links and last-five eligibility are reconstructed from the pinned reference. Future completeness remains inherited offline eligibility.",
            "Absolute tolerance is 1e-9, relative tolerance zero. Counts, identifiers, hashes and source coordinates are exact; checkpoint corner float32 values are compared bitwise.",
            "Git state, environment, decoder sequence, measured timing and sampled RSS are recorded historical evidence. A prefix cost projection cannot certify whole-video density, runtime or peak memory, and never authorizes a full extraction.",
            "This engineering benchmark does not evaluate ADE/FDE, prediction improvement, physical fluid velocity, statistical superiority or independent generalization."]}


def self_test():
    points = np.array([[0.25, 0.75], [0., 0.], [1e-12, 1e-12], [-1e-12, 0.]], dtype=np.float64)
    corners = np.tile(np.array([[0, 0], [1, 0], [0, 1], [1, 1]], dtype=np.int64), (4, 1, 1))
    fields = np.tile(np.array([[2, 3], [4, 2], [5, 7], [7, 6]], dtype=np.float32), (4, 1, 1))
    valid = np.ones((4, 4), dtype=bool)
    fields[1:3, 3] = np.nan
    valid[1:3, 3] = False
    corners[3], fields[3], valid[3] = -1, np.nan, False
    values, supported, reasons = independent_witness(points, corners, fields, valid,
        np.array([True, True, True, False]), width=2, height=2)
    require(supported.tolist() == [True, True, False, False], "Synthetic witness support differs")
    require(values[:2].tolist() == [[4.75, 5.75], [2.0, 3.0]], "Synthetic affine/zero-weight interpolation differs")
    require(reasons == ["", "", "invalid_contributor", "outside_image"], "Synthetic missing-value reasons differ")
    audit = Audit()
    for operation in (lambda: audit.path("data/sources/forbidden.json"),
                      lambda: audit.read("data/derived/unregistered.json"),
                      lambda: parse_json(b'{"x":1,"x":2}'),
                      lambda: audit.near(1e8 + 1e-6, 1e8, "no relative tolerance"),
                      lambda: audit.coordinate(1 + 1e-15, 1, "exact coordinate")):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise ValueError("Synthetic negative audit guard accepted invalid input")
    return {"status": "passed", "mode": "synthetic_self_test", "experiment_artifacts_read": False,
            "checks": ["analytic witness interpolation", "strict positive-weight support", "zero-weight NaN",
                       "float64 bounds", "explicit invalid reasons", "forbidden source reads", "duplicate JSON",
                       "absolute-only tolerance", "exact coordinates"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="One immutable compact benchmark manifest.json")
    parser.add_argument("--output", help="Exclusive new JSON outside the immutable run, in its parent folder")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        require(args.manifest is None and args.output is None, "Self-test does not accept scientific paths")
        print(json.dumps(self_test()), flush=True)
        return 0
    require(args.manifest and args.output, "Explicit --manifest and --output are required")
    manifest_path, output = Path(args.manifest).resolve(), Path(args.output).resolve()
    run = manifest_path.parent
    require(manifest_path.name == "manifest.json" and run.is_relative_to(ROOT / "data/tests/flow/farneback")
            and run.parent.name == "benchmark" and output.parent == run.parent
            and output.suffix == ".json" and output.parent.is_dir(), "Output must be an exclusive new JSON sibling of the immutable benchmark")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        start, audit = time.perf_counter(), Audit()
        try:
            report, code = verify(manifest_path, audit), 0
        except Exception as exc:
            report, code = {"status": "failed", "requested_manifest": str(manifest_path),
                            "error_type": type(exc).__name__, "error": str(exc)}, 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter() - start,
            files_verified=len(audit.files), input_files=list(audit.files.values()), comparisons=audit.comparisons,
            numeric_comparisons=audit.numeric_comparisons, coordinate_comparisons=audit.coordinate_comparisons,
            max_absolute_difference=audit.max_absolute_difference, max_difference_label=audit.max_difference_label,
            pair_pixels_diagnosed=audit.pair_pixels_diagnosed,
            directional_field_pixels_validated=audit.directional_field_pixels_validated,
            comparison_rules={"absolute_tolerance": TOLERANCE, "relative_tolerance": 0.0,
                "coordinates": "exact binary64", "counts_keys_hashes": "exact", "checkpoint_corner_values": "bitwise float32"},
            project_implementation_imported=False, original_sources_opened=False, estimator_reexecuted=False,
            verifier_path=str(Path(__file__).resolve()), verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            runtime={"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()})
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files),
                      "numeric_comparisons": audit.numeric_comparisons}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
