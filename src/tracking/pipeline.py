"""Reproducible CLI for tracking a unified detection CSV.

The input is the long CSV produced by ``src.detection``.  One source
(``detection`` or ``manual``) feeds the tracker; manual rows are independently
retained as identity ground truth.  Every invocation creates a fresh immutable
run directory with CSV/MOT outputs, summary, metadata and provenance manifest.

File map: src/tracking/README.md.
Official commands: script/README.md, section 2 (Tracking).
"""
from __future__ import annotations

import argparse
import csv
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.core.artifacts import (
    sha256_file as _sha256,
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

from .factory import TRACKERS, create_tracker
from .flow_cache import LazyFlowCacheIndex
from .io import export_motchallenge, export_tracks_csv
from .metrics import IdentityMetrics, evaluate_identity_events
from .runner import group_results_by_frame, track_sequence
from .types import TrackDetection, TrackResult


DEFAULT_CONFIG: dict[str, Any] = {
    "method": None,
    "input_source": None,
    "params": {},
    "evaluation": {"center_gate_px": 15.0, "class_policy": "binary"},
    "run": {
        "stage": "development",
        "split": "unspecified",
        "seed": 42,
    },
    "input": {
        "csv": None,
        "frame_metrics_csv": None,
        "flow_cache_index": None,
        "source": None,
        "video_id": None,
        "frame_start": None,
        "frame_end": None,
    },
}

_REQUIRED_CSV_FIELDS = {
    "video_id",
    "frame",
    "source",
    "object_id",
    "class_id",
    "cx",
    "cy",
    "w",
    "h",
    "score",
}
_SOURCE_ALIASES = {
    "detection": "detection",
    "detector": "detection",
    "frozen_detector": "detection",
    "yolo": "detection",
    "manual": "manual",
    "ground_truth": "manual",
    "gt": "manual",
}


@dataclass(frozen=True)
class TrackingCsvSequence:
    """One selected video/source expanded into consecutive frames."""

    video_id: str
    input_source: str
    configured_input_source: str
    frame_start: int
    frame_end: int
    detections_by_frame: tuple[tuple[TrackDetection, ...], ...]
    annotation_by_frame: dict[int, bool | None]
    ground_truth_by_frame: dict[int, tuple[TrackDetection, ...]]
    input_rows: int
    manual_rows: int
    ignored_input_rows_outside_interval: int
    identity_ground_truth_status: str
    frame_universe_status: str
    frame_metrics_rows: int
    annotated_frames: int
    unannotated_frames: int
    unknown_annotation_frames: int

    @property
    def frames_processed(self) -> int:
        return self.frame_end - self.frame_start + 1

    @property
    def empty_input_frames(self) -> int:
        return sum(not detections for detections in self.detections_by_frame)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tracking online a partir do CSV unificado de detecção."
    )
    parser.add_argument("--config", default=None, help="Configuração YAML de tracking.")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="key=value",
        help="Override repetível; chave simples entra em params.",
    )
    parser.add_argument("--method", choices=sorted(TRACKERS), default=None)
    parser.add_argument("--input-csv", default=None, help="CSV longo da detecção.")
    parser.add_argument(
        "--frame-metrics-csv",
        default=None,
        help=(
            "Companion frame_metrics.csv; quando omitido, tenta o arquivo irmão "
            "do CSV de detecção."
        ),
    )
    parser.add_argument(
        "--flow-cache-index",
        default=None,
        help=(
            "cache_index.csv de src.flow; usado pelo adaptive_flow_sort como "
            "campo lazy do par frame-1->frame."
        ),
    )
    parser.add_argument(
        "--input-source",
        choices=("detection", "manual"),
        default=None,
        help="Fonte que alimenta o tracker; manual continua separado como GT.",
    )
    parser.add_argument("--video-id", default=None, help="Vídeo a selecionar no CSV.")
    parser.add_argument(
        "--frame-start", type=int, default=None, help="Primeiro frame inclusivo."
    )
    parser.add_argument(
        "--frame-end", type=int, default=None, help="Último frame inclusivo."
    )
    parser.add_argument("--stage", default=None, help="Etapa experimental da run.")
    parser.add_argument("--split", default=None, help="Split/fold da run.")
    parser.add_argument("--seed", type=int, default=None, help="Semente da run.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Raiz opcional; default por etapa em data/tests ou data/results.",
    )
    return parser.parse_args(argv)


