"""Independent, streaming audit of complete training prediction baselines.

Read only the explicitly selected new run and its pinned derived GT reference
(CSV/JSON). Never import src/script, open YAML, original labels, MP4 or images,
or rerun the scientific predictor. Rebuild both formulae using Python floats,
componentwise sorted medians, math.hypot and compensated aggregate sums.
The exclusive report must be a sibling of the immutable run. --self-test uses
only synthetic in-memory objects and reads no experiment artifacts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
from itertools import zip_longest
import io
import json
import math
from pathlib import Path
import platform
import re
import struct
import sys
import time
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "data/tests/prediction/baselines"
REFERENCE_ROOT = ROOT / "data/derived/prediction/ground_truth_individuals"
PLAN_HASH = "11aeec0be9f32f8905288c7118ce8b723180e7afb1ef8e7111d404a033e67ec9"
PARENT_HASH = "88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35"
QA_HASH = "f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
WINDOWS = dict(zip(TRAIN, (52223, 34093, 60406, 23315, 30574, 14944, 2922, 4058, 14582, 43998, 18802, 43859)))
COUNTS = {v: 1440 if v == "35" else 1500 if v == "82" else 1470 for v in TRAIN}
METHODS = ("persistence", "cv_median5")
REPORT_H = (1, 5, 10)
KEYS = "window_id video_id track_id segment_id split history_start origin_frame future_end".split()
METRICS = tuple(f"{name}_h{h}" for h in REPORT_H for name in ("ade", "fde"))
ALL_METRICS = METRICS + tuple(f"window_weighted_{name}" for name in METRICS)
PRED_FIELDS = KEYS + [f"{axis}_h{h}" for h in range(1, 11) for axis in ("cx", "cy")]
WINDOW_FIELDS = KEYS + ["history_length", "forecast_horizon"]
OBS_FIELDS = "video_id frame_index annotated track_id segment_id class_id cx cy w h x y".split()
SEG_FIELDS = "video_id track_id segment_id split start_frame end_frame observation_count start_reason end_reason end_boundary_frame".split()
TRACK_FIELDS = "video_id configuration_id track_id n_windows segments_with_windows".split() + list(METRICS)
ABS_TOL, REL_TOL = 1e-9, 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(type(value) is int or isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value),
            f"Invalid nonnegative integer: {value!r}")
    result = int(value)
    require(result >= 0, "Negative index/count")
    return result


def number(value):
    require(not isinstance(value, bool) and value not in (None, ""), f"Invalid number: {value!r}")
    result = float(value)
    require(math.isfinite(result), f"Nonfinite number: {value!r}")
    return result


def digest(value, *, ascii=True):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=ascii, allow_nan=False).encode()).hexdigest()


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Malformed SHA256")
    return value


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def lexical(value):
    """Normalize metadata references without resolving/opening their sources."""
    p = Path(value)
    return str(p if p.is_absolute() else ROOT / p).replace("/", "\\").rstrip("\\").casefold()


def recorded_ref(ref):
    require(set(ref) == {"path", "sha256", "bytes"}, "Unexpected recorded reference schema")
    require(isinstance(ref["path"], str) and ref["path"], "Missing reference path")
    return lexical(ref["path"]), sha(ref["sha256"]), integer(ref["bytes"])


def timestamp(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Timestamp lacks timezone")
    return result


class Audit:
    def __init__(self):
        self.files = {}
        self.comparisons = 0
        self.numeric_comparisons = 0
        self.max_absolute_difference = 0.0
        self.max_difference_label = None
        self.allowed = None

    def path(self, value):
        p = Path(value)
        p = (p if p.is_absolute() else ROOT / p).resolve()
        require((p.is_relative_to(RUN_ROOT) or p.is_relative_to(REFERENCE_ROOT))
                and p.suffix.lower() in (".csv", ".json"), f"Forbidden read path: {p}")
        require(self.allowed is None or p in self.allowed, f"Read outside selected run/reference: {p}")
        return p

    def hash(self, value, expected=None):
        p = self.path(value)
        before, h = p.stat(), hashlib.sha256()
        with p.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        after, actual = p.stat(), h.hexdigest()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Artifact changed while hashing")
        require(expected is None or actual == sha(expected), f"Hash mismatch: {p}")
        old = self.files.get(str(p))
        require(old is None or old["sha256"] == actual, f"Artifact changed since earlier read: {p}")
        self.files[str(p)] = {"path": str(p), "sha256": actual, "bytes": after.st_size,
            "mtime_ns": after.st_mtime_ns,
            "expected_hash_verified": expected is not None or bool(old and old["expected_hash_verified"])}
        return p

    def reference(self, ref):
        recorded_ref(ref)
        p = self.hash(ref["path"], ref["sha256"])
        self.equal(self.files[str(p)]["bytes"], ref["bytes"], "artifact byte count")
        return p

    def before_read(self, value):
        p = self.path(value)
        if str(p) not in self.files:
            self.hash(p)
        st, old = p.stat(), self.files[str(p)]
        require((st.st_size, st.st_mtime_ns) == (old["bytes"], old["mtime_ns"]), "Artifact changed before parsing")
        return p

    def json(self, value):
        p = self.before_read(value)
        with p.open("r", encoding="utf-8-sig") as stream:
            result = json.load(stream, object_pairs_hook=strict_object, parse_constant=bad_constant)
        self.before_read(p)
        return result

    def rows(self, value, fields=None):
        p = self.before_read(value)
        with p.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "Duplicate/empty CSV header")
            require(fields is None or reader.fieldnames == list(fields), f"Unexpected CSV columns: {p}")
            for row in reader:
                require(None not in row and all(v is not None for v in row.values()), f"Malformed CSV row: {p}")
                yield row
        self.before_read(p)

    def equal(self, actual, expected, label):
        self.comparisons += 1
        if isinstance(expected, dict):
            require(isinstance(actual, dict) and set(actual) == set(expected), f"{label}: mapping keys differ")
            for key, value in expected.items():
                self.equal(actual[key], value, f"{label}.{key}")
        elif isinstance(expected, (tuple, list)):
            require(isinstance(actual, (tuple, list)) and len(actual) == len(expected), f"{label}: sequence lengths differ")
            for i, value in enumerate(expected):
                self.equal(actual[i], value, f"{label}[{i}]")
        elif type(expected) is bool:
            require(type(actual) is bool and actual == expected, f"{label}: Boolean differs")
        elif isinstance(expected, int):
            require(integer(actual) == expected, f"{label}: count/index differs ({actual!r} != {expected!r})")
        elif isinstance(expected, float):
            self.near(actual, expected, label)
        else:
            require(actual == expected, f"{label}: value differs ({actual!r} != {expected!r})")

    def near(self, actual, expected, label):
        self.comparisons += 1
        self.numeric_comparisons += 1
        left, right = number(actual), number(expected)
        difference = abs(left - right)
        if difference > self.max_absolute_difference:
            self.max_absolute_difference, self.max_difference_label = difference, label
        require(math.isclose(left, right, rel_tol=REL_TOL, abs_tol=ABS_TOL),
                f"{label}: numerical difference {difference!r} ({left!r} != {right!r})")


class Sum:
    """Compensated streaming sum independent of the producer's NumPy batching."""
    def __init__(self):
        self.total, self.correction = 0.0, 0.0

    def add(self, value):
        new = self.total + value
        if abs(self.total) >= abs(value):
            self.correction += (self.total - new) + value
        else:
            self.correction += (value - new) + self.total
        self.total = new

    def value(self):
        return math.fsum((self.total, self.correction))


