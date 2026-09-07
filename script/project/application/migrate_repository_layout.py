"""Migrate legacy datasets and experiment artifacts to the canonical TCC layout.

The migration is deliberately conservative:

* every source and destination is validated as a child of the repository;
* experiment artifacts are moved, never copied;
* historical manifests are not rewritten;
* a machine-readable migration map records original and final paths;
* duplicate frame inputs are removed only after SHA-256 equality is proven;
* unrelated private PDFs are quarantined instead of deleted.

Run from the repository root with::

    python -m script.project.application.migrate_repository_layout --apply
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT / "data"
MIGRATION_ID = "layout_20260829"
FINAL_STAGES = {"test", "five_fold", "oof", "cross_validation", "final", "application"}


@dataclass
class MigrationRow:
    original_path: str
    new_path: str
    action: str
    bytes: int
    file_count: int
    sha256: str
    verified: bool


def _safe(path: Path) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Caminho fora do repositório: {resolved}") from exc
    if resolved == REPO_ROOT:
        raise RuntimeError("A raiz do repositório nunca pode ser alvo direto.")
    return resolved


def _relative(path: Path) -> str:
    return _safe(path).relative_to(REPO_ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_stats(path: Path) -> tuple[int, int]:
    files = [item for item in path.rglob("*") if item.is_file()]
    return len(files), sum(item.stat().st_size for item in files)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip().lower())
    return text.strip("_.-") or "unnamed"


def _scientific_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return the algorithm/evaluation configuration, excluding run identity."""
    ignored_top = {"input", "search_space", "selection", "configuration_id"}
    result = {key: value for key, value in config.items() if key not in ignored_top}
    run = result.get("run")
    if isinstance(run, dict):
        ignored_run = {
            "stage", "split", "seed", "seeds", "save_video", "max_frames",
            "draw_mode", "frozen", "frame_limit_source",
        }
        reduced = {key: value for key, value in run.items() if key not in ignored_run}
        if reduced:
            result["run"] = reduced
        else:
            result.pop("run", None)
    return result


def _config_hash(config: dict[str, Any]) -> str:
    encoded = json.dumps(
        _scientific_config(config), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:8]


def _algorithm_and_config(manifest: dict[str, Any]) -> tuple[str, str]:
    method = _slug(str(manifest.get("method") or "unknown"))
    config = manifest.get("config") if isinstance(manifest.get("config"), dict) else {}
    params = config.get("params") if isinstance(config.get("params"), dict) else {}
    algorithm = method
    human = _slug(str(config.get("configuration_id") or method))
    if method == "threshold":
        if bool(params.get("adaptive")):
            algorithm = "adaptive_threshold"
            human = "adaptive"
        elif params.get("threshold_value") in (None, ""):
            algorithm = "otsu"
            human = "otsu"
        else:
            threshold = int(params["threshold_value"])
            opening = int(params.get("morph_iterations", 1))
            closing = int(params.get("close_iterations", 1))
            human = f"t{threshold}_o{opening}_c{closing}"
    elif method == "yolo_train" or method == "yolo_val":
        algorithm = "yolo"
    return algorithm, f"{human}__cfg{_config_hash(config)}"


