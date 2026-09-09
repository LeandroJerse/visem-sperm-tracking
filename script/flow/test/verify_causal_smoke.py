"""Independent audit of the registered causal Farneback smoke derivatives.

Only this standalone module, the standard library, NumPy and SciPy are used.
No project implementation is imported; no source MP4 or original annotation
is opened. The decoder and Farneback are not rerun. Interpolation is rebuilt
with SciPy, separately checking each positive-weight contributing corner.
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
PLAN_HASH = "f7e0afa345b3774127bb622a03ab21d1100dd9655dbd7bb0c6c3eaaa4f13708f"
PARENT_HASH = "88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35"
PARENT_QA_HASH = "f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9"
VIDEOS = ("11", "12")
TOLERANCE = 1e-9
WINDOW_FIELDS = "window_id video_id track_id segment_id split history_start origin_frame future_end history_length forecast_horizon".split()
HISTORY_FIELDS = "window_id video_id track_id segment_id origin_frame frame_index cx cy".split()
FEATURE_FIELDS = "window_id video_id track_id segment_id origin_frame frame_from frame_to available_at sample_x sample_y u v valid invalid_reason pair_sha256".split()
COVERAGE_FIELDS = "window_id video_id origin_frame track_id segment_id expected_samples valid_samples invalid_samples all_history_flow_valid".split()
PHOTO_FB_FIELDS = "photometric_warp_mae photometric_zero_mae photometric_valid_pixels photometric_valid_fraction forward_backward_mae consistent_fraction forward_backward_valid_pixels forward_backward_valid_fraction flow_finite_valid_fraction".split()
TEMPORAL_FIELDS = "advected_temporal_mean_change advected_temporal_p95_change advected_temporal_valid_pixels advected_temporal_valid_fraction".split()
PAIR_FIELDS = "video_id frame_from frame_to estimate_seconds diagnostics_seconds".split() + PHOTO_FB_FIELDS
TRIO_FIELDS = "video_id first_frame middle_frame last_frame".split() + TEMPORAL_FIELDS
IDENTITY_KEYS = {"video_id", "frame_from", "frame_to", "source_sha256", "estimator_hash", "width", "height"}
VIDEO_TABLES = ("selected_windows.csv", "histories.csv", "frames.json", "pair_index.json",
                "features.csv", "window_coverage.csv", "pair_metrics.csv", "temporal_metrics.csv", "summary.json")


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
    require(type(value) is bool or value in ("True", "False"), "Invalid Boolean")
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


def mean(values):
    return math.fsum(values) / len(values) if len(values) else None


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
        self.temporal_pixels_diagnosed = 0
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


def temporal(first, following, first_valid, following_valid):
    yy, xx = np.indices(first_valid.shape, dtype=np.float64)
    points = np.column_stack((xx.ravel(), yy.ravel())) + first.reshape(-1, 2).astype(np.float64)
    sampled, good = independent_sample(following, following_valid, points)
    good &= first_valid.ravel()
    count = int(good.sum())
    first_points = first.reshape(-1, 2)[good].astype(np.float64)
    differences = np.hypot(sampled[good, 0] - first_points[:, 0], sampled[good, 1] - first_points[:, 1])
    if count:
        # Explicit linear quantile formula, independent of np.percentile.
        ordered = np.sort(differences)
        fractional_rank = (count - 1) * 0.95
        lower, upper = math.floor(fractional_rank), math.ceil(fractional_rank)
        p95 = float(ordered[lower] + (ordered[upper] - ordered[lower]) * (fractional_rank - lower))
    else:
        p95 = None
    return {
        "advected_temporal_mean_change": float(np.mean(differences, dtype=np.float64)) if count else None,
        "advected_temporal_p95_change": p95,
        "advected_temporal_valid_pixels": count,
        "advected_temporal_valid_fraction": count / first_valid.size,
    }


def authenticate_pair(audit, path, record, video, frame, source, estimator_hash):
    identity = {"video_id": video, "frame_from": frame, "frame_to": frame + 1,
                "source_sha256": source["sha256"], "estimator_hash": estimator_hash, "width": 640, "height": 480}
    expected = {"path": f"{frame:06d}_{frame + 1:06d}.npz", "sha256": sha(record["sha256"]), **identity}
    audit.equal(record, expected, "pair index row")
    require(type(record["frame_from"]) is int and type(record["frame_to"]) is int and frame + 1 <= 19,
            "Pair is not available at origin19")
    with np.load(io.BytesIO(audit.read(path, record["sha256"])), allow_pickle=False) as stored:
        names = {"metadata", "forward", "backward", "forward_valid", "backward_valid"}
        require(len(stored.files) == len(names) and set(stored.files) == names, "Unexpected NPZ array set")
        metadata = stored["metadata"]
        require(metadata.dtype.kind == "U" and metadata.shape == (), "NPZ metadata must be Unicode scalar")
        parsed = parse_json(str(metadata.item()).encode("utf-8"))
        require(type(parsed.get("schema_version")) is int and parsed["schema_version"] == 1, "NPZ version mismatch")
        audit.equal(parsed, {"schema_version": 1, **identity}, "NPZ metadata")
        arrays = [stored[name] for name in ("forward", "backward", "forward_valid", "backward_valid")]
    forward, backward, fv, bv = arrays
    for name, field, valid in (("forward", forward, fv), ("backward", backward, bv)):
        require(field.dtype == np.float32 and field.shape == (480, 640, 2), f"Invalid raw {name} dtype/shape")
        require(valid.dtype == bool and valid.shape == (480, 640), f"Invalid raw {name} validity")
        require(np.isfinite(field[valid]).all(), f"Nonfinite {name} vector declared valid")
        audit.directional_field_pixels_validated += valid.size
    return forward, backward, fv, bv


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


def reconstruct_histories(audit, parent_folder, folder, video):
    windows = audit.rows(parent_folder / "by_video" / video / "windows.csv", WINDOW_FIELDS)
    selected = [row for row in windows if integer(row["history_start"]) == 0 and integer(row["origin_frame"]) == 19]
    require(selected and len({row["window_id"] for row in selected}) == len(selected), "No unique fixed-origin cohort")
    exported = audit.rows(folder / "selected_windows.csv", WINDOW_FIELDS)
    audit.equal(exported, selected, "complete selected window sequence")
    for row in selected:
        for key, value in {"video_id": video, "split": "train", "history_start": 0, "origin_frame": 19,
                           "future_end": 29, "history_length": 20, "forecast_horizon": 10}.items():
            audit.equal(row[key], value, f"window {key}")
    selected_keys = {(row["track_id"], row["segment_id"]) for row in selected}
    positions = {}
    for row in audit.rows(parent_folder / "by_video" / video / "observations.csv"):
        frame = integer(row["frame_index"])
        key = (row["track_id"], row["segment_id"])
        if frame > 19 or key not in selected_keys:
            continue
        require(row["video_id"] == video and row["annotated"] == "True" and row["class_id"] in ("0", "2"),
                "Invalid selected individual observation")
        full_key = (*key, frame)
        require(full_key not in positions, "Duplicate parent historical observation")
        positions[full_key] = (number(row["cx"]), number(row["cy"]))
    histories = audit.rows(folder / "histories.csv", HISTORY_FIELDS)
    require(len(histories) == len(selected) * 20, "Missing/excess history rows")
    tensors = np.empty((len(selected), 20, 2), dtype=np.float64)
    for index, row in enumerate(selected):
        for frame in range(20):
            xy = positions[(row["track_id"], row["segment_id"], frame)]
            exported_row = histories[index * 20 + frame]
            expected = {"window_id": row["window_id"], "video_id": video, "track_id": row["track_id"],
                        "segment_id": row["segment_id"], "origin_frame": 19, "frame_index": frame}
            for key, value in expected.items():
                audit.equal(exported_row[key], value, f"history {key}")
            audit.coordinate(exported_row["cx"], xy[0], "history cx")
            audit.coordinate(exported_row["cy"], xy[1], "history cy")
            tensors[index, frame] = xy
    return selected, tensors


def verify_video(audit, parent_folder, run, video, plan, estimator_hash):
    folder, source = run / "by_video" / video, plan["sources"][video]
    selected, histories = reconstruct_histories(audit, parent_folder, folder, video)
    frame_index = audit.json(folder / "frames.json")
    require(set(frame_index) == {"schema_version", "source_sha256", "width", "height", "fps", "backend", "frames",
                                "frames_requested", "last_frame_returned", "full_video_decoding_verified", "video_id"},
            "Unexpected decoded-frame index schema")
    for key, value in {"schema_version": 1, "video_id": video, "source_sha256": source["sha256"],
        "width": 640, "height": 480, "fps": 49.0, "frames_requested": 20, "last_frame_returned": 19,
        "full_video_decoding_verified": False}.items():
        audit.equal(frame_index[key], value, f"frame index {key}")
    require(isinstance(frame_index["backend"], str) and frame_index["backend"], "Missing decoder backend")
    require(len(frame_index["frames"]) == 20, "Decoded prefix is incomplete")
    frames = []
    for frame, row in enumerate(frame_index["frames"]):
        expected = {"frame_index": frame, "path": f"{frame:06d}.npy", "sha256": sha(row["sha256"]),
                    "bytes": integer(row["bytes"]), "decoded_position_after_read": float(frame + 1)}
        audit.equal(row, expected, "decoded frame row")
        gray = np.load(io.BytesIO(audit.read(folder / "frames" / expected["path"], row["sha256"], row["bytes"])), allow_pickle=False)
        require(gray.dtype == np.uint8 and gray.shape == (480, 640), "Unexpected grayscale NPY dtype/shape")
        frames.append(gray)
    index = audit.json(folder / "pair_index.json")
    expected_index = {"schema_version": 1, "video_id": video, "origin_frame": 19,
                      "source_sha256": source["sha256"], "estimator_hash": estimator_hash}
    require(set(index) == set(expected_index) | {"pairs"}, "Pair index schema differs")
    for key, value in expected_index.items():
        audit.equal(index[key], value, f"pair index {key}")
    require(len(index["pairs"]) == 19, "Incomplete pair universe")
    feature_rows = audit.rows(folder / "features.csv", FEATURE_FIELDS)
    pair_rows = audit.rows(folder / "pair_metrics.csv", PAIR_FIELDS)
    temporal_rows = audit.rows(folder / "temporal_metrics.csv", TRIO_FIELDS)
    require(len(feature_rows) == len(selected) * 19 and len(pair_rows) == 19 and len(temporal_rows) == 18,
            "Incomplete features or diagnostic rows")
    valid_counts, reasons = Counter(), Counter()
    rebuilt_pairs, rebuilt_temporal, previous_forward, previous_valid = [], [], None, None
    for frame, record in enumerate(index["pairs"]):
        forward, backward, fv, bv = authenticate_pair(audit, folder / "pairs" / f"{frame:06d}_{frame + 1:06d}.npz",
            record, video, frame, source, estimator_hash)
        rebuilt = diagnostics(frames[frame], frames[frame + 1], forward, backward, fv, bv)
        audit.pair_pixels_diagnosed += 480 * 640
        original = pair_rows[frame]
        for key, value in {"video_id": video, "frame_from": frame, "frame_to": frame + 1, **rebuilt}.items():
            audit.equal(original[key], value, f"video {video} pair {frame} {key}")
        require(number(original["estimate_seconds"]) >= 0 and number(original["diagnostics_seconds"]) >= 0,
                "Negative recorded timing")
        rebuilt_pairs.append(rebuilt)
        if previous_forward is not None:
            changed = temporal(previous_forward, forward, previous_valid, fv)
            audit.temporal_pixels_diagnosed += 480 * 640
            for key, value in {"video_id": video, "first_frame": frame - 1, "middle_frame": frame,
                               "last_frame": frame + 1, **changed}.items():
                audit.equal(temporal_rows[frame - 1][key], value, f"video {video} temporal {frame - 1} {key}")
            rebuilt_temporal.append(changed)
        sampled, supported = independent_sample(forward, fv, histories[:, frame])
        for window_index, window in enumerate(selected):
            original = feature_rows[frame * len(selected) + window_index]
            valid = bool(supported[window_index])
            x, y = map(float, histories[window_index, frame])
            reason = "" if valid else "outside_image" if not (0 <= x <= 639 and 0 <= y <= 479) else "invalid_support"
            expected = {"window_id": window["window_id"], "video_id": video, "track_id": window["track_id"],
                "segment_id": window["segment_id"], "origin_frame": 19, "frame_from": frame,
                "frame_to": frame + 1, "available_at": frame + 1, "valid": valid,
                "invalid_reason": reason, "pair_sha256": record["sha256"],
                "u": float(sampled[window_index, 0]) if valid else None,
                "v": float(sampled[window_index, 1]) if valid else None}
            for key, value in expected.items():
                audit.equal(original[key], value, f"video {video} feature {frame}/{window_index} {key}")
            audit.coordinate(original["sample_x"], x, "feature source-center x")
            audit.coordinate(original["sample_y"], y, "feature source-center y")
            valid_counts[window["window_id"]] += valid
            if not valid:
                reasons[reason] += 1
        previous_forward, previous_valid = forward, fv
    coverage = audit.rows(folder / "window_coverage.csv", COVERAGE_FIELDS)
    require(len(coverage) == len(selected), "Coverage dropped a window")
    for window, original in zip(selected, coverage):
        count = valid_counts[window["window_id"]]
        expected = {"window_id": window["window_id"], "video_id": video, "origin_frame": 19,
                    "track_id": window["track_id"], "segment_id": window["segment_id"],
                    "expected_samples": 19, "valid_samples": count, "invalid_samples": 19 - count,
                    "all_history_flow_valid": count == 19}
        audit.equal(original, expected, "window coverage")
    metrics = {}
    for rows, names in ((rebuilt_pairs, [key for key in PHOTO_FB_FIELDS if not key.endswith("_pixels")]),
                        (rebuilt_temporal, [key for key in TEMPORAL_FIELDS if not key.endswith("_pixels")])):
        for key in names:
            values = [row[key] for row in rows if row[key] is not None]
            metrics[key] = {"mean_equal_pairs_with_support": mean(values), "pairs_with_support": len(values), "total_pairs": len(rows)}
    valid = sum(valid_counts.values())
    summary = {"video_id": video, "split": "train", "origin_frame": 19, "decoded_frames": 20,
        "pairs": 19, "directional_fields": 38, "temporal_comparisons": 18,
        "selected_windows": len(selected), "feature_rows": len(feature_rows), "valid_feature_rows": valid,
        "invalid_feature_rows": len(feature_rows) - valid,
        "complete_valid_windows": sum(valid_counts[row["window_id"]] == 19 for row in selected),
        "invalid_reasons": dict(reasons), "metrics": metrics,
        "estimate_both_directions_seconds": math.fsum(number(row["estimate_seconds"]) for row in pair_rows),
        "diagnostics_seconds": math.fsum(number(row["diagnostics_seconds"]) for row in pair_rows),
        "interpretation": "causal_engineering_smoke_not_flow_accuracy_or_prediction_improvement"}
    audit.equal(audit.json(folder / "summary.json"), summary, f"video {video} summary")
    return summary


def verify(run, audit):
    run = Path(run).resolve()
    if run.name == "manifest.json":
        run = run.parent
    require(run.is_relative_to(audit.root / "data/tests/flow/farneback") and run.parent.name == "smoke",
            "Expected one selected Farneback smoke run")
    manifest_path = run / "manifest.json"
    audit.allow((manifest_path,))
    manifest = audit.json(manifest_path)
    for key, expected in {"status": "complete", "module": "flow", "method": "farneback", "algorithm": "farneback",
                          "stage": "smoke", "seed": 42, "git_dirty": False, "storage_class": "tests", "run_id": run.name}.items():
        audit.equal(manifest[key], expected, f"run {key}")
    require(manifest["git_dirty"] is False, "Scientific run did not have clean Git")
    plan = manifest["config"]
    require(digest(plan) == PLAN_HASH and manifest["config_hash"] == PLAN_HASH[:12], "Unregistered resolved smoke plan")
    require(re.fullmatch(r"[0-9a-f]{7,40}", manifest["git_sha"]) is not None, "Invalid scientific commit")
    sha(manifest["source_hash"])
    capture = manifest["provenance_capture"]
    require(capture["mode"] == "shared_batch" and capture["per_candidate_recheck"] is False,
            "Missing shared provenance capture")
    expected_snapshot = digest({"repo_root": str(audit.root), "captured_at": capture["captured_at"],
        "process_id": capture["process_id"], "git_sha": manifest["git_sha"], "git_dirty": False,
        "source_hash": manifest["source_hash"], "environment": manifest["environment"]})
    audit.equal(capture["snapshot_sha256"], expected_snapshot, "capture digest")
    require(audit.path(capture["origin_batch_manifest"]) == manifest_path, "Snapshot origin differs")
    recheck = manifest["repository_recheck"]
    require(recheck["status"] == "verified" and recheck["scope"] == "causal_smoke_end_before_certification",
            "Missing final repository check")
    audit.equal(recheck["snapshot_sha256"], expected_snapshot, "rechecked snapshot")
    audit.equal(recheck["checks"], ["git_sha", "git_dirty", "source_hash", "environment"], "repository checks")
    timestamps = [datetime.fromisoformat(value) for value in (capture["captured_at"], manifest["started_at"],
                  recheck["checked_at"], manifest["finished_at"])]
    require(all(value.tzinfo is not None for value in timestamps) and timestamps == sorted(timestamps), "Invalid provenance chronology")
    require(f"__{manifest['git_sha']}__cfg{PLAN_HASH[:12]}__src{manifest['source_hash'][:10]}__s42" in run.name,
            "Run directory does not bind recorded source/configuration")
    expected_artifacts = {run / "summary.json"}
    for video in VIDEOS:
        expected_artifacts.update(run / "by_video" / video / name for name in VIDEO_TABLES)
        expected_artifacts.update(run / "by_video" / video / "frames" / f"{frame:06d}.npy" for frame in range(20))
        expected_artifacts.update(run / "by_video" / video / "pairs" / f"{frame:06d}_{frame + 1:06d}.npz" for frame in range(19))
    artifacts = reference_map(audit, manifest["artifacts"], expected_artifacts, "smoke artifacts")
    require({path.resolve() for path in run.rglob("*") if path.is_file()} == expected_artifacts | {manifest_path},
            "Unindexed or missing file in immutable run")
    metadata_paths = [audit.root / "configs/flow/farneback/causal_smoke_v1.yaml", audit.root / "configs/protocol/splits.yaml"]
    meta = reference_map(audit, manifest["metadata"], metadata_paths, "smoke metadata")
    audit.equal(meta[metadata_paths[1]]["sha256"], plan["protocol"]["splits_sha256"], "split identity")
    sources = [{"path": plan["sources"][video]["path"], "sha256": plan["sources"][video]["sha256"],
                "bytes": plan["sources"][video]["bytes"]} for video in VIDEOS]
    # This comparison deliberately performs no stat/open/hash on original paths.
    audit.equal(manifest["source_videos"], sources, "declared original sources")
    parent_folder, _ = read_parent(audit, plan, manifest)
    estimator_hash = digest({"method": "farneback", "params": plan["params"], "input": plan["flow"]["input"], "mask": "none"})
    audit.equal(manifest["runtime_settings"], {"opencv_threads": 1, "opencl": False, "rng_seed": 42,
                                             "estimator_hash": estimator_hash}, "runtime settings")
    videos = []
    for video in VIDEOS:
        videos.append(verify_video(audit, parent_folder, run, video, plan, estimator_hash))
        print(f"Verified video {video}: 20 frames, 19 pairs, all historical features and diagnostics", flush=True)
    summary = {"status": "complete_causal_engineering_smoke", "video_ids": list(VIDEOS),
        **{key: sum(row[key] for row in videos) for key in ("decoded_frames", "pairs", "directional_fields", "selected_windows",
            "feature_rows", "valid_feature_rows", "invalid_feature_rows")}, "videos": videos,
        **{key: False for key in ("hypothesis_evaluated", "prediction_evaluated", "parameters_selected", "validation_test_sources_read",
                                  "future_images_returned_to_estimator", "physical_fluid_velocity_measured")}}
    audit.equal(manifest["summary"], summary, "manifest summary")
    audit.equal(audit.json(run / "summary.json"), summary, "root summary")
    require(summary["decoded_frames"] == 40 and summary["pairs"] == 38 and summary["directional_fields"] == 76,
            "Incomplete smoke totals")
    resources = manifest["resources"]
    require(0 < number(resources["ram_rss_peak_mb"]) <= 2048 and 0 < number(manifest["elapsed_seconds"]) <= 900,
            "Recorded resource/time limit violated")
    artifact_bytes = sum(row["bytes"] for row in artifacts.values())
    total_bytes = artifact_bytes + audit.files[str(manifest_path)]["bytes"]
    require(artifact_bytes <= integer(resources["artifact_bytes_before_final_manifest"]) <= 512 * 1024**2
            and total_bytes <= 512 * 1024**2, "Recorded artifact budget violated")
    # Reauthenticate the exact accepted byte identities after all reconstruction.
    for record in list(audit.files.values()):
        audit.reference(record)
    return {"status": "passed", "run_manifest": str(manifest_path),
        "run_manifest_sha256": audit.files[str(manifest_path)]["sha256"], "plan_hash": PLAN_HASH,
        "parent_manifest_sha256": PARENT_HASH, "parent_verification_sha256": PARENT_QA_HASH,
        "git_sha_of_verified_run": manifest["git_sha"], "source_hash_of_verified_run": manifest["source_hash"],
        "shared_snapshot_sha256": expected_snapshot, "video_ids": list(VIDEOS), "gray_frames_verified": 40,
        "pair_archives_verified": 38, "directional_fields_verified": 76, "temporal_comparisons_verified": 36,
        "selected_windows_rebuilt": summary["selected_windows"], "feature_rows_rebuilt": summary["feature_rows"],
        "invalid_features_preserved": summary["invalid_feature_rows"], "all_selected_windows_and_histories_reconstructed": True,
        "sampling_at_source_history_center_confirmed": True, "coordinates_compared_as_exact_binary_floats": True,
        "new_artifacts_verified": len(artifacts), "new_run_bytes_including_manifest": total_bytes,
        "summary_rebuilt": summary, "recorded_resources": resources, "recorded_elapsed_seconds": manifest["elapsed_seconds"],
        "limitations": [
            "No MP4, original annotation, validation/test source, project implementation or Farneback estimator was opened/imported/executed.",
            "Saved grayscale arrays and flow fields are authenticated derivatives. Their correspondence to decoded source pixels and their equality to Farneback output remain recorded producer evidence; this audit does not independently prove either.",
            "Source hashes are cross-checked as recorded identities between the pinned plan, parent contract and new indexes. Original source bytes are not independently rehashed here.",
            "All diagnostics use saved fields/images. SciPy interpolation, hypot and explicit linear quantiles are independent numerical formulations, with absolute tolerance1e-9 and no relative tolerance.",
            "History/frame identity and field availability are reconstructed. Equality to a causal formula does not prove every historical internal runtime access.",
            "Historical Git/environment checks, timing, decoder position and sampled RAM are recorded evidence, not a live reconstruction of past machine state or unsampled peaks.",
            "The cohort remains conditional on the parent's complete future eligibility. This engineering smoke does not measure prediction improvement, physical fluid velocity or independent generalization."]}


def self_test():
    yy, xx = np.indices((4, 5), dtype=np.float64)
    values = np.stack((2 * xx + 3 * yy, -xx + 4 * yy), axis=2)
    points = np.array([[0, 0], [4, 3], [1.123456789, 2.25], [4 + 1e-12, 1]], dtype=np.float64)
    sampled, good = independent_sample(values, np.ones((4, 5), dtype=bool), points)
    require(good.tolist() == [True, True, True, False], "Float64 bounds failed")
    require(np.allclose(sampled[:3, 0], 2 * points[:3, 0] + 3 * points[:3, 1], rtol=0, atol=1e-14), "Affine interpolation failed")
    corner = np.array([[1., 2.], [3., np.nan]])
    sampled, good = independent_sample(corner, np.array([[True, True], [True, False]]), np.array([[0, 0], [1e-10, 1e-10]]))
    require(good.tolist() == [True, False] and sampled[0] == 1 and np.isnan(sampled[1]), "Strict support/zero-weight corner failed")
    image = (xx * 5 + yy * 3).astype(np.uint8)
    translated = np.zeros_like(image)
    translated[:, 1:] = image[:, :-1]
    forward = np.zeros((*image.shape, 2), dtype=np.float32)
    forward[..., 0] = 1
    valid = np.ones(image.shape, dtype=bool)
    result = diagnostics(image, translated, forward, -forward, valid, valid)
    require(result["photometric_warp_mae"] == 0 and result["forward_backward_mae"] == 0
            and result["consistent_fraction"] == 1 and result["photometric_valid_pixels"] == 16, "Known translation failed")
    zero_expected = np.abs(image[:, :-1].astype(np.float64) - translated[:, :-1]).mean() / 255
    require(result["photometric_zero_mae"] == zero_expected, "Photometric support is not common")
    changed = forward.copy()
    changed[..., 0] = 3
    change = temporal(forward, changed, valid, valid)
    require(change["advected_temporal_mean_change"] == 2 and change["advected_temporal_p95_change"] == 2
            and change["advected_temporal_valid_pixels"] == 16, "Advected temporal change failed")
    empty = diagnostics(image, image, forward, -forward, np.zeros_like(valid), valid)
    require(empty["photometric_warp_mae"] is None and empty["forward_backward_mae"] is None
            and empty["consistent_fraction"] is None, "Empty support imputed as zero")
    audit = Audit()
    audit.near(1 + 5e-10, 1, "valid tolerance")
    for operation in (lambda: audit.near(1 + 2e-9, 1, "invalid tolerance"),
                      lambda: audit.coordinate(1 + 1e-15, 1, "exact coordinate"),
                      lambda: audit.path(ROOT / "data/sources/forbidden.json"),
                      lambda: audit.read(ROOT / "unregistered.json"),
                      lambda: parse_json(b'{"a":1,"a":2}')):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise ValueError("Negative synthetic guard accepted invalid input")
    return {"status": "passed", "mode": "synthetic_self_test", "experiment_artifacts_read": False,
            "checks": ["analytic affine interpolation", "float64 bounds", "positive-weight support", "zero-weight NaN",
                       "known translation orientation", "common photometric support", "advected temporal change",
                       "empty support", "absolute-only tolerance", "exact coordinates", "forbidden reads", "duplicate JSON"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="One immutable smoke directory or its manifest.json")
    parser.add_argument("--output", help="Exclusive new JSON beside the run, outside its immutable directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        require(args.run is None and args.output is None, "Self-test must not receive scientific paths")
        print(json.dumps(self_test()), flush=True)
        return 0
    require(args.run and args.output, "Explicit --run and --output are required")
    run = Path(args.run).resolve()
    if run.name == "manifest.json":
        run = run.parent
    output = Path(args.output).resolve()
    require(run.is_relative_to(ROOT / "data/tests/flow/farneback") and run.parent.name == "smoke"
            and output.parent == run.parent and output.suffix == ".json" and output.parent.is_dir(),
            "Output must be a new JSON sibling of the selected immutable smoke run")
    # Reserve output before any scientific reads: a failure receives its own
    # immutable report, and an existing report is never silently replaced.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        start, audit = time.perf_counter(), Audit()
        try:
            report, code = verify(run, audit), 0
        except Exception as exc:
            report, code = {"status": "failed", "requested_run": str(run), "error_type": type(exc).__name__, "error": str(exc)}, 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter() - start,
            files_verified=len(audit.files), input_files=list(audit.files.values()), comparisons=audit.comparisons,
            numeric_comparisons=audit.numeric_comparisons, coordinate_comparisons=audit.coordinate_comparisons,
            max_absolute_difference=audit.max_absolute_difference, max_difference_label=audit.max_difference_label,
            pair_pixels_diagnosed=audit.pair_pixels_diagnosed, temporal_pixels_diagnosed=audit.temporal_pixels_diagnosed,
            directional_field_pixels_validated=audit.directional_field_pixels_validated,
            comparison_rules={"absolute_tolerance": TOLERANCE, "relative_tolerance": 0.0,
                "coordinates": "exact binary64", "counts_keys_hashes": "exact", "metrics_features": "absolute difference <= 1e-9"},
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
