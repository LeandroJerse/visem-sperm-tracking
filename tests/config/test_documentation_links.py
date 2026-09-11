"""Mantém o mapa documental navegável depois de futuras reorganizações."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _active_markdown_files() -> list[Path]:
    audit_root = REPOSITORY_ROOT / "data" / "derived" / "project_audits"
    files = [REPOSITORY_ROOT / "README.md"]
    for relative in ("docs", "src", "script", "tests", "configs", "monografia"):
        files.extend((REPOSITORY_ROOT / relative).rglob("*.md"))
    files.extend(
        path
        for path in (REPOSITORY_ROOT / "data").rglob("README.md")
        if "quarantine" not in path.parts
        # Audit snapshots preserve original bytes and relative links. Their
        # canonical documents are checked above; snapshots are not entry points.
        and not (
            path.is_relative_to(audit_root)
            and {"before", "documentation_before"}.intersection(path.relative_to(audit_root).parts)
        )
    )
    return sorted({path for path in files if path.is_file()})


def test_all_active_local_markdown_links_resolve():
    broken: list[str] = []
    for document in _active_markdown_files():
        text = document.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            raw = match.group(1).strip().strip("<>")
            if not raw or raw.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_text = unquote(raw.split("#", 1)[0])
            if not path_text:
                continue
            destination = (document.parent / path_text).resolve()
            if not destination.exists():
                location = document.relative_to(REPOSITORY_ROOT).as_posix()
                broken.append(f"{location} -> {raw}")
    assert not broken, "Links locais quebrados:\n" + "\n".join(broken)
