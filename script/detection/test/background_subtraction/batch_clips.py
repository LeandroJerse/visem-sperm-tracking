"""Triagem científica de MOG2/KNN em clipes distribuídos pelo vídeo.

Este executor existe porque subtração de fundo é temporal: avaliar um frame
isolado não representa o algoritmo. Cada clipe possui uma janela de aquecimento
e uma janela posterior de avaliação. O detector é reiniciado antes de cada
clipe e nenhum frame de aquecimento entra em CSVs ou métricas de qualidade e
latência.

Por padrão, uma configuração é executada nos vídeos de treino. A expansão do
``search_space`` do YAML só ocorre mediante ``--expand-search-space`` para
evitar iniciar acidentalmente uma bateria grande.
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from src.core.artifacts import (
    normalize_parameter_overrides,
    sha256_file,
    write_csv_exclusive,
    write_json_exclusive,
)
from src.core.paths import (
    EXPERIMENT_TESTS_ROOT,
    REPOSITORY_ROOT,
    VISEM_TRACKING_TRAIN_ROOT,
    resolve_from_repository,
)
from src.detection.discovery import discover_tracked_ids
from src.detection.io import (
    detection_to_row,
    index_label_files,
    load_gt_for_frame,
    write_detections_csv,
)
from src.detection.registry import build_detector
from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    DEFAULT_SENSITIVITY_GATES_PX,
    DetectionEvaluator,
    write_frame_metrics_csv,
)
from src.experiments.config import ConfigError, canonical_json, resolve_config
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext
from src.experiments.sampling import ClipWindow, evenly_spaced_clips
from src.experiments.sweep import deterministic_subset, parameter_grid


SUPPORTED_METHODS = frozenset({"mog2", "knn"})
MINIMUM_WARMUP_FRAMES = 100
EVALUATION_PROTOCOL_ID = DEFAULT_EVALUATION_PROTOCOL_ID
DEFAULTS: dict[str, Any] = {
    "configuration_id": "background_subtraction_screening",
    "method": None,
    "params": {},
    "sampling": {
        "unit": "clip",
        "clip_count": 3,
        "warmup_frames": MINIMUM_WARMUP_FRAMES,
        "scored_frames": 200,
    },
    "evaluation": {
        "protocol_id": EVALUATION_PROTOCOL_ID,
        "center_gate_px": DEFAULT_CENTER_GATE_PX,
        "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
        "class_policy": DEFAULT_CLASS_POLICY,
    },
    "run": {
        "stage": "screen",
        "split": "train",
        "seed": 42,
        "save_video": False,
        "frozen": False,
    },
    "protocol": {"splits_config": "configs/protocol/splits.yaml"},
    "provenance": {},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Triagem temporal de MOG2/KNN: clipes distribuídos, reset por clipe "
            "e aquecimento excluído das métricas."
        )
    )
    parser.add_argument(
        "--config",
        required=True,
        help="YAML de MOG2 ou KNN (por exemplo configs/detection/mog2/search.yaml).",
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="key=value",
        help=(
            "Override repetível; chave simples entra em params. "
            "Use seção.chave para sampling/evaluation/run."
        ),
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help="Subconjunto de IDs de treino; validação e teste são recusados.",
    )
    parser.add_argument(
        "--clip-count",
        type=int,
        default=None,
        help="Número de clipes distribuídos por vídeo (default: YAML ou 3).",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=None,
        help="Frames de aquecimento por clipe; mínimo científico: 100.",
    )
    parser.add_argument(
        "--scored-frames",
        type=int,
        default=None,
        help="Frames pontuados após o aquecimento de cada clipe.",
    )
    parser.add_argument(
        "--stage",
        choices=["smoke", "screen", "search", "refine"],
        default=None,
        help="Etapa exploratória; validação deve usar o vídeo completo.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--expand-search-space",
        action="store_true",
        help="Expande o produto cartesiano de search_space do YAML.",
    )
    parser.add_argument(
        "--max-configs",
        type=int,
        default=None,
        help="Subamostra determinística do grid (somente com --expand-search-space).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida configuração e mostra as janelas sem executar detectores.",
    )
    return parser.parse_args(argv)


def _require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if value is None:
        value = {}
        config[key] = value
    if not isinstance(value, dict):
        raise ConfigError(f"A seção YAML {key!r} deve ser um mapping.")
    return value


def _validate_sampling(sampling: Mapping[str, Any]) -> tuple[int, int, int]:
    try:
        clip_count = int(sampling.get("clip_count", 3))
        warmup_frames = int(sampling.get("warmup_frames", MINIMUM_WARMUP_FRAMES))
        scored_frames = int(sampling.get("scored_frames", 200))
    except (TypeError, ValueError) as exc:
        raise ConfigError("clip_count, warmup_frames e scored_frames devem ser inteiros.") from exc
    if clip_count <= 0:
        raise ConfigError("sampling.clip_count deve ser positivo.")
    if warmup_frames < MINIMUM_WARMUP_FRAMES:
        raise ConfigError(
            f"sampling.warmup_frames deve ser >= {MINIMUM_WARMUP_FRAMES}; "
            "o transiente não pode ser usado como avaliação."
        )
    if scored_frames <= 0:
        raise ConfigError("sampling.scored_frames deve ser positivo.")
    return clip_count, warmup_frames, scored_frames


def _validate_official_evaluation(evaluation: Mapping[str, Any]) -> None:
    try:
        gate = float(evaluation.get("center_gate_px", DEFAULT_CENTER_GATE_PX))
    except (TypeError, ValueError) as exc:
        raise ConfigError("evaluation.center_gate_px deve ser numérico.") from exc
    policy = str(evaluation.get("class_policy", DEFAULT_CLASS_POLICY)).strip().lower()
    if gate != DEFAULT_CENTER_GATE_PX or policy != DEFAULT_CLASS_POLICY:
        raise ConfigError(
            "A triagem oficial exige GT individual e clusters ignorados a 10 px; "
            f"recebido gate={gate:g}, class_policy={policy!r}."
        )
    try:
        sensitivity = tuple(
            float(value)
            for value in evaluation.get("sensitivity_gates_px", DEFAULT_SENSITIVITY_GATES_PX)
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError("evaluation.sensitivity_gates_px deve ser uma lista numérica.") from exc
    if sorted(sensitivity) != sorted(DEFAULT_SENSITIVITY_GATES_PX):
        raise ConfigError("A triagem oficial exige sensibilidades de 15 e 20 px.")
    if evaluation.get("protocol_id", EVALUATION_PROTOCOL_ID) != EVALUATION_PROTOCOL_ID:
        raise ConfigError(f"A triagem oficial exige evaluation.protocol_id={EVALUATION_PROTOCOL_ID}.")


def _portable_config_source(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve YAML, flags operacionais e ``--set`` com precedência final."""

    config_path = resolve_from_repository(args.config)
    config = resolve_config(config_path, defaults=DEFAULTS)
    params = _require_mapping(config, "params")
    sampling = _require_mapping(config, "sampling")
    evaluation = _require_mapping(config, "evaluation")
    run = _require_mapping(config, "run")
    _require_mapping(config, "protocol")
    provenance = _require_mapping(config, "provenance")

    if config.get("method") not in SUPPORTED_METHODS:
        raise ConfigError(
            "Este executor aceita apenas method: mog2 ou method: knn; "
            f"recebido {config.get('method')!r}."
        )
    if not isinstance(params, dict) or not isinstance(evaluation, dict):
        raise ConfigError("params/evaluation inválidos.")
    if args.clip_count is not None:
        sampling["clip_count"] = args.clip_count
    if args.warmup_frames is not None:
        sampling["warmup_frames"] = args.warmup_frames
    if args.scored_frames is not None:
        sampling["scored_frames"] = args.scored_frames
    if args.stage is not None:
        run["stage"] = args.stage
    if args.seed is not None:
        run["seed"] = args.seed
    run["split"] = "train"
    run["save_video"] = False
    run["frozen"] = False
    sampling["unit"] = "clip"
    provenance.update(
        {
            "config_source": _portable_config_source(config_path),
            "config_source_sha256": sha256_file(config_path),
            "executor": "script.detection.test.background_subtraction.batch_clips",
            "clip_policy": "evenly_spaced_reset_each_clip",
            "warmup_excluded_from_metrics": True,
        }
    )

    config = resolve_config(
        defaults=config,
        overrides=normalize_parameter_overrides(args.overrides),
    )
    _validate_sampling(_require_mapping(config, "sampling"))
    _validate_official_evaluation(_require_mapping(config, "evaluation"))
    if str(config["run"].get("split", "train")) != "train":
        raise ConfigError("A triagem por clipes usa somente o split de treino.")
    if str(config["run"].get("stage", "screen")) not in {
        "smoke",
        "screen",
        "search",
        "refine",
    }:
        raise ConfigError("Etapa inválida para triagem; validação deve usar vídeo completo.")
    return config