def predictions(history, method):
    require(len(history) == 20 and all(len(p) == 2 for p in history), "History must be exactly20x2")
    last = history[-1]
    if method == "persistence":
        velocity = (0.0, 0.0)
    else:
        require(method == "cv_median5", "Unknown method")
        velocity = tuple(sorted(history[j][axis] - history[j-1][axis]
                                for j in range(15, 20))[2] for axis in (0, 1))
    return [(last[0] + h * velocity[0], last[1] + h * velocity[1]) for h in range(1, 11)]


def errors(predicted, targets):
    require(len(predicted) == len(targets) == 10, "Dense ten-step predictions/targets required")
    distances = [math.hypot(p[0] - t[0], p[1] - t[1]) for p, t in zip(predicted, targets)]
    return {f"{name}_h{h}": math.fsum(distances[:h]) / h if name == "ade" else distances[h-1]
            for h in REPORT_H for name in ("ade", "fde")}


def aggregate(track_stats):
    tracks = []
    for identity in sorted(track_stats):
        item = track_stats[identity]
        require(item["count"] > 0, "Empty IDs cannot receive imputed metrics")
        tracks.append({"track_id": identity, "n_windows": item["count"],
            "segments_with_windows": len(item["segments"]),
            **{key: item["sums"][key].value() / item["count"] for key in METRICS}})
    require(tracks, "No evaluable original IDs")
    total = sum(row["n_windows"] for row in tracks)
    values = {key: math.fsum(row[key] for row in tracks) / len(tracks) for key in METRICS}
    values.update({f"window_weighted_{key}": math.fsum(item["sums"][key].value()
        for item in track_stats.values()) / total for key in METRICS})
    return tracks, values


