"""Describe training annotation geometry without evaluating or tuning a detector.

Read the registered training split only. Preserve every anomaly in a separate
table, exclude invalid rows from descriptive geometry, and refuse an existing
output directory. JPEGs are opened for dimensions, never decoded as video.
Official invocation belongs in script/README.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import scipy
from PIL import Image, __version__ as pillow_version
from scipy.spatial import cKDTree
import yaml


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_TRAIN_IDS = (11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82)
COHORTS = {"class0": (0,), "class1": (1,), "class2": (2,),
           "cells0_2": (0, 2), "all": (0, 1, 2)}
RADII = (10, 15, 20)
QUANTILES = {"q05": .05, "q25": .25, "q50": .5, "q75": .75, "q95": .95}
METRICS = ("width_px", "height_px", "diagonal_px", "half_diagonal_px", "nearest_neighbor_px")
PIXEL_ATOL = 1e-9
COMPARISON_ATOL = 1e-12
OUTPUT = ROOT / "data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria"


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Unable to record Git state: {result.stderr}")
    return result.stdout.strip()


def json_write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                    encoding="utf-8")


def csv_write(path: Path, rows: list[dict], fields: tuple | list | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Audit:
    def __init__(self) -> None:
        self.inputs: list[dict] = []
        self.anomalies: list[dict] = []
        self.peak_rss = psutil.Process().memory_info().rss

    def anomaly(self, video: int, frame: int | None, path: Path, kind: str,
                detail: str, line: int | None = None, raw: str = "") -> None:
        self.anomalies.append({"video_id": video, "frame": frame, "source": relative(path),
                               "line": line, "kind": kind, "detail": detail, "raw": raw})

    def source_bytes(self, path: Path, role: str, video: int | None = None,
                     frame: int | None = None) -> bytes:
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Input changed during read: {path}")
        self.inputs.append({"path": relative(path), "role": role, "video_id": video,
                            "frame": frame, "bytes": len(content),
                            "mtime_ns": after.st_mtime_ns,
                            "sha256": hashlib.sha256(content).hexdigest()})
        return content

    def source_text(self, path: Path, role: str, video: int | None = None,
                    frame: int | None = None) -> str:
        return self.source_bytes(path, role, video, frame).decode("utf-8-sig")

    def index(self, folder: Path, pattern: str, video: int) -> dict[int, Path]:
        indexed: dict[int, Path] = {}
        if not folder.is_dir():
            self.anomaly(video, None, folder, "missing_directory", "Directory unavailable; no labels inferred.")
            return indexed
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            match = re.fullmatch(pattern, path.name)
            if not match:
                self.anomaly(video, None, path, "unexpected_filename", "Not used: cannot align by frame number.")
                continue
            frame = int(match.group(1))
            if frame in indexed:
                raise ValueError(f"Duplicate frame filename: {path}")
            indexed[frame] = path
        return indexed

    def parse(self, path: Path, video: int, frame: int, *, tracked: bool) -> list[dict]:
        role = "labels_ftid" if tracked else "labels"
        rows = []
        text = self.source_text(path, role, video, frame)
        for line_number, raw in enumerate(text.splitlines(), 1):
            if not raw.strip():
                continue
            fields = raw.split()
            row = {"track_id": fields[0] if tracked and fields else None,
                   "line": line_number, "raw": raw, "valid": True,
                   "class_id": None, "coords": None}
            rows.append(row)
            if len(fields) != (6 if tracked else 5):
                row["valid"] = False
                self.anomaly(video, frame, path, "field_count", f"Expected {6 if tracked else 5}, found {len(fields)}.", line_number, raw)
                continue
            offset = int(tracked)
            try:
                class_id = int(fields[offset])
                coords = tuple(float(value) for value in fields[offset + 1:])
            except ValueError:
                row["valid"] = False
                self.anomaly(video, frame, path, "numeric_parse", "Class or coordinate cannot be parsed.", line_number, raw)
                continue
            row.update(class_id=class_id, coords=coords)
            if class_id not in (0, 1, 2):
                row["valid"] = False
                self.anomaly(video, frame, path, "unknown_class", f"Class {class_id} is outside 0, 1, 2.", line_number, raw)
            if not all(math.isfinite(value) for value in coords):
                row["valid"] = False
                self.anomaly(video, frame, path, "nonfinite_coordinates", "NaN or infinite coordinate.", line_number, raw)
            elif not all(0 <= value <= 1 for value in coords):
                row["valid"] = False
                self.anomaly(video, frame, path, "unnormalized_coordinates", "A normalized coordinate is outside [0, 1].", line_number, raw)
            if math.isfinite(coords[2]) and math.isfinite(coords[3]) and min(coords[2:]) <= 0:
                row["valid"] = False
                self.anomaly(video, frame, path, "nonpositive_size", "Box width or height is not positive.", line_number, raw)
        if tracked:
            counts = Counter(row["track_id"] for row in rows)
            for row in rows:
                if counts[row["track_id"]] > 1:
                    row["valid"] = False
                    self.anomaly(video, frame, path, "duplicate_track_id",
                                 f"ID occurs {counts[row['track_id']]} times; all occurrences excluded.", row["line"], row["raw"])
        return rows

    def check_boxes(self, rows: list[dict], width: int, height: int,
                    path: Path, video: int, frame: int) -> None:
        for row in rows:
            if row["coords"] is None or not all(math.isfinite(x) for x in row["coords"]):
                continue
            cx, cy, w, h = np.asarray(row["coords"]) * (width, height, width, height)
            x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
            if min(x0, y0) < -PIXEL_ATOL or x1 > width + PIXEL_ATOL or y1 > height + PIXEL_ATOL:
                row["valid"] = False
                detail = f"Box ({x0:.12g}, {y0:.12g}, {x1:.12g}, {y1:.12g}) outside image {width}x{height}; not clipped."
                self.anomaly(video, frame, path, "box_outside_image", detail, row["line"], row["raw"])
            row["pixels"] = (float(cx), float(cy), float(w), float(h))

    def check_input_metadata(self) -> None:
        for item in self.inputs:
            state = (ROOT / item["path"]).stat()
            if (state.st_size, state.st_mtime_ns) != (item["bytes"], item["mtime_ns"]):
                raise RuntimeError(f"Input metadata changed during audit: {item['path']}")


def compare_formats(tracked: list[dict], simple: list[dict]) -> bool:
    def signatures(rows: list[dict]) -> list[tuple] | None:
        if any(row["coords"] is None or row["class_id"] is None for row in rows):
            return None
        return sorted((row["class_id"], *row["coords"]) for row in rows)
    left, right = signatures(tracked), signatures(simple)
    return left is not None and right is not None and len(left) == len(right) and (
        not left or bool(np.allclose(left, right, atol=COMPARISON_ATOL, rtol=0)))


def nearest_neighbors(centers: np.ndarray) -> np.ndarray:
    if len(centers) == 1:
        return np.full(1, np.inf)
    return cKDTree(centers).query(centers, k=2, workers=1)[0][:, 1]


def fractions_summary(values: list[float]) -> dict:
    return {"n_videos": len(values), "mean_equal_video_weight": float(np.mean(values)) if values else None,
            "min_video": min(values) if values else None, "max_video": max(values) if values else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True,
                        help="Run the fixed, descriptive training-only audit; does not run a detector.")
    parser.parse_args()
    started = time.perf_counter()
    start_utc = datetime.now(timezone.utc).isoformat()
    if OUTPUT.exists():
        parser.error("Output already exists; no files overwritten. A new audit requires an explicitly distinct output.")
    audit = Audit()
    split_path = ROOT / "configs/protocol/splits.yaml"
    spec = yaml.safe_load(audit.source_text(split_path, "split_config"))
    train_ids = tuple(spec["fixed_split"]["train"])
    if train_ids != EXPECTED_TRAIN_IDS:
        parser.error("Training split differs from the 12 video IDs authorized for this audit.")
    if set(train_ids) & (set(spec["fixed_split"]["val"]) | set(spec["fixed_split"]["test"])):
        parser.error("Training split overlaps validation/test; no source opened.")
    audit.source_bytes(Path(__file__), "generator_script")
    git_before = {"commit": git_output("rev-parse", "HEAD"), "status_porcelain": git_output("status", "--porcelain")}
    frames, geometry, gates, video_summaries = [], [], [], []
    for video in train_ids:
        base = ROOT / "data/sources/visem_tracking/dataset/Train" / str(video)
        tracked_files = audit.index(base / "labels_ftid", rf"{video}_frame_(\d+)_with_ftid\.txt", video)
        simple_files = audit.index(base / "labels", rf"{video}_frame_(\d+)\.txt", video)
        images = audit.index(base / "images", rf"{video}_frame_(\d+)\.jpg", video)
        collected = {cohort: [] for cohort in COHORTS}
        video_counter = Counter()
        sizes = Counter()
        for frame in sorted(set(images) | set(tracked_files) | set(simple_files)):
            record = {"video_id": video, "frame": frame, "annotation_state": "unlabeled",
                      "image_present": frame in images, "labels_ftid_present": frame in tracked_files,
                      "labels_present": frame in simple_files, "image_width": None, "image_height": None,
                      "raw_rows": 0, "valid_rows": 0, "invalid_rows": 0,
                      "raw_class0": 0, "raw_class1": 0, "raw_class2": 0, "raw_unknown_class": 0,
                      "valid_class0": 0, "valid_class1": 0, "valid_class2": 0,
                      "formats_equivalent": None}
            frames.append(record)
            video_counter["indexed_frames"] += 1
            if frame not in tracked_files:
                video_counter["unlabeled_frames"] += 1
                audit.anomaly(video, frame, base / "labels_ftid" / f"{video}_frame_{frame}_with_ftid.txt",
                              "missing_labels_ftid", "Unlabeled frame excluded, never interpreted as a negative.")
                continue
            path = tracked_files[frame]
            rows = audit.parse(path, video, frame, tracked=True)
            video_counter["annotated_frames"] += 1
            video_counter["raw_rows"] += len(rows)
            record["annotation_state"] = "annotated_empty" if not rows else "annotated"
            record["raw_rows"] = len(rows)
            if not rows:
                video_counter["annotated_empty_frames"] += 1
            for row in rows:
                key = f"raw_class{row['class_id']}" if row["class_id"] in (0, 1, 2) else "raw_unknown_class"
                record[key] += 1
                video_counter[key] += 1
            simple = None
            if frame in simple_files:
                simple = audit.parse(simple_files[frame], video, frame, tracked=False)
                record["formats_equivalent"] = compare_formats(rows, simple)
                video_counter["format_compared_frames"] += 1
                if not record["formats_equivalent"]:
                    video_counter["format_divergent_frames"] += 1
                    audit.anomaly(video, frame, simple_files[frame], "formats_diverge",
                                  "Classes/coordinates differ from labels_ftid (permutation-invariant, atol=1e-12).")
            else:
                audit.anomaly(video, frame, base / "labels" / f"{video}_frame_{frame}.txt",
                              "missing_simple_labels", "No cross-format comparison; labels_ftid remains primary.")
            dimensions = None
            if frame not in images:
                audit.anomaly(video, frame, base / "images" / f"{video}_frame_{frame}.jpg",
                              "missing_image", "All rows excluded: pixel dimensions cannot be established.")
            else:
                image_bytes = audit.source_bytes(images[frame], "image_header_and_hash", video, frame)
                try:
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        dimensions = image.size
                        if image.format != "JPEG" or min(dimensions) <= 0:
                            raise ValueError("Not a JPEG with positive dimensions")
                except (OSError, ValueError) as error:
                    audit.anomaly(video, frame, images[frame], "invalid_image_header", str(error))
            if dimensions is None:
                for row in rows:
                    row["valid"] = False
            else:
                width, height = dimensions
                record.update(image_width=width, image_height=height)
                sizes[f"{width}x{height}"] += 1
                audit.check_boxes(rows, width, height, path, video, frame)
                if simple is not None:
                    audit.check_boxes(simple, width, height, simple_files[frame], video, frame)
            valid = [row for row in rows if row["valid"]]
            record["valid_rows"], record["invalid_rows"] = len(valid), len(rows) - len(valid)
            video_counter["valid_rows"] += len(valid)
            video_counter["invalid_rows"] += len(rows) - len(valid)
            for row in valid:
                record[f"valid_class{row['class_id']}"] += 1
            for cohort, classes in COHORTS.items():
                chosen = [row for row in valid if row["class_id"] in classes]
                if not chosen:
                    continue
                positions = np.asarray([row["pixels"] for row in chosen], dtype=np.float64)
                widths, heights = positions[:, 2], positions[:, 3]
                diagonals = np.hypot(widths, heights)
                neighbors = nearest_neighbors(positions[:, :2])
                collected[cohort].append(np.column_stack((widths, heights, diagonals, diagonals / 2, neighbors)))
            audit.peak_rss = max(audit.peak_rss, psutil.Process().memory_info().rss)
        for cohort, chunks in collected.items():
            observations = np.concatenate(chunks) if chunks else np.empty((0, 5))
            n = len(observations)
            nn = observations[:, 4]
            finite = np.isfinite(nn)
            finite_n = int(finite.sum())
            for metric_index, metric in enumerate(METRICS):
                values = observations[:, metric_index]
                values = values[np.isfinite(values)]
                row = {"video_id": video, "cohort": cohort, "metric": metric, "observations": n,
                       "finite_observations": len(values), "singleton_observations": int(n - finite_n),
                       "frames_with_cohort": len(chunks), "min": float(values.min()) if len(values) else None,
                       "max": float(values.max()) if len(values) else None}
                row.update({key: float(np.quantile(values, q, method="linear")) if len(values) else None
                            for key, q in QUANTILES.items()})
                geometry.append(row)
            for radius in RADII:
                center_count = int((nn <= radius).sum())
                overlap_count = int((nn < 2 * radius).sum())
                beyond_count = int((radius > observations[:, 3]).sum())
                gates.append({"video_id": video, "cohort": cohort, "radius_px": radius,
                              "observations": n, "finite_neighbor_observations": finite_n,
                              "singleton_observations": n - finite_n,
                              "neighbor_le_radius_count": center_count,
                              "neighbor_le_radius_fraction_all": center_count / n if n else None,
                              "neighbor_le_radius_fraction_finite": center_count / finite_n if finite_n else None,
                              "neighbor_lt_2radius_count": overlap_count,
                              "neighbor_lt_2radius_fraction_all": overlap_count / n if n else None,
                              "neighbor_lt_2radius_fraction_finite": overlap_count / finite_n if finite_n else None,
                              "radius_gt_half_diagonal_count": beyond_count,
                              "radius_gt_half_diagonal_fraction_all": beyond_count / n if n else None})
        video_summary = {"video_id": video, **dict(video_counter),
                         "image_file_count": len(images), "labels_ftid_file_count": len(tracked_files),
                         "simple_labels_file_count": len(simple_files), "dimensions_annotated_frames": dict(sizes)}
        video_summaries.append(video_summary)
        print(json.dumps({"completed_video": video, "annotated_frames": video_counter["annotated_frames"],
                          "unlabeled_frames": video_counter["unlabeled_frames"], "raw_rows": video_counter["raw_rows"],
                          "invalid_rows": video_counter["invalid_rows"]}), flush=True)
    audit.check_input_metadata()
    aggregated = {}
    for cohort in COHORTS:
        selected_geometry = [row for row in geometry if row["cohort"] == cohort]
        by_metric = {}
        for metric in METRICS:
            medians = [row["q50"] for row in selected_geometry if row["metric"] == metric and row["q50"] is not None]
            by_metric[metric] = {"n_videos_with_observations": len(medians),
                                 "median_of_video_medians": float(np.median(medians)) if medians else None,
                                 "min_video_median": min(medians) if medians else None,
                                 "max_video_median": max(medians) if medians else None}
        by_radius = {}
        for radius in RADII:
            selected = [row for row in gates if row["cohort"] == cohort and row["radius_px"] == radius]
            by_radius[str(radius)] = {field: fractions_summary([row[field] for row in selected if row[field] is not None])
                                     for field in ("neighbor_le_radius_fraction_all", "neighbor_lt_2radius_fraction_all",
                                                   "radius_gt_half_diagonal_fraction_all")}
        aggregated[cohort] = {"geometry_equal_video_weight": by_metric, "gates_equal_video_weight": by_radius}
    anomaly_counts = Counter(row["kind"] for row in audit.anomalies)
    summary = {"schema_version": 1, "kind": "training_annotation_geometry_descriptive_audit",
               "split": "train", "video_ids": list(train_ids), "videos": video_summaries,
               "totals": {key: sum(video.get(key, 0) for video in video_summaries)
                          for key in ("indexed_frames", "annotated_frames", "annotated_empty_frames", "unlabeled_frames",
                                      "raw_rows", "valid_rows", "invalid_rows", "raw_class0", "raw_class1", "raw_class2",
                                      "raw_unknown_class", "format_compared_frames", "format_divergent_frames")},
               "anomalies_by_kind": dict(anomaly_counts), "cohorts": aggregated}
    OUTPUT.mkdir(parents=True, exist_ok=False)
    csv_write(OUTPUT / "per_video_geometry.csv", geometry)
    csv_write(OUTPUT / "per_video_gates.csv", gates)
    csv_write(OUTPUT / "per_frame_counts.csv", frames)
    csv_write(OUTPUT / "anomalies.csv", audit.anomalies,
              ("video_id", "frame", "source", "line", "kind", "detail", "raw"))
    csv_write(OUTPUT / "input_files.csv", audit.inputs)
    json_write(OUTPUT / "summary.json", summary)
    manifest = {"schema_version": 1, "kind": summary["kind"], "started_at_utc": start_utc,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_seconds": time.perf_counter() - started,
                "configuration": {"split": "train", "video_ids": list(train_ids), "cohorts": COHORTS,
                                  "radii_px": RADII, "quantiles": QUANTILES, "quantile_method": "linear",
                                  "pixel_bounds_atol": PIXEL_ATOL, "format_comparison_atol": COMPARISON_ATOL,
                                  "seed": None, "output": relative(OUTPUT)},
                "input_index": {"path": relative(OUTPUT / "input_files.csv"), "entries": len(audit.inputs),
                                "sha256": digest(OUTPUT / "input_files.csv"),
                                "method": "SHA256 of full bytes read; file size/mtime checked before/after read and at end"},
                "split_config_sha256": digest(split_path), "generator": {"path": relative(Path(__file__)), "sha256": digest(Path(__file__))},
                "git": git_before, "git_at_finish": {"commit": git_output("rev-parse", "HEAD"), "status_porcelain": git_output("status", "--porcelain")},
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                                "pillow": pillow_version, "pyyaml": yaml.__version__, "psutil": psutil.__version__,
                                "os": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
                                "cpu_logical_count": psutil.cpu_count(), "cpu_physical_count": psutil.cpu_count(logical=False),
                                "system_ram_bytes": psutil.virtual_memory().total},
                "resources": {"peak_rss_bytes_sampled_each_frame": audit.peak_rss,
                              "rss_bytes_at_finish": psutil.Process().memory_info().rss,
                              "gpu_used": False, "vram_used_bytes": 0, "seed": None},
                "definitions": {
                    "observation": "One valid annotation in one labeled frame; repeat identities over time are repeated observations.",
                    "validity": "6 fields, known class, finite normalized coordinates, positive size, unique frame ID, valid JPEG dimensions and bounds within 1e-9 px; no clipping or GT changes.",
                    "groups": "class0/class1/class2 separately; cells0_2 merges 0 and 2; all merges 0,1,2. No group chooses a class policy.",
                    "nearest_neighbor": "Euclidean distance to another valid annotation in the same frame and same cohort; singleton has infinity.",
                    "nn_quantiles": "Quantiles use only finite neighbors, with finite and singleton observation counts saved. Gate fractions use all valid annotations unless explicitly suffixed finite.",
                    "neighbor_le_radius": "Another annotated center is inside or on the acceptance disk; descriptive geometry, not an identity error or actual false-positive rate.",
                    "neighbor_lt_2radius": "Acceptance disks overlap with positive area; strict <2r. This is geometric potential for ambiguous location, not a measured error rate.",
                    "radius_gt_half_diagonal": "Radius exceeds the center-to-corner distance of that box, allowing locations farther from its center than every corner. This alone does not define an adequate matching radius.",
                    "aggregation": "Compute per-video quantiles and fractions first. Principal summary: median of available video medians, and equal-video mean/min/max of fractions. Videos without a cohort are not zero-valued observations.",
                    "missing_labels": "Missing labels_ftid is unlabeled and excluded, never a negative; existing empty file is annotated_empty.",
                    "format_comparison": "labels_ftid is primary. Compare raw class/coordinates as sorted multisets to labels at absolute tolerance1e-12; discrepancies recorded, never silently corrected."},
                "limitations": ["Training data only; neither validation nor test source files are read.",
                                "No detector, matching, parameter search, or protocol change is performed.",
                                "No independent frame-based confidence intervals or hypothesis tests: scientific aggregation unit is video.",
                                "Box centers are geometric reference points, not anatomical point annotations.",
                                "Does not measure inter-annotator uncertainty, GT completeness, temporal ID consistency, or physical fluid speed.",
                                "Invalid labels are excluded from geometry and retained in anomaly/count tables; this may change statistics near image boundaries.",
                                "JPEG dimensions come from headers; JPEG content is read for hashes but never decoded. Videos are not opened."],
                "outputs": {path.name: {"path": relative(path), "sha256": digest(path), "bytes": path.stat().st_size}
                            for path in sorted(OUTPUT.iterdir())}}
    json_write(OUTPUT / "manifest.json", manifest)
    print(json.dumps({"output": relative(OUTPUT), "totals": summary["totals"],
                      "anomalies": summary["anomalies_by_kind"], "runtime_seconds": manifest["runtime_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
