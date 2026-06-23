"""Resolve the dataset video ID and look up per-video clinical metadata.

The VISEM CSVs are **per participant/video** (one row per video, key ``ID`` 1-85),
not per frame. ``videos.csv`` maps ``ID`` to the ``.avi`` filename. This module
resolves a video path to its numeric ``ID`` and optionally fetches selected
clinical fields, so the detection summary can carry the video identity and (for
later, correlational) the lab counts.

All dataset CSVs use ``;`` as separator and ``,`` as decimal (European format).
"""
from __future__ import annotations

import csv
from pathlib import Path

# Default locations inside the VISEM original dataset (data/raw).
_RAW_ROOT = Path("data/raw")
DEFAULT_VIDEOS_CSV = _RAW_ROOT / "videos.csv"
DEFAULT_ANALYSIS_CSV = _RAW_ROOT / "semen_analysis_data.csv"

# Clinical fields most relevant to validating counts/motility later on.
# Maps the dataset's raw CSV header (with unicode superscripts) to a clean,
# ASCII-safe key used in our outputs.
CLINICAL_FIELDS = {
    "Sperm concentration (x10⁶/mL)": "sperm_concentration_x10e6_per_ml",
    "Total sperm count (x10⁶)": "total_sperm_count_x10e6",
    "Progressive motility (%)": "progressive_motility_pct",
}


def load_video_id_map(videos_csv: str | Path = DEFAULT_VIDEOS_CSV) -> dict[str, int]:
    """Return a map from both filename and stem -> numeric dataset ID."""
    mapping: dict[str, int] = {}
    path = Path(videos_csv)
    if not path.exists():
        return mapping
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            try:
                vid = int(row["ID"])
            except (KeyError, ValueError):
                continue
            name = (row.get("video") or "").strip()
            if name:
                mapping[name] = vid
                mapping[Path(name).stem] = vid
    return mapping


def resolve_video_id(
    video_path: str | Path, videos_csv: str | Path = DEFAULT_VIDEOS_CSV
) -> int | None:
    """Resolve a video path to its dataset ID.

    Tries ``videos.csv`` (by filename, then stem); falls back to the leading
    number of the filename (``1_09.09.02_SSW.avi`` -> 1). Returns ``None`` if
    it cannot be determined.
    """
    name = Path(video_path).name
    stem = Path(video_path).stem
    mapping = load_video_id_map(videos_csv)
    if name in mapping:
        return mapping[name]
    if stem in mapping:
        return mapping[stem]
    head = stem.split("_", 1)[0]
    return int(head) if head.isdigit() else None


def load_clinical_row(
    dataset_id: int | None,
    csv_path: str | Path = DEFAULT_ANALYSIS_CSV,
    fields: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return selected clinical fields for ``dataset_id`` (empty dict if absent).

    ``fields`` maps raw CSV headers -> clean output keys; the returned dict uses
    the clean keys. If ``None``, returns the whole row as-is.
    """
    path = Path(csv_path)
    if dataset_id is None or not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            try:
                if int(row["ID"]) != dataset_id:
                    continue
            except (KeyError, ValueError):
                continue
            if fields is None:
                return dict(row)
            return {clean: row.get(raw, "") for raw, clean in fields.items()}
    return {}
