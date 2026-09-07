"""Operações comuns e seguras para artefatos imutáveis de experimentos."""
from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def normalize_parameter_overrides(
    overrides: Sequence[str] | None, *, section: str = "params"
) -> list[str]:
    """Prefix bare ``key=value`` overrides with the scientific parameter section."""

    normalized: list[str] = []
    for expression in overrides or ():
        key = expression.split("=", 1)[0].strip()
        normalized.append(expression if "." in key else f"{section}.{expression}")
    return normalized


def sha256_file(path: str | Path) -> str:
    """Return a streaming SHA-256 without loading a large artifact in memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_exclusive(path: str | Path, value: Any) -> Path:
    """Create one JSON artifact and fail instead of overwriting an existing file."""

    target = Path(path)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
    return target


def _infer_fields(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    return fields


def write_csv_exclusive(
    path: str | Path,
    rows: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    fieldnames: Sequence[str] | None = None,
) -> Path:
    """Create one CSV artifact with deterministic fields and no overwrite."""

    materialized = [dict(rows)] if isinstance(rows, Mapping) else [dict(row) for row in rows]
    fields = list(fieldnames) if fieldnames is not None else _infer_fields(materialized)
    target = Path(path)
    with target.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(materialized)
    return target


__all__ = [
    "normalize_parameter_overrides",
    "sha256_file",
    "write_csv_exclusive",
    "write_json_exclusive",
]