def snapshot_check(audit, manifest, path):
    require(manifest.get("status") == "complete" and manifest.get("git_dirty") is False,
            "Run must be complete with a recorded clean Git state")
    audit.equal({k: manifest.get(k) for k in ("module", "method", "algorithm", "stage", "seed", "storage_class")},
        {"module": "prediction", "method": "prediction_baselines", "algorithm": "baselines",
         "stage": "development", "seed": 42, "storage_class": "tests"}, "run identity")
    require(digest(manifest["config"]) == PLAN_HASH and manifest["config_hash"] == PLAN_HASH[:12], "Pinned embedded plan hash differs")
    require(re.fullmatch(r"[0-9a-f]{7,40}", manifest["git_sha"]), "Malformed recorded commit")
    sha(manifest["source_hash"])
    require(path.parent.name == manifest["run_id"]
        and f"__{manifest['git_sha']}__cfg{PLAN_HASH[:12]}__src{manifest['source_hash'][:10]}__s42" in manifest["run_id"],
        "Run directory and provenance identity differ")
    capture = manifest["provenance_capture"]
    require(integer(capture["process_id"]) > 0, "Recorded process ID must be positive")
    audit.equal({k: capture.get(k) for k in ("mode", "per_candidate_recheck", "recheck_policy")},
        {"mode": "shared_batch", "per_candidate_recheck": False, "recheck_policy": "batch_end_before_ranking"}, "capture policy")
    require(audit.path(capture["origin_batch_manifest"]) == path, "Snapshot origin is another run")
    snapshot = digest({"repo_root": str(ROOT), "captured_at": capture["captured_at"],
        "process_id": capture["process_id"], "git_sha": manifest["git_sha"], "git_dirty": False,
        "source_hash": manifest["source_hash"], "environment": manifest["environment"]})
    audit.equal(capture["snapshot_sha256"], snapshot, "recorded snapshot hash")
    end = manifest["repository_recheck"]
    require(end["status"] == "verified" and end["snapshot_sha256"] == snapshot
        and end["scope"] == "baseline_end_before_comparison"
        and end["checks"] == ["git_sha", "git_dirty", "source_hash", "environment"], "Final repository verification missing")
    require(timestamp(capture["captured_at"]) <= timestamp(manifest["started_at"])
        <= timestamp(end["checked_at"]) <= timestamp(manifest["finished_at"]), "Invalid capture/run/recheck chronology")
    plan = manifest["config"]
    audit.equal(plan["protocol"]["video_ids"], list(map(int, TRAIN)), "registered cohort")
    audit.equal(plan["protocol"]["expected_windows"], WINDOWS, "registered window counts")
    audit.equal(plan["protocol"]["expected_total_windows"], 343776, "registered total windows")
    audit.equal(plan["models"], [
        {"configuration_id": "persistence", "method": "persistence", "params": {}},
        {"configuration_id": "cv_median5", "method": "constant_velocity", "params": {"window": 5, "method": "median"}}], "fixed methods/params")
    audit.equal(plan["evaluation"]["predicted_horizons"], list(range(1, 11)), "dense horizon axis")
    audit.equal(plan["evaluation"]["report_horizons"], list(REPORT_H), "reported horizons")
    metadata = manifest["metadata"]
    require(len(metadata) == 2, "Unexpected baseline prerequisite metadata count")
    require([recorded_ref(ref)[0] for ref in metadata] == [lexical(p) for p in
        ("configs/protocol/prediction_baselines_v1.yaml", "configs/protocol/splits.yaml")], "Recorded plan/split paths differ")
    require(metadata[1]["sha256"] == plan["protocol"]["splits_sha256"], "Recorded split hash differs")
    return snapshot


def pin_artifacts(audit, manifest, path, expected_names):
    refs = manifest["artifacts"]
    require(len(refs) == len(expected_names), "Wrong declared artifact count")
    result = {}
    for ref in refs:
        p = audit.path(ref["path"])
        require(p.is_relative_to(path.parent), "Artifact escapes its own run")
        name = p.relative_to(path.parent).as_posix()
        require(name in expected_names and name not in result, "Unknown/duplicate artifact")
        result[name] = audit.reference(ref)
    require(set(result) == expected_names, "Missing artifacts")
    found = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob("*") if p.is_file()}
    require(found == expected_names | {"manifest.json"}, "Undeclared/missing files in immutable run")
    return result


def reference_chain(audit, manifest):
    parent_ref = manifest["config"]["reference"]
    require(parent_ref["manifest_sha256"] == PARENT_HASH and parent_ref["verification_sha256"] == QA_HASH,
            "Pinned parent/QA identity differs")
    pp = audit.hash(parent_ref["manifest"], PARENT_HASH)
    qp = audit.hash(parent_ref["verification"], QA_HASH)
    require(pp.is_relative_to(REFERENCE_ROOT) and qp.parent == pp.parent.parent, "Parent/QA are outside canonical reference scope")
    parent, qa = audit.json(pp), audit.json(qp)
    require(parent["status"] == "complete" and parent["git_dirty"] is False and parent["method"] == "ground_truth_individuals",
            "Reference is not a complete clean preparation")
    require(qa["status"] == "passed" and qa["run_manifest_sha256"] == PARENT_HASH
            and audit.path(qa["run_manifest"]) == pp, "QA does not certify the pinned parent")
    require(qa["plan_hash"] == digest(parent["config"])
        and qa["git_sha_of_verified_run"] == parent["git_sha"]
        and qa["source_hash_of_verified_run"] == parent["source_hash"], "Parent QA provenance differs")
    require(qa["all_observations_segments_windows_compared"] is True
        and qa["original_sources_opened"] is False and qa["project_implementation_imported"] is False,
        "Parent independent audit scope differs")
    audit.equal(parent["summary"]["video_ids"], list(TRAIN), "parent cohort")
    audit.equal(qa["totals_rebuilt"], parent["summary"]["totals"], "parent QA totals")
    audit.equal(qa["video_summaries_rebuilt"], parent["summary"]["videos"], "parent QA per-video summaries")
    expected = {"summary.json"} | {f"by_video/{v}/{name}" for v in TRAIN for name in
        ("observations.csv", "windows.csv", "segments.csv", "frame_status.csv", "ground_truth_raw.csv", "input_contract.json", "summary.json")}
    artifacts = pin_artifacts(audit, parent, pp, expected)
    audit.equal(audit.json(artifacts["summary.json"]), parent["summary"], "parent exported summary")
    certified = {}
    for ref in qa["input_files"]:
        p = audit.path(ref["path"])
        require(p not in certified and str(p) in audit.files, "Unexpected/duplicate QA file")
        certified[p] = (sha(ref["sha256"]), integer(ref["bytes"]))
        audit.equal(certified[p], (audit.files[str(p)]["sha256"], audit.files[str(p)]["bytes"]), "QA-certified file bytes/hash")
    require(set(certified) == set(artifacts.values()) | {pp} and qa["files_verified"] == 86, "Incomplete QA artifact set")
    provenance = manifest["reference_provenance"]
    audit.reference(provenance["parent_manifest"])
    audit.reference(provenance["verification"])
    require(audit.path(provenance["parent_manifest"]["path"]) == pp
        and audit.path(provenance["verification"]["path"]) == qp
        and provenance["original_sources_read"] is False
        and provenance["scope"] == "individual_reference_v1_training_only"
        and provenance["boundary_reason_policy"] == "class_1_vs_id_absent_inherited_from_hashed_audited_reference",
        "Reference use/provenance scope differs")
    # Metadata identities are compared but YAML/inventory files are NOT opened.
    expected_refs = {lexical(r["path"]): recorded_ref(r) for r in parent["artifacts"] + parent["metadata"]}
    for p in (pp, qp):
        item = audit.files[str(p)]
        expected_refs[lexical(str(p))] = (lexical(str(p)), item["sha256"], item["bytes"])
    actual_refs = [recorded_ref(r) for r in provenance["validated_inputs"]]
    require(len(actual_refs) == 91 and len({r[0] for r in actual_refs}) == 91
        and set(actual_refs) == set(expected_refs.values()), "Recorded validated input chain differs")
    recheck = manifest["reference_recheck"]
    require(recheck["status"] == "verified" and recheck["files_verified"] == 91
        and recheck["scope"] == "exported_reference_end_of_batch_no_original_source_recheck",
        "End-of-batch reference verification missing")
    require(timestamp(manifest["started_at"]) <= timestamp(recheck["checked_at"])
        <= timestamp(manifest["repository_recheck"]["checked_at"]), "Reference recheck chronology differs")
    return parent, qa, artifacts


