"""Immutable run directories and machine-readable provenance manifests."""
from __future__ import annotations

import importlib.metadata
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.core.paths import (
    EXPERIMENT_RESULTS_ROOT,
    EXPERIMENT_TESTS_ROOT,
    REPOSITORY_ROOT,
)

from .config import config_hash


FINAL_STAGES = frozenset(
    {"test", "five_fold", "oof", "cross_validation", "final", "application"}
)


def scientific_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fields that define the scientific configuration.

    Input paths, video identity, split, seed and rendering options identify a
    run, not an algorithm configuration. Excluding them keeps all videos and
    seeds of the same configuration in one directory.
    """
    ignored_top = {
        "input",
        "output",
        "provenance",
        "search_space",
        "selection",
        "configuration_id",
        "implementation_hash",
    }
    reduced = {key: value for key, value in config.items() if key not in ignored_top}

    # Prediction keeps both input identity and scientific window parameters in
    # ``data``.  Strip only the fields inferred from one tracks.csv so videos
    # of the same configuration share a directory.
    data = reduced.get("data")
    if isinstance(data, Mapping):
        ignored_data = {
            "tracks_csv",
            "tracks_sha256",
            "tracks_bytes",
            "video_id",
            "track_ids",
            "annotation_column_present",
            "annotation_policy",
            "annotated_rows",
            "unannotated_rows",
            "unknown_annotation_rows",
        }
        scientific_data = {
            key: value for key, value in data.items() if key not in ignored_data
        }
        if scientific_data:
            reduced["data"] = scientific_data
        else:
            reduced.pop("data", None)

    # A mask policy is scientific; its per-video CSV identity and row counts
    # are not.  The source/margin/pair policy remain in the hash.
    mask = reduced.get("mask")
    if isinstance(mask, Mapping):
        ignored_mask = {
            "csv",
            "path",
            "sha256",
            "bytes",
            "video_id",
            "rows_read",
            "boxes_used",
        }
        scientific_mask = {
            key: value for key, value in mask.items() if key not in ignored_mask
        }
        if scientific_mask:
            reduced["mask"] = scientific_mask
        else:
            reduced.pop("mask", None)

    # Hash model/training data by content when the pipeline has already
    # fingerprinted it, avoiding machine-specific absolute paths.
    model = reduced.get("model")
    if isinstance(model, Mapping) and model.get("checkpoint_sha256"):
        reduced["model"] = {
            key: value for key, value in model.items() if key != "checkpoint"
        }
    training = reduced.get("training")
    if isinstance(training, Mapping) and training.get("csv_sha256"):
        reduced["training"] = {
            key: value for key, value in training.items() if key != "csv"
        }

    run = reduced.get("run")
    if isinstance(run, Mapping):
        ignored_run = {
            "stage",
            "split",
            "seed",
            "seeds",
            "save_video",
            "max_frames",
            "draw_mode",
            "frozen",
            "frame_limit_source",
            "cache",
            "cache_dir",
            "render",
        }
        scientific_run = {
            key: value for key, value in run.items() if key not in ignored_run
        }
        if scientific_run:
            reduced["run"] = scientific_run
        else:
            reduced.pop("run", None)
    return reduced


def configuration_hash(config: Mapping[str, Any]) -> str:
    """Stable hash shared by videos/splits/seeds of one configuration."""
    return config_hash(scientific_config(config))


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value).strip().lower())
    return text.strip("_.-") or "unnamed"


def configuration_directory(method: str, config: Mapping[str, Any]) -> str:
    human_id = config.get("configuration_id") or method
    return f"{_slug(human_id)}__cfg{configuration_hash(config)[:8]}"


def _git_sha(cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "nogit"
    return proc.stdout.strip() or "nogit"


def _git_dirty(cwd: Path) -> bool | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(proc.stdout.strip()) if proc.returncode == 0 else None


def _source_hash(root: Path) -> str:
    """Fingerprint executable/config source, including untracked new files."""
    candidates: list[Path] = []
    for folder in (root / "src", root / "configs", root / "script"):
        if folder.is_dir():
            candidates.extend(
                path
                for path in folder.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix.lower() in {".py", ".yaml", ".yml"}
            )
    for name in ("pyproject.toml", "requirements.txt", "requirements-core.lock"):
        path = root / name
        if path.is_file():
            candidates.append(path)
    digest = hashlib.sha256()
    for path in sorted(set(candidates), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _package_versions(names: tuple[str, ...]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def environment_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": _package_versions(
            (
                "numpy",
                "opencv-python",
                "opencv-python-headless",
                "scipy",
                "PyYAML",
                "psutil",
                "torch",
                "torchvision",
                "ultralytics",
                "filterpy",
            )
        ),
    }
    try:  # optional GPU information
        import torch

        snapshot["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            snapshot["cuda_device"] = torch.cuda.get_device_name(0)
            snapshot["cuda_version"] = torch.version.cuda
    except ImportError:
        snapshot["cuda_available"] = False
    return snapshot


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, path)


@dataclass
class RunContext:
    run_id: str
    path: Path
    module: str
    method: str
    algorithm: str
    stage: str
    seed: int
    config: dict[str, Any]
    repo_root: Path
    source_hash: str
    configuration_id: str
    configuration_hash: str
    storage_class: str
    git_dirty: bool | None
    started_at: str
    _start_clock: float = field(repr=False)

    @classmethod
    def create(
        cls,
        *,
        module: str,
        method: str,
        algorithm: str | None = None,
        stage: str,
        seed: int,
        config: Mapping[str, Any],
        repo_root: str | Path = REPOSITORY_ROOT,
        output_root: str | Path | None = None,
        results_root: str | Path | None = None,
    ) -> "RunContext":
        root = Path(repo_root).resolve()
        sha = _git_sha(root)
        dirty = _git_dirty(root)
        source_hash = _source_hash(root)
        digest = config_hash(config)
        scientific_digest = configuration_hash(config)
        algorithm_id = algorithm or method
        configuration_id = configuration_directory(algorithm_id, config)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{stamp}__{sha}__cfg{digest}__src{source_hash[:10]}__s{seed}"
        if output_root is not None and results_root is not None:
            raise ValueError("Use apenas output_root; results_root é compatibilidade legada.")
        custom_root = output_root if output_root is not None else results_root
        normalized_stage = _slug(stage).replace("-", "_")
        if custom_root is None:
            storage_class = "results" if normalized_stage in FINAL_STAGES else "tests"
            storage_root = (
                EXPERIMENT_RESULTS_ROOT
                if storage_class == "results"
                else EXPERIMENT_TESTS_ROOT
            )
        else:
            storage_class = "custom"
            storage_root = Path(custom_root)
            if not storage_root.is_absolute():
                storage_root = root / storage_root
        path = (
            storage_root
            / _slug(module)
            / _slug(algorithm_id)
            / configuration_id
            / normalized_stage
            / run_id
        )
        path.mkdir(parents=True, exist_ok=False)
        context = cls(
            run_id=run_id,
            path=path,
            module=module,
            method=method,
            algorithm=algorithm_id,
            stage=stage,
            seed=seed,
            config=dict(config),
            repo_root=root,
            source_hash=source_hash,
            configuration_id=configuration_id,
            configuration_hash=scientific_digest,
            storage_class=storage_class,
            git_dirty=dirty,
            started_at=datetime.now(timezone.utc).isoformat(),
            _start_clock=time.perf_counter(),
        )
        context.write_manifest(status="running")
        return context

    def write_manifest(self, *, status: str, **extra: Any) -> Path:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "status": status,
            "module": self.module,
            "method": self.method,
            "algorithm": self.algorithm,
            "stage": self.stage,
            "seed": self.seed,
            "started_at": self.started_at,
            "git_sha": _git_sha(self.repo_root),
            "git_dirty": self.git_dirty,
            "source_hash": self.source_hash,
            "configuration_id": self.configuration_id,
            "configuration_hash": self.configuration_hash,
            "storage_class": self.storage_class,
            "config_hash": config_hash(self.config),
            "config": self.config,
            "environment": environment_snapshot(),
            **extra,
        }
        if status != "running":
            payload["finished_at"] = datetime.now(timezone.utc).isoformat()
            payload["elapsed_seconds"] = round(time.perf_counter() - self._start_clock, 6)
        target = self.path / "manifest.json"
        _atomic_json(target, payload)
        return target

    def complete(self, **extra: Any) -> Path:
        return self.write_manifest(status="complete", **extra)

    def fail(self, error: BaseException | str, **extra: Any) -> Path:
        return self.write_manifest(status="failed", error=str(error), **extra)
