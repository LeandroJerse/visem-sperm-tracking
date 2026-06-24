"""Battery test: threshold configurations across all tracked VISEM videos.

Runs a fixed set of configurations on N frames of every tracked video and
writes per-video ``comparisons.csv`` (via single_frame) plus a global
``results/tests/batch_<timestamp>.csv`` aggregating mean/median diff and ratio
per configuration.

Usage
-----
Default (10 configs × 3 frames × all 20 videos = 600 runs)::

    python -m tests.sandbox.batch

Custom frames and output dir::

    python -m tests.sandbox.batch --frames 0 100 500 --out-dir results/tests

Dry-run (prints the plan without executing)::

    python -m tests.sandbox.batch --dry-run
"""
from __future__ import annotations

import argparse
import csv
import statistics
from datetime import datetime
from pathlib import Path

from src.detection.interactive import discover_ids

from .single_frame import main as run_single_frame

TRAIN_ROOT = Path("data/tracked/VISEM_Tracking_Train_v4/Train")

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
    "timestamp", "config", "overrides",
    "n_runs", "n_videos", "n_frames_per_video",
    "mean_diff", "median_diff", "std_diff",
    "mean_ratio", "median_ratio",
    "mean_abs_diff", "median_abs_diff",
]


def _overrides_to_argv(overrides: dict) -> list[str]:
    argv: list[str] = []
    for key, val in overrides.items():
        argv += ["--set", f"{key}={val}"]
    return argv


def run_battery(
    video_ids: list[str],
    frames: list[int],
    out_dir: str,
    dry_run: bool,
) -> None:
    total = len(CONFIGS) * len(video_ids) * len(frames)
    print(f"Bateria: {len(CONFIGS)} configs × {len(video_ids)} vídeos × {len(frames)} frames = {total} runs")
    print(f"Configs: {', '.join(c for c, _ in CONFIGS)}")
    print(f"Vídeos : {', '.join(video_ids)}")
    print(f"Frames : {frames}")
    if dry_run:
        print("\n[dry-run] Nenhuma execução realizada.")
        return

    # config_label -> list of (diff, ratio) across all runs
    results: dict[str, list[tuple[int, float | None]]] = {c: [] for c, _ in CONFIGS}

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
                     "--no-stages", "--out-dir", out_dir]
                    + _overrides_to_argv(overrides)
                )
                try:
                    summary = run_single_frame(argv)
                    diff   = summary["count_diff"]
                    ratio  = summary["count_ratio"]
                    n_gt   = summary["n_ground_truth"]
                    n_det  = summary["n_detections"]
                    gt_str = f"GT={n_gt}" if n_gt > 0 else "sem GT"
                    sign   = "+" if diff > 0 else ""
                    print(f"  [{run_n}/{total}] {vid} f{frame_idx}: "
                          f"det={n_det} {gt_str} diff={sign}{diff} "
                          f"ratio={ratio:.3f}" if ratio is not None
                          else f"  [{run_n}/{total}] {vid} f{frame_idx}: det={n_det} {gt_str}")
                    results[label].append((diff, ratio))
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{run_n}/{total}] {vid} f{frame_idx}: ERRO — {exc}")

    _write_global_summary(results, frames, video_ids, out_dir)


def _write_global_summary(
    results: dict[str, list[tuple[int, float | None]]],
    frames: list[int],
    video_ids: list[str],
    out_dir: str,
) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(out_dir) / f"batch_{ts}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for label, overrides in CONFIGS:
        pairs = results[label]
        diffs  = [d for d, _ in pairs]
        ratios = [r for _, r in pairs if r is not None]
        abs_diffs = [abs(d) for d in diffs]

        row: dict = {
            "timestamp": ts,
            "config": label,
            "overrides": str({k: v for k, v in sorted(
                next((ov for lbl, ov in CONFIGS if lbl == label), {}).items()
            )}),
            "n_runs": len(pairs),
            "n_videos": len(video_ids),
            "n_frames_per_video": len(frames),
            "mean_diff":       round(statistics.mean(diffs), 3)      if diffs   else "",
            "median_diff":     round(statistics.median(diffs), 3)    if diffs   else "",
            "std_diff":        round(statistics.stdev(diffs), 3)     if len(diffs) > 1 else "",
            "mean_ratio":      round(statistics.mean(ratios), 3)     if ratios  else "",
            "median_ratio":    round(statistics.median(ratios), 3)   if ratios  else "",
            "mean_abs_diff":   round(statistics.mean(abs_diffs), 3)  if abs_diffs else "",
            "median_abs_diff": round(statistics.median(abs_diffs), 3) if abs_diffs else "",
        }
        rows.append(row)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GLOBAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # Print ranking by mean_abs_diff (lower = better).
    ranked = sorted(rows, key=lambda r: float(r["mean_abs_diff"]) if r["mean_abs_diff"] != "" else 9999)
    print(f"\n{'='*60}")
    print(f"RESUMO GLOBAL — {out_path}")
    print(f"{'Config':<22} {'mean_diff':>10} {'median_diff':>12} {'mean_abs_diff':>14} {'mean_ratio':>11}")
    print("-" * 72)
    for r in ranked:
        print(f"  {r['config']:<20} {str(r['mean_diff']):>10} {str(r['median_diff']):>12} "
              f"{str(r['mean_abs_diff']):>14} {str(r['mean_ratio']):>11}")
    print(f"\nSalvo em: {out_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bateria de testes: threshold × vídeos rastreados.")
    p.add_argument("--frames", nargs="+", type=int, default=[0, 50, 100],
                   help="Frames a testar por vídeo (default: 0 50 100).")
    p.add_argument("--ids", nargs="+", default=None,
                   help="IDs dos vídeos (default: todos os disponíveis).")
    p.add_argument("--out-dir", default="results/tests",
                   help="Raiz das saídas (default: results/tests).")
    p.add_argument("--dry-run", action="store_true",
                   help="Mostra o plano sem executar.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    video_ids = args.ids or discover_ids()
    if not video_ids:
        raise SystemExit("Nenhum vídeo anotado encontrado em data/tracked/.")
    run_battery(video_ids, args.frames, args.out_dir, args.dry_run)


if __name__ == "__main__":
    main()
