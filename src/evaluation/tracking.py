"""Fronteira de avaliação oficial de tracking por TrackEval/HOTA.

This module intentionally does not contain a home-grown metric labelled HOTA.
It prepares/parses an official TrackEval run so reported values retain their
standard meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrackEvalHOTAAdapter:
    """Build commands and parse summaries for a checked-out TrackEval repo."""

    trackeval_root: Path
    python_executable: str = "python"

    def __init__(
        self, trackeval_root: str | Path, *, python_executable: str = "python"
    ) -> None:
        object.__setattr__(self, "trackeval_root", Path(trackeval_root))
        object.__setattr__(self, "python_executable", python_executable)

    @property
    def script_path(self) -> Path:
        return self.trackeval_root / "scripts" / "run_mot_challenge.py"

    def build_command(
        self,
        *,
        ground_truth_folder: str | Path,
        trackers_folder: str | Path,
        benchmark: str,
        split: str,
        tracker_name: str,
    ) -> tuple[str, ...]:
        """Return, but do not execute, a TrackEval HOTA command."""
        if not self.script_path.is_file():
            raise FileNotFoundError(
                f"TrackEval script not found: {self.script_path}. Clone/install "
                "TrackEval explicitly before reporting HOTA."
            )
        return (
            self.python_executable,
            str(self.script_path),
            "--GT_FOLDER",
            str(Path(ground_truth_folder)),
            "--TRACKERS_FOLDER",
            str(Path(trackers_folder)),
            "--BENCHMARK",
            benchmark,
            "--SPLIT_TO_EVAL",
            split,
            "--TRACKERS_TO_EVAL",
            tracker_name,
            "--METRICS",
            "HOTA",
        )

    @staticmethod
    def parse_summary(path: str | Path) -> float:
        """Read an actual TrackEval summary and return its HOTA column."""
        lines = [
            line.strip()
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(lines) < 2:
            raise ValueError("TrackEval summary must contain a header and values")
        header = lines[0].replace(",", " ").split()
        values = lines[1].replace(",", " ").split()
        if "HOTA" not in header:
            raise ValueError("Summary has no exact HOTA column")
        index = header.index("HOTA")
        if index >= len(values):
            raise ValueError("TrackEval summary row is shorter than its header")
        return float(values[index])
