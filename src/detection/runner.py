"""Frame-loop runner: apply a detector to a video, write CSV + annotated video.

Kept separate from ``base`` to avoid an import cycle (``io`` imports
``Detection`` from ``base``; this runner imports both plus the
visualization helpers).
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path

import cv2

from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    DEFAULT_SENSITIVITY_GATES_PX,
    DetectionEvaluator,
    write_frame_metrics_csv,
)
from src.experiments.resources import ResourceMonitor

from .base import Detector
from .io import (
    detection_to_row,
    index_label_files,
    load_gt_for_frame,
    write_detections_csv,
)
from .visualization import COLORS, draw_detections, draw_legend, open_writer


def _percentile(values: list[float], percentile: float) -> float:
    """Linear-interpolated percentile without a NumPy dependency here."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def run_on_video(
    detector: Detector,
    video_path: str | Path,
    out_csv: str | Path,
    out_video: str | Path | None = None,
    video_id: str | None = None,
    gt_dir: str | Path | None = None,
    max_frames: int | None = None,
    draw_mode: str = "both",
    verbose: bool = True,
    out_frames_csv: str | Path | None = None,
    center_gate_px: float = DEFAULT_CENTER_GATE_PX,
    class_policy: str = DEFAULT_CLASS_POLICY,
    sensitivity_gates_px: tuple[float, ...] | list[float] = DEFAULT_SENSITIVITY_GATES_PX,
    warmup_frames: int = 0,
) -> dict:
    """Run ``detector`` over ``video_path``.

    Writes the unified CSV to ``out_csv``. If ``out_video`` is given, writes an
    annotated mp4 (detections in green; ground truth in red when ``gt_dir`` is
    provided). Ground-truth label files are matched through the frame number
    encoded in each filename. Missing files are marked unannotated and excluded
    from metrics; existing empty files remain valid annotated negative frames.

    A companion per-frame CSV is always written (``<out_csv>_frames.csv`` by
    default). It stores annotation status, official one-to-one metrics and
    detector timing, including frames with zero objects.

    Returns a summary dict.
    """
    if warmup_frames < 0:
        raise ValueError("warmup_frames must be non-negative")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_id = video_id or Path(video_path).stem

    detector.reset()
    gt_index = index_label_files(gt_dir) if gt_dir else None
    writer = open_writer(out_video, fps, (w, h)) if out_video else None
    evaluator = DetectionEvaluator(
        center_gate_px=center_gate_px,
        class_policy=class_policy,
        sensitivity_gates_px=sensitivity_gates_px,
    )
    evaluation_protocol_id = (
        DEFAULT_EVALUATION_PROTOCOL_ID
        if evaluator.class_policy == DEFAULT_CLASS_POLICY
        and evaluator.center_gate_px == DEFAULT_CENTER_GATE_PX
        and sorted(evaluator.sensitivity_gates_px) == sorted(DEFAULT_SENSITIVITY_GATES_PX)
        else None
    )
    resources = ResourceMonitor()

    rows: list[dict] = []
    n_det = 0
    frame_idx = 0
    per_frame_counts: list[int] = []
    detection_times_ms: list[float] = []
    while True:
        if max_frames is not None and frame_idx >= max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break

        started = time.perf_counter()
        dets = detector.detect(frame)
        detection_ms = (time.perf_counter() - started) * 1000.0
        resources.sample()
        if frame_idx < warmup_frames:
            frame_idx += 1
            continue
        detection_times_ms.append(detection_ms)
        for i, d in enumerate(dets):
            if d.object_id is None or (
                isinstance(d.object_id, (int, float)) and d.object_id < 0
            ):
                d.object_id = i
            rows.append(detection_to_row(video_id, frame_idx, "detection", d))
        n_det += len(dets)
        per_frame_counts.append(len(dets))

        gt: list = []
        annotated = False
        if gt_index is not None:
            gt_frame = load_gt_for_frame(
                gt_dir, frame_idx, w, h, label_index=gt_index
            )
            annotated = gt_frame.annotated
            gt = list(gt_frame.detections)
            for d in gt:
                rows.append(detection_to_row(video_id, frame_idx, "manual", d))
        frame_metrics = evaluator.add_frame(
            dets,
            gt if annotated else None,
            video_id=video_id,
            frame=frame_idx,
            annotated=annotated,
            detection_ms=detection_ms,
        )
        frame_metrics["evaluation_protocol_id"] = evaluation_protocol_id

        if writer is not None:
            vis = frame.copy()
            draw_detections(vis, dets, COLORS["detection"], draw_mode)
            legend = [(f"detection ({detector.name})", COLORS["detection"])]
            if gt:
                draw_detections(vis, gt, COLORS["manual"], "box", draw_id=True)
                legend.append(("manual GT", COLORS["manual"]))
            draw_legend(vis, legend)
            writer.write(vis)

        frame_idx += 1
        if verbose and frame_idx % 50 == 0:
            print(f"  ...{frame_idx} frames ({n_det} detections so far)")

    cap.release()
    if writer is not None:
        writer.release()

    write_detections_csv(rows, out_csv)
    if out_frames_csv is None:
        csv_path = Path(out_csv)
        out_frames_csv = csv_path.with_name(f"{csv_path.stem}_frames.csv")
    write_frame_metrics_csv(evaluator.frames, out_frames_csv)
    mean_pf = statistics.fmean(per_frame_counts) if per_frame_counts else 0.0
    median_pf = statistics.median(per_frame_counts) if per_frame_counts else 0.0
    evaluation = evaluator.summary(video_id)
    summary = {
        **evaluation,
        "video_id": video_id,
        "method": detector.name,
        "frames": frame_idx,
        "scored_frames": len(per_frame_counts),
        "warmup_frames": min(frame_idx, warmup_frames),
        "detections": n_det,
        "det_per_frame_mean": round(mean_pf, 2),
        "det_per_frame_median": round(float(median_pf), 2),
        "det_per_frame_max": max(per_frame_counts) if per_frame_counts else 0,
        "rows": len(rows),
        "csv": str(out_csv),
        "frames_csv": str(out_frames_csv),
        "video": str(out_video) if out_video else None,
        "class_policy": evaluator.class_policy,
        "center_gate_px": evaluator.center_gate_px,
        "sensitivity_gates_px": list(evaluator.sensitivity_gates_px),
        "evaluation_protocol_id": evaluation_protocol_id,
        "metric_primary": (
            f"f1_individuals_center_{evaluator.center_gate_px:g}px"
            if evaluator.class_policy == DEFAULT_CLASS_POLICY
            else f"f1_center_{evaluator.center_gate_px:g}px"
        ),
        "count_scope": (
            "scored_predictions_minus_individually_annotated_gt"
            if evaluator.class_policy == DEFAULT_CLASS_POLICY else "all_annotated_objects"
        ),
        "annotated_frames": evaluation["frames_annotated"],
        "unannotated_frames": evaluation["frames_unannotated"],
        "tp": evaluation["tp"],
        "fp": evaluation["fp"],
        "fn": evaluation["fn"],
        "precision": evaluation["precision"],
        "recall": evaluation["recall"],
        "f1": evaluation["f1"],
        "center_error_mean_px": evaluation["center_error_mean_px"],
        "count_mae": evaluation["count_mae"],
        "count_bias": evaluation["count_bias"],
        "detection_ms_mean": round(statistics.fmean(detection_times_ms), 4)
        if detection_times_ms else 0.0,
        "detection_ms_median": round(float(statistics.median(detection_times_ms)), 4)
        if detection_times_ms else 0.0,
        "detection_ms_p95": round(_percentile(detection_times_ms, 0.95), 4),
        "detection_ms_max": round(max(detection_times_ms), 4)
        if detection_times_ms else 0.0,
    }
    summary.update(resources.summary())
    if verbose:
        print(
            f"[{detector.name}] {video_id}: {frame_idx} frames, "
            f"{n_det} detections -> {out_csv}"
        )
    return summary