def video_reference(audit, artifacts, parent, qa, video):
    prefix = f"by_video/{video}/"
    summary = audit.json(artifacts[prefix + "summary.json"])
    audit.equal(summary, next(s for s in parent["summary"]["videos"] if s["video_id"] == video), "parent per-video summary")
    contract = audit.json(artifacts[prefix + "input_contract.json"])
    require(contract["input_hash"] == digest({k: v for k, v in contract.items() if k != "input_hash"}, ascii=False)
        and contract["input_hash"] == qa["input_hashes_recorded"][video], "Exported input contract hash differs")
    md = contract["video_metadata"]
    require(contract["video_id"] == video and contract["expected_frame_count"] == COUNTS[video]
        and md["frame_count"] == COUNTS[video] and md["width"] == 640 and md["height"] == 480,
        "Exported dimensions/frame count differ")
    fps = number(md["fps"])
    require(fps > 0, "FPS must be positive")
    positions, identities, classes = {}, set(), defaultdict(int)
    previous = None
    for row in audit.rows(artifacts[prefix + "observations.csv"], OBS_FIELDS):
        frame, identity, segment = integer(row["frame_index"]), row["track_id"], row["segment_id"]
        cls = integer(row["class_id"])
        require(row["video_id"] == video and row["annotated"] == "True" and cls in (0, 2)
            and 0 <= frame < COUNTS[video] and identity, "Invalid reference observation")
        key = (frame, identity)
        require(previous is None or previous < key, "Reference observations must be unique in frame/ID order")
        previous = key
        entry = positions.setdefault(segment, {"identity": identity, "start": frame, "xy": []})
        require(entry["identity"] == identity and frame == entry["start"] + len(entry["xy"]),
            "Reference segment observation axis is not consecutive or changes identity")
        entry["xy"].append((number(row["cx"]), number(row["cy"])))
        identities.add(identity)
        classes[str(cls)] += 1
    audit.equal(len(identities), summary["unique_individual_track_ids"], "parent original IDs")
    audit.equal(sum(len(p["xy"]) for p in positions.values()), summary["individual_observations"], "parent observations")
    for cls in ("0", "2"):
        audit.equal(classes[cls], summary["class_observations"][cls], "parent class count")
    expected_windows, declared, segments_with_windows = [], set(), 0
    previous = None
    for row in audit.rows(artifacts[prefix + "segments.csv"], SEG_FIELDS):
        seg, identity = row["segment_id"], row["track_id"]
        start, end = integer(row["start_frame"]), integer(row["end_frame"])
        require(row["video_id"] == video and row["split"] == "train" and seg in positions and seg not in declared,
            "Unknown/duplicate parent segment")
        require(seg == f"{video}/{quote(identity, safe='')}/{start}" and start <= end,
            "Segment ID/original identity differs")
        p = positions[seg]
        require(p["identity"] == identity and p["start"] == start and len(p["xy"]) == end - start + 1
            and integer(row["observation_count"]) == len(p["xy"]), "Declared segment differs from observations")
        order = (start, identity)
        require(previous is None or previous < order, "Segment order differs")
        previous = order
        declared.add(seg)
        segments_with_windows += len(p["xy"]) >= 30
        for origin in range(start + 19, end - 9):
            expected_windows.append((f"{seg}/{origin}/h20_f10", video, identity, seg, "train",
                                     origin - 19, origin, origin + 10, 20, 10))
    require(declared == set(positions), "A reference segment is missing")
    expected_windows.sort(key=lambda row: (row[6], row[2], row[3]))
    audit.equal(len(declared), summary["segments_total"], "all parent segments")
    audit.equal(segments_with_windows, summary["segments_with_windows"], "parent segments with windows")
    audit.equal(len(expected_windows), WINDOWS[video], "registered per-video windows")
    audit.equal(len(expected_windows), summary["windows_total"], "parent per-video windows")
    for i, (row, expected) in enumerate(zip_longest(audit.rows(artifacts[prefix + "windows.csv"], WINDOW_FIELDS), expected_windows)):
        require(row is not None and expected is not None, "Reference window coverage differs")
        actual = tuple(row[k] if index < 5 else integer(row[k]) for index, k in enumerate(WINDOW_FIELDS))
        audit.equal(actual, expected, f"all parent window identities {video}/{i}")
    return positions, expected_windows, summary, fps


