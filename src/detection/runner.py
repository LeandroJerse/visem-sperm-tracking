"""Frame-loop runner: apply a detector to a video, write CSV + annotated video.

Kept separate from ``base_detector`` to avoid an import cycle (``visem_io``
imports ``Detection`` from ``base_detector``; this runner imports both plus the
visualization helpers).
"""
from __future__ import annotations

import statistics
from pathlib import Path

import cv2

from .base_detector import Detector
from .visem_io import (
    detection_to_row,
    list_label_files,
    load_gt_frame,
    write_detections_csv,
)
from .visualize import COLORS, draw_detections, draw_legend, open_writer


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
) -> dict:
    """Run ``detector`` over ``video_path``.

    Writes the unified CSV to ``out_csv``. If ``out_video`` is given, writes an
    annotated mp4 (detections in green; ground truth in red when ``gt_dir`` is
    provided). Ground-truth label files are matched to frames **by sorted
    order** (frame *i* -> i-th label file), which assumes the labels were
    extracted in frame order — verify this alignment on first use.

    Returns a summary dict.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_id = video_id or Path(video_path).stem

    detector.reset()
    gt_files = list_label_files(gt_dir) if gt_dir else None
    writer = open_writer(out_video, fps, (w, h)) if out_video else None

    rows: list[dict] = []
    n_det = 0
    frame_idx = 0
    per_frame_counts: list[int] = []
    while True:
        if max_frames is not None and frame_idx >= max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break

        dets = detector.detect(frame)
        for i, d in enumerate(dets):
            if d.object_id < 0:
                d.object_id = i
            rows.append(detection_to_row(video_id, frame_idx, "detection", d))
        n_det += len(dets)
        per_frame_counts.append(len(dets))

        gt: list = []
        if gt_files is not None and frame_idx < len(gt_files):
            gt = load_gt_frame(gt_files[frame_idx], w, h)
            for d in gt:
                rows.append(detection_to_row(video_id, frame_idx, "manual", d))

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
    mean_pf = statistics.fmean(per_frame_counts) if per_frame_counts else 0.0
    median_pf = statistics.median(per_frame_counts) if per_frame_counts else 0.0
    summary = {
        "video_id": video_id,
        "method": detector.name,
        "frames": frame_idx,
        "detections": n_det,
        "det_per_frame_mean": round(mean_pf, 2),
        "det_per_frame_median": round(float(median_pf), 2),
        "det_per_frame_max": max(per_frame_counts) if per_frame_counts else 0,
        "rows": len(rows),
        "csv": str(out_csv),
        "video": str(out_video) if out_video else None,
    }
    if verbose:
        print(
            f"[{detector.name}] {video_id}: {frame_idx} frames, "
            f"{n_det} detections -> {out_csv}"
        )
    return summary
