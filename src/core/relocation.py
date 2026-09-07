"""Resolve caminhos históricos sem reescrever artefatos científicos antigos.

Runs migradas preservam seus ``manifest.json`` e ``metadata.json`` originais.
O mapa de migração traduz essas referências para a árvore canônica no momento
da leitura, mantendo simultaneamente a proveniência e a usabilidade.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from .paths import DATA_ROOT, REPOSITORY_ROOT


DEFAULT_LAYOUT_MANIFEST = DATA_ROOT / "manifests" / "layout_20260829.csv"


def _portable(value: str | Path) -> str:
    text = str(value).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return PurePosixPath(text).as_posix()


@dataclass(frozen=True)
class PathMigrationMap:
    """Exact file moves plus longest-prefix directory moves."""

    repository_root: Path
    exact: dict[str, str]
    prefixes: tuple[tuple[str, str], ...]

    @classmethod
    def from_csv(
        cls,
        manifest_path: str | Path,
        *,
        repository_root: str | Path = REPOSITORY_ROOT,
    ) -> "PathMigrationMap":
        manifest = Path(manifest_path)
        exact: dict[str, str] = {}
        prefixes: list[tuple[str, str]] = []
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                old = _portable(row.get("original_path", ""))
                new = _portable(row.get("new_path", ""))
                if not old or old == "." or not new or new == ".":
                    continue
                action = str(row.get("action", "")).strip().lower()
                if "tree" in action:
                    prefixes.append((old.casefold(), new))
                else:
                    exact[old.casefold()] = new
        prefixes.sort(key=lambda pair: len(pair[0]), reverse=True)
        return cls(
            repository_root=Path(repository_root).resolve(),
            exact=exact,
            prefixes=tuple(prefixes),
        )

    def resolve(self, value: str | Path) -> Path | None:
        """Return the canonical absolute target, or ``None`` if not migrated."""
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate.resolve()
        portable = _portable(value)
        key = portable.casefold()
        target = self.exact.get(key)
        if target is not None:
            return (self.repository_root / Path(target)).resolve()
        for old_prefix, new_prefix in self.prefixes:
            if key == old_prefix:
                suffix = ""
            elif key.startswith(old_prefix + "/"):
                suffix = portable[len(old_prefix) + 1 :]
            else:
                continue
            destination = self.repository_root / Path(new_prefix)
            if suffix:
                destination /= Path(suffix)
            return destination.resolve()
        return None


@lru_cache(maxsize=1)
def default_migration_map() -> PathMigrationMap | None:
    if not DEFAULT_LAYOUT_MANIFEST.is_file():
        return None
    return PathMigrationMap.from_csv(DEFAULT_LAYOUT_MANIFEST)


def resolve_migrated_path(value: str | Path) -> Path | None:
    """Resolve one value using the repository's audited migration manifest."""
    mapping = default_migration_map()
    return mapping.resolve(value) if mapping is not None else None


__all__ = [
    "DEFAULT_LAYOUT_MANIFEST",
    "PathMigrationMap",
    "default_migration_map",
    "resolve_migrated_path",
]
