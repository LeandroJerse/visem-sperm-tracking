"""Lazy bridge from ``src.flow`` cache indexes to tracking frame updates.

The flow CLI writes one ``.npz`` field for each pair ``previous -> next`` and
an accompanying ``cache_index.csv``.  Tracking advances on the *next* frame,
so update ``t`` must receive the field ``(t - 1) -> t``.  This module keeps the
index small in memory while loading at most one dense field at a time.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from src.flow.cache import load_flow_file

from .base import FlowInput


_REQUIRED_INDEX_FIELDS = {"previous_frame", "next_frame", "path"}


@dataclass(frozen=True)
class FlowCacheEntry:
    previous_frame: int
    next_frame: int
    path: Path
    key: str | None = None


class LazyFlowCacheIndex:
    """Validated pair index with lazy, validity-aware dense-field loading."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Índice de fluxo não encontrado: {self.path}")
        self._entries = self._read_entries()
        self.fields_loaded = 0
        self.missing_pairs: list[tuple[int, int]] = []
        self.loaded_pairs: list[tuple[int, int]] = []

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _read_entries(self) -> dict[tuple[int, int], FlowCacheEntry]:
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = sorted(_REQUIRED_INDEX_FIELDS - fields)
            if missing:
                raise ValueError(
                    f"cache_index.csv sem colunas obrigatórias: {missing}"
                )
            rows = list(reader)
        if not rows:
            raise ValueError("cache_index.csv está vazio")

        entries: dict[tuple[int, int], FlowCacheEntry] = {}
        for row_number, row in enumerate(rows, start=2):
            try:
                previous = int(row["previous_frame"])
                following = int(row["next_frame"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Par de frames inválido no cache_index.csv, linha {row_number}"
                ) from exc
            if previous < 0 or following != previous + 1:
                raise ValueError(
                    "O cache de tracking exige pares consecutivos não negativos; "
                    f"linha {row_number} contém {previous}->{following}."
                )
            raw_path = (row.get("path") or "").strip()
            if not raw_path:
                raise ValueError(
                    f"Caminho de cache vazio no cache_index.csv, linha {row_number}"
                )
            field_path = Path(raw_path)
            if not field_path.is_absolute():
                field_path = self.path.parent / field_path
            pair = (previous, following)
            if pair in entries:
                raise ValueError(f"Par duplicado no cache_index.csv: {previous}->{following}")
            entries[pair] = FlowCacheEntry(
                previous_frame=previous,
                next_frame=following,
                path=field_path.resolve(),
                key=(row.get("key") or "").strip() or None,
            )
        return entries

    @staticmethod
    def _load_dense(entry: FlowCacheEntry) -> np.ndarray:
        if not entry.path.is_file():
            raise FileNotFoundError(
                f"Campo de fluxo ausente para {entry.previous_frame}->{entry.next_frame}: "
                f"{entry.path}"
            )
        try:
            result = load_flow_file(entry.path)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Não foi possível ler o cache de fluxo {entry.path}: {exc}"
            ) from exc

        # Invalid vectors must remain visibly missing.  Replacing them with
        # zero would create a false 'no motion' measurement in the hybrid.
        dense = result.flow.copy()
        finite = np.isfinite(dense).all(axis=-1)
        dense[~(result.valid & finite)] = np.nan
        return dense

    def iter_for_interval(self, frame_start: int, frame_end: int) -> Iterator[FlowInput]:
        """Yield one item per tracking frame, mapping update ``t`` to ``t-1 -> t``.

        The first processed frame always yields ``None`` because a reset tracker
        has no state to propagate into that frame.  Missing later pairs also
        yield ``None`` and are retained in :attr:`missing_pairs` for provenance.
        """

        if frame_start < 0 or frame_end < frame_start:
            raise ValueError("Invalid tracking frame interval")
        self.fields_loaded = 0
        self.missing_pairs = []
        self.loaded_pairs = []
        for frame in range(frame_start, frame_end + 1):
            if frame == frame_start:
                yield None
                continue
            pair = (frame - 1, frame)
            entry = self._entries.get(pair)
            if entry is None:
                self.missing_pairs.append(pair)
                yield None
                continue
            dense = self._load_dense(entry)
            self.fields_loaded += 1
            self.loaded_pairs.append(pair)
            yield dense

    def interval_entry_count(self, frame_start: int, frame_end: int) -> int:
        return sum(
            (frame - 1, frame) in self._entries
            for frame in range(frame_start + 1, frame_end + 1)
        )
