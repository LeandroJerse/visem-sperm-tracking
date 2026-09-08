"""Attach cached apparent-flow features to a tracking ``tracks.csv``.

The input file is never overwritten.  A canonical enriched artifact is always
written inside a new immutable run; ``--output`` optionally creates an
additional exclusive copy for the next pipeline stage.

Example
-------
python -m script.integration.application.enrich_tracks_with_flow \
    --tracks-csv data/tests/tracking/sort/<config>/validation/<run>/tracks.csv \
    --cache-index data/tests/flow/farneback/<config>/validation/<run>/cache_index.csv \
    --sampling background --radius 7 --inner-radius 2
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.core.artifacts import (
    sha256_file as _sha256,
    write_csv_exclusive as _write_csv_new,
    write_json_exclusive as _write_json_new,
)
from src.experiments.config import ConfigError, resolve_config
from src.experiments.protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_overrides,
    assert_frozen_release,
    assert_protocol_access,
    assert_video_ids_in_split,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext

from src.flow.cache import load_flow_file, sample_background_flow, sample_flow


FLOW_COLUMNS = (
    "flow_u",
    "flow_v",
    "flow_magnitude",
    "flow_direction",
    "flow_valid",
    "flow_confidence",
    "flow_next_frame",
    "flow_cache_key",
    "flow_sampling",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "input": {"tracks_csv": None, "cache_index": None},
    "sampling": {
        "mode": "background",
        "radius": 7,
        "inner_radius": 2,
        "min_samples": 8,
    },
    "output": {"path": None},
    "run": {
        "stage": "development",
        "split": "unspecified",
        "seed": 42,
        "frozen": False,
    },
}


@dataclass(frozen=True)
class CacheEntry:
    video_id: str
    previous_frame: int
    next_frame: int
    key: str
    path: Path


@dataclass(frozen=True)
class CacheIndex:
    entries: dict[tuple[str, int], CacheEntry]
    video_ids: tuple[str, ...]

    def entry_for(self, video_id: str, frame: int) -> CacheEntry | None:
        return self.entries.get((video_id, frame)) or self.entries.get(("", frame))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Anexa atributos de fluxo cacheado a tracks.csv sem sobrescrever."
    )
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--set", dest="overrides", action="append", default=[], metavar="key=value"
    )
    parser.add_argument("--tracks-csv", default=None)
    parser.add_argument("--cache-index", default=None)
    parser.add_argument("--sampling", choices=("direct", "background"), default=None)
    parser.add_argument("--radius", type=int, default=None)
    parser.add_argument("--inner-radius", type=int, default=None)
    parser.add_argument("--min-samples", type=int, default=None)
    parser.add_argument(
        "--output",
        default=None,
        help="Cópia externa opcional; falha se o caminho já existir.",
    )
    parser.add_argument("--stage", default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args(argv)


def _normalise_overrides(overrides: list[str] | None) -> list[str]:
    sampling_keys = {"mode", "radius", "inner_radius", "min_samples"}
    normalised: list[str] = []
    for expression in overrides or []:
        key, separator, raw_value = expression.partition("=")
        key = key.strip()
        if "." in key:
            normalised.append(expression)
        elif key in sampling_keys:
            normalised.append(f"sampling.{key}{separator}{raw_value}")
        else:
            normalised.append(expression)
    return normalised


_FROZEN_ENRICHMENT_OVERRIDE_KEYS = frozenset(
    {
        "input.tracks_csv",
        "input.cache_index",
        "output.path",
        "run.stage",
        "run.split",
        "run.seed",
        "run.frozen",
    }
)


def _assert_frozen_cli_is_operational(args: argparse.Namespace) -> None:
    """Keep the promoted spatial sampling policy immutable."""

    forbidden = [
        flag
        for flag, value in (
            ("--sampling", args.sampling),
            ("--radius", args.radius),
            ("--inner-radius", args.inner_radius),
            ("--min-samples", args.min_samples),
        )
        if value is not None
    ]
    if forbidden:
        raise ProtocolViolation(
            "Configuração congelada não permite overrides científicos: "
            f"{forbidden}. Crie/promova outro YAML."
        )
    assert_frozen_overrides(
        _normalise_overrides(args.overrides),
        allowed_keys=_FROZEN_ENRICHMENT_OVERRIDE_KEYS,
    )


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in ("input", "sampling", "output", "run"):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config[section], dict):
            raise ConfigError(f"A seção {section!r} deve ser um mapping.")
    if args.tracks_csv is not None:
        config["input"]["tracks_csv"] = args.tracks_csv
    if args.cache_index is not None:
        config["input"]["cache_index"] = args.cache_index
    if args.sampling is not None:
        config["sampling"]["mode"] = args.sampling
    if args.radius is not None:
        config["sampling"]["radius"] = args.radius
    if args.inner_radius is not None:
        config["sampling"]["inner_radius"] = args.inner_radius
    if args.min_samples is not None:
        config["sampling"]["min_samples"] = args.min_samples
    if args.output is not None:
        config["output"]["path"] = args.output
    if args.stage is not None:
        config["run"]["stage"] = args.stage
    if args.split is not None:
        config["run"]["split"] = args.split
    if args.seed is not None:
        config["run"]["seed"] = args.seed
    config = resolve_config(
        defaults=config, overrides=_normalise_overrides(args.overrides)
    )
    assert_frozen_release(
        args.config, stage=config["run"].get("stage", "development"),
        split=config["run"].get("split", "unspecified"),
        frozen=config["run"].get("frozen", False),
        splits_config=(config.get("protocol") or {}).get("splits_config"),
    )
    return config


def load_cache_index(path: str | Path) -> CacheIndex:
    index_path = Path(path)
    if not index_path.is_file():
        raise FileNotFoundError(f"cache_index.csv não encontrado: {index_path}")
    with index_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        required = {"previous_frame", "next_frame", "key", "path"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"cache_index.csv sem colunas: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError("cache_index.csv está vazio.")
    entries: dict[tuple[str, int], CacheEntry] = {}
    for row_number, row in enumerate(rows, start=2):
        try:
            previous = int(row["previous_frame"])
            following = int(row["next_frame"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Frames inválidos no índice, linha {row_number}.") from exc
        if previous < 0 or following != previous + 1:
            raise ValueError(
                f"Índice exige pares consecutivos na linha {row_number}: {previous}->{following}"
            )
        key = (row.get("key") or "").strip()
        raw_path = (row.get("path") or "").strip()
        if not key or not raw_path:
            raise ValueError(f"key/path vazio no índice, linha {row_number}.")
        artifact = Path(raw_path)
        if not artifact.is_absolute():
            artifact = (index_path.parent / artifact).resolve()
        if not artifact.is_file():
            raise FileNotFoundError(f"Campo de fluxo ausente: {artifact}")
        if artifact.suffix.lower() != ".npz":
            raise ValueError(f"Artefato de fluxo deve ser .npz: {artifact}")
        video_id = (row.get("video_id") or "").strip()
        lookup = (video_id, previous)
        if lookup in entries:
            raise ValueError(f"Entrada duplicada para vídeo/frame {lookup}.")
        entries[lookup] = CacheEntry(video_id, previous, following, key, artifact)
    return CacheIndex(
        entries=entries,
        video_ids=tuple(
            sorted({entry.video_id for entry in entries.values() if entry.video_id})
        ),
    )


def _read_track_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or ())
        required = {"video_id", "frame_index", "track_id", "cx", "cy"}
        missing = sorted(required - set(fields))
        if missing:
            raise ValueError(f"tracks.csv sem colunas: {missing}")
        collisions = sorted(set(fields) & set(FLOW_COLUMNS))
        if collisions:
            raise ValueError(
                "tracks.csv já contém colunas de fluxo; recuso sobrescrever: "
                + ", ".join(collisions)
            )
        rows = list(reader)
    if not rows:
        raise ValueError("tracks.csv está vazio.")
    return fields, rows


def enrich_track_rows(
    rows: list[dict[str, str]],
    cache_index: CacheIndex,
    *,
    sampling: str = "background",
    radius: int = 7,
    inner_radius: int = 2,
    min_samples: int = 8,
    resources: ResourceMonitor | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Enrich rows in memory while loading at most one flow field per group."""

    if sampling not in {"direct", "background"}:
        raise ValueError("sampling deve ser direct ou background.")
    if sampling == "background" and (
        radius <= 0 or inner_radius < 0 or inner_radius >= radius or min_samples <= 0
    ):
        raise ValueError(
            "Amostragem background exige radius > inner_radius >= 0 "
            "e min_samples > 0."
        )
    output: list[dict[str, Any]] = [dict(row) for row in rows]
    groups: dict[CacheEntry, list[tuple[int, np.ndarray]]] = defaultdict(list)
    missing_cache = 0
    for index, row in enumerate(rows):
        try:
            frame = int(row["frame_index"])
            point = np.asarray([float(row["cx"]), float(row["cy"])], dtype=np.float32)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Linha {index + 2} de tracks.csv inválida: {exc}") from exc
        if frame < 0 or not np.isfinite(point).all():
            raise ValueError(f"Linha {index + 2} possui frame/posição inválido.")
        video_id = (row.get("video_id") or "").strip()
        entry = cache_index.entry_for(video_id, frame)
        if entry is None:
            missing_cache += 1
            output[index].update(
                {
                    "flow_u": "",
                    "flow_v": "",
                    "flow_magnitude": "",
                    "flow_direction": "",
                    "flow_valid": 0,
                    "flow_confidence": "",
                    "flow_next_frame": "",
                    "flow_cache_key": "",
                    "flow_sampling": sampling,
                }
            )
            continue
        groups[entry].append((index, point))

    invalid_sampling = 0
    for entry, indexed_points in groups.items():
        result = load_flow_file(entry.path)
        points = np.stack([point for _, point in indexed_points])
        sampled = (
            sample_flow(result, points)
            if sampling == "direct"
            else sample_background_flow(
                result,
                points,
                radius=radius,
                inner_radius=inner_radius,
                min_samples=min_samples,
            )
        )
        for local_index, (row_index, _) in enumerate(indexed_points):
            valid = bool(sampled.valid[local_index])
            if not valid:
                invalid_sampling += 1
            vector = sampled.vectors[local_index]
            confidence: float | str = ""
            if sampled.confidence is not None:
                confidence = float(sampled.confidence[local_index])
            output[row_index].update(
                {
                    "flow_u": float(vector[0]) if valid else "",
                    "flow_v": float(vector[1]) if valid else "",
                    "flow_magnitude": float(np.linalg.norm(vector)) if valid else "",
                    "flow_direction": float(np.arctan2(vector[1], vector[0])) if valid else "",
                    "flow_valid": int(valid),
                    "flow_confidence": confidence if valid else "",
                    "flow_next_frame": entry.next_frame,
                    "flow_cache_key": entry.key,
                    "flow_sampling": sampling,
                }
            )
        if resources is not None:
            resources.sample()
    counts = {
        "rows": len(rows),
        "valid": sum(int(row["flow_valid"]) for row in output),
        "missing_cache": missing_cache,
        "invalid_sampling": invalid_sampling,
        "fields_loaded": len(groups),
    }
    return output, counts