def verify_model(audit, files, video, method, positions, windows, parent_summary, fps):
    prefix = f"by_video/{video}/{method}/"
    tracks = defaultdict(lambda: {"count": 0, "segments": set(), "sums": {k: Sum() for k in METRICS}})
    hashes = [hashlib.sha256() for _ in range(3)]
    iterators = (audit.rows(files[prefix + "predictions.csv"], PRED_FIELDS),
                 audit.rows(files[prefix + "window_metrics.csv"], KEYS + list(METRICS)), windows)
    count = 0
    for pr, mr, row in zip_longest(*iterators):
        require(pr is not None and mr is not None and row is not None, "Missing/extra prediction or metric window")
        keys = row[:8]
        label = f"{video}/{method}/{row[0]}"
        audit.equal({k: pr[k] for k in KEYS}, dict(zip(KEYS, keys)), label + ".prediction_identity")
        audit.equal({k: mr[k] for k in KEYS}, dict(zip(KEYS, keys)), label + ".metric_identity")
        segment = positions[row[3]]
        offset = row[5] - segment["start"]
        history, target = segment["xy"][offset:offset+20], segment["xy"][offset+20:offset+30]
        require(len(history) == 20 and len(target) == 10, "Incomplete history/future in reconstructed window")
        hashes[0].update(json.dumps(keys, ensure_ascii=True, separators=(",", ":")).encode() + b"\n")
        hashes[1].update(struct.pack("<40d", *(v for p in history for v in p)))
        hashes[2].update(struct.pack("<20d", *(v for p in target for v in p)))
        predicted = predictions(history, method)
        expected = errors(predicted, target)
        for h, xy in enumerate(predicted, 1):
            for axis, value in zip(("cx", "cy"), xy):
                audit.near(pr[f"{axis}_h{h}"], value, label + f".{axis}_h{h}")
        for key, value in expected.items():
            audit.near(mr[key], value, label + "." + key)
        audit.near(mr["ade_h1"], number(mr["fde_h1"]), label + ".ADE1_equals_FDE1")
        item = tracks[row[2]]
        item["count"] += 1
        item["segments"].add(row[3])
        for key, value in expected.items():
            item["sums"][key].add(value)
        count += 1
    audit.equal(count, WINDOWS[video], "all paired model windows")
    track_rows, means = aggregate(tracks)
    expected_tracks = [{"video_id": video, "configuration_id": method, **row} for row in track_rows]
    audit.equal(list(audit.rows(files[prefix + "track_metrics.csv"], TRACK_FIELDS)), expected_tracks, "all original-ID metrics")
    model_summary = audit.json(files[prefix + "summary.json"])
    for key, value in {"status": "complete", "params": {} if method == "persistence" else {"window": 5, "method": "median"},
        "prediction_schema": "wide_dense_positions_v1", "dtype": "float64", "predictor_input": "history_positions_only",
        "future_targets_passed_to_predictor": False, "clipped_to_image": False}.items():
        audit.equal(model_summary[key], value, "model summary scientific contract")
    refs = model_summary["artifacts"]
    require(len(refs) == 3 and [audit.path(r["path"]) for r in refs] ==
        [files[prefix + n] for n in ("predictions.csv", "window_metrics.csv", "track_metrics.csv")],
        "Model summary artifact order/set differs")
    for ref in refs:
        p = audit.path(ref["path"])
        audit.equal(recorded_ref(ref)[1:], (audit.files[str(p)]["sha256"], audit.files[str(p)]["bytes"]), "child artifact hash/size")
    expected_flat = {"video_id": video, "configuration_id": method,
        "method": "persistence" if method == "persistence" else "constant_velocity", "split": "train",
        "n_windows": count, "evaluated_original_ids": len(tracks),
        "all_original_individual_ids": parent_summary["unique_individual_track_ids"],
        "original_ids_without_windows": parent_summary["unique_individual_track_ids"] - len(tracks),
        "segments_total": len(positions), "segments_with_windows": len(set().union(*(s["segments"] for s in tracks.values()))),
        "fps": fps, "history_span_seconds": 19 / fps,
        **{f"horizon_seconds_h{h}": h / fps for h in REPORT_H},
        **dict(zip(("window_keys_sha256", "histories_sha256", "targets_sha256"), (h.hexdigest() for h in hashes))), **means}
    flat = model_summary["metrics"]
    require(set(flat) == set(expected_flat) | {"prediction_seconds", "prediction_ms_per_window"}, "Unexpected video/method metric schema")
    audit.equal({k: flat[k] for k in expected_flat}, expected_flat, "all video/method fields")
    seconds, elapsed = number(flat["prediction_seconds"]), number(model_summary["elapsed_seconds"])
    require(0 <= seconds <= elapsed, "Invalid recorded prediction/elapsed time")
    audit.near(flat["prediction_ms_per_window"], seconds * 1000 / count, "recorded prediction rate")
    expected_flat.update(prediction_seconds=seconds, prediction_ms_per_window=number(flat["prediction_ms_per_window"]))
    return expected_flat, expected_tracks