def _normalise_overrides(overrides: list[str] | None) -> list[str]:
    top_level = {"method"}
    normalised: list[str] = []
    for expression in overrides or []:
        key, separator, raw_value = expression.partition("=")
        key = key.strip()
        # Existing tracking YAMLs use top-level ``input_source``. Internally it
        # is migrated to one canonical field so --set remains truly last-wins.
        if key == "input_source":
            normalised.append(f"input.source{separator}{raw_value}")
            continue
        if "." in key or key in top_level:
            normalised.append(expression)
        else:
            normalised.append(f"params.{expression}")
    return normalised


_FROZEN_TRACKING_OVERRIDE_KEYS = frozenset(
    {
        "input.csv",
        "input.frame_metrics_csv",
        "input.flow_cache_index",
        "input.video_id",
        "run.stage",
        "run.split",
        "run.seed",
        "run.frozen",
    }
)


def _assert_frozen_cli_is_operational(args: argparse.Namespace) -> None:
    """Prevent a promoted tracker from changing scientific parameters."""

    forbidden = [
        flag
        for flag, value in (
            ("--method", args.method),
            ("--input-source", args.input_source),
            ("--frame-start", args.frame_start),
            ("--frame-end", args.frame_end),
        )
        if value is not None
    ]
    if forbidden:
        raise ProtocolViolation(
            "Configuração congelada não permite overrides científicos/amostrais: "
            f"{forbidden}. Crie/promova outro YAML."
        )
    assert_frozen_overrides(
        _normalise_overrides(args.overrides),
        allowed_keys=_FROZEN_TRACKING_OVERRIDE_KEYS,
    )