class Migrator:
    def __init__(self, *, apply: bool) -> None:
        self.apply = apply
        self.rows: list[MigrationRow] = []

    def _record(
        self, source: Path, destination: Path, action: str, *, size: int,
        count: int, digest: str = "", verified: bool = True,
    ) -> None:
        self.rows.append(
            MigrationRow(
                original_path=_relative(source),
                new_path=_relative(destination),
                action=action,
                bytes=size,
                file_count=count,
                sha256=digest,
                verified=verified,
            )
        )

    def move_file(self, source: Path, destination: Path, *, hash_file: bool = True) -> None:
        source, destination = _safe(source), _safe(destination)
        if not source.exists():
            return
        if not source.is_file():
            raise RuntimeError(f"Esperava arquivo: {source}")
        if destination.exists():
            raise FileExistsError(destination)
        size = source.stat().st_size
        digest = _sha256(source) if hash_file else ""
        if self.apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            if destination.stat().st_size != size:
                raise RuntimeError(f"Tamanho mudou durante a migração: {destination}")
            if digest and _sha256(destination) != digest:
                raise RuntimeError(f"Hash mudou durante a migração: {destination}")
        self._record(source, destination, "move_file", size=size, count=1, digest=digest)

    def move_tree(self, source: Path, destination: Path, *, detailed: bool = False) -> None:
        source, destination = _safe(source), _safe(destination)
        if not source.exists():
            return
        if not source.is_dir():
            raise RuntimeError(f"Esperava diretório: {source}")
        if destination.exists():
            raise FileExistsError(destination)
        files = [item for item in source.rglob("*") if item.is_file()]
        count, size = len(files), sum(item.stat().st_size for item in files)
        details: list[tuple[Path, Path, int, str]] = []
        if detailed:
            for item in files:
                target = destination / item.relative_to(source)
                details.append((item, target, item.stat().st_size, _sha256(item)))
        if self.apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            new_count, new_size = _tree_stats(destination)
            if (new_count, new_size) != (count, size):
                raise RuntimeError(
                    f"Árvore divergente: {source} -> {destination}: "
                    f"{count}/{size} != {new_count}/{new_size}"
                )
            if detailed:
                for old, target, item_size, digest in details:
                    if target.stat().st_size != item_size or _sha256(target) != digest:
                        raise RuntimeError(f"Artefato divergente após migração: {target}")
        if detailed:
            for old, target, item_size, digest in details:
                self._record(old, target, "move_file_in_tree", size=item_size, count=1, digest=digest)
        else:
            self._record(source, destination, "move_tree", size=size, count=count)

    def remove_recreatable(self, path: Path) -> None:
        path = _safe(path)
        if not path.exists():
            return
        if not path.is_file():
            raise RuntimeError(f"Remoção limitada a arquivo: {path}")
        size, digest = path.stat().st_size, _sha256(path)
        if self.apply:
            path.unlink()
        self._record(path, path, "remove_recreatable", size=size, count=1, digest=digest)

    def remove_empty(self, paths: Iterable[Path]) -> None:
        if not self.apply:
            return
        for raw in paths:
            path = _safe(raw)
            if path.exists() and path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    def write_manifest(self) -> Path:
        destination = DATA_ROOT / "manifests" / f"{MIGRATION_ID}.csv"
        if not self.apply:
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(self.rows[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(row) for row in self.rows)
        return destination


def _inventory(names: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "directories": {},
    }
    for name in names:
        path = REPO_ROOT / name
        if path.is_dir():
            count, size = _tree_stats(path)
            result["directories"][name] = {"files": count, "bytes": size}
        elif path.is_file():
            result["directories"][name] = {"files": 1, "bytes": path.stat().st_size}
        else:
            result["directories"][name] = {"files": 0, "bytes": 0}
    return result


def _write_inventory(name: str, value: dict[str, Any]) -> None:
    path = DATA_ROOT / "manifests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_sources(m: Migrator) -> None:
    raw = DATA_ROOT / "raw"
    m.move_tree(raw / "videos", DATA_ROOT / "sources" / "visem" / "videos")
    for name in (
        "fatty_acids_serum.csv", "fatty_acids_spermatoza.csv",
        "participant_related_data.csv", "semen_analysis_data.csv", "sex_hormones.csv",
    ):
        m.move_file(raw / name, DATA_ROOT / "sources" / "visem" / "clinical" / name)
    for name in ("videos.csv", "descriptions.txt"):
        m.move_file(raw / name, DATA_ROOT / "sources" / "visem" / "metadata" / name)

    tracked = DATA_ROOT / "tracked"
    m.move_tree(
        tracked / "VISEM_Tracking_Train_v4",
        DATA_ROOT / "sources" / "visem_tracking" / "dataset",
    )
    m.move_tree(
        tracked / "visem-extracted-30s-excluding-selected-20",
        DATA_ROOT / "derived" / "clips" / "untracked_65",
    )
    m.move_tree(
        tracked / "visem-extracted-30s-selected-20-videos-excluding-first-30s",
        DATA_ROOT / "derived" / "clips" / "tracked_20_after_30s",
    )
    for item in list(tracked.glob("*.csv")):
        m.move_file(item, DATA_ROOT / "sources" / "visem_tracking" / "metadata" / item.name)
    for item in list(tracked.glob("DAS-PGMEI*.pdf")):
        m.move_file(
            item,
            DATA_ROOT / "quarantine" / "unrelated_private_documents" / item.name,
        )

    processed = DATA_ROOT / "processed"
    mapping = {
        "annotations": DATA_ROOT / "derived" / "detection" / "annotations",
        "frames": DATA_ROOT / "derived" / "detection" / "frames",
        "flow_cache": DATA_ROOT / "derived" / "flow" / "cache",
        "tracks": DATA_ROOT / "derived" / "tracking" / "tracks",
        "prediction_windows": DATA_ROOT / "derived" / "prediction" / "windows",
    }
    for source_name, destination in mapping.items():
        m.move_tree(processed / source_name, destination)
    if (processed / "README.md").exists():
        m.move_file(
            processed / "README.md",
            DATA_ROOT
            / "quarantine"
            / "redundant_20260829"
            / "data_processed_README.md",
        )
    m.move_tree(DATA_ROOT / "yolo", DATA_ROOT / "datasets" / "yolo" / "legacy_16_4")

    for weights in ("yolov8n.pt", "yolo26n.pt"):
        m.move_file(
            REPO_ROOT / weights,
            DATA_ROOT / "models" / "detection" / "yolo" / "pretrained" / weights,
        )

    if m.apply:
        for cache in (DATA_ROOT / "sources" / "visem_tracking" / "dataset").rglob("labels.cache"):
            m.remove_recreatable(cache)
    m.remove_empty(
        (
            raw,
            tracked,
            processed,
            DATA_ROOT / "derived" / "detection" / "frames",
        )
    )


def _legacy_config(summary: dict[str, Any]) -> tuple[str, str]:
    method = _slug(str(summary.get("method") or "unknown"))
    overrides = summary.get("overrides") if isinstance(summary.get("overrides"), dict) else {}
    algorithm = method
    if method == "threshold":
        if overrides.get("adaptive"):
            algorithm, human = "adaptive_threshold", "legacy_adaptive"
        elif overrides.get("threshold_value") in (None, ""):
            algorithm, human = "otsu", "legacy_otsu_defaults"
        else:
            human = f"legacy_t{int(overrides['threshold_value'])}"
            if "morph_iterations" in overrides:
                human += f"_o{int(overrides['morph_iterations'])}"
            if "close_iterations" in overrides:
                human += f"_c{int(overrides['close_iterations'])}"
    else:
        human = f"legacy_{method}_defaults"
    digest = hashlib.sha256(
        json.dumps({"method": method, "overrides": overrides}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:8]
    return algorithm, f"{human}__cfg{digest}"


def migrate_frame_tests(m: Migrator) -> None:
    source_root = REPO_ROOT / "results" / "tests"
    if not source_root.exists():
        return
    for batch in list(source_root.glob("*.csv")):
        m.move_file(
            batch,
            DATA_ROOT / "tests" / "detection" / "threshold" / "_comparisons"
            / "frame_screening" / batch.name,
        )
    for video_dir in [path for path in source_root.iterdir() if path.is_dir()]:
        comparison = video_dir / "comparisons.csv"
        if comparison.is_file():
            m.move_file(
                comparison,
                DATA_ROOT / "tests" / "detection" / "threshold" / "_comparisons"
                / "frame_screening" / "by_video" / f"video_{video_dir.name}.csv",
            )
        for run_dir in [path for path in video_dir.iterdir() if path.is_dir()]:
            summary_path = run_dir / "summary.json"
            if not summary_path.is_file():
                algorithm, config_id = "unknown", "legacy_unknown"
                frame = "unknown"
            else:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                algorithm, config_id = _legacy_config(summary)
                frame = str(summary.get("frame", "unknown"))
            destination = (
                DATA_ROOT / "tests" / "detection" / algorithm / config_id
                / "frame_screening" / f"video_{video_dir.name}" / f"frame_{frame}"
                / _slug(run_dir.name)
            )
            files = [item for item in run_dir.rglob("*") if item.is_file()]
            for item in files:
                relative = item.relative_to(run_dir)
                if item.name == "00_input.png" and frame != "unknown":
                    canonical = (
                        DATA_ROOT / "tests" / "detection" / "_shared_inputs"
                        / f"video_{video_dir.name}" / f"frame_{frame}.png"
                    )
                    if canonical.exists():
                        source_hash, canonical_hash = _sha256(item), _sha256(canonical)
                        if source_hash != canonical_hash:
                            canonical = canonical.with_name(f"frame_{frame}__{source_hash[:8]}.png")
                        if canonical.exists():
                            if m.apply:
                                item.unlink()
                            m._record(
                                item, canonical, "deduplicate_identical_input",
                                size=item.stat().st_size if item.exists() else canonical.stat().st_size,
                                count=1, digest=source_hash, verified=True,
                            )
                            continue
                    m.move_file(item, canonical)
                    continue
                m.move_file(item, destination / relative)
            m.remove_empty((run_dir,))
        m.remove_empty((video_dir,))
    m.remove_empty((source_root,))


def migrate_immutable_runs(m: Migrator) -> None:
    runs_root = REPO_ROOT / "results" / "runs"
    if not runs_root.exists():
        return
    manifests = list(runs_root.rglob("manifest.json"))
    for manifest_path in manifests:
        run_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        module = _slug(str(manifest.get("module") or "unknown"))
        algorithm, config_id = _algorithm_and_config(manifest)
        stage = _slug(str(manifest.get("stage") or "unknown"))
        storage = "results" if stage in FINAL_STAGES else "tests"
        destination = DATA_ROOT / storage / module / algorithm / config_id / stage / run_dir.name
        m.move_tree(run_dir, destination, detailed=True)
    if m.apply:
        for directory in sorted(runs_root.rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    m.remove_empty((runs_root,))


def migrate_legacy_pilots(m: Migrator) -> None:
    legacy = REPO_ROOT / "results" / "tracked"
    if legacy.exists():
        for run_dir in [path for path in legacy.iterdir() if path.is_dir()]:
            name = run_dir.name.lower()
            if "threshold" in name:
                algorithm = "threshold"
            elif "bold" in name or "blob" in name:
                algorithm = "blob"
            elif "bgsub" in name:
                algorithm = "mog2"
            elif "watershed" in name:
                algorithm = "watershed"
            else:
                algorithm = "unknown"
            destination = (
                DATA_ROOT / "tests" / "detection" / algorithm
                / "legacy_default__cfgunknown" / "pilot" / run_dir.name
            )
            m.move_tree(run_dir, destination, detailed=True)
        m.remove_empty((legacy,))

    yolo = REPO_ROOT / "results" / "yolo"
    if yolo.exists():
        m.move_tree(
            yolo / "visem_full",
            DATA_ROOT / "tests" / "detection" / "yolo"
            / "pilot_100_epochs__cfglegacy" / "training" / "visem_full",
            detailed=True,
        )
        inferences = yolo / "results"
        if inferences.exists():
            for run_dir in [path for path in inferences.iterdir() if path.is_dir()]:
                m.move_tree(
                    run_dir,
                    DATA_ROOT / "tests" / "detection" / "yolo"
                    / "pilot_100_epochs__cfglegacy" / "pilot" / run_dir.name,
                    detailed=True,
                )
            m.remove_empty((inferences,))
        m.remove_empty((yolo,))


def migrate_reports_and_catalog(m: Migrator) -> None:
    report_root = (
        DATA_ROOT / "tests" / "detection" / "threshold" / "_comparisons"
        / "legacy_pilot_202606" / "report"
    )
    m.move_file(
        REPO_ROOT / "docs" / "relatorio_estatistico_threshold_tcc.docx",
        report_root / "relatorio_estatistico_threshold_tcc.docx",
    )
    m.move_file(
        REPO_ROOT / "output" / "pdf" / "relatorio_estatistico_threshold_tcc.pdf",
        report_root / "relatorio_estatistico_threshold_tcc.pdf",
    )
    m.move_file(
        REPO_ROOT / "results" / "visem.db",
        DATA_ROOT / "catalog" / "legacy" / "visem.db",
        hash_file=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Executa a migração; sem esta flag é dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    before_names = ("data", "results", "output", "tmp", "src", "tests", "configs", "docs", "monografia")
    before = _inventory(before_names)
    migrator = Migrator(apply=args.apply)
    migrate_sources(migrator)
    migrate_frame_tests(migrator)
    migrate_immutable_runs(migrator)
    migrate_legacy_pilots(migrator)
    migrate_reports_and_catalog(migrator)
    if args.apply:
        _write_inventory(f"inventory_before_{MIGRATION_ID}.json", before)
        manifest = migrator.write_manifest()
        _write_inventory(f"inventory_after_{MIGRATION_ID}.json", _inventory(before_names))
        print(f"Migração concluída: {len(migrator.rows)} registros em {manifest}")
    else:
        print(f"Dry-run concluído: {len(migrator.rows)} operações planejadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
