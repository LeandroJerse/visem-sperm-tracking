"""Descoberta reutilizável das fontes locais e pesos de detecção."""
from __future__ import annotations

from pathlib import Path

from src.core.paths import (
    EXPERIMENT_TESTS_ROOT,
    VISEM_TRACKING_TRAIN_ROOT,
    VISEM_VIDEOS_ROOT,
)


TRAIN_ROOT = VISEM_TRACKING_TRAIN_ROOT
RAW_VIDEOS_ROOT = VISEM_VIDEOS_ROOT
YOLO_TEST_RUNS_ROOT = EXPERIMENT_TESTS_ROOT / "detection" / "yolo"


def _id_sort_key(value: str) -> tuple[bool, int, str]:
    return (not value.isdigit(), int(value) if value.isdigit() else 0, value)


def discover_tracked_ids(train_root: Path = TRAIN_ROOT) -> list[str]:
    """Return annotated video IDs that contain their canonical MP4."""

    if not train_root.exists():
        return []
    ids = [
        folder.name
        for folder in train_root.iterdir()
        if folder.is_dir() and (folder / f"{folder.name}.mp4").exists()
    ]
    return sorted(ids, key=_id_sort_key)


def discover_raw_videos(root: Path = RAW_VIDEOS_ROOT) -> dict[str, Path]:
    """Map the numeric prefix of each raw VISEM AVI to its path."""

    result: dict[str, Path] = {}
    if not root.exists():
        return result
    for path in sorted(root.glob("*.avi")):
        head = path.stem.split("_", 1)[0]
        if head.isdigit():
            result[head] = path
    return dict(sorted(result.items(), key=lambda item: _id_sort_key(item[0])))


def discover_yolo_weights(root: Path = YOLO_TEST_RUNS_ROOT) -> list[Path]:
    """Return prior ``best.pt`` artifacts, newest first."""

    if not root.exists():
        return []
    return sorted(root.rglob("best.pt"), key=lambda path: path.stat().st_mtime, reverse=True)


__all__ = [
    "RAW_VIDEOS_ROOT",
    "TRAIN_ROOT",
    "YOLO_TEST_RUNS_ROOT",
    "discover_raw_videos",
    "discover_tracked_ids",
    "discover_yolo_weights",
]