def comparison(rows, videos=TRAIN):
    by_pair = {(r["video_id"], r["configuration_id"]): r for r in rows}
    require(len(by_pair) == len(rows) == 2 * len(videos), "Duplicate/missing video/method summary")
    require(set(by_pair) == {(v, m) for v in videos for m in METHODS}, "Comparison video universe differs")
    paired = []
    for video in videos:
        left, right = (by_pair[video, method] for method in METHODS)
        for key in ("n_windows", "evaluated_original_ids", "all_original_individual_ids", "original_ids_without_windows",
                    "segments_total", "segments_with_windows", "fps", "window_keys_sha256", "histories_sha256", "targets_sha256"):
            require(left[key] == right[key], f"Unpaired video {video}: {key}")
        paired.append({"video_id": video, "n_windows": left["n_windows"], "evaluated_original_ids": left["evaluated_original_ids"],
                       **{f"cv_minus_persistence_{k}": right[k] - left[k] for k in ALL_METRICS}})
    methods = [{"configuration_id": method, "n_videos": len(videos),
        "n_windows": sum(by_pair[v, method]["n_windows"] for v in videos),
        **{f"macro_{key}": math.fsum(by_pair[v, method][key] for v in videos) / len(videos) for key in ALL_METRICS}}
        for method in METHODS]
    return {"status": "complete_descriptive_training_baselines", "video_ids": list(videos), "methods": methods,
        "paired_video_differences": paired, "hypothesis_tests": False, "confidence_intervals": False,
        "model_selected": False, "test_executed": False, "flow_evaluated": False, "end_to_end_evaluated": False}


