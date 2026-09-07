"""Audita a organização física sem executar algoritmos científicos."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.paths import DATA_ROOT, REPOSITORY_ROOT
from src.db.run_ingest import load_run_tables


REQUIRED_ROOTS = (
    "data/sources",
    "data/manifests",
    "data/datasets",
    "data/derived",
    "data/tests",
    "data/results",
    "data/models",
    "data/catalog",
    "data/quarantine",
    "src",
    "script",
    "tests",
    "configs",
    "docs",
    "monografia",
)

FORBIDDEN_LEGACY_ROOTS = (
    "results",
    "output",
    "tmp",
    "data/raw",
    "data/tracked",
    "data/processed",
    "data/yolo",
)


def _tree_stats(path: Path) -> dict[str, int]:
    files = 0
    size = 0
    if not path.exists():
        return {"files": 0, "bytes": 0}
    for root, _, names in os.walk(path):
        for name in names:
            candidate = Path(root) / name
            try:
                size += candidate.stat().st_size
                files += 1
            except OSError:
                continue
    return {"files": files, "bytes": size}


def _artifact_strings(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _artifact_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _artifact_strings(item)
    elif isinstance(value, str) and value:
        yield value


def build_inventory() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    for relative in REQUIRED_ROOTS:
        if not (REPOSITORY_ROOT / relative).is_dir():
            errors.append(f"diretório obrigatório ausente: {relative}")
    for relative in FORBIDDEN_LEGACY_ROOTS:
        if (REPOSITORY_ROOT / relative).exists():
            errors.append(f"raiz legada não pode existir: {relative}")

    tracked_root = DATA_ROOT / "sources" / "visem_tracking" / "dataset" / "Train"
    tracked_ids = sorted(
        path.name
        for path in tracked_root.iterdir()
        if path.is_dir() and (path / f"{path.name}.mp4").is_file()
    )
    visem_videos = list((DATA_ROOT / "sources" / "visem" / "videos").glob("*.avi"))
    if len(tracked_ids) != 20:
        errors.append(f"esperados 20 vídeos anotados; encontrados {len(tracked_ids)}")
    if len(visem_videos) != 85:
        errors.append(f"esperados 85 vídeos VISEM; encontrados {len(visem_videos)}")

    layout_manifest = DATA_ROOT / "manifests" / "layout_20260829.csv"
    migration_rows: list[dict[str, str]] = []
    if layout_manifest.is_file():
        with layout_manifest.open(encoding="utf-8-sig", newline="") as handle:
            migration_rows = list(csv.DictReader(handle))
        unverified = [row for row in migration_rows if row.get("verified") != "True"]
        if unverified:
            errors.append(f"linhas de migração não verificadas: {len(unverified)}")
    else:
        errors.append("manifesto de migração ausente")

    experiment_roots = (DATA_ROOT / "tests", DATA_ROOT / "results")
    run_manifests = [
        path for root in experiment_roots for path in root.rglob("manifest.json")
    ]
    for manifest_path in run_manifests:
        experiment_root = next(
            root for root in experiment_roots if manifest_path.is_relative_to(root)
        )
        relative = manifest_path.relative_to(experiment_root)
        # module/algorithm/configuration/stage/run_id/manifest.json
        if len(relative.parts) != 6:
            errors.append(f"hierarquia de run inválida: {relative.as_posix()}")
            continue
        configuration_directory = relative.parts[2]
        if re.fullmatch(r".+__cfg[0-9a-fA-F]+", configuration_directory) is None:
            errors.append(
                "diretório de configuração sem identificador/hash: "
                f"{relative.as_posix()}"
            )

    run_tables = load_run_tables(DATA_ROOT)
    run_rows = run_tables["runs"]
    if len(run_rows) != len(run_manifests):
        errors.append(
            f"manifests/runs divergentes: {len(run_manifests)}/{len(run_rows)}"
        )
    unresolved_artifacts = 0
    unidentified_runs = 0
    for row in run_rows.to_dict(orient="records"):
        if not row.get("configuration_id") or not row.get("configuration_hash"):
            unidentified_runs += 1
        try:
            artifacts = json.loads(row.get("artifacts_json") or "{}")
        except (TypeError, ValueError):
            unresolved_artifacts += 1
            continue
        for value in _artifact_strings(artifacts):
            if "://" in value:
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = DATA_ROOT / candidate
            if not candidate.exists():
                unresolved_artifacts += 1
    if unresolved_artifacts:
        errors.append(f"artefatos de runs sem destino resolvível: {unresolved_artifacts}")
    if unidentified_runs:
        errors.append(f"runs sem configuration_id/hash: {unidentified_runs}")
    shared_inputs = list(
        (DATA_ROOT / "tests" / "detection" / "_shared_inputs").rglob("*.png")
    )
    duplicate_inputs = [
        path
        for path in (DATA_ROOT / "tests" / "detection").rglob("00_input.png")
        if "_shared_inputs" not in path.parts
    ]
    if len(shared_inputs) != 60:
        errors.append(f"esperadas 60 entradas frame-a-frame comuns; encontradas {len(shared_inputs)}")
    if duplicate_inputs:
        errors.append(f"entradas frame-a-frame duplicadas: {len(duplicate_inputs)}")

    top_level = {
        name: _tree_stats(REPOSITORY_ROOT / name)
        for name in ("data", "src", "script", "tests", "configs", "docs", "monografia")
    }
    data_sections = {
        path.name: _tree_stats(path)
        for path in sorted(DATA_ROOT.iterdir())
        if path.is_dir()
    }
    inventory: dict[str, Any] = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": ".",
        "status": "ok" if not errors else "invalid",
        "top_level": top_level,
        "data_sections": data_sections,
        "scientific_counts": {
            "visem_videos": len(visem_videos),
            "visem_tracking_videos": len(tracked_ids),
            "visem_tracking_ids": tracked_ids,
            "migration_rows": len(migration_rows),
            "immutable_run_manifests": len(run_manifests),
            "resolved_run_artifacts": sum(
                1
                for raw in run_rows.get("artifacts_json", [])
                for value in _artifact_strings(
                    json.loads(raw) if isinstance(raw, str) else {}
                )
            ),
            "unresolved_run_artifacts": unresolved_artifacts,
            "unidentified_runs": unidentified_runs,
            "frame_screening_summaries": len(
                [
                    path
                    for path in (DATA_ROOT / "tests" / "detection").rglob("summary.json")
                    if "frame_screening" in path.parts
                ]
            ),
            "shared_frame_inputs": len(shared_inputs),
            "duplicate_frame_inputs": len(duplicate_inputs),
            "configuration_yamls": len(list((REPOSITORY_ROOT / "configs").rglob("*.yaml"))),
            "source_python_files": len(list((REPOSITORY_ROOT / "src").rglob("*.py"))),
            "automated_test_files": len(list((REPOSITORY_ROOT / "tests").rglob("test_*.py"))),
        },
        "required_roots": list(REQUIRED_ROOTS),
        "forbidden_legacy_roots": list(FORBIDDEN_LEGACY_ROOTS),
        "errors": errors,
    }
    return inventory, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-manifest",
        default=None,
        help="Grava o inventário JSON exclusivamente no caminho informado.",
    )
    args = parser.parse_args(argv)
    inventory, errors = build_inventory()
    if args.write_manifest:
        destination = Path(args.write_manifest)
        if not destination.is_absolute():
            destination = REPOSITORY_ROOT / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(inventory, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"Inventário: {destination}")
    if errors:
        for error in errors:
            print(f"ERRO: {error}")
        return 1
    counts = inventory["scientific_counts"]
    print(
        "OK: layout canônico; "
        f"{counts['visem_videos']} vídeos VISEM, "
        f"{counts['visem_tracking_videos']} anotados, "
        f"{counts['immutable_run_manifests']} runs e "
        f"{counts['migration_rows']} movimentos auditáveis."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
