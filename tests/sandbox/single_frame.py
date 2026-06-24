"""Run ONE detector on ONE frame and dump every stage to ``results/tests/``.

This is a manual tuning sandbox — not pytest. Pick a video, a frame, a method,
optionally override the detector's constructor parameters, and inspect what each
stage produced.

Examples
--------
Threshold on the first frame of annotated video 11 (ground truth overlaid)::

    python -m tests.sandbox.single_frame --method threshold --id 11 --frame 0

Background subtraction on frame 50, priming the model with 30 prior frames::

    python -m tests.sandbox.single_frame --method bgsub --id 11 --frame 50 --warmup 30

Blob on a raw video with tuned area limits::

    python -m tests.sandbox.single_frame --method blob \
        --video "data/raw/videos/1_09.09.02_SSW.avi" --frame 100 \
        --set min_area=3 --set max_area=150

Output (one folder per run) under ``results/tests/<method>__<video>__f<frame>/``:

    00_input.png            the raw frame
    NN_<stage>.png          intermediate stages (gray, mask, morphology, ...)
    detections.png          final boxes (green) + ground truth (red) overlaid
    detections.csv          one row per detection (unified schema)
    summary.json            params, counts, and the detection list
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2

from src.detection.detect_bgsub import BackgroundSubtractionDetector
from src.detection.run_detection import DETECTORS
from src.detection.visem_io import detection_to_row, write_detections_csv
from src.detection.visualize import COLORS, draw_detections, draw_legend

from .frames import load_gt, read_frame, read_warmup, resolve_source
from .stages import compute_stages


def _cast(value: str):
    """Cast a CLI ``key=value`` string to bool / int / float / str."""
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_overrides(pairs: list[str] | None) -> dict:
    """Parse repeated ``--set key=value`` into a kwargs dict for the detector."""
    overrides: dict = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--set espera key=value, recebi: {item!r}")
        key, raw = item.split("=", 1)
        overrides[key.strip()] = _cast(raw.strip())
    return overrides


def build_detector(method: str, overrides: dict, weights: str | None):
    if method not in DETECTORS:
        raise SystemExit(f"Método desconhecido: {method}. Opções: {', '.join(DETECTORS)}")
    cls = DETECTORS[method]
    if method == "yolo":
        return cls(weights=weights, **overrides)
    return cls(**overrides)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sandbox: roda 1 detector em 1 frame e salva todas as etapas."
    )
    p.add_argument("--method", required=True, choices=list(DETECTORS))
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--id", dest="video_id", help="ID do vídeo anotado (VISEM-Tracking).")
    src.add_argument("--video", help="Caminho de um vídeo bruto.")
    p.add_argument("--frame", type=int, default=0, help="Índice do frame (0-based).")
    p.add_argument("--warmup", type=int, default=0,
                   help="Frames de aquecimento antes do alvo (só bgsub).")
    p.add_argument("--set", dest="overrides", action="append", default=[],
                   metavar="key=value", help="Sobrescreve um parâmetro do detector. Repetível.")
    p.add_argument("--draw-mode", default="both", choices=["box", "centroid", "circle", "both"])
    p.add_argument("--weights", default=None, help="Pesos YOLO (--method yolo).")
    p.add_argument("--out-dir", default="results/tests", help="Raiz das saídas.")
    p.add_argument("--no-stages", action="store_true",
                   help="Não salva imagens de etapas intermediárias (útil em baterias).")
    return p.parse_args(argv)


COMPARISON_FIELDS = [
    "timestamp", "method", "video", "frame", "warmup",
    "n_detections", "n_ground_truth", "count_diff", "count_ratio",
    "overrides", "run_dir",
]


def _append_comparison(summary: dict, out_root: Path) -> None:
    """Append one row to the cumulative comparisons CSV in ``out_root``."""
    csv_path = out_root / "comparisons.csv"
    write_header = not csv_path.exists()
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": summary["method"],
        "video": Path(summary["video"]).stem,
        "frame": summary["frame"],
        "warmup": summary["warmup"],
        "n_detections": summary["n_detections"],
        "n_ground_truth": summary["n_ground_truth"],
        "count_diff": summary["count_diff"],
        "count_ratio": summary["count_ratio"] if summary["count_ratio"] is not None else "",
        "overrides": json.dumps(summary["overrides"], ensure_ascii=False),
        "run_dir": Path(summary["out_dir"]).name,
    }
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPARISON_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    overrides = parse_overrides(args.overrides)

    video_path, gt_dir, stem = resolve_source(args.video, args.video_id)
    frame, w, h = read_frame(video_path, args.frame)
    warmup_frames = (
        read_warmup(video_path, args.frame, args.warmup)
        if args.method == "bgsub" else []
    )

    detector = build_detector(args.method, overrides, args.weights)

    # Detections: prime stateful detectors on the warmup frames first.
    if isinstance(detector, BackgroundSubtractionDetector):
        detector.reset()
        for f in warmup_frames:
            detector._subtractor.apply(f)
    dets = detector.detect(frame)
    for i, d in enumerate(dets):
        if d.object_id is None or d.object_id == -1:
            d.object_id = i

    gt = load_gt(gt_dir, args.frame, w, h)

    # Output: results/tests/<stem>/<method>__f<frame>[__params]/
    param_parts: list[str] = []
    if args.method == "bgsub" and len(warmup_frames) > 0:
        param_parts.append(f"w{len(warmup_frames)}")
    for key, val in sorted(overrides.items()):
        param_parts.append(f"{key}={val}")
    params_str = ("__" + "_".join(param_parts)) if param_parts else ""
    video_dir = Path(args.out_dir) / stem
    out_dir = video_dir / f"{args.method}__f{args.frame}{params_str}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(out_dir / "00_input.png"), frame)

    # Intermediate stages — skipped in batch mode (--no-stages).
    stages = compute_stages(args.method, detector, frame, warmup_frames)
    if not args.no_stages:
        for idx, (name, img) in enumerate(stages, start=1):
            cv2.imwrite(str(out_dir / f"{idx:02d}_{name}.png"), img)

    # Final annotated frame: detections (green) + ground truth (red).
    annotated = frame.copy()
    draw_detections(annotated, dets, COLORS["detection"], args.draw_mode)
    legend = [(f"detection ({detector.name}): {len(dets)}", COLORS["detection"])]
    if gt:
        draw_detections(annotated, gt, COLORS["manual"], "box", draw_id=True)
        legend.append((f"manual GT: {len(gt)}", COLORS["manual"]))
    draw_legend(annotated, legend)
    cv2.imwrite(str(out_dir / "detections.png"), annotated)

    # Per-detection CSV (unified schema; detection + manual rows).
    rows = [detection_to_row(stem, args.frame, "detection", d) for d in dets]
    rows += [detection_to_row(stem, args.frame, "manual", d) for d in gt]
    write_detections_csv(rows, out_dir / "detections.csv")

    n_det = len(dets)
    n_gt = len(gt)
    diff = n_det - n_gt
    ratio = n_det / n_gt if n_gt > 0 else None

    summary = {
        "method": detector.name,
        "video": str(video_path),
        "frame": args.frame,
        "frame_size": [w, h],
        "warmup": len(warmup_frames) if args.method == "bgsub" else 0,
        "overrides": overrides,
        "n_detections": n_det,
        "n_ground_truth": n_gt,
        "count_diff": diff,          # positivo = excesso, negativo = falta
        "count_ratio": round(ratio, 3) if ratio is not None else None,
        "detections": [
            {"cx": round(d.cx, 2), "cy": round(d.cy, 2),
             "w": round(d.w, 2), "h": round(d.h, 2), "score": round(d.score, 3)}
            for d in dets
        ],
        "stages": [f"{i:02d}_{n}.png" for i, (n, _) in enumerate(stages, start=1)],
        "out_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _append_comparison(summary, video_dir)

    # Console report.
    if overrides:
        print("  overrides:", overrides)
    print(f"  etapas:", ", ".join(n for n, _ in stages) or "(nenhuma)")

    if n_gt > 0:
        sign = "+" if diff > 0 else ""
        bar_len = 20
        filled = round(min(n_det / n_gt, 2.0) * (bar_len / 2))
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\n  contagem")
        print(f"    detectado : {n_det:>4}")
        print(f"    GT        : {n_gt:>4}")
        print(f"    diferença : {sign}{diff:>4}  ({sign}{diff/n_gt*100:.1f}%)")
        print(f"    ratio     : {ratio:.3f}  [{bar}]")
    else:
        print(f"\n  detectado: {n_det}  (sem GT disponível)")

    print(f"\n  saída: {out_dir}")
    return summary


if __name__ == "__main__":
    main()