def verify(value, audit):
    require(not any(n == "src" or n.startswith("src.") or n == "script" or n.startswith("script.") for n in sys.modules),
            "Scientific implementation was imported")
    path = audit.path(value)
    require(path.name == "manifest.json" and path.is_relative_to(RUN_ROOT) and path.parent.parent.name == "development",
            "An explicit baseline development manifest is required")
    audit.hash(path)
    manifest = audit.json(path)
    snapshot = snapshot_check(audit, manifest, path)
    plan = manifest["config"]
    parent_path, qa_path = audit.path(plan["reference"]["manifest"]), audit.path(plan["reference"]["verification"])
    expected = {f"by_video/{v}/{m}/{name}" for v in TRAIN for m in METHODS for name in
                ("predictions.csv", "window_metrics.csv", "track_metrics.csv", "summary.json")}
    expected |= {"video_metrics.csv", "paired_video_metrics.csv", "summary.json"}
    parent_names = {f"by_video/{v}/{name}" for v in TRAIN for name in
        ("observations.csv", "windows.csv", "segments.csv", "frame_status.csv", "ground_truth_raw.csv", "input_contract.json", "summary.json")}
    parent_names.add("summary.json")
    audit.allowed = {path, parent_path, qa_path} | {path.parent / n for n in expected} | {parent_path.parent / n for n in parent_names}
    artifacts = pin_artifacts(audit, manifest, path, expected)
    require(len(artifacts) == 99, "Exactly99 new artifacts are required")
    parent, qa, reference_files = reference_chain(audit, manifest)
    all_rows, original_id_counts, per_video_checks = [], {}, []
    for index, video in enumerate(TRAIN, 1):
        positions, windows, ps, fps = video_reference(audit, reference_files, parent, qa, video)
        for method in METHODS:
            row, tracks = verify_model(audit, artifacts, video, method, positions, windows, ps, fps)
            all_rows.append(row)
            original_id_counts[video] = len(tracks)
            per_video_checks.append({"video_id": video, "method": method, "windows_rebuilt": len(windows),
                "predicted_positions_compared": len(windows) * 10, "coordinate_values_compared": len(windows) * 20,
                "dense_window_metrics_compared": len(windows) * 6, "original_ids": len(tracks)})
            print(json.dumps({"verified_video": video, "video_index": index, "method": method,
                "windows": len(windows), "numeric_comparisons": audit.numeric_comparisons}), flush=True)
        del positions, windows
    audit.equal(list(audit.rows(artifacts["video_metrics.csv"])), all_rows, "top video metrics and registered order")
    rebuilt = comparison(all_rows)
    audit.equal(list(audit.rows(artifacts["paired_video_metrics.csv"])), rebuilt["paired_video_differences"], "all paired video differences")
    audit.equal(audit.json(artifacts["summary.json"]), rebuilt, "all global aggregates and flags")
    audit.equal(manifest["summary"], rebuilt, "manifest comparison summary")
    require(all(m["n_windows"] == 343776 for m in rebuilt["methods"]), "Incomplete method coverage")
    resources, budget = manifest["resources"], plan["budget"]
    require(0 <= number(resources["ram_rss_peak_mb"]) <= budget["max_sampled_rss_mb"], "Recorded sampled RSS limit exceeded")
    require(0 <= number(manifest["elapsed_seconds"]) <= budget["soft_wall_seconds"], "Recorded completed run wall budget exceeded")
    artifact_bytes = sum(audit.files[str(p)]["bytes"] for p in artifacts.values())
    total_bytes = artifact_bytes + audit.files[str(path)]["bytes"]
    require(artifact_bytes <= integer(resources["artifact_bytes_before_final_manifest"]) <= budget["max_artifact_mb"] * 1024**2
        and total_bytes <= budget["max_artifact_mb"] * 1024**2, "Artifact size/accounting exceeds registered limit")
    # Rehash accepted outputs/reference after the full streamed reconstruction.
    for item in list(audit.files.values()):
        audit.hash(item["path"], item["sha256"])
    require(len(audit.files) == 187, "Expected100 new run files and87 reference files")
    return {"status": "passed", "run_manifest": str(path), "run_manifest_sha256": audit.files[str(path)]["sha256"],
        "plan_hash": PLAN_HASH, "parent_manifest_sha256": PARENT_HASH, "parent_verification_sha256": QA_HASH,
        "git_sha_of_verified_run": manifest["git_sha"], "source_hash_of_verified_run": manifest["source_hash"],
        "shared_snapshot_sha256": snapshot, "video_ids": list(TRAIN), "windows_per_method": 343776,
        "prediction_rows_compared": 687552, "window_metric_rows_compared": 687552,
        "dense_future_positions_compared": 6875520, "coordinate_values_compared": 13751040,
        "dense_window_metric_values_compared": 4125312, "all_windows_reconstructed": True,
        "new_artifacts_verified": 99, "new_manifest_verified": 1, "derived_reference_files_verified": 87,
        "per_video_method_checks": per_video_checks, "evaluated_original_ids_by_video": original_id_counts,
        "comparison_rebuilt": rebuilt, "video_metrics_rebuilt": all_rows,
        "new_artifact_bytes_excluding_manifest": artifact_bytes, "new_run_bytes_including_manifest": total_bytes,
        "recorded_resources": resources, "recorded_elapsed_seconds": manifest["elapsed_seconds"],
        "limits": [
            "Only the selected baseline CSV/JSON and pinned derived-reference CSV/JSON were opened. No YAML, original labels, videos, images, validation/test sources or scientific project imports.",
            "Parent source identity, dimensions, FPS and raw-label accuracy remain recorded producer evidence and the pinned earlier audit. This audit does not independently reopen or revalidate original source bytes.",
            "Recorded plan/split/other prerequisite file references were compared without opening those files. The embedded plan was independently hashed against its registered digest.",
            "All prediction coordinates and dense displacement metrics were reconstructed with binary64 Python arithmetic; math.hypot/compensated sums may differ slightly from NumPy. Tolerances are explicit.",
            "Causal formula reconstruction confirms output equality to history-only baselines. It does not by itself prove every internal runtime access; no target-dependent formula was used here.",
            "Coverage is conditional on parent GT history20/future10 eligibility. This is descriptive training prediction with GT, not end-to-end accuracy, independent generalization or a test of the optical-flow hypothesis.",
            "Video remains the unit. Original IDs pool their segments; overlapping windows, segments and deterministic seeds are not independent experimental replicates.",
            "Git/environment checks, timing and sampled RSS are recorded execution evidence, not live historical reconstruction or proof of unsampled memory peaks."]}