def _deduplicate_configurations(configs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for config in configs:
        identity = canonical_json(config)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(config)
    return result


def expand_configurations(
    base: Mapping[str, Any],
    *,
    expand_search_space: bool,
    overrides: Sequence[str],
    max_configs: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    """Materialize one base config or a deterministic subset of its YAML grid."""

    normalized_overrides = normalize_parameter_overrides(overrides)
    if not expand_search_space:
        if max_configs is not None:
            raise ConfigError("--max-configs requer --expand-search-space.")
        return [copy.deepcopy(dict(base))]

    search_space = base.get("search_space")
    if not isinstance(search_space, Mapping) or not search_space:
        raise ConfigError("--expand-search-space requer search_space não vazio no YAML.")
    candidates: list[dict[str, Any]] = []
    for combination in parameter_grid(search_space):
        candidate = copy.deepcopy(dict(base))
        params = _require_mapping(candidate, "params")
        params.update(combination)
        # CLI overrides constrain the grid and always have final precedence.
        candidate = resolve_config(defaults=candidate, overrides=normalized_overrides)
        candidates.append(candidate)
    candidates = _deduplicate_configurations(candidates)
    if max_configs is not None:
        try:
            candidates = deterministic_subset(candidates, maximum=max_configs, seed=seed)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    return candidates


def _value_token(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return f"{value:g}".replace("-", "m").replace(".", "p") if isinstance(value, float) else str(value)


def configuration_label(method: str, params: Mapping[str, Any]) -> str:
    """Readable directory label; the RunContext appends the canonical hash."""

    tokens = [f"h{_value_token(params.get('history', 'na'))}"]
    if method == "mog2":
        tokens.append(f"vt{_value_token(params.get('var_threshold', 'na'))}")
    else:
        tokens.append(f"d2{_value_token(params.get('dist2_threshold', 'na'))}")
    tokens.extend(
        [
            f"k{_value_token(params.get('morph_kernel', 'na'))}",
            f"a{_value_token(params.get('min_area', 'na'))}-{_value_token(params.get('max_area', 'na'))}",
            f"s{_value_token(params.get('detect_shadows', False))}",
        ]
    )
    return f"{method}_" + "_".join(tokens)


def _video_probe(video_path: Path) -> tuple[int, int, int]:
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")
        total_frames = int(round(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        width = int(round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        cap.release()
    if total_frames <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"Metadados de vídeo inválidos em {video_path}.")
    return total_frames, width, height


def plan_video_clips(
    video_path: str | Path,
    *,
    clip_count: int,
    warmup_frames: int,
    scored_frames: int,
) -> tuple[ClipWindow, ...]:
    """Return non-overlapping, deterministic evaluation windows for one video."""

    _validate_sampling(
        {
            "clip_count": clip_count,
            "warmup_frames": warmup_frames,
            "scored_frames": scored_frames,
        }
    )
    total_frames, _, _ = _video_probe(Path(video_path))
    windows = evenly_spaced_clips(
        total_frames,
        count=clip_count,
        evaluation_frames=scored_frames,
        warmup_frames=warmup_frames,
    )
    for previous, current in zip(windows, windows[1:]):
        if current.evaluation_start < previous.evaluation_stop:
            raise ValueError(
                "As janelas de avaliação se sobrepõem. Reduza clip_count/scored_frames "
                "para não contar o mesmo frame mais de uma vez."
            )
    return windows


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _window_rows(windows: Sequence[ClipWindow]) -> list[dict[str, Any]]:
    return [
        {
            "clip_index": clip_index,
            "warmup_start": window.warmup_start,
            "evaluation_start": window.evaluation_start,
            "evaluation_stop_exclusive": window.evaluation_stop,
            "warmup_frames": window.warmup_frames,
            "scored_frames_planned": window.evaluation_frames,
        }
        for clip_index, window in enumerate(windows)
    ]


def run_video_configuration(
    config: Mapping[str, Any],
    *,
    video_path: str | Path,
    gt_dir: str | Path | None,
    video_id: str,
    windows: Sequence[ClipWindow],
    output_root: str | Path | None = None,
    repo_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Execute one immutable video/configuration run and return its summary."""

    method = str(config.get("method", ""))
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"Método não suportado: {method!r}.")
    params = config.get("params")
    if not isinstance(params, Mapping):
        raise ValueError("config.params deve ser um mapping.")
    resolved = copy.deepcopy(dict(config))
    evaluator_cfg = _require_mapping(resolved, "evaluation")
    for key, value in DEFAULTS["evaluation"].items():
        evaluator_cfg.setdefault(key, copy.deepcopy(value))
    _validate_official_evaluation(evaluator_cfg)
    if not windows:
        raise ValueError("Ao menos um clipe é necessário.")
    for window in windows:
        if window.warmup_frames < MINIMUM_WARMUP_FRAMES:
            raise ValueError(
                f"Todo clipe deve aquecer por >= {MINIMUM_WARMUP_FRAMES} frames."
            )

    video_path = Path(video_path)
    if gt_dir is not None and not Path(gt_dir).is_dir():
        raise FileNotFoundError(f"Pasta de ground truth não encontrada: {gt_dir}")
    total_frames, width, height = _video_probe(video_path)
    if any(window.evaluation_stop > total_frames for window in windows):
        raise ValueError("Uma janela planejada ultrapassa o fim do vídeo.")
    label_index = index_label_files(gt_dir) if gt_dir is not None else None
    resolved["configuration_id"] = configuration_label(method, params)
    resolved["input"] = {
        "video": str(video_path.resolve()),
        "video_id": str(video_id),
        "gt_dir": str(Path(gt_dir).resolve()) if gt_dir is not None else None,
        "total_frames": total_frames,
        "clip_windows": _window_rows(windows),
    }
    run_cfg = _require_mapping(resolved, "run")
    stage = str(run_cfg.get("stage", "screen"))
    seed = int(run_cfg.get("seed", 42))
    create_kwargs: dict[str, Any] = {
        "module": "detection",
        "method": method,
        "algorithm": method,
        "stage": stage,
        "seed": seed,
        "config": resolved,
        "repo_root": repo_root,
    }
    if output_root is not None:
        create_kwargs["output_root"] = output_root
    context = RunContext.create(**create_kwargs)

    evaluator = DetectionEvaluator(
        center_gate_px=float(evaluator_cfg["center_gate_px"]),
        class_policy=str(evaluator_cfg.get("class_policy", DEFAULT_CLASS_POLICY)),
        sensitivity_gates_px=tuple(
            float(value)
            for value in evaluator_cfg["sensitivity_gates_px"]
        ),
    )
    detector = build_detector(method, params=dict(params))
    monitor = ResourceMonitor()
    detection_rows: list[dict[str, Any]] = []
    scored_times_ms: list[float] = []
    warmup_decoded = 0
    scored_decoded = 0

    try:
        cap = cv2.VideoCapture(str(video_path))
        try:
            if not cap.isOpened():
                raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")
            for clip_index, window in enumerate(windows):
                detector.reset()
                if not cap.set(cv2.CAP_PROP_POS_FRAMES, float(window.warmup_start)):
                    raise RuntimeError(
                        f"O backend de vídeo recusou seek para frame {window.warmup_start}."
                    )
                positioned_at = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES)))
                if positioned_at != window.warmup_start:
                    raise RuntimeError(
                        "Seek inexato: solicitado frame "
                        f"{window.warmup_start}, backend posicionou em {positioned_at}."
                    )
                for frame_idx in range(window.warmup_start, window.evaluation_stop):
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError(
                            f"Falha ao decodificar {video_path} no frame {frame_idx}."
                        )
                    next_position = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES)))
                    if next_position != frame_idx + 1:
                        raise RuntimeError(
                            "Decodificação perdeu alinhamento: após o frame "
                            f"{frame_idx}, backend reportou posição {next_position}."
                        )
                    started = time.perf_counter()
                    detections = detector.detect(frame)
                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    monitor.sample()
                    if frame_idx < window.evaluation_start:
                        warmup_decoded += 1
                        continue

                    scored_decoded += 1
                    scored_times_ms.append(elapsed_ms)
                    for object_index, detection in enumerate(detections):
                        if detection.object_id is None or detection.object_id == -1:
                            detection.object_id = object_index
                        detection_rows.append(
                            detection_to_row(str(video_id), frame_idx, "detection", detection)
                        )

                    ground_truth: list[Any] = []
                    annotated = False
                    if gt_dir is not None:
                        gt_frame = load_gt_for_frame(
                            gt_dir,
                            frame_idx,
                            width,
                            height,
                            label_index=label_index,
                        )
                        annotated = gt_frame.annotated
                        ground_truth = list(gt_frame.detections)
                        detection_rows.extend(
                            detection_to_row(str(video_id), frame_idx, "manual", item)
                            for item in ground_truth
                        )
                    frame_metrics = evaluator.add_frame(
                        detections,
                        ground_truth if annotated else None,
                        video_id=str(video_id),
                        frame=frame_idx,
                        annotated=annotated,
                        detection_ms=elapsed_ms,
                    )
                    frame_metrics.update(
                        {
                            "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
                            "clip_index": clip_index,
                            "clip_evaluation_offset": frame_idx - window.evaluation_start,
                            "warmup_excluded": True,
                        }
                    )
        finally:
            cap.release()

        expected_warmup = sum(window.warmup_frames for window in windows)
        expected_scored = sum(window.evaluation_frames for window in windows)
        if warmup_decoded != expected_warmup or scored_decoded != expected_scored:
            raise RuntimeError(
                "Execução incompleta: "
                f"warmup {warmup_decoded}/{expected_warmup}, "
                f"avaliação {scored_decoded}/{expected_scored}."
            )

        detections_path = write_detections_csv(
            detection_rows, context.path / "detections.csv"
        )
        frame_metrics_path = write_frame_metrics_csv(
            evaluator.frames, context.path / "frame_metrics.csv"
        )
        windows_path = write_csv_exclusive(
            context.path / "clip_windows.csv", _window_rows(windows)
        )
        evaluation = evaluator.summary(str(video_id))
        costs = monitor.summary()
        summary: dict[str, Any] = {
            **evaluation,
            "run_id": context.run_id,
            "configuration_id": context.configuration_id,
            "configuration_hash": context.configuration_hash,
            "algorithm": method,
            "method": method,
            "stage": stage,
            "split": "train",
            "seed": seed,
            "video_id": str(video_id),
            "video": str(video_path.resolve()),
            "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
            "metric_primary": f"f1_individuals_center_{DEFAULT_CENTER_GATE_PX:g}px",
            "center_gate_px": DEFAULT_CENTER_GATE_PX,
            "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
            "class_policy": DEFAULT_CLASS_POLICY,
            "count_scope": "scored_predictions_minus_individually_annotated_gt",
            "clip_count": len(windows),
            "reset_policy": "reset_before_each_clip",
            "warmup_excluded_from_metrics": True,
            "warmup_frames_total": warmup_decoded,
            "scored_frames": scored_decoded,
            "annotated_frames": evaluation["frames_annotated"],
            "unannotated_frames": evaluation["frames_unannotated"],
            "tp": evaluation["tp"],
            "fp": evaluation["fp"],
            "fn": evaluation["fn"],
            "precision": evaluation["precision"],
            "recall": evaluation["recall"],
            "f1": evaluation["f1"],
            "center_error_mean_px": evaluation["center_error_mean_px"],
            "count_mae": evaluation["count_mae"],
            "count_bias": evaluation["count_bias"],
            "detection_ms_mean": (
                statistics.fmean(scored_times_ms) if scored_times_ms else None
            ),
            "detection_ms_median": (
                statistics.median(scored_times_ms) if scored_times_ms else None
            ),
            "detection_ms_p95": _percentile(scored_times_ms, 0.95),
            "detection_ms_max": max(scored_times_ms) if scored_times_ms else None,
            **costs,
        }
        summary_csv = write_csv_exclusive(context.path / "summary.csv", summary)
        summary_json = write_json_exclusive(context.path / "summary.json", summary)
        metadata = {
            "summary": summary,
            "clip_windows": _window_rows(windows),
            "artifacts": {
                "detections_csv": str(detections_path),
                "frame_metrics_csv": str(frame_metrics_path),
                "clip_windows_csv": str(windows_path),
                "summary_csv": str(summary_csv),
                "summary_json": str(summary_json),
            },
        }
        metadata_path = write_json_exclusive(context.path / "metadata.json", metadata)
        artifacts = {
            **metadata["artifacts"],
            "metadata_json": str(metadata_path),
        }
        context.complete(summary=summary, artifacts=artifacts, costs=costs)
        return {**summary, "run_dir": str(context.path)}
    except BaseException as exc:
        context.fail(exc)
        raise


def _select_train_ids(requested: Sequence[str] | None) -> list[str]:
    split = load_split_spec(REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml")
    available = set(discover_tracked_ids())
    ids = [str(value) for value in (requested or split.train)]
    if len(set(ids)) != len(ids):
        raise ConfigError("A lista de IDs contém vídeos duplicados.")
    outside_train = sorted(set(ids) - set(split.train))
    if outside_train:
        raise ConfigError(
            "A triagem por clipes aceita somente treino; IDs recusados: "
            + ", ".join(outside_train)
        )
    missing = sorted(set(ids) - available)
    if missing:
        raise ConfigError("Vídeos anotados não encontrados: " + ", ".join(missing))
    return ids


def _aggregate_configurations(
    summaries: Sequence[Mapping[str, Any]],
    *,
    method: str,
    output_root: Path,
    batch_id: str,
    invocation: Mapping[str, Any],
) -> tuple[Path, Path]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for summary in summaries:
        grouped.setdefault(str(summary["configuration_id"]), []).append(summary)
    rows: list[dict[str, Any]] = []
    for configuration_id, records in sorted(grouped.items()):
        f1_values = [float(row["f1"]) for row in records if row.get("f1") is not None]
        count_mae_values = [
            float(row["count_mae"])
            for row in records
            if row.get("count_mae") is not None
        ]
        sensitivity_metrics: dict[str, float | None] = {}
        measure_names = {
            key for row in records for key in row
            if key.startswith("secondary_all_objects_")
            and any(key == f"secondary_all_objects_{metric}" or key.startswith(f"secondary_all_objects_{metric}_at_")
                    for metric in ("precision", "recall", "f1", "count_mae", "count_bias", "center_error_mean_px"))
        } | {f"f1_at_{gate:g}px" for gate in DEFAULT_SENSITIVITY_GATES_PX} | {
            key for row in records for key in row if key.startswith(("count_mae", "count_bias"))
        }
        for metric in sorted(measure_names):
            values = [
                float(row[metric])
                for row in records
                if row.get(metric) is not None
            ]
            sensitivity_metrics[f"macro_video_{metric}"] = (
                statistics.fmean(values) if values else None
            )
        total_fields = {
            key for row in records for key in row
            if key.startswith(("n_predictions_", "n_ground_truth_", "n_gt_", "frames_", "count_evaluated_frames", "count_error", "count_abs_error"))
            or (key.startswith("secondary_all_objects_") and key not in measure_names)
            or key.startswith(("tp_at_", "fp_at_", "fn_at_"))
        }
        rows.append(
            {
                "batch_id": batch_id,
                "algorithm": method,
                "configuration_id": configuration_id,
                "configuration_hash": records[0]["configuration_hash"],
                "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
                "metric_primary": f"macro_video_f1_individuals_center_{DEFAULT_CENTER_GATE_PX:g}px",
                "center_gate_px": DEFAULT_CENTER_GATE_PX,
                "sensitivity_gates_px": json.dumps(DEFAULT_SENSITIVITY_GATES_PX),
                "class_policy": DEFAULT_CLASS_POLICY,
                "count_scope": "scored_predictions_minus_individually_annotated_gt",
                "n_videos": len(records),
                "n_videos_with_gt": sum(bool(row.get("frames_annotated", row.get("annotated_frames", 0))) for row in records),
                "n_videos_primary_evaluable": len(f1_values),
                "macro_video_f1": statistics.fmean(f1_values) if f1_values else None,
                **sensitivity_metrics,
                **{f"total_{key}": sum(row.get(key) or 0 for row in records) for key in sorted(total_fields)},
                "macro_video_count_mae": (
                    statistics.fmean(count_mae_values) if count_mae_values else None
                ),
                "total_tp": sum(int(row["tp"]) for row in records),
                "total_fp": sum(int(row["fp"]) for row in records),
                "total_fn": sum(int(row["fn"]) for row in records),
                "run_ids": json.dumps([row["run_id"] for row in records]),
            }
        )
    comparison_root = (
        output_root / "detection" / method / "_comparisons" / "clip_screening"
    )
    comparison_root.mkdir(parents=True, exist_ok=True)
    comparison_path = write_csv_exclusive(
        comparison_root / f"{batch_id}.csv", rows
    )
    batch_manifest = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": method,
        "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
        "metric_primary": f"macro_video_f1_individuals_center_{DEFAULT_CENTER_GATE_PX:g}px",
        "center_gate_px": DEFAULT_CENTER_GATE_PX,
        "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
        "class_policy": DEFAULT_CLASS_POLICY,
        "count_scope": "scored_predictions_minus_individually_annotated_gt",
        "statistical_unit": "video_id",
        "warmup_excluded_from_metrics": True,
        "invocation": dict(invocation),
        "runs": [
            {"run_id": row["run_id"], "run_dir": row["run_dir"]}
            for row in summaries
        ],
        "comparison_csv": str(comparison_path),
    }
    manifest_path = write_json_exclusive(
        comparison_root / f"{batch_id}.json", batch_manifest
    )
    return comparison_path, manifest_path


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    args = parse_args(argv)
    try:
        base = resolve_cli_config(args)
        seed = int(base["run"].get("seed", 42))
        configs = expand_configurations(
            base,
            expand_search_space=args.expand_search_space,
            overrides=args.overrides,
            max_configs=args.max_configs,
            seed=seed,
        )
        video_ids = _select_train_ids(args.ids)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc

    method = str(base["method"])
    clip_count, warmup_frames, scored_frames = _validate_sampling(base["sampling"])
    plans: dict[str, tuple[ClipWindow, ...]] = {}
    for video_id in video_ids:
        video_path = VISEM_TRACKING_TRAIN_ROOT / video_id / f"{video_id}.mp4"
        try:
            plans[video_id] = plan_video_clips(
                video_path,
                clip_count=clip_count,
                warmup_frames=warmup_frames,
                scored_frames=scored_frames,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"Vídeo {video_id}: {exc}") from exc

    total_scored = len(configs) * len(video_ids) * clip_count * scored_frames
    print(
        f"Plano: {method}, {len(configs)} configuração(ões), "
        f"{len(video_ids)} vídeo(s), {clip_count} clipe(s)/vídeo, "
        f"{total_scored} frames pontuados."
    )
    for video_id, windows in plans.items():
        compact = ", ".join(
            f"[{item.warmup_start}:{item.evaluation_start}|{item.evaluation_stop})"
            for item in windows
        )
        print(f"  vídeo {video_id}: {compact}")
    if args.dry_run:
        print("[dry-run] Nenhum detector foi executado e nenhum artefato foi criado.")
        return []

    summaries: list[dict[str, Any]] = []
    for config_index, config in enumerate(configs, start=1):
        config_sampling = config.get("sampling") or {}
        current_dimensions = _validate_sampling(config_sampling)
        if current_dimensions != (clip_count, warmup_frames, scored_frames):
            raise SystemExit(
                "O search_space não pode variar clip_count/warmup/scored_frames; "
                "a amostragem deve ser idêntica entre configurações."
            )
        label = configuration_label(method, config.get("params") or {})
        print(f"Configuração {config_index}/{len(configs)}: {label}")
        for video_id in video_ids:
            folder = VISEM_TRACKING_TRAIN_ROOT / video_id
            summary = run_video_configuration(
                config,
                video_path=folder / f"{video_id}.mp4",
                gt_dir=folder / "labels",
                video_id=video_id,
                windows=plans[video_id],
            )
            summaries.append(summary)
            f1_text = "sem GT" if summary["f1"] is None else f"F1={summary['f1']:.4f}"
            print(f"  vídeo {video_id}: {f1_text} -> {summary['run_dir']}")

    batch_id = datetime.now(timezone.utc).strftime("batch_%Y%m%dT%H%M%S%fZ")
    comparison, manifest = _aggregate_configurations(
        summaries,
        method=method,
        output_root=EXPERIMENT_TESTS_ROOT,
        batch_id=batch_id,
        invocation={
            "config": str(resolve_from_repository(args.config).resolve()),
            "overrides": list(args.overrides),
            "video_ids": video_ids,
            "clip_count": clip_count,
            "warmup_frames": warmup_frames,
            "scored_frames": scored_frames,
            "expand_search_space": args.expand_search_space,
            "max_configs": args.max_configs,
            "seed": seed,
        },
    )
    print(f"Comparação por vídeo: {comparison}")
    print(f"Manifesto da bateria: {manifest}")
    return summaries


if __name__ == "__main__":
    main()