def _copy_exclusive(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            writer.write(block)
    return destination


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except (ConfigError, ProtocolViolation) as exc:
        raise SystemExit(str(exc)) from exc
    tracks_value = config["input"].get("tracks_csv")
    index_value = config["input"].get("cache_index")
    if not tracks_value or not index_value:
        raise SystemExit("Informe --tracks-csv e --cache-index.")
    tracks_path, index_path = Path(tracks_value), Path(index_value)
    output_value = config["output"].get("path")
    external_output = Path(output_value) if output_value else None
    if external_output is not None and external_output.exists():
        raise SystemExit(f"Saída já existe; recuso sobrescrever: {external_output}")

    sampling_config = config["sampling"]
    mode = str(sampling_config.get("mode", "background"))
    radius = int(sampling_config.get("radius", 7))
    inner_radius = int(sampling_config.get("inner_radius", 2))
    min_samples = int(sampling_config.get("min_samples", 8))
    try:
        original_fields, rows = _read_track_rows(tracks_path)
        cache_index = load_cache_index(index_path)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    run_config = config["run"]
    stage = str(run_config.get("stage", "development"))
    split = str(run_config.get("split", "unspecified"))
    seed = int(run_config.get("seed", 42))
    frozen = bool(run_config.get("frozen", False))
    try:
        assert_protocol_access(stage=stage, split=split, frozen=frozen)
        if frozen:
            frozen_source = assert_frozen_config_source(args.config)
            _assert_frozen_cli_is_operational(args)
            provenance = config.setdefault("provenance", {})
            provenance.update(
                {
                    "frozen_config_source": str(frozen_source),
                    "frozen_config_sha256": _sha256(frozen_source),
                }
            )
        artifact_video_ids = [row.get("video_id", "") for row in rows]
        artifact_video_ids.extend(cache_index.video_ids)
        assert_video_ids_in_split(artifact_video_ids, split=split)
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc
    random.seed(seed)
    np.random.seed(seed)

    tracks_sha, index_sha = _sha256(tracks_path), _sha256(index_path)
    config["input"].update(
        {
            "tracks_csv": str(tracks_path.resolve()),
            "tracks_sha256": tracks_sha,
            "cache_index": str(index_path.resolve()),
            "cache_index_sha256": index_sha,
        }
    )
    if external_output is not None:
        config["output"]["path"] = str(external_output.resolve())
    create_kwargs: dict[str, Any] = {
        "module": "flow",
        "method": "enrich_tracks",
        "algorithm": "track_flow_enrichment",
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        resources = ResourceMonitor()
        enriched, counts = enrich_track_rows(
            rows,
            cache_index,
            sampling=mode,
            radius=radius,
            inner_radius=inner_radius,
            min_samples=min_samples,
            resources=resources,
        )
        artifact = _write_csv_new(
            context.path / "tracks_with_flow.csv",
            enriched,
            original_fields + list(FLOW_COLUMNS),
        )
        exported = (
            _copy_exclusive(artifact, external_output)
            if external_output is not None
            else None
        )
        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": stage,
            "split": split,
            "seed": seed,
            "sampling": mode,
            "radius": radius if mode == "background" else None,
            "inner_radius": inner_radius if mode == "background" else None,
            "min_samples": min_samples if mode == "background" else None,
            "rows_processed": counts["rows"],
            "rows_with_valid_flow": counts["valid"],
            "valid_flow_fraction": counts["valid"] / counts["rows"],
            "rows_without_cache_pair": counts["missing_cache"],
            "rows_invalid_at_sampling": counts["invalid_sampling"],
            "cache_fields_loaded": counts["fields_loaded"],
            "external_output": str(exported) if exported is not None else None,
        }
        summary.update(resources.summary())
        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_csv_new(
            context.path / "summary.csv", [summary], list(summary)
        )
        artifacts = {
            "tracks_with_flow_csv": str(artifact),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
        }
        if exported is not None:
            artifacts["external_copy"] = str(exported)
        input_metadata = {
            "tracks_csv": str(tracks_path.resolve()),
            "tracks_sha256": tracks_sha,
            "cache_index": str(index_path.resolve()),
            "cache_index_sha256": index_sha,
            "cache_video_ids": list(cache_index.video_ids),
        }
        metadata_path = _write_json_new(
            context.path / "metadata.json",
            {"summary": summary, "input": input_metadata, "artifacts": artifacts},
        )
        artifacts["metadata_json"] = str(metadata_path)
        context.complete(summary=summary, input=input_metadata, artifacts=artifacts)
    except BaseException as exc:
        context.fail(exc)
        raise

    print("Run:", context.run_id)
    print("Resumo:", summary)
    print("Artefatos:", context.path)
    return summary


if __name__ == "__main__":
    main()
