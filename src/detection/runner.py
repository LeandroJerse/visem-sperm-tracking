"""Frame-loop runner: apply a detector to a video, write CSV + annotated video.

Kept separate from ``base`` to avoid an import cycle (``io`` imports
``Detection`` from ``base``; this runner imports both plus the
visualization helpers).
"""
from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from src.core.artifacts import write_csv_exclusive
from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    DEFAULT_SENSITIVITY_GATES_PX,
    DetectionEvaluator,
    evaluate_frame,
    write_frame_metrics_csv,
)
from src.experiments.resources import ResourceMonitor

from .base import Detection, Detector
from .io import (
    CSV_FIELDS,
    detection_to_row,
    index_label_files,
    load_gt_for_frame,
    write_detections_csv,
)
from .visualization import COLORS, draw_detections, draw_legend, open_writer
from .strict_inputs import FullVideoInput


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
    full_video_input: FullVideoInput | None = None,
    progress_callback: Callable[[int, list[Detection]], None] | None = None,
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

    With ``full_video_input``, reject partial/extra/invalid decoded frames and
    consume only its already-validated GT. The callback receives frame index
    and all predictions after detection, before matching/export; raising aborts.
    Strict failures preserve completed-frame CSVs when possible and re-raise.
    Source hashes must be rechecked with ``verify_current`` before batch completion.

    Returns a summary dict only on successful completion.
    """
    if warmup_frames < 0:
        raise ValueError("warmup_frames must be non-negative")
    video_id = video_id or Path(video_path).stem
    if out_frames_csv is None:
        csv_path = Path(out_csv)
        out_frames_csv = csv_path.with_name(f"{csv_path.stem}_frames.csv")
    if full_video_input is not None:
        if not isinstance(full_video_input, FullVideoInput):
            raise TypeError("full_video_input must be prepared by prepare_full_video_input")
        full_video_input.assert_matches(video_path, gt_dir, video_id)
        if max_frames is not None or warmup_frames != 0:
            raise ValueError("Strict full-video execution forbids max_frames and warmup_frames")
        targets = [Path(path).resolve() for path in (out_csv, out_frames_csv, out_video) if path is not None]
        if len(set(targets)) != len(targets):
            raise ValueError("Strict output paths must be distinct")
        for target in targets:
            if target.is_relative_to(full_video_input.video_path.parent):
                raise ValueError("Strict outputs must not be written inside the source video folder")
            if target.exists():
                raise FileExistsError(f"Strict execution will not overwrite an output: {target}")
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
    cap = None
    writer = None
    extra_read_eof = False

    def write_outputs() -> None:
        if full_video_input is None:
            write_detections_csv(rows, out_csv)
            write_frame_metrics_csv(evaluator.frames, out_frames_csv)
            return
        for target in (Path(out_csv), Path(out_frames_csv)):
            target.parent.mkdir(parents=True, exist_ok=True)
        write_csv_exclusive(out_csv, rows, CSV_FIELDS)
        fields = list(evaluate_frame([], None, sensitivity_gates_px=()).keys())
        fields += sorted({key for row in evaluator.frames for key in row} - set(fields))
        write_csv_exclusive(out_frames_csv, evaluator.frames, fields)

    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if full_video_input is not None:
            for name, prop, expected in (
                ("width", cv2.CAP_PROP_FRAME_WIDTH, full_video_input.expected_width),
                ("height", cv2.CAP_PROP_FRAME_HEIGHT, full_video_input.expected_height),
                ("frame_count", cv2.CAP_PROP_FRAME_COUNT, full_video_input.expected_frame_count),
            ):
                if cap.get(prop) != expected:
                    raise ValueError(f"Decoded video metadata {name} differs from the prepared input")
        detector.reset()
        gt_index = index_label_files(gt_dir) if gt_dir and full_video_input is None else None
        writer = open_writer(out_video, fps, (w, h)) if out_video else None
        while True:
            if max_frames is not None and frame_idx >= max_frames:
                break
            ok, frame = cap.read()
            if full_video_input is not None:
                if frame_idx == full_video_input.expected_frame_count:
                    if ok:
                        raise ValueError("Video has extra decoded frames beyond the prepared universe")
                    extra_read_eof = True
                    break
                if not ok:
                    raise ValueError(
                        f"Premature EOF after {frame_idx} frames; expected {full_video_input.expected_frame_count}"
                    )
                if (not isinstance(frame, np.ndarray) or frame.shape != (h, w, 3)
                        or frame.dtype != np.uint8):
                    raise ValueError(f"Decoded frame {frame_idx} has invalid dimensions/type; expected uint8 BGR {w}x{h}")
            elif not ok:
                break
            started = time.perf_counter()
            dets = detector.detect(frame)
            detection_ms = (time.perf_counter() - started) * 1000.0
            resources.sample()
            if progress_callback is not None:
                progress_callback(frame_idx, dets)
            if frame_idx < warmup_frames:
                frame_idx += 1
                continue
            frame_rows = []
            for i, d in enumerate(dets):
                if d.object_id is None or (
                    isinstance(d.object_id, (int, float)) and d.object_id < 0
                ):
                    d.object_id = i
                frame_rows.append(detection_to_row(video_id, frame_idx, "detection", d))
            gt: list = []
            annotated = False
            if full_video_input is not None:
                gt_frame = full_video_input.gt_frame(frame_idx)
            elif gt_index is not None:
                gt_frame = load_gt_for_frame(gt_dir, frame_idx, w, h, label_index=gt_index)
            else:
                gt_frame = None
            if gt_frame is not None:
                annotated = gt_frame.annotated
                gt = list(gt_frame.detections)
                frame_rows.extend(detection_to_row(video_id, frame_idx, "manual", d) for d in gt)
            frame_metrics = evaluator.add_frame(
                dets, gt if annotated else None, video_id=video_id, frame=frame_idx,
                annotated=annotated, detection_ms=detection_ms,
            )
            frame_metrics["evaluation_protocol_id"] = evaluation_protocol_id
            rows.extend(frame_rows)
            n_det += len(dets)
            per_frame_counts.append(len(dets))
            detection_times_ms.append(detection_ms)
            frame_idx += 1
            if writer is not None:
                vis = frame.copy()
                draw_detections(vis, dets, COLORS["detection"], draw_mode)
                legend = [(f"detection ({detector.name})", COLORS["detection"])]
                if gt:
                    draw_detections(vis, gt, COLORS["manual"], "box", draw_id=True)
                    legend.append(("manual GT", COLORS["manual"]))
                draw_legend(vis, legend)
                writer.write(vis)
            if verbose and frame_idx % 50 == 0:
                print(f"  ...{frame_idx} frames ({n_det} detections so far)")
        if full_video_input is not None and (
            not extra_read_eof or frame_idx != full_video_input.expected_frame_count
            or len(evaluator.frames) != full_video_input.expected_frame_count
        ):
            raise ValueError("Strict decoded/evaluated frame universe is incomplete")
    except BaseException as exc:
        if full_video_input is not None:
            try:
                write_outputs()
            except Exception as output_error:
                exc.add_note(f"Could not preserve all partial CSVs: {output_error}")
        raise
    finally:
        try:
            if cap is not None:
                cap.release()
        finally:
            if writer is not None:
                writer.release()
    write_outputs()
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
    if full_video_input is not None:
        summary["full_video_input"] = full_video_input.reference()
        summary["completeness"] = {
            "status": "complete", "expected_frames": full_video_input.expected_frame_count,
            "decoded_frames": frame_idx, "frame_metric_rows": len(evaluator.frames),
            "extra_read_eof": extra_read_eof,
            "input_hash_verification": "required_before_batch_completion",
        }
    if verbose:
        print(
            f"[{detector.name}] {video_id}: {frame_idx} frames, "
            f"{n_det} detections -> {out_csv}"
        )
    return summary
