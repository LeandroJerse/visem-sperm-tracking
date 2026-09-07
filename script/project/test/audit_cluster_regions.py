"""Audit training GT cluster regions without a detector or a class-policy change.

Reuse the immutable geometry audit for per-frame dimensions, expected counts
and source hashes. Read only training labels_ftid and four selected training
JPEGs. Refuse an existing output directory. --self-test opens no data sources.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import platform
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version
import scipy
import yaml

from script.project.test import analyze_annotation_geometry as previous


ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / "data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria"
OUTPUT = ROOT / "data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos"
TRAIN_IDS = (11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82)
RADII = (10, 15, 20)
Rect = tuple[float, float, float, float]


def clipped_rectangles(rectangles: list[Rect], width: float, height: float) -> list[Rect]:
    clipped = []
    for x0, y0, x1, y1 in rectangles:
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 < x0 or y1 < y0:
            raise ValueError("Invalid rectangle for union")
        x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(width, x1), min(height, y1)
        if x1 > x0 and y1 > y0:
            clipped.append((x0, y0, x1, y1))
    return clipped


def rectangle_union_area(rectangles: list[Rect], width: float, height: float) -> float:
    """Continuous geometric union by x slabs and union of y intervals; no raster mask."""
    boxes = clipped_rectangles(rectangles, width, height)
    xs = sorted({edge for box in boxes for edge in (box[0], box[2])})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((y0, y1) for x0, y0, x1, y1 in boxes if x0 < right and x1 > left)
        if not intervals:
            continue
        start, end = intervals[0]
        y_union = 0.0
        for low, high in intervals[1:]:
            if low <= end:
                end = max(end, high)
            else:
                y_union += end - start
                start, end = low, high
        y_union += end - start
        area += (right - left) * y_union
    return area


def center_region_distances(centers: np.ndarray, rectangles: list[Rect]) -> np.ndarray:
    """Euclidean distance from each point to the union of closed rectangles."""
    if not rectangles:
        return np.full(len(centers), np.inf)
    if not len(centers):
        return np.empty(0)
    boxes = np.asarray(rectangles)
    dx = np.maximum(np.maximum(boxes[None, :, 0] - centers[:, None, 0],
                               centers[:, None, 0] - boxes[None, :, 2]), 0)
    dy = np.maximum(np.maximum(boxes[None, :, 1] - centers[:, None, 1],
                               centers[:, None, 1] - boxes[None, :, 3]), 0)
    return np.hypot(dx, dy).min(axis=1)


def intersects_positive(a: Rect, b: Rect) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def self_test() -> dict:
    cases = [([], 0), ([(1, 1, 4, 5)], 12),
             ([(0, 0, 4, 4), (2, 2, 6, 6)], 28),
             ([(0, 0, 4, 4), (1, 1, 2, 2), (0, 0, 4, 4)], 16),
             ([(0, 0, 2, 2), (2, 0, 4, 2)], 8),
             ([(-2, -3, 3, 4), (8, 8, 12, 12)], 16),
             ([(12, 12, 15, 15)], 0)]
    for boxes, expected in cases:
        if not math.isclose(rectangle_union_area(boxes, 10, 10), expected, abs_tol=1e-12):
            raise AssertionError((boxes, expected))
    # Independent integer-cell reference covers overlaps, duplicates and clipping.
    grid_boxes = [(-1, 0, 3, 5), (2, 2, 7, 8), (4, -1, 9, 3), (2, 2, 7, 8)]
    reference = sum(any(x0 <= x + .5 < x1 and y0 <= y + .5 < y1
                        for x0, y0, x1, y1 in grid_boxes)
                    for x in range(8) for y in range(8))
    if rectangle_union_area(grid_boxes, 8, 8) != reference:
        raise AssertionError("Rectangle union differs from independent unit-cell reference")
    np.testing.assert_allclose(center_region_distances(np.asarray([[1, 1], [2, 1], [5, 6]]),
                                                       [(0, 0, 2, 2)]), [0, 0, 5])
    if intersects_positive((0, 0, 2, 2), (2, 0, 4, 2)):
        raise AssertionError("Touching boxes must not count as positive-area intersections")
    return {"rectangle_cases": len(cases), "independent_integer_grid_case": 1,
            "point_distance_case": 1, "touching_box_case": 1, "passed": True}


def ratio(numerator: float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def row_rectangle(row: dict) -> Rect:
    cx, cy, width, height = row["pixels"]
    return cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2


def font_path(bold: bool = False) -> Path:
    candidates = [Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")]
    return next(path for path in candidates if path.is_file())


def render_examples(examples: list[dict], images: dict[tuple[int, int], Image.Image]) -> Image.Image:
    if len(examples) != 4:
        raise ValueError("Expected four training videos with clusters, as in the previous audit")
    regular, bold = font_path(), font_path(True)
    f = lambda size, strong=False: ImageFont.truetype(str(bold if strong else regular), size)
    bg, ink, muted = "#f3f6fa", "#142b40", "#4f6376"
    colors = {0: "#12d9c3", 1: "#ffb000", 2: "#ff65df"}
    canvas = Image.new("RGB", (1352, 1376), bg)
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 20), "Agrupamentos nas anotações de treino", fill=ink, font=f(35, True))
    draw.text((28, 67), "Gabarito manual do VISEM-Tracking · nenhum detector executado", fill=muted, font=f(24))
    draw.text((28, 107), "Primeiro quadro com classe 1 em cada um dos quatro vídeos com agrupamentos", fill=muted, font=f(22))
    for number, example in enumerate(examples):
        left, top = 28 + (number % 2) * 668, 164 + (number // 2) * 572
        video, frame = example["video_id"], example["frame"]
        rows = example["rows"]
        image = images[(video, frame)]
        draw.text((left, top), f"{chr(65 + number)} · Vídeo {video} · Quadro {frame}", fill=ink, font=f(24, True))
        image_top = top + 39
        canvas.paste(image, (left, image_top))
        for row in rows:
            if row["class_id"] == 1:
                continue
            x0, y0, x1, y1 = row_rectangle(row)
            draw.rectangle((left + x0, image_top + y0, left + x1, image_top + y1),
                           outline=colors[row["class_id"]], width=1)
        clusters = [row for row in rows if row["class_id"] == 1]
        for index, row in enumerate(clusters, 1):
            x0, y0, x1, y1 = row_rectangle(row)
            draw.rectangle((left + x0, image_top + y0, left + x1, image_top + y1), outline=colors[1], width=4)
            label = f"C{index:02d}"
            label_width = draw.textbbox((0, 0), label, font=f(16, True))[2] + 8
            tx = min(max(left, left + x0), left + 640 - label_width)
            ty = min(max(image_top, image_top + y0 - 24), image_top + 456)
            draw.rectangle((tx, ty, tx + label_width, ty + 22), fill=colors[1])
            draw.text((tx + 4, ty + 1), label, font=f(16, True), fill=ink)
        counts = Counter(row["class_id"] for row in rows)
        draw.text((left, image_top + 490), f"Classe 0: {counts[0]}   |   Classe 1: {counts[1]}   |   Classe 2: {counts[2]}",
                  fill=muted, font=f(19))
    draw.text((28, 1321), "Linhas finas: classes 0 (verde) e 2 (rosa). Laranja: classe 1, agrupamento.", fill=ink, font=f(21))
    draw.text((28, 1350), "C01… identifica caixas nesta figura; IDs originais constam na tabela. Caixa não é segmentação.", fill=muted, font=f(19))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    synthetic = self_test()
    if args.self_test:
        print(json.dumps(synthetic))
        return
    if OUTPUT.exists():
        parser.error("Output exists; no files will be overwritten. Do not delete prior audits to rerun.")
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    audit = previous.Audit()
    configuration = yaml.safe_load(audit.source_text(ROOT / "configs/protocol/splits.yaml", "current_protocol"))
    split = configuration["fixed_split"]
    if tuple(split["train"]) != TRAIN_IDS or set(TRAIN_IDS) & (set(split["val"]) | set(split["test"])):
        parser.error("Training split differs or overlaps validation/test; no data sources opened")
    for code in (Path(__file__), Path(previous.__file__)):
        audit.source_bytes(code, "generator_code")
    git_start = {"commit": previous.git_output("rev-parse", "HEAD"),
                 "status_porcelain": previous.git_output("status", "--porcelain")}
    prior_manifest = json.loads(audit.source_text(PRIOR / "manifest.json", "prior_audit_manifest"))
    if tuple(prior_manifest["configuration"]["video_ids"]) != TRAIN_IDS:
        raise ValueError("Prior geometry audit does not describe the authorized training videos")

    def prior_text(name: str) -> str:
        text = audit.source_text(PRIOR / name, "prior_derived")
        if audit.inputs[-1]["sha256"] != prior_manifest["outputs"][name]["sha256"]:
            raise ValueError(f"Prior artifact differs from its immutable manifest: {name}")
        return text

    prior_summary = json.loads(prior_text("summary.json"))
    prior_inputs = {row["path"]: row for row in csv.DictReader(io.StringIO(prior_text("input_files.csv")))}
    prior_frames = list(csv.DictReader(io.StringIO(prior_text("per_frame_counts.csv"))))
    frame_index = {(int(row["video_id"]), int(row["frame"])): row for row in prior_frames}
    if len(frame_index) != len(prior_frames) or set(v for v, _ in frame_index) != set(TRAIN_IDS):
        raise ValueError("Prior per-frame index is duplicated or contains an unexpected video")

    def verify_source(path: Path) -> None:
        key = previous.relative(path)
        if key not in prior_inputs or audit.inputs[-1]["path"] != key or audit.inputs[-1]["sha256"] != prior_inputs[key]["sha256"]:
            raise ValueError(f"Source differs from previous geometry audit: {path}")

    frame_rows, video_rows = [], []
    first_examples: list[dict] = []
    candidates: dict[str, dict] = {}
    for video in TRAIN_IDS:
        folder = ROOT / "data/sources/visem_tracking/dataset/Train" / str(video) / "labels_ftid"
        labels = audit.index(folder, rf"{video}_frame_(\d+)_with_ftid\.txt", video)
        expected_frames = {frame for (vid, frame), r in frame_index.items()
                           if vid == video and r["annotation_state"] != "unlabeled"}
        if set(labels) != expected_frames:
            raise ValueError(f"Current label frame set differs from prior audit for video {video}")
        counts = Counter()
        area_sum = 0.0
        video_cluster_rows = []
        for frame in sorted(labels):
            prior_frame = frame_index[(video, frame)]
            width, height = int(prior_frame["image_width"]), int(prior_frame["image_height"])
            if (width, height) != (640, 480):
                raise ValueError("Unexpected recorded dimensions")
            rows = audit.parse(labels[frame], video, frame, tracked=True)
            verify_source(labels[frame])
            audit.check_boxes(rows, width, height, labels[frame], video, frame)
            if audit.anomalies or any(not row["valid"] for row in rows):
                raise ValueError(f"Unexpected annotation anomaly: {audit.anomalies[:3]}")
            classes = Counter(row["class_id"] for row in rows)
            if len(rows) != int(prior_frame["valid_rows"]) or any(classes[c] != int(prior_frame[f"valid_class{c}"]) for c in (0, 1, 2)):
                raise ValueError(f"Counts differ from the prior audit: {video}/{frame}")
            counts["annotated_frames"] += 1
            counts["observations"] += len(rows)
            for c in (0, 1, 2):
                counts[f"class{c}_observations"] += classes[c]
            if not classes[1]:
                continue
            individuals = [row for row in rows if row["class_id"] in (0, 2)]
            cluster_boxes = clipped_rectangles([row_rectangle(row) for row in rows if row["class_id"] == 1], width, height)
            area = rectangle_union_area(cluster_boxes, width, height)
            if not 0 < area <= width * height:
                raise ValueError("Invalid cluster union coverage")
            centers = np.asarray([row["pixels"][:2] for row in individuals], dtype=float).reshape(-1, 2)
            distances = center_region_distances(centers, cluster_boxes)
            inside = int((distances == 0).sum())
            overlaps = sum(any(intersects_positive(row_rectangle(row), box) for box in cluster_boxes)
                           for row in individuals)
            record = {"video_id": video, "frame": frame, "width": width, "height": height,
                      "class0_count": classes[0], "cluster_count": classes[1], "class2_count": classes[2],
                      "individual_count": len(individuals), "cluster_only": int(not individuals),
                      "cluster_union_area_px2": area, "cluster_coverage_fraction": area / (width * height),
                      "individual_centers_in_cluster_union": inside,
                      "individual_boxes_intersecting_cluster_union": overlaps}
            counts["frames_with_clusters"] += 1
            counts["cluster_only_frames"] += int(not individuals)
            counts["individual_observations_in_cluster_frames"] += len(individuals)
            counts["individual_centers_in_cluster_union"] += inside
            counts["individual_boxes_intersecting_cluster_union"] += overlaps
            for radius in RADII:
                key = f"individual_centers_within_{radius}px_of_cluster_union"
                record[key] = int((distances <= radius).sum())
                counts[key] += record[key]
            for c in (0, 2):
                key = f"class{c}_centers_in_cluster_union"
                record[key] = sum(distances[i] == 0 for i, row in enumerate(individuals) if row["class_id"] == c)
                record[key] = int(record[key])
                counts[key] += record[key]
            frame_rows.append(record)
            video_cluster_rows.append(record)
            area_sum += area
            example = {"video_id": video, "frame": frame, "rows": rows, "metrics": record}
            if len(video_cluster_rows) == 1:
                first_examples.append(example)
            for name, field in (("max_individual_centers_in_cluster", "individual_centers_in_cluster_union"),
                                ("max_individual_boxes_intersecting_cluster", "individual_boxes_intersecting_cluster_union"),
                                ("max_cluster_coverage", "cluster_coverage_fraction")):
                old = candidates.get(name)
                if old is None or record[field] > old["metrics"][field]:
                    candidates[name] = example
            audit.peak_rss = max(audit.peak_rss, psutil.Process().memory_info().rss)
        prior_video = next(row for row in prior_summary["videos"] if row["video_id"] == video)
        for key, prior_key in (("annotated_frames", "annotated_frames"), ("observations", "valid_rows"),
                               ("class0_observations", "raw_class0"), ("class1_observations", "raw_class1"),
                               ("class2_observations", "raw_class2")):
            if counts[key] != prior_video.get(prior_key, 0):
                raise ValueError(f"Per-video count mismatch: {video} {key}")
        n, n_cluster = counts["annotated_frames"], counts["frames_with_clusters"]
        summary = {"video_id": video, **{key: counts[key] for key in (
            "annotated_frames", "frames_with_clusters", "cluster_only_frames", "observations",
            "class0_observations", "class1_observations", "class2_observations",
            "individual_observations_in_cluster_frames", "individual_centers_in_cluster_union",
            "class0_centers_in_cluster_union", "class2_centers_in_cluster_union",
            "individual_boxes_intersecting_cluster_union", *(f"individual_centers_within_{r}px_of_cluster_union" for r in RADII))},
            "unlabeled_frames_excluded": prior_video.get("unlabeled_frames", 0),
            "cluster_frame_fraction": ratio(n_cluster, n),
            "coverage_mean_all_annotated_frames": ratio(area_sum, n * 640 * 480),
            "coverage_mean_cluster_frames": ratio(area_sum, n_cluster * 640 * 480),
            "coverage_max_frame": max((r["cluster_coverage_fraction"] for r in video_cluster_rows), default=0),
            "individual_centers_inside_fraction_all_individuals": ratio(counts["individual_centers_in_cluster_union"], counts["class0_observations"] + counts["class2_observations"]),
            "individual_centers_inside_fraction_cluster_frames": ratio(counts["individual_centers_in_cluster_union"], counts["individual_observations_in_cluster_frames"])}
        video_rows.append(summary)
        print(json.dumps({"completed_video": video, "cluster_frames": n_cluster,
                          "clusters": counts["class1_observations"]}), flush=True)

    selected = [("first_cluster_in_video", e) for e in first_examples] + list(candidates.items())
    selection_rows, example_rows = [], []
    seen = set()
    for purpose, example in selected:
        video, frame = example["video_id"], example["frame"]
        selection_rows.append({"purpose": purpose, **example["metrics"]})
        if (video, frame) in seen:
            continue
        seen.add((video, frame))
        cluster_number = 0
        for row in example["rows"]:
            cluster_number += int(row["class_id"] == 1)
            x0, y0, x1, y1 = row_rectangle(row)
            example_rows.append({"video_id": video, "frame": frame, "source_line": row["line"],
                                 "class_id": row["class_id"], "track_id": row["track_id"],
                                 "cluster_visual_label": f"C{cluster_number:02d}" if row["class_id"] == 1 else "",
                                 "cx": row["pixels"][0], "cy": row["pixels"][1],
                                 "x_min": x0, "y_min": y0, "x_max": x1, "y_max": y1})
    if len(first_examples) != sum(v.get("raw_class1", 0) > 0 for v in prior_summary["videos"]):
        raise ValueError("Cluster-presence videos differ from prior geometry audit")
    images = {}
    for example in first_examples:
        video, frame = example["video_id"], example["frame"]
        path = ROOT / f"data/sources/visem_tracking/dataset/Train/{video}/images/{video}_frame_{frame}.jpg"
        content = audit.source_bytes(path, "selected_training_jpeg", video, frame)
        verify_source(path)
        with Image.open(io.BytesIO(content)) as source:
            if source.size != (640, 480) or source.format != "JPEG":
                raise ValueError("Selected JPEG dimensions differ from previous audit")
            images[(video, frame)] = source.convert("RGB")
    fonts = [{"path": str(path), "sha256": previous.digest(path)} for path in (font_path(), font_path(True))]
    figure = render_examples(first_examples, images)
    audit.peak_rss = max(audit.peak_rss, psutil.Process().memory_info().rss)
    audit.check_input_metadata()
    totals = {key: sum(row[key] for row in video_rows) for key in (
        "annotated_frames", "frames_with_clusters", "cluster_only_frames", "observations",
        "class0_observations", "class1_observations", "class2_observations",
        "individual_observations_in_cluster_frames", "individual_centers_in_cluster_union",
        "class0_centers_in_cluster_union", "class2_centers_in_cluster_union",
        "individual_boxes_intersecting_cluster_union", "unlabeled_frames_excluded",
        *(f"individual_centers_within_{r}px_of_cluster_union" for r in RADII))}
    def video_mean(key: str) -> float | None:
        values = [row[key] for row in video_rows if row[key] is not None]
        return float(np.mean(values)) if values else None
    summary = {"kind": "training_cluster_region_descriptive_audit", "split": "train", "video_ids": TRAIN_IDS,
               "totals": totals, "videos_with_clusters": len(first_examples),
               "equal_video_weight": {key: video_mean(key) for key in (
                   "cluster_frame_fraction", "coverage_mean_all_annotated_frames", "coverage_mean_cluster_frames",
                   "individual_centers_inside_fraction_all_individuals", "individual_centers_inside_fraction_cluster_frames")},
               "synthetic_checks": synthetic,
               "count_checks_against_prior_audit": "Passed per frame and per video; all labels and four selected JPEGs match prior SHA256.",
               "selected_examples": selection_rows}
    OUTPUT.mkdir(parents=True, exist_ok=False)
    previous.csv_write(OUTPUT / "per_video_clusters.csv", video_rows)
    previous.csv_write(OUTPUT / "frames_with_clusters.csv", frame_rows)
    previous.csv_write(OUTPUT / "selected_examples.csv", selection_rows)
    previous.csv_write(OUTPUT / "example_annotations.csv", example_rows)
    previous.csv_write(OUTPUT / "input_files.csv", audit.inputs)
    previous.json_write(OUTPUT / "summary.json", summary)
    figure.save(OUTPUT / "agrupamentos_primeiros_quadros.png")
    manifest = {"schema_version": 1, "kind": summary["kind"], "started_at_utc": started_utc,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_seconds": time.perf_counter() - started,
                "configuration": {"train_video_ids": TRAIN_IDS, "reference_dimensions": [640, 480],
                                  "cluster_class": 1, "individual_classes": [0, 2], "proximity_radii_px": RADII,
                                  "seed": None, "output": previous.relative(OUTPUT)},
                "prior_audit_manifest": {"path": previous.relative(PRIOR / "manifest.json"),
                                         "sha256": previous.digest(PRIOR / "manifest.json")},
                "git_at_start": git_start,
                "git_at_finish": {"commit": previous.git_output("rev-parse", "HEAD"), "status_porcelain": previous.git_output("status", "--porcelain")},
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "pillow": pillow_version,
                                "scipy": scipy.__version__, "psutil": psutil.__version__, "pyyaml": yaml.__version__,
                                "os": platform.platform(), "processor": platform.processor(),
                                "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
                                "system_ram_bytes": psutil.virtual_memory().total, "figure_fonts": fonts},
                "resources": {"peak_rss_bytes_sampled": audit.peak_rss, "gpu_used": False, "vram_used_bytes": 0},
                "definitions": {
                    "observation": "One annotated object in one frame; repeated IDs in time are repeated observations, not unique cells.",
                    "region": "Continuous geometric union of axis-aligned class1 boxes, clipped to [0,width] x [0,height]; exact rectangle sweep, no pixel rasterization or naive sum of box areas.",
                    "inside": "An individual class0/2 box center lies within/on at least one closed cluster rectangle; each individual observation is counted at most once.",
                    "proximity": "Euclidean distance of each individual center to the cluster-rectangle union <= radius, including centers already inside; not square box expansion. No enlarged-region area is claimed.",
                    "box_intersection": "A class0/2 box intersects at least one cluster rectangle with positive area; tangencies do not count; each observation counted once.",
                    "coverage": "Cluster union area / full frame area. Mean_all includes every annotated frame, assigning zero when no cluster exists. Mean_cluster_frames conditions on cluster presence, null when absent.",
                    "cluster_only": "At least one class1 annotation and no class0/2 annotation in that frame; not a claim that individual cells are absent from the image.",
                    "dimensions": "Per-frame image dimensions from the SHA256-verified previous audit; selected figure JPEGs additionally checked directly.",
                    "selection": "First annotated frame with class1 per training video. Also maximize individual centers inside cluster regions, number of individual boxes intersecting regions, and region coverage; ties choose lowest video ID then frame. Selection never uses model metrics.",
                    "figure": "Four first-cluster training JPEGs at original resolution; manual class0/2 boxes thin, class1 orange, visual C-numbers local to each panel. No algorithmic predictions or synthetic microscopy imagery.",
                    "aggregation": "First per video, then equal-video means of available values. No frame-level independence or inferential tests assumed.",
                    "source_verification": "Every training label and selected JPEG read matches the prior input SHA256. Primary counts checked against previous per-frame and per-video records. Missing annotation frames stay excluded."},
                "limitations": ["Training data only; no validation/test source opened, no detector or tracking run.",
                                "Cluster boxes are annotations, not cell contours, physical objects of known cardinality, or ground-truth segmentation masks.",
                                "Overlap with individual GT is descriptive and does not determine whether detections should be ignored.",
                                "No class policy or matching tolerance changed. No inter-annotator uncertainty, GT completeness, or temporal ID correctness measured.",
                                "Source files and previous artifacts were not modified; existing output is refused."],
                "outputs": {path.name: {"path": previous.relative(path), "sha256": previous.digest(path), "bytes": path.stat().st_size}
                            for path in sorted(OUTPUT.iterdir())}}
    previous.json_write(OUTPUT / "manifest.json", manifest)
    print(json.dumps({"output": previous.relative(OUTPUT), "totals": totals,
                      "equal_video_weight": summary["equal_video_weight"], "runtime_seconds": manifest["runtime_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
