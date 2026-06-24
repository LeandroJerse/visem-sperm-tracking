"""Locate and read a single frame (plus its ground truth) for the sandbox.

Two video sources are supported, mirroring ``src.detection.interactive``:

* ``--id <N>``    annotated VISEM-Tracking video at
  ``data/tracked/VISEM_Tracking_Train_v4/Train/<N>/<N>.mp4`` with per-frame
  ground truth in ``labels_ftid/`` (matched by sorted order, frame *i* ->
  i-th label file, exactly as :func:`src.detection.runner.run_on_video` does).
* ``--video <path>``  any raw video file (no ground truth).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.detection.base_detector import Detection
from src.detection.visem_io import list_label_files, load_gt_frame

TRAIN_ROOT = Path("data/tracked/VISEM_Tracking_Train_v4/Train")


def resolve_source(
    video: str | None, video_id: str | None
) -> tuple[Path, Path | None, str]:
    """Resolve CLI ``--video`` / ``--id`` to ``(video_path, gt_dir, stem)``.

    ``gt_dir`` is ``None`` for raw videos (no ground truth available).
    """
    if video_id is not None:
        base = TRAIN_ROOT / video_id
        video_path = base / f"{video_id}.mp4"
        if not video_path.exists():
            raise FileNotFoundError(
                f"Vídeo anotado não encontrado: {video_path}. "
                f"IDs disponíveis em {TRAIN_ROOT}."
            )
        gt_dir = base / "labels_ftid"
        if not gt_dir.exists():
            gt_dir = base / "labels"
        return video_path, (gt_dir if gt_dir.exists() else None), video_id

    if video is not None:
        video_path = Path(video)
        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")
        return video_path, None, video_path.stem

    raise SystemExit("Informe --id <N> (VISEM-Tracking) ou --video <caminho>.")


def read_frame(video_path: Path, index: int) -> tuple[np.ndarray, int, int]:
    """Read frame ``index`` (0-based) from ``video_path``.

    Returns ``(frame_bgr, width, height)``.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise IndexError(f"Frame {index} fora do alcance em {video_path}.")
    return frame, w, h


def read_warmup(video_path: Path, index: int, warmup: int) -> list[np.ndarray]:
    """Read the ``warmup`` frames immediately *before* ``index``.

    Used to prime stateful detectors (background subtraction) so that frame
    ``index`` is evaluated against an adapted background model. Returns frames
    in chronological order; may be shorter than ``warmup`` near the start.
    """
    if warmup <= 0:
        return []
    start = max(0, index - warmup)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames: list[np.ndarray] = []
    for _ in range(index - start):
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def load_gt(gt_dir: Path | None, frame_index: int, w: int, h: int) -> list[Detection]:
    """Ground-truth detections for ``frame_index`` (by sorted label order)."""
    if gt_dir is None:
        return []
    files = list_label_files(gt_dir)
    if frame_index >= len(files):
        return []
    return load_gt_frame(files[frame_index], w, h)
