"""Threshold frame-screening battery restricted by the official split.

Runs a fixed set of configurations on N frames of every tracked video and
writes per-video ``comparisons.csv`` (via single_frame) plus a global
``data/tests/detection/threshold/_comparisons/frame_screening/<evaluation_protocol_id>/batch_<timestamp>.csv``
aggregating the official spatial F1 first by video, plus count diagnostics,
per configuration.

Usage
-----
Default (10 configs × 3 frames × 12 training videos = 360 runs)::

    python -m script.detection.test.threshold.batch_frames

Custom frames and output dir::

    python -m script.detection.test.threshold.batch_frames --frames 0 100 500

Dry-run (prints the plan without executing)::

    python -m script.detection.test.threshold.batch_frames --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

from src.core.paths import EXPERIMENT_TESTS_ROOT, REPOSITORY_ROOT
from src.detection.discovery import discover_tracked_ids
from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_SENSITIVITY_GATES_PX,
    aggregate_frame_metrics,
)
from src.experiments.dataset import load_split_spec

from .single_frame import EVALUATION_PROTOCOL_ID, main as run_single_frame

DEFAULT_TEST_ROOT = EXPERIMENT_TESTS_ROOT / "detection"

# ---------------------------------------------------------------------------
# Configurations to benchmark.
# Each entry: (label, overrides_dict).
# label is human-readable and used in the global summary.
# ---------------------------------------------------------------------------
CONFIGS: list[tuple[str, dict]] = [
    ("otsu__o1_c1",       {}),
    ("otsu__o1_c0",       {"close_iterations": 0}),
    ("otsu__o2_c1",       {"morph_iterations": 2}),
    ("t180__o1_c1",       {"threshold_value": 180}),
    ("t190__o1_c1",       {"threshold_value": 190}),
    ("t200__o1_c0",       {"threshold_value": 200, "close_iterations": 0}),
    ("t200__o1_c1",       {"threshold_value": 200}),
    ("t200__o1_c2",       {"threshold_value": 200, "close_iterations": 2}),
    ("t200__o2_c1",       {"threshold_value": 200, "morph_iterations": 2}),
    ("t210__o1_c1",       {"threshold_value": 210}),
]

GLOBAL_FIELDS = [
    "timestamp", "split", "config", "overrides",
    "evaluation_protocol_id", "metric_primary", "center_gate_px", "sensitivity_gates_px",
    "n_runs", "n_videos", "n_frames_per_video",
    "mean_diff", "median_diff", "std_diff",
    "mean_ratio", "median_ratio",
    "mean_abs_diff", "median_abs_diff",
    "macro_video_f1", "mean_frame_f1", "total_tp", "total_fp", "total_fn",
    "macro_video_f1_at_15px", "mean_frame_f1_at_15px", "total_tp_at_15px", "total_fp_at_15px", "total_fn_at_15px",
    "macro_video_f1_at_20px", "mean_frame_f1_at_20px", "total_tp_at_20px", "total_fp_at_20px", "total_fn_at_20px",
]


def _overrides_to_argv(overrides: dict) -> list[str]:
    argv: list[str] = []
    for key, val in overrides.items():
        argv += ["--set", f"{key}={val}"]
    return argv


def run_battery(
    video_ids: list[str],
    frames: list[int],
    dry_run: bool,
    split_name: str,
) -> None:
    total = len(CONFIGS) * len(video_ids) * len(frames)
    print(f"Bateria: {len(CONFIGS)} configs × {len(video_ids)} vídeos × {len(frames)} frames = {total} runs")
    print(f"Configs: {', '.join(c for c, _ in CONFIGS)}")
    print(f"Vídeos : {', '.join(video_ids)}")
    print(f"Frames : {frames}")
    if dry_run:
        print("\n[dry-run] Nenhuma execução realizada.")
        return

    # config_label -> annotated frame records across all videos.
    results: dict[str, list[dict]] = {c: [] for c, _ in CONFIGS}

    run_n = 0
    for label, overrides in CONFIGS:
        print(f"\n{'='*60}")
        print(f"Config: {label}  overrides={overrides}")
        for vid in video_ids:
            for frame_idx in frames:
                run_n += 1
                argv = (
                    ["--method", "threshold", "--id", vid,
                     "--frame", str(frame_idx),
                     "--no-stages"]
                    + _overrides_to_argv(overrides)
                )
                try:
                    summary = run_single_frame(argv)
                    diff   = summary["count_diff"]
                    ratio  = summary["count_ratio"]
                    n_gt   = summary["n_ground_truth"]
                    n_det  = summary["n_detections"]
                    gt_str = f"objetos GT brutos={n_gt}"
                    sign   = "+" if diff > 0 else ""
                    message = (
                        f"  [{run_n}/{total}] {vid} f{frame_idx}: "
                        f"det={n_det} {gt_str} diff={sign}{diff}"
                    )
                    if ratio is not None:
                        message += f" ratio={ratio:.3f}"
                    print(message)
                    results[label].append(
                        {
                            **summary,
                            "video_id": vid,
                            "count_diff": diff,
                            "count_ratio": ratio,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{run_n}/{total}] {vid} f{frame_idx}: ERRO — {exc}")

    _write_global_summary(results, frames, video_ids, split_name)


def _write_global_summary(
    results: dict[str, list[dict]],
    frames: list[int],
    video_ids: list[str],
    split_name: str,
) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = (
        DEFAULT_TEST_ROOT / "threshold" / "_comparisons" / "frame_screening"
        / EVALUATION_PROTOCOL_ID
        / f"batch_{ts}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for label, overrides in CONFIGS:
        records = results[label]
        diffs = [int(record["count_diff"]) for record in records]
        ratios = [
            float(record["count_ratio"])
            for record in records
            if record["count_ratio"] is not None
        ]
        abs_diffs = [abs(d) for d in diffs]
        video_summaries = [
            aggregate_frame_metrics(records, video_id=video_id)
            for video_id in video_ids
            if any(record["video_id"] == video_id for record in records)
        ]
        spatial_metrics: dict = {}
        for key in sorted({key for row in video_summaries for key in row
                           if key.startswith(("count_mae", "count_bias"))}):
            values = [float(row[key]) for row in video_summaries if row.get(key) is not None]
            spatial_metrics[f"macro_video_{key}"] = statistics.mean(values) if values else ""
        for suffix in ("", *(f"_at_{gate:g}px" for gate in DEFAULT_SENSITIVITY_GATES_PX)):
            video_f1 = [row[f"f1{suffix}"] for row in video_summaries if row.get(f"f1{suffix}") is not None]
            frame_f1 = [record[f"f1{suffix}"] for record in records if record.get(f"f1{suffix}") is not None]
            spatial_metrics.update({
                f"macro_video_f1{suffix}": round(statistics.mean(video_f1), 6) if video_f1 else "",
                f"mean_frame_f1{suffix}": round(statistics.mean(frame_f1), 6) if frame_f1 else "",
                f"n_videos_primary_evaluable{suffix}": len(video_f1),
                f"total_tp{suffix}": sum(row.get(f"tp{suffix}") or 0 for row in video_summaries),
                f"total_fp{suffix}": sum(row.get(f"fp{suffix}") or 0 for row in video_summaries),
                f"total_fn{suffix}": sum(row.get(f"fn{suffix}") or 0 for row in video_summaries),
            })
        for key in sorted({key for row in video_summaries for key in row}):
            if key.startswith(("n_predictions_", "n_ground_truth_", "n_gt_", "frames_", "count_evaluated_frames", "count_error", "count_abs_error")):
                spatial_metrics[f"total_{key}"] = sum(int(row.get(key) or 0) for row in video_summaries)
            if key.startswith("secondary_all_objects_"):
                if any(key.startswith(f"secondary_all_objects_{metric}") for metric in (
                    "precision", "recall", "f1", "count_mae", "count_bias", "center_error_mean_px",
                )):
                    values = [float(row[key]) for row in video_summaries if row.get(key) is not None]
                    spatial_metrics[f"macro_video_{key}"] = statistics.mean(values) if values else ""
                else:
                    spatial_metrics[f"total_{key}"] = sum(row.get(key) or 0 for row in video_summaries)

        row: dict = {
            "timestamp": ts,
            "split": split_name,
            "config": label,
            "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
            "metric_primary": f"macro_video_f1_individuals_center_{DEFAULT_CENTER_GATE_PX:g}px",
            "center_gate_px": DEFAULT_CENTER_GATE_PX,
            "sensitivity_gates_px": json.dumps(DEFAULT_SENSITIVITY_GATES_PX),
            "class_policy": DEFAULT_CLASS_POLICY,
            "count_scope": "scored_predictions_minus_individually_annotated_gt",
            "overrides": str({k: v for k, v in sorted(
                next((ov for lbl, ov in CONFIGS if lbl == label), {}).items()
            )}),
            "n_runs": len(records),
            "n_videos": len(video_ids),
            "n_frames_per_video": len(frames),
            "mean_diff":       round(statistics.mean(diffs), 3)      if diffs   else "",
            "median_diff":     round(statistics.median(diffs), 3)    if diffs   else "",
            "std_diff":        round(statistics.stdev(diffs), 3)     if len(diffs) > 1 else "",
            "mean_ratio":      round(statistics.mean(ratios), 3)     if ratios  else "",
            "median_ratio":    round(statistics.median(ratios), 3)   if ratios  else "",
            "mean_abs_diff":   round(statistics.mean(abs_diffs), 3)  if abs_diffs else "",
            "median_abs_diff": round(statistics.median(abs_diffs), 3) if abs_diffs else "",
            **spatial_metrics,
        }
        rows.append(row)

    with open(out_path, "x", newline="", encoding="utf-8") as f:
        extra_fields = sorted({key for row in rows for key in row} - set(GLOBAL_FIELDS))
        writer = csv.DictWriter(f, fieldnames=GLOBAL_FIELDS + extra_fields)
        writer.writeheader()
        writer.writerows(rows)

    # Promotion follows macro F1 by video; count MAE only breaks ties.
    ranked = sorted(
        rows,
        key=lambda row: (
            -float(row["macro_video_f1"])
            if row["macro_video_f1"] != "" else float("inf"),
            float(row["macro_video_count_mae"])
            if row["macro_video_count_mae"] != "" else float("inf"),
        ),
    )
    print(f"\n{'='*60}")
    print(f"RESUMO GLOBAL — {out_path}")
    print(
        f"{'Config':<22} {'macro_F1':>10} {'frame_F1':>10} "
        f"{'mean_abs_diff':>14} {'mean_ratio':>11}"
    )
    print("-" * 78)
    for r in ranked:
        print(
            f"  {r['config']:<20} {str(r['macro_video_f1']):>10} "
            f"{str(r['mean_frame_f1']):>10} {str(r['mean_abs_diff']):>14} "
            f"{str(r['mean_ratio']):>11}"
        )
    print(f"\nSalvo em: {out_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bateria de testes: threshold × vídeos rastreados.")
    p.add_argument("--frames", nargs="+", type=int, default=[0, 50, 100],
                   help="Frames a testar por vídeo (default: 0 50 100).")
    p.add_argument("--ids", nargs="+", default=None,
                   help="IDs customizados; vídeos do teste são sempre rejeitados.")
    p.add_argument(
        "--split",
        choices=["train", "val"],
        default="train",
        help="Split permitido quando --ids não é usado (default: train).",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Mostra o plano sem executar.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    split = load_split_spec(
        REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml"
    )
    available = set(discover_tracked_ids())
    if args.ids:
        video_ids = [str(video_id) for video_id in args.ids]
        blocked = sorted(set(video_ids) & set(split.test))
        if blocked:
            raise SystemExit(
                "A bancada de tuning não pode abrir o teste bloqueado: "
                + ", ".join(blocked)
            )
        outside = sorted(set(video_ids) - (set(split.train) | set(split.val)))
        if outside:
            raise SystemExit("IDs fora de treino/validação: " + ", ".join(outside))
        split_name = "custom_train_val"
    else:
        video_ids = list(split.ids_for(args.split))
        split_name = args.split
    missing = sorted(set(video_ids) - available)
    if missing:
        raise SystemExit("Vídeos anotados não encontrados: " + ", ".join(missing))
    if not video_ids:
        raise SystemExit(
            "Nenhum vídeo anotado encontrado em "
            "data/sources/visem_tracking/dataset/Train/."
        )
    run_battery(video_ids, args.frames, args.dry_run, split_name)


if __name__ == "__main__":
    main()
