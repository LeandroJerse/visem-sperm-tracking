"""Discover immutable experiment runs and prepare analytical tables.

``manifest.json`` is the authoritative run record.  Metric and cost artifacts
are optional because different pipeline modules are implemented at different
times.  A run is therefore ingested even when it has no metric CSV yet.

The metric tables are intentionally wide: each artifact row remains one frame
or one video and module-specific columns are retained.  Provenance columns are
added uniformly, while nested values are encoded as JSON strings for SQLite.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.relocation import resolve_migrated_path


RUN_COLUMNS = [
    "run_id",
    "run_path",
    "manifest_path",
    "metadata_path",
    "module",
    "method",
    "algorithm",
    "stage",
    "split",
    "seed",
    "status",
    "config_hash",
    "configuration_id",
    "configuration_hash",
    "storage_class",
    "git_sha",
    "git_dirty",
    "source_hash",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "error",
    "config_json",
    "environment_json",
    "artifacts_json",
]

METRIC_FRAME_COLUMNS = [
    "run_id", "run_path", "module", "method", "algorithm", "stage", "split", "seed",
    "source_path", "metric_unit", "video_id", "frame", "annotated",
]
METRIC_VIDEO_COLUMNS = [
    "run_id", "run_path", "module", "method", "algorithm", "stage", "split", "seed",
    "source_path", "video_id",
]
COST_COLUMNS = [
    "run_id", "run_path", "module", "method", "algorithm", "stage", "split", "seed",
    "source_path", "elapsed_seconds",
]


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def _relative(path: Path, root: Path) -> str:
    """Return a portable relative path, including for paths outside ``root``."""
    try:
        value = os.path.relpath(path.resolve(), root.resolve())
    except (OSError, ValueError):
        value = str(path)
    return value.replace("\\", "/")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _clean_col(name: Any) -> str:
    # Local, deliberately conservative version: artifact columns are already
    # machine-readable in normal runs, but external modules may use spaces.
    import re
    import unicodedata

    text = str(name).strip().replace("⁶", "6").replace("²", "2").replace("³", "3")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower() or "col"


def _clean_columns(columns: list[Any]) -> list[str]:
    result: list[str] = []
    used: dict[str, int] = {}
    for raw in columns:
        base = _clean_col(raw)
        count = used.get(base, 0)
        used[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def _normalise_artifact_value(value: Any, results_dir: Path, run_dir: Path) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalise_artifact_value(item, results_dir, run_dir)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalise_artifact_value(item, results_dir, run_dir) for item in value]
    if not isinstance(value, str) or not value:
        return value
    if "://" in value:
        return value
    migrated = resolve_migrated_path(value)
    if migrated is not None:
        return _relative(migrated, results_dir)
    candidate = Path(value.replace("\\", "/"))
    if candidate.is_absolute():
        return _relative(candidate, results_dir)
    # Runs anteriores à reorganização gravavam o caminho inteiro abaixo de
    # results/runs. Se não houver uma linha no manifesto (fixtures ou material
    # externo), o run_id ainda localiza o mesmo artefato na pasta migrada.
    lowered = [part.casefold() for part in candidate.parts]
    if lowered[:2] == ["results", "runs"]:
        try:
            run_position = lowered.index(run_dir.name.casefold())
        except ValueError:
            run_position = -1
        if run_position >= 0:
            relocated = run_dir.joinpath(*candidate.parts[run_position + 1 :])
            return _relative(relocated, results_dir)
    # Artifact paths emitted as just "summary.csv" are relative to their run.
    if len(candidate.parts) == 1:
        return _relative(run_dir / candidate, results_dir)
    # Paths beginning in the configured results directory are usually relative
    # to the repository, not to the run directory.
    if candidate.parts and candidate.parts[0].lower() == results_dir.name.lower():
        return Path(*candidate.parts[1:]).as_posix()
    if candidate.parts and candidate.parts[0].lower() == "runs":
        return candidate.as_posix()
    return _relative(run_dir / candidate, results_dir)


def _normalise_config_value(value: Any, results_dir: Path, run_dir: Path) -> Any:
    """Normalise declared source/artifact paths without changing other text."""
    if isinstance(value, Mapping):
        return {
            str(key): _normalise_config_value(item, results_dir, run_dir)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalise_config_value(item, results_dir, run_dir) for item in value]
    if not _looks_like_path(value):
        return value
    assert isinstance(value, str)
    if "://" in value:
        return value
    migrated = resolve_migrated_path(value)
    if migrated is not None:
        return _relative(migrated, results_dir)
    candidate = Path(value.replace("\\", "/"))
    if candidate.is_absolute():
        return _relative(candidate, results_dir)
    lowered = [part.casefold() for part in candidate.parts]
    if lowered[:2] == ["results", "runs"]:
        return _normalise_artifact_value(value, results_dir, run_dir)
    # An unknown source remains a portable declared path. It must not be
    # concatenated to the run directory as if it were an output artifact.
    return candidate.as_posix()


def _configuration_identity(
    manifest: Mapping[str, Any], run_dir: Path
) -> tuple[Any, Any]:
    configuration_id = manifest.get("configuration_id")
    configuration_hash = manifest.get("configuration_hash")
    if configuration_id is not None and configuration_hash is not None:
        return configuration_id, configuration_hash
    # Canonical hierarchy: algorithm/configuration/stage/run_id.
    directory = run_dir.parent.parent.name
    match = re.fullmatch(
        r"(?P<identifier>.+)__cfg(?P<digest>[0-9a-fA-F]+)", directory
    )
    if match is None:
        return configuration_id, configuration_hash
    return (
        configuration_id or match.group("identifier"),
        configuration_hash or match.group("digest").lower(),
    )


def _looks_like_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "://" in value:
        return False
    suffix = Path(value).suffix.lower()
    return (
        "/" in value
        or "\\" in value
        or suffix in {".csv", ".json", ".mp4", ".avi", ".parquet", ".pt", ".npy", ".npz"}
    )


def _normalise_dataframe_paths(df: pd.DataFrame, results_dir: Path, run_dir: Path) -> None:
    for column in df.columns:
        if not (
            column in {"csv", "video", "file", "path", "weights"}
            or column.endswith(("_csv", "_file", "_path", "_dir", "_video"))
        ):
            continue
        df[column] = df[column].map(
            lambda value: _normalise_artifact_value(value, results_dir, run_dir)
            if _looks_like_path(value)
            else value
        )


def _serialise_complex_cells(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in result.columns:
        result[column] = result[column].map(
            lambda value: _json(value) if isinstance(value, (dict, list, tuple)) else value
        )
    return result


def _read_table(path: Path) -> pd.DataFrame | None:
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None

    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if not isinstance(payload, Mapping):
        return None
    for key in ("frames", "videos", "records", "metrics", "costs"):
        records = payload.get(key)
        if isinstance(records, list):
            return pd.DataFrame(records)
    return pd.DataFrame([dict(payload)])


def _artifact_kind(path: Path) -> str | None:
    stem = path.stem.lower()
    if stem in {
        "frame_metrics",
        "metrics_frame",
        "pair_metrics",
        "window_metrics",
    } or stem.endswith("_frame_metrics"):
        return "metrics_frame"
    if stem in {"summary", "metrics_video", "video_metrics"} or stem.endswith("_summary"):
        return "metrics_video"
    if stem in {"cost", "costs", "run_costs"} or stem.endswith("_costs"):
        return "costs"
    return None


def _split_from_manifest(manifest: Mapping[str, Any]) -> Any:
    config = manifest.get("config")
    if not isinstance(config, Mapping):
        return None
    run = config.get("run")
    if isinstance(run, Mapping) and run.get("split") is not None:
        return run.get("split")
    return config.get("split")


def _provenance(
    manifest: Mapping[str, Any], run_dir: Path, results_dir: Path
) -> dict[str, Any]:
    return {
        "run_id": str(manifest.get("run_id") or run_dir.name),
        "run_path": _relative(run_dir, results_dir),
        "module": manifest.get("module"),
        "method": manifest.get("method"),
        "algorithm": manifest.get("algorithm") or manifest.get("method"),
        "stage": manifest.get("stage"),
        "split": _split_from_manifest(manifest),
        "seed": manifest.get("seed"),
    }


def _with_provenance(
    df: pd.DataFrame,
    provenance: Mapping[str, Any],
    source_path: Path,
    results_dir: Path,
    run_dir: Path,
    required: list[str],
) -> pd.DataFrame:
    result = df.copy()
    result.columns = _clean_columns(list(result.columns))
    stem = source_path.stem.lower()
    unit_by_stem = {
        "frame_metrics": "frame",
        "metrics_frame": "frame",
        "pair_metrics": "frame_pair",
        "window_metrics": "trajectory_window",
    }
    result["metric_unit"] = unit_by_stem.get(stem, stem)
    if "frame" not in result:
        if "previous_frame" in result:
            result["frame"] = result["previous_frame"]
        elif "origin_frame" in result:
            result["frame"] = result["origin_frame"]
    _normalise_dataframe_paths(result, results_dir, run_dir)
    for key, value in provenance.items():
        result[key] = value
    result["source_path"] = _relative(source_path, results_dir)
    for column in required:
        if column not in result:
            result[column] = None
    ordered = required + [column for column in result.columns if column not in required]
    return _serialise_complex_cells(result[ordered])


def _is_cost_column(column: str) -> bool:
    name = _clean_col(column)
    return (
        name == "fps"
        or "_ms_" in name
        or name.endswith(("_ms", "_seconds", "_hours", "_mb", "_fps"))
        or any(token in name for token in ("latency", "runtime", "throughput", "memory", "vram", "ram_peak"))
    )


def _cost_values(
    manifest: Mapping[str, Any], video_frames: list[pd.DataFrame]
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if manifest.get("elapsed_seconds") is not None:
        values["elapsed_seconds"] = manifest.get("elapsed_seconds")
    declared = manifest.get("costs")
    if isinstance(declared, Mapping):
        values.update({_clean_col(key): value for key, value in declared.items()})
    summary = manifest.get("summary")
    if isinstance(summary, Mapping):
        values.update(
            {_clean_col(key): value for key, value in summary.items() if _is_cost_column(str(key))}
        )
    for frame in video_frames:
        if frame.empty:
            continue
        row = frame.iloc[0].to_dict()
        values.update({key: value for key, value in row.items() if _is_cost_column(key)})
    return values


def load_run_tables(results_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load every immutable run below a data/results root.

    Invalid manifests are skipped. Missing metric/cost artifacts simply produce
    no rows in the corresponding table; they never prevent the run itself from
    appearing in ``runs``. Recursive discovery supports both the historical
    ``results/runs`` tree and the canonical ``data/{tests,results}`` layout.
    """
    results_root = Path(results_dir)
    runs_root = results_root
    run_rows: list[dict[str, Any]] = []
    frame_tables: list[pd.DataFrame] = []
    video_tables: list[pd.DataFrame] = []
    cost_tables: list[pd.DataFrame] = []
    seen_run_ids: set[str] = set()

    for manifest_path in sorted(runs_root.rglob("manifest.json")) if runs_root.exists() else []:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(manifest, Mapping):
            continue
        run_dir = manifest_path.parent
        provenance = _provenance(manifest, run_dir, results_root)
        run_id = provenance["run_id"]
        if run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)

        artifacts = manifest.get("artifacts")
        normalised_artifacts = _normalise_artifact_value(
            artifacts if isinstance(artifacts, (Mapping, list)) else {},
            results_root,
            run_dir,
        )
        config = manifest.get("config") if isinstance(manifest.get("config"), Mapping) else {}
        normalised_config = _normalise_config_value(config, results_root, run_dir)
        environment = (
            manifest.get("environment")
            if isinstance(manifest.get("environment"), Mapping)
            else {}
        )
        metadata_path = run_dir / "metadata.json"
        configuration_id, configuration_hash = _configuration_identity(
            manifest, run_dir
        )
        run_rows.append(
            {
                **provenance,
                "manifest_path": _relative(manifest_path, results_root),
                "metadata_path": _relative(metadata_path, results_root)
                if metadata_path.exists()
                else None,
                "status": manifest.get("status"),
                "config_hash": manifest.get("config_hash"),
                "configuration_id": configuration_id,
                "configuration_hash": configuration_hash,
                "storage_class": manifest.get("storage_class"),
                "git_sha": manifest.get("git_sha"),
                "git_dirty": manifest.get("git_dirty"),
                "source_hash": manifest.get("source_hash"),
                "started_at": manifest.get("started_at"),
                "finished_at": manifest.get("finished_at"),
                "elapsed_seconds": manifest.get("elapsed_seconds"),
                "error": manifest.get("error"),
                "config_json": _json(normalised_config),
                "environment_json": _json(environment),
                "artifacts_json": _json(normalised_artifacts),
            }
        )

        discovered: dict[str, list[tuple[Path, pd.DataFrame]]] = {
            "metrics_frame": [], "metrics_video": [], "costs": []
        }
        seen_artifacts: set[tuple[str, str]] = set()
        for artifact_path in sorted(run_dir.rglob("*")):
            if not artifact_path.is_file() or artifact_path.suffix.lower() not in {".csv", ".json"}:
                continue
            kind = _artifact_kind(artifact_path)
            if kind is None:
                continue
            logical_artifact = (kind, artifact_path.with_suffix("").as_posix())
            if logical_artifact in seen_artifacts:
                continue
            table = _read_table(artifact_path)
            if table is not None and not table.empty:
                discovered[kind].append((artifact_path, table))
                seen_artifacts.add(logical_artifact)

        for artifact_path, table in discovered["metrics_frame"]:
            frame_tables.append(
                _with_provenance(
                    table, provenance, artifact_path, results_root, run_dir,
                    METRIC_FRAME_COLUMNS,
                )
            )

        current_video_frames: list[pd.DataFrame] = []
        for artifact_path, table in discovered["metrics_video"]:
            prepared = _with_provenance(
                table, provenance, artifact_path, results_root, run_dir,
                METRIC_VIDEO_COLUMNS,
            )
            video_tables.append(prepared)
            current_video_frames.append(prepared)
        if not current_video_frames and isinstance(manifest.get("summary"), Mapping):
            prepared = _with_provenance(
                pd.DataFrame([dict(manifest["summary"])]),
                provenance,
                manifest_path,
                results_root,
                run_dir,
                METRIC_VIDEO_COLUMNS,
            )
            video_tables.append(prepared)
            current_video_frames.append(prepared)

        derived_costs = _cost_values(manifest, current_video_frames)
        if discovered["costs"]:
            for artifact_path, table in discovered["costs"]:
                for key, value in derived_costs.items():
                    if key not in table:
                        table[key] = value
                cost_tables.append(
                    _with_provenance(
                        table, provenance, artifact_path, results_root, run_dir,
                        COST_COLUMNS,
                    )
                )
        elif derived_costs:
            cost_tables.append(
                _with_provenance(
                    pd.DataFrame([derived_costs]),
                    provenance,
                    manifest_path,
                    results_root,
                    run_dir,
                    COST_COLUMNS,
                )
            )

    runs = pd.DataFrame(run_rows)
    if runs.empty:
        runs = _empty_frame(RUN_COLUMNS)
    else:
        for column in RUN_COLUMNS:
            if column not in runs:
                runs[column] = None
        runs = runs[RUN_COLUMNS]

    return {
        "runs": runs,
        "metrics_frame": pd.concat(frame_tables, ignore_index=True, sort=False)
        if frame_tables else _empty_frame(METRIC_FRAME_COLUMNS),
        "metrics_video": pd.concat(video_tables, ignore_index=True, sort=False)
        if video_tables else _empty_frame(METRIC_VIDEO_COLUMNS),
        "costs": pd.concat(cost_tables, ignore_index=True, sort=False)
        if cost_tables else _empty_frame(COST_COLUMNS),
    }


def load_runs(results_dir: str | Path) -> pd.DataFrame:
    return load_run_tables(results_dir)["runs"]


def load_metrics_frame(results_dir: str | Path) -> pd.DataFrame:
    return load_run_tables(results_dir)["metrics_frame"]


def load_metrics_video(results_dir: str | Path) -> pd.DataFrame:
    return load_run_tables(results_dir)["metrics_video"]


def load_costs(results_dir: str | Path) -> pd.DataFrame:
    return load_run_tables(results_dir)["costs"]