def self_test():
    audit = Audit()
    history = [(float(t*t), 0.0) for t in range(20)]
    target = [(float(t*t), 0.0) for t in range(20, 30)]
    predicted = predictions(history, "cv_median5")
    require(predicted[0] == (394.0, 0.0) and predicted[-1] == (691.0, 0.0), "Five componentwise differences/indexing failed")
    metric = errors(predicted, target)
    require(metric["ade_h10"] == 66.0 and metric["fde_h10"] == 150.0
        and metric["ade_h5"] == 26.0 and metric["fde_h5"] == 50.0, "Dense acceleration metric failed")
    sparse = math.fsum(math.hypot(predicted[h-1][0] - target[h-1][0], 0) for h in REPORT_H) / 3
    require(sparse != metric["ade_h10"], "Sparse/dense metric test is ineffective")
    changed_target = [(x + 1000, y - 17) for x, y in target]
    require(predictions(history, "cv_median5") == predicted
        and errors(predicted, changed_target) != metric, "Target perturbation test failed")
    require(predictions(history, "persistence") == [(361.0, 0.0)] * 10, "Persistence failed")
    motion = [(1000.0 + 20*t, -100.0 - 7*t) for t in range(20)]
    require(predictions(motion, "cv_median5")[-1] == (1580.0, -303.0), "Out-of-image positions were clipped")
    two_axes = [(0.0, 0.0)] * 14 + [(0.0, 0.0)]
    for dx, dy in [(1, 100), (2, 1), (3, 99), (4, 2), (5, 3)]:
        two_axes.append((two_axes[-1][0] + dx, two_axes[-1][1] + dy))
    require(predictions(two_axes, "cv_median5")[0] == (18.0, 208.0), "Componentwise median was replaced by a vector statistic")
    stats = defaultdict(lambda: {"count": 0, "segments": set(), "sums": {k: Sum() for k in METRICS}})
    for identity, segment, value in [("A", "s1", 0.0), ("A", "s1", 0.0), ("A", "s2", 9.0), ("B", "s3", 10.0)]:
        item = stats[identity]
        item["count"] += 1
        item["segments"].add(segment)
        for key in METRICS:
            item["sums"][key].add(value)
    tracks, values = aggregate(stats)
    require(tracks[0]["ade_h10"] == 3.0 and tracks[0]["segments_with_windows"] == 2
        and values["ade_h10"] == 6.5 and values["window_weighted_ade_h10"] == 4.75,
        "ID weighting/segment pooling failed")
    rows = []
    for video, count, value in [("a", 4, 6.5), ("b", 100, 20.0)]:
        for method in METHODS:
            rows.append({"video_id": video, "configuration_id": method, "n_windows": count,
                "evaluated_original_ids": 2, "all_original_individual_ids": 3, "original_ids_without_windows": 1,
                "segments_total": 4, "segments_with_windows": 3, "fps": 50.0,
                "window_keys_sha256": "a", "histories_sha256": "b", "targets_sha256": "c",
                **{k: value - (1 if method == "cv_median5" else 0) for k in ALL_METRICS}})
    compare = comparison(rows, ("a", "b"))
    require(compare["methods"][0]["macro_ade_h10"] == 13.25
        and compare["paired_video_differences"][0]["cv_minus_persistence_ade_h10"] == -1,
        "Equal video weighting or paired difference failed")
    try:
        comparison(rows[:-1], ("a", "b"))
    except ValueError:
        pass
    else:
        raise ValueError("Incomplete method/video coverage accepted")
    for path in (ROOT / "data/sources/test.json", ROOT / "configs/protocol/prediction_baselines_v1.yaml", ROOT / "other.csv"):
        try:
            audit.path(path)
        except ValueError:
            pass
        else:
            raise ValueError("Forbidden path accepted")
    audit.near(1.0 + 1e-10, 1.0, "accepted tolerance")
    try:
        audit.near(1.01, 1.0, "rejected corruption")
    except ValueError:
        pass
    else:
        raise ValueError("Numerical corruption accepted")
    require(struct.unpack("<d", struct.pack("<d", 10.004))[0].hex() == float(repr(10.004)).hex(), "Binary64 roundtrip failed")
    memory = io.StringIO(newline="")
    csv.writer(memory).writerows([["track_id", "cx"], ["001/a%", 10.004]])
    memory.seek(0)
    exported = next(csv.DictReader(memory))
    require(exported["track_id"] == "001/a%" and float(exported["cx"]).hex() == (10.004).hex(),
            "CSV original identity/float roundtrip failed")
    return {"status": "passed", "mode": "synthetic_self_test", "experiment_artifacts_read": False,
        "checks": ["x=t^2 origin19: CV ADE10=66/FDE10=150 and ADE5=26/FDE5=50", "dense versus sparse ADE",
                   "persistence last position", "five differences/six positions", "componentwise median", "target perturbation",
                   "no image clipping", "segments pooled within original ID", "unequal ID/window/video weights",
                   "CV minus persistence sign", "missing pair rejected", "source/YAML/path guards", "numeric tolerance", "binary64/CSV original-ID roundtrip"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest")
    parser.add_argument("--output", help="Exclusive new JSON report in the parent development directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        require(args.run_manifest is None and args.output is None, "Synthetic self-test accepts no experiment paths")
        print(json.dumps(self_test()), flush=True)
        return 0
    require(args.run_manifest is not None and args.output is not None, "Explicit run manifest and exclusive report path required")
    run, output = Path(args.run_manifest).resolve(), Path(args.output).resolve()
    require(run.is_relative_to(RUN_ROOT) and run.name == "manifest.json"
        and output.parent == run.parent.parent and output.suffix.lower() == ".json" and output.parent.is_dir(),
        "Report must be a new JSON sibling of the immutable run in its development directory")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        start, audit = time.perf_counter(), Audit()
        try:
            report, code = verify(args.run_manifest, audit), 0
        except Exception as exc:
            report, code = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                "requested_run_manifest": args.run_manifest}, 1
        report.update(created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-start,
            comparisons=audit.comparisons, numeric_comparisons=audit.numeric_comparisons,
            max_absolute_difference=audit.max_absolute_difference, max_difference_label=audit.max_difference_label,
            files_verified=len(audit.files), input_files=list(audit.files.values()),
            comparison_rules={"counts_ids_params": "exact", "float_abs_tolerance": ABS_TOL, "float_rel_tolerance": REL_TOL,
                "float_rule": "math.isclose: difference <= max(abs_tol, rel_tol*max(abs(actual),abs(expected)))",
                "coordinate_and_displacement_unit": "original image pixels", "other_floats": "same tolerances in the field's recorded unit"},
            verifier_path=str(Path(__file__).resolve()), verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            runtime={"python": sys.version, "platform": platform.platform()},
            project_implementation_imported=False, original_sources_opened=False, yaml_files_opened=False, seed=None)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "output": str(output), "files_verified": len(audit.files),
                      "numeric_comparisons": audit.numeric_comparisons}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