def _canonical_source(value: object) -> tuple[str, str]:
    configured = str(value or "detection").strip().lower()
    try:
        return _SOURCE_ALIASES[configured], configured
    except KeyError as exc:
        accepted = ", ".join(sorted(_SOURCE_ALIASES))
        raise ConfigError(
            f"input_source desconhecido: {configured!r}. Aceitos: {accepted}"
        ) from exc


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve YAML, explicit flags and highest-precedence ``--set`` values."""
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in ("params", "evaluation", "run", "input"):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config.get(section), dict):
            raise ConfigError(f"A seção YAML {section!r} deve ser um mapping.")

    # Backward-compatible migration for the already versioned tracking YAMLs.
    if config["input"].get("source") is None and config.get("input_source") is not None:
        config["input"]["source"] = config["input_source"]

    if args.method is not None:
        config["method"] = args.method
    if args.input_csv is not None:
        config["input"]["csv"] = args.input_csv
    if args.frame_metrics_csv is not None:
        config["input"]["frame_metrics_csv"] = args.frame_metrics_csv
    if args.flow_cache_index is not None:
        config["input"]["flow_cache_index"] = args.flow_cache_index
    if args.input_source is not None:
        config["input"]["source"] = args.input_source
    if args.video_id is not None:
        config["input"]["video_id"] = str(args.video_id)
    if args.frame_start is not None:
        config["input"]["frame_start"] = args.frame_start
    if args.frame_end is not None:
        config["input"]["frame_end"] = args.frame_end
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
    source_value = config["input"].get("source")
    if source_value is None:
        source_value = config.get("input_source")
    canonical, configured = _canonical_source(source_value)
    config["input_source"] = configured
    config["input"]["source"] = canonical
    config["input"]["configured_source"] = configured
    return config


def _optional_frame(value: object, name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer or null") from exc
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _parse_detection_row(row: dict[str, str], row_number: int) -> TrackDetection:
    object_id_raw = (row.get("object_id") or "").strip()
    object_id: str | None = (
        None if object_id_raw in {"", "-1", "None", "null"} else object_id_raw
    )
    try:
        return TrackDetection(
            cx=float(row["cx"]),
            cy=float(row["cy"]),
            w=float(row["w"]),
            h=float(row["h"]),
            score=float(row.get("score") or 1.0),
            class_id=int(float(row.get("class_id") or 0)),
            object_id=object_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid detection at CSV row {row_number}: {exc}") from exc


def _parse_annotated(value: object, row_number: int) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "sim"}:
        return True
    if normalized in {"0", "false", "no", "nao", "não"}:
        return False
    raise ValueError(
        f"Valor annotated inválido no frame_metrics.csv, linha {row_number}: {value!r}"
    )


def _load_frame_metrics(
    path: str | Path,
) -> tuple[dict[str, dict[int, bool]], int]:
    metrics_path = Path(path)
    if not metrics_path.is_file():
        raise FileNotFoundError(f"frame_metrics.csv não encontrado: {metrics_path}")
    with metrics_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        required = {"video_id", "frame", "annotated"}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(
                f"frame_metrics.csv sem colunas obrigatórias: {missing}"
            )
        rows = list(reader)
    if not rows:
        raise ValueError("frame_metrics.csv está vazio")

    by_video: dict[str, dict[int, bool]] = {}
    for row_number, row in enumerate(rows, start=2):
        video = (row.get("video_id") or "").strip()
        if not video:
            raise ValueError(
                f"video_id vazio no frame_metrics.csv, linha {row_number}"
            )
        try:
            frame = int(row["frame"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Frame inválido no frame_metrics.csv, linha {row_number}"
            ) from exc
        if frame < 0:
            raise ValueError(
                f"Frame negativo no frame_metrics.csv, linha {row_number}"
            )
        annotated = _parse_annotated(row.get("annotated"), row_number)
        frames = by_video.setdefault(video, {})
        if frame in frames:
            raise ValueError(
                f"Frame duplicado no frame_metrics.csv: vídeo={video}, frame={frame}"
            )
        frames[frame] = annotated
    return by_video, len(rows)


def load_tracking_csv(
    path: str | Path,
    *,
    input_source: str,
    configured_input_source: str | None = None,
    video_id: str | None = None,
    frame_start: int | None = None,
    frame_end: int | None = None,
    frame_metrics_csv: str | Path | None = None,
) -> TrackingCsvSequence:
    """Load one video and materialize its scored frame universe.

    ``frame_metrics_csv`` is authoritative for which frames were processed and
    which have manual annotation.  Without it, the object-row interval remains
    available as an explicit, conservative fallback.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV de entrada não encontrado: {csv_path}")
    canonical_source, default_configured = _canonical_source(input_source)
    configured = str(configured_input_source or default_configured)

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(_REQUIRED_CSV_FIELDS - fields)
        if missing:
            raise ValueError(f"CSV unificado sem colunas obrigatórias: {missing}")
        raw_rows = list(reader)
    frame_metrics_by_video: dict[str, dict[int, bool]] = {}
    frame_metrics_rows_total = 0
    if frame_metrics_csv is not None:
        frame_metrics_by_video, frame_metrics_rows_total = _load_frame_metrics(
            frame_metrics_csv
        )
    if not raw_rows and not frame_metrics_by_video:
        raise ValueError(
            "CSV unificado está vazio e não há frame_metrics.csv para recuperar frames"
        )

    object_video_ids = {
        (row.get("video_id") or "").strip()
        for row in raw_rows
        if row.get("video_id")
    }
    available_video_ids = sorted(object_video_ids | set(frame_metrics_by_video))
    if video_id is None:
        if len(available_video_ids) != 1:
            raise ValueError(
                "CSV contém múltiplos vídeos; informe --video-id. "
                f"Disponíveis: {available_video_ids}"
            )
        selected_video = available_video_ids[0]
    else:
        selected_video = str(video_id)
        if selected_video not in available_video_ids:
            raise ValueError(
                f"video_id {selected_video!r} não encontrado. "
                f"Disponíveis: {available_video_ids}"
            )
    if frame_metrics_by_video and selected_video not in frame_metrics_by_video:
        raise ValueError(
            f"video_id {selected_video!r} ausente no frame_metrics.csv; "
            f"disponíveis: {sorted(frame_metrics_by_video)}"
        )

    parsed_rows: list[tuple[int, str, TrackDetection]] = []
    for row_number, row in enumerate(raw_rows, start=2):
        if (row.get("video_id") or "").strip() != selected_video:
            continue
        source = (row.get("source") or "").strip().lower()
        if source not in {"detection", "manual"}:
            raise ValueError(
                f"Source inválido na linha {row_number}: {source!r}; "
                "esperado detection ou manual"
            )
        try:
            frame = int(row["frame"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Frame inválido na linha {row_number}") from exc
        if frame < 0:
            raise ValueError(f"Frame negativo na linha {row_number}")
        parsed_rows.append((frame, source, _parse_detection_row(row, row_number)))

    input_frames = [frame for frame, source, _ in parsed_rows if source == canonical_source]
    metric_frames = frame_metrics_by_video.get(selected_video, {})
    universe_frames = sorted(metric_frames) if metric_frames else input_frames
    start = _optional_frame(frame_start, "frame_start")
    end = _optional_frame(frame_end, "frame_end")
    if start is None:
        if not universe_frames:
            raise ValueError(
                "Não há frames da fonte escolhida nem frame_metrics.csv para inferir frame_start"
            )
        start = min(universe_frames)
    if end is None:
        if not universe_frames:
            raise ValueError(
                "Não há frames da fonte escolhida nem frame_metrics.csv para inferir frame_end"
            )
        end = max(universe_frames)
    if start > end:
        raise ValueError("frame_start cannot be greater than frame_end")

    input_by_frame: dict[int, list[TrackDetection]] = {}
    manual_by_frame: dict[int, list[TrackDetection]] = {}
    ignored = 0
    input_rows = manual_rows = 0
    manual_ids_valid = True
    for frame, source, detection in parsed_rows:
        if source == canonical_source:
            if start <= frame <= end:
                input_by_frame.setdefault(frame, []).append(detection)
                input_rows += 1
            else:
                ignored += 1
        if source == "manual" and start <= frame <= end:
            manual_by_frame.setdefault(frame, []).append(detection)
            manual_rows += 1
            if detection.object_id is None:
                manual_ids_valid = False

    if metric_frames:
        missing_from_metrics = sorted(
            frame for frame in manual_by_frame if frame not in metric_frames
        )
        inconsistent = sorted(
            frame
            for frame in manual_by_frame
            if frame in metric_frames and not metric_frames[frame]
        )
        if missing_from_metrics:
            raise ValueError(
                "Há linhas manuais fora do universo do frame_metrics.csv: "
                f"{missing_from_metrics[:10]}"
            )
        if inconsistent:
            raise ValueError(
                "frame_metrics.csv marca como não anotados frames com linhas manuais: "
                f"{inconsistent[:10]}"
            )
        annotated_frame_ids = {
            frame
            for frame, annotated in metric_frames.items()
            if annotated and start <= frame <= end
        }
        ground_truth = {
            frame: tuple(manual_by_frame.get(frame, ()))
            for frame in sorted(annotated_frame_ids)
        }
        metrics_rows_in_interval = sum(start <= frame <= end for frame in metric_frames)
        unannotated_frames = sum(
            start <= frame <= end and not annotated
            for frame, annotated in metric_frames.items()
        )
        unknown_annotation_frames = (
            end - start + 1 - metrics_rows_in_interval
        )
        frame_universe_status = "frame_metrics_csv"
        annotation_by_frame = {
            frame: metric_frames.get(frame) for frame in range(start, end + 1)
        }
    else:
        ground_truth = {
            frame: tuple(detections)
            for frame, detections in sorted(manual_by_frame.items())
        }
        annotated_frame_ids = set(ground_truth)
        metrics_rows_in_interval = 0
        unannotated_frames = 0
        unknown_annotation_frames = end - start + 1 - len(annotated_frame_ids)
        frame_universe_status = "object_rows_fallback"
        # A manual object row proves that its frame was annotated.  All other
        # frames remain unknown: absence of an object row cannot distinguish an
        # annotated-empty frame from a missing label file.
        annotation_by_frame = {
            frame: (True if frame in annotated_frame_ids else None)
            for frame in range(start, end + 1)
        }

    if not manual_ids_valid:
        gt_status = "unavailable_missing_persistent_ids"
    elif metric_frames and ground_truth:
        gt_status = "available_frame_metrics"
    elif not metric_frames and manual_rows:
        gt_status = "available_manual_rows_fallback"
    elif metric_frames:
        gt_status = "unavailable_no_annotated_frames"
    else:
        gt_status = "unavailable_no_manual_rows"
    sequence = tuple(
        tuple(input_by_frame.get(frame, ())) for frame in range(start, end + 1)
    )
    return TrackingCsvSequence(
        video_id=selected_video,
        input_source=canonical_source,
        configured_input_source=configured,
        frame_start=start,
        frame_end=end,
        detections_by_frame=sequence,
        annotation_by_frame=annotation_by_frame,
        ground_truth_by_frame=ground_truth,
        input_rows=input_rows,
        manual_rows=manual_rows,
        ignored_input_rows_outside_interval=ignored,
        identity_ground_truth_status=gt_status,
        frame_universe_status=frame_universe_status,
        frame_metrics_rows=(
            metrics_rows_in_interval if frame_metrics_by_video else frame_metrics_rows_total
        ),
        annotated_frames=len(annotated_frame_ids),
        unannotated_frames=unannotated_frames,
        unknown_annotation_frames=unknown_annotation_frames,
    )


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _write_summary_csv_new(summary: dict[str, Any], path: Path) -> Path:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary))
        writer.writeheader()
        writer.writerow(summary)
    return path


