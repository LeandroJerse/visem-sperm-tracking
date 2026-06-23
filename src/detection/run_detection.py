"""CLI entry point for sperm detection.

Examples
--------
Classical baseline on the first 300 frames of one video::

    python -m src.detection.run_detection --method threshold \
        --video "Dataset/visem-dataset/visem-dataset/videos/1_09.09.02_SSW.avi" \
        --max-frames 300

Compare against VISEM-Tracking ground truth (overlaid in red)::

    python -m src.detection.run_detection --method threshold \
        --video path/to/52/52.mp4 --gt-dir path/to/52/labels_ftid --max-frames 300

Outputs ``results/<video>_<method>.csv`` and ``results/<video>_<method>.mp4``.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .detect_bgsub import BackgroundSubtractionDetector
from .detect_blob import BlobDetector
from .detect_threshold_contours import ThresholdContourDetector
from .detect_watershed import WatershedDetector
from .detect_yolo import YoloDetector
from .runner import run_on_video
from .video_metadata import CLINICAL_FIELDS, load_clinical_row, resolve_video_id

# Registry: method name -> Detector class. New detectors plug in here.
DETECTORS = {
    "threshold": ThresholdContourDetector,
    "blob": BlobDetector,
    "bgsub": BackgroundSubtractionDetector,
    "watershed": WatershedDetector,
    "yolo": YoloDetector,
}


def build_detector(method: str, weights: str | None):
    if method not in DETECTORS:
        raise SystemExit(
            f"Método desconhecido: {method}. Opções: {', '.join(DETECTORS)}"
        )
    if method == "yolo":
        return YoloDetector(weights=weights)
    return DETECTORS[method]()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detecção de espermatozoides (baselines clássicos + YOLO).")
    p.add_argument("--method", required=True, choices=list(DETECTORS),
                   help="Algoritmo de detecção.")
    p.add_argument("--video", required=True, help="Caminho do vídeo de entrada.")
    p.add_argument("--out-dir", default="results", help="Diretório de saída (default: results).")
    p.add_argument("--gt-dir", default=None,
                   help="Pasta de labels do VISEM-Tracking para sobrepor o ground truth.")
    p.add_argument("--max-frames", type=int, default=None,
                   help="Limita o número de frames processados.")
    p.add_argument("--draw-mode", default="both", choices=["box", "centroid", "circle", "both"],
                   help="Como desenhar as detecções no vídeo.")
    p.add_argument("--no-video", action="store_true",
                   help="Não gerar vídeo anotado (apenas CSV).")
    p.add_argument("--weights", default=None, help="Pesos do modelo YOLO (apenas --method yolo).")
    p.add_argument("--videos-csv", default=None,
                   help="Caminho de videos.csv para resolver o ID do dataset (default: VISEM original).")
    return p.parse_args(argv)


def write_summary_csv(summary: dict, path: Path) -> None:
    """Append/write a one-row per-video summary CSV (count stats + clinical join)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    video_path = Path(args.video)
    stem = video_path.stem
    out_dir = Path(args.out_dir)
    out_csv = out_dir / f"{stem}_{args.method}.csv"
    out_video = None if args.no_video else out_dir / f"{stem}_{args.method}.mp4"

    detector = build_detector(args.method, args.weights)
    summary = run_on_video(
        detector,
        video_path=video_path,
        out_csv=out_csv,
        out_video=out_video,
        gt_dir=args.gt_dir,
        max_frames=args.max_frames,
        draw_mode=args.draw_mode,
    )

    # Resolve the dataset video ID and attach clinical metadata (per-video).
    videos_csv = args.videos_csv
    dataset_id = (
        resolve_video_id(video_path, videos_csv) if videos_csv
        else resolve_video_id(video_path)
    )
    clinical = load_clinical_row(dataset_id, fields=CLINICAL_FIELDS) if dataset_id else {}
    summary = {"dataset_id": dataset_id, **summary, **clinical}

    out_summary = out_dir / f"{stem}_{args.method}_summary.csv"
    write_summary_csv(summary, out_summary)
    print("Resumo:", summary)
    print("Resumo salvo em:", out_summary)


if __name__ == "__main__":
    main()