def _write_identity_events_new(
    metrics: IdentityMetrics | None, path: Path
) -> Path:
    fields = (
        "frame_index",
        "event",
        "ground_truth_id",
        "previous_prediction_id",
        "current_prediction_id",
    )
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if metrics is not None:
            for event in metrics.events:
                writer.writerow(asdict(event))
    return path


def _evaluate_identity(
    sequence: TrackingCsvSequence,
    results: list[TrackResult],
    evaluation_config: dict[str, Any],
) -> tuple[str, IdentityMetrics | None]:
    if not sequence.identity_ground_truth_status.startswith("available_"):
        return sequence.identity_ground_truth_status, None
    policy = str(evaluation_config.get("class_policy", "binary")).lower()
    if policy not in {"binary", "class_aware", "multiclass"}:
        raise ValueError(
            "evaluation.class_policy must be binary, class_aware or multiclass"
        )
    predictions = group_results_by_frame(results)
    # With frame_metrics.csv this includes annotated-empty GT frames.  The
    # fallback contains only frames represented by manual object rows and keeps
    # that limitation explicit in the returned status.
    evaluation_frames = set(sequence.ground_truth_by_frame)
    predictions_on_annotated_rows = {
        frame: predictions.get(frame, []) for frame in evaluation_frames
    }
    metrics = evaluate_identity_events(
        sequence.ground_truth_by_frame,
        predictions_on_annotated_rows,
        max_center_distance=float(evaluation_config.get("center_gate_px", 15.0)),
        class_aware=policy != "binary",
    )
    status = (
        "computed_on_frame_metrics_universe"
        if sequence.frame_universe_status == "frame_metrics_csv"
        else "computed_on_frames_with_manual_rows"
    )
    return status, metrics


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except (ConfigError, ProtocolViolation) as exc:
        raise SystemExit(str(exc)) from exc

    method = str(config.get("method") or "")
    if not method:
        raise SystemExit("Informe --method ou defina 'method' no YAML.")
    if method not in TRACKERS:
        raise SystemExit(
            f"Método desconhecido: {method}. Opções: {', '.join(sorted(TRACKERS))}"
        )
    input_csv_value = config["input"].get("csv")
    if not input_csv_value:
        raise SystemExit("Informe --input-csv ou defina 'input.csv' no YAML.")
    params = config.get("params", {})
    if not isinstance(params, dict):
        raise SystemExit("A seção 'params' deve ser um mapping.")

    run_config = config["run"]
    seed = int(run_config.get("seed", 42))
    stage = str(run_config.get("stage", "development"))
    split = str(run_config.get("split", "unspecified"))
    frozen = bool(run_config.get("frozen", False))
    try:
        assert_protocol_access(stage=stage, split=split, frozen=frozen)
        if frozen:
            frozen_source = assert_frozen_config_source(args.config)
            _assert_frozen_cli_is_operational(args)
            if config["input"].get("frame_start") not in (None, "") or config[
                "input"
            ].get("frame_end") not in (None, ""):
                raise ProtocolViolation(
                    "Tracking congelado deve processar a sequência completa; "
                    "frame_start/frame_end são proibidos."
                )
            provenance = config.setdefault("provenance", {})
            provenance.update(
                {
                    "frozen_config_source": str(frozen_source),
                    "frozen_config_sha256": _sha256(frozen_source),
                }
            )
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc

    input_csv = Path(input_csv_value)
    configured_frame_metrics = config["input"].get("frame_metrics_csv")
    if configured_frame_metrics in (None, ""):
        sibling_metrics = input_csv.with_name("frame_metrics.csv")
        frame_metrics_path = sibling_metrics if sibling_metrics.is_file() else None
        frame_metrics_resolution = (
            "auto_detected_sibling" if frame_metrics_path is not None else "not_available"
        )
    else:
        frame_metrics_path = Path(configured_frame_metrics)
        frame_metrics_resolution = "explicit"
        if not frame_metrics_path.is_file():
            raise SystemExit(f"frame_metrics.csv não encontrado: {frame_metrics_path}")
    try:
        sequence = load_tracking_csv(
            input_csv,
            input_source=str(config["input"]["source"]),
            configured_input_source=str(config["input"]["configured_source"]),
            video_id=config["input"].get("video_id"),
            frame_start=config["input"].get("frame_start"),
            frame_end=config["input"].get("frame_end"),
            frame_metrics_csv=frame_metrics_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    try:
        assert_video_ids_in_split([sequence.video_id], split=split)
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc

    flow_index: LazyFlowCacheIndex | None = None
    flow_index_path: Path | None = None
    configured_flow_index = config["input"].get("flow_cache_index")
    if configured_flow_index not in (None, ""):
        if method != "adaptive_flow_sort":
            raise SystemExit(
                "--flow-cache-index é exclusivo de adaptive_flow_sort; "
                "os baselines puros não recebem fluxo."
            )
        flow_index_path = Path(configured_flow_index)
        try:
            flow_index = LazyFlowCacheIndex(flow_index_path)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc

    # Values inferred from the data are part of the resolved, hashed provenance.
    config["input"]["csv"] = str(input_csv.resolve())
    config["input"]["csv_sha256"] = _sha256(input_csv)
    config["input"]["csv_bytes"] = input_csv.stat().st_size
    if frame_metrics_path is not None:
        config["input"]["frame_metrics_csv"] = str(frame_metrics_path.resolve())
        config["input"]["frame_metrics_sha256"] = _sha256(frame_metrics_path)
        config["input"]["frame_metrics_bytes"] = frame_metrics_path.stat().st_size
        config["input"]["frame_metrics_resolution"] = frame_metrics_resolution
    else:
        config["input"]["frame_metrics_csv"] = None
        config["input"]["frame_metrics_resolution"] = "not_available"
    if flow_index is not None and flow_index_path is not None:
        config["input"]["flow_cache_index"] = str(flow_index_path.resolve())
        config["input"]["flow_cache_index_sha256"] = _sha256(flow_index_path)
        config["input"]["flow_cache_index_bytes"] = flow_index_path.stat().st_size
        config["input"]["flow_cache_entries"] = flow_index.entry_count
    else:
        config["input"]["flow_cache_index"] = None
    config["input"]["video_id"] = sequence.video_id
    config["input"]["frame_start"] = sequence.frame_start
    config["input"]["frame_end"] = sequence.frame_end
    _set_seed(seed)

    create_kwargs: dict[str, Any] = {
        "module": "tracking",
        "method": method,
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        tracker = create_tracker(method, **params)
        resources = ResourceMonitor()
        tracking_started = time.perf_counter()
        flows = (
            flow_index.iter_for_interval(sequence.frame_start, sequence.frame_end)
            if flow_index is not None
            else None
        )
        results = track_sequence(
            tracker,
            sequence.detections_by_frame,
            start_frame=sequence.frame_start,
            flows=flows,
            reset=True,
        )
        tracking_seconds = time.perf_counter() - tracking_started
        resources.sample()
        identity_status, identity_metrics = _evaluate_identity(
            sequence, results, config["evaluation"]
        )

        tracks_path = export_tracks_csv(
            results,
            context.path / "tracks.csv",
            video_id=sequence.video_id,
            annotated_by_frame=sequence.annotation_by_frame,
        )
        mot_path = export_motchallenge(results, context.path / "tracks_mot.txt")
        events_path = _write_identity_events_new(
            identity_metrics, context.path / "identity_events.csv"
        )

        grouped = group_results_by_frame(results)
        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": stage,
            "split": split,
            "seed": seed,
            "video_id": sequence.video_id,
            "method": method,
            "input_source": sequence.input_source,
            "configured_input_source": sequence.configured_input_source,
            "frame_start": sequence.frame_start,
            "frame_end": sequence.frame_end,
            "frames_processed": sequence.frames_processed,
            "empty_input_frames": sequence.empty_input_frames,
            "frame_universe_status": sequence.frame_universe_status,
            "frame_metrics_rows": sequence.frame_metrics_rows,
            "annotated_frames": sequence.annotated_frames,
            "unannotated_frames": sequence.unannotated_frames,
            "unknown_annotation_frames": sequence.unknown_annotation_frames,
            "input_detections": sequence.input_rows,
            "manual_gt_rows": sequence.manual_rows,
            "track_rows": len(results),
            "unique_tracks": len({result.track_id for result in results}),
            "predicted_track_rows": sum(result.predicted for result in results),
            "max_tracks_per_frame": max((len(items) for items in grouped.values()), default=0),
            "tracking_seconds": round(tracking_seconds, 6),
            "tracking_ms_per_frame": round(
                1000.0 * tracking_seconds / sequence.frames_processed, 6
            ),
            "identity_evaluation_status": identity_status,
            "hota_status": "external_not_run_use_tracks_mot_artifact",
            "flow_cache_status": (
                "loaded_lazy" if flow_index is not None else "not_provided"
            ),
            "flow_pairs_indexed_for_interval": (
                flow_index.interval_entry_count(
                    sequence.frame_start, sequence.frame_end
                )
                if flow_index is not None
                else 0
            ),
            "flow_fields_loaded": (
                flow_index.fields_loaded if flow_index is not None else 0
            ),
            "flow_pairs_missing": (
                len(flow_index.missing_pairs) if flow_index is not None else 0
            ),
        }
        if identity_metrics is not None:
            summary.update(
                {
                    "identity_matches": identity_metrics.matches,
                    "identity_false_negatives": identity_metrics.false_negatives,
                    "identity_false_positives": identity_metrics.false_positives,
                    "id_switches": identity_metrics.id_switches,
                    "fragmentations": identity_metrics.fragmentations,
                    "spatial_recall": identity_metrics.detection_recall,
                    "spatial_precision": identity_metrics.detection_precision,
                }
            )
        summary.update(resources.summary())

        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_summary_csv_new(summary, context.path / "summary.csv")
        identity_payload: dict[str, Any] = {
            "status": identity_status,
            "scope_note": (
                "Annotated-empty frames are included from frame_metrics.csv."
                if sequence.frame_universe_status == "frame_metrics_csv"
                else "Fallback: only frames represented by manual object rows are "
                "evaluated because no frame_metrics.csv companion was available."
            ),
            "metrics": asdict(identity_metrics) if identity_metrics else None,
        }
        identity_path = _write_json_new(
            context.path / "identity_evaluation.json", identity_payload
        )
        artifacts = {
            "tracks_csv": str(tracks_path),
            "motchallenge_predictions": str(mot_path),
            "identity_events_csv": str(events_path),
            "identity_evaluation_json": str(identity_path),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
        }
        frame_metrics_metadata = (
            {
                "status": frame_metrics_resolution,
                "path": str(frame_metrics_path.resolve()),
                "sha256": config["input"]["frame_metrics_sha256"],
                "bytes": config["input"]["frame_metrics_bytes"],
                "rows_in_interval": sequence.frame_metrics_rows,
                "annotated_frames": sequence.annotated_frames,
                "unannotated_frames": sequence.unannotated_frames,
                "unknown_annotation_frames": sequence.unknown_annotation_frames,
            }
            if frame_metrics_path is not None
            else {
                "status": "not_available_object_rows_fallback",
                "scope_note": identity_payload["scope_note"],
            }
        )
        flow_metadata = (
            {
                "status": "loaded_lazy",
                "path": str(flow_index_path.resolve()),
                "sha256": config["input"]["flow_cache_index_sha256"],
                "bytes": config["input"]["flow_cache_index_bytes"],
                "entries": flow_index.entry_count,
                "indexed_pairs_in_interval": flow_index.interval_entry_count(
                    sequence.frame_start, sequence.frame_end
                ),
                "loaded_pairs": [list(pair) for pair in flow_index.loaded_pairs],
                "missing_pairs": [list(pair) for pair in flow_index.missing_pairs],
                "invalid_pixel_policy": "converted_to_nan_before_tracking",
                "frame_mapping": "update_t_uses_pair_t_minus_1_to_t",
            }
            if flow_index is not None and flow_index_path is not None
            else {"status": "not_provided"}
        )
        input_metadata = {
            "path": str(input_csv.resolve()),
            "sha256": config["input"]["csv_sha256"],
            "bytes": input_csv.stat().st_size,
            "video_id": sequence.video_id,
            "source": sequence.input_source,
            "configured_source": sequence.configured_input_source,
            "frame_interval": [sequence.frame_start, sequence.frame_end],
            "ignored_input_rows_outside_interval": (
                sequence.ignored_input_rows_outside_interval
            ),
            "frame_metrics": frame_metrics_metadata,
            "flow_cache_index": flow_metadata,
        }
        metadata_path = _write_json_new(
            context.path / "metadata.json",
            {
                "summary": summary,
                "input": input_metadata,
                "frame_metrics": frame_metrics_metadata,
                "flow_cache_index": flow_metadata,
                "identity_evaluation": identity_payload,
                "artifacts": artifacts,
            },
        )
        artifacts["metadata_json"] = str(metadata_path)
        context.complete(
            summary=summary,
            input=input_metadata,
            frame_metrics=frame_metrics_metadata,
            flow_cache_index=flow_metadata,
            artifacts=artifacts,
            hota={
                "status": "external_not_run",
                "adapter": "src.evaluation.tracking.TrackEvalHOTAAdapter",
                "motchallenge_predictions": str(mot_path),
            },
        )
    except BaseException as exc:
        context.fail(exc)
        raise

    print("Run:", context.run_id)
    print("Resumo:", summary)
    print("Artefatos:", context.path)
    return summary


if __name__ == "__main__":
    main()
