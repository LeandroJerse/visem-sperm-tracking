"""Reproducible trajectory-prediction CLI for a tracking ``tracks.csv``.

The evaluated CSV is never used to fit an LSTM implicitly.  Learned predictors
require either a checkpoint or explicit ``--train --train-csv OTHER.csv`` with
video-disjoint training data.

File map: src/prediction/README.md.
Official commands: script/README.md, section 4 (Predição).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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
    assert_protocol_access,
    assert_video_ids_in_split,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext

from .base import TrajectoryPredictor
from .hybrid.lstm_with_flow import FlowAwareLSTMPredictor
from .learned.lstm import LSTMPredictor
from .metrics import displacement_errors, trajectory_metrics
from .registry import PREDICTORS, create_predictor
from .windows import TrajectoryWindow, make_trajectory_windows


DEFAULT_CONFIG: dict[str, Any] = {
    "method": None,
    "params": {},
    "data": {
        "tracks_csv": None,
        "video_id": None,
        "track_ids": [],
        "history_length": 20,
        "horizons": [1, 5, 10],
        "stride": 1,
        "include_predicted_rows": False,
        "future_flow_mode": "last_observed",
    },
    "evaluation": {"primary": ["ADE", "FDE"]},
    "model": {"checkpoint": None},
    "training": {
        "enabled": False,
        "csv": None,
        "epochs": 50,
        "batch_size": 128,
        "learning_rate": 1e-3,
        "weight_decay": 1e-5,
        "patience": 8,
    },
    "run": {
        "stage": "development",
        "split": "unspecified",
        "seed": 42,
        "frozen": False,
    },
}

_REQUIRED_TRACK_FIELDS = {"video_id", "frame_index", "track_id", "cx", "cy"}
_FLOW_METHODS = {
    "flow_aware_constant_velocity",
    "flow_aware_kalman",
    "flow_aware_particle_filter",
    "flow_aware_lstm",
}
_LSTM_METHODS = {"lstm", "flow_aware_lstm"}


@dataclass(frozen=True)
class LoadedTracks:
    records: tuple[dict[str, Any], ...]
    video_ids: tuple[str, ...]
    track_ids: tuple[str, ...]
    rows_read: int
    rows_used: int
    predicted_rows_ignored: int
    flow_columns_present: bool
    annotation_column_present: bool
    annotation_policy: str
    annotated_rows: int
    unannotated_rows: int
    unknown_annotation_rows: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predição e ADE/FDE a partir de trajetórias contínuas."
    )
    parser.add_argument("--config", default=None, help="YAML de predição.")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="key=value",
        help="Override repetível; chave simples entra em params.",
    )
    parser.add_argument("--method", choices=sorted(PREDICTORS), default=None)
    parser.add_argument("--tracks-csv", default=None)
    parser.add_argument("--video-id", default=None)
    parser.add_argument(
        "--track-id", action="append", default=None, help="ID repetível a selecionar."
    )
    parser.add_argument("--history-length", type=int, default=None)
    parser.add_argument("--horizons", type=int, nargs="+", default=None)
    parser.add_argument("--stride", type=int, default=None)
    parser.add_argument("--checkpoint", default=None, help="Checkpoint LSTM existente.")
    parser.add_argument(
        "--train",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Treino LSTM explícito antes da avaliação.",
    )
    parser.add_argument(
        "--train-csv", default=None, help="CSV de treino, com vídeos disjuntos."
    )
    parser.add_argument("--stage", default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--out-dir", default=None, help="Raiz opcional; default por etapa em data/tests ou data/results."
    )
    return parser.parse_args(argv)


def _normalise_overrides(overrides: list[str] | None) -> list[str]:
    normalised: list[str] = []
    for expression in overrides or []:
        key, separator, raw_value = expression.partition("=")
        key = key.strip()
        if "." in key or key == "method":
            normalised.append(expression)
        else:
            normalised.append(f"params.{key}{separator}{raw_value}")
    return normalised


_FROZEN_PREDICTION_OVERRIDE_KEYS = frozenset(
    {
        "data.tracks_csv",
        "data.video_id",
        "run.stage",
        "run.split",
        "run.seed",
        "run.frozen",
    }
)


def _assert_frozen_cli_is_operational(args: argparse.Namespace) -> None:
    """Allow only input-sequence and provenance changes for frozen models."""

    forbidden = [
        flag
        for flag, value in (
            ("--method", args.method),
            ("--track-id", args.track_id),
            ("--history-length", args.history_length),
            ("--horizons", args.horizons),
            ("--stride", args.stride),
            ("--checkpoint", args.checkpoint),
            ("--train/--no-train", args.train),
            ("--train-csv", args.train_csv),
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
        allowed_keys=_FROZEN_PREDICTION_OVERRIDE_KEYS,
    )


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in ("params", "data", "evaluation", "model", "training", "run"):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config[section], dict):
            raise ConfigError(f"A seção {section!r} deve ser um mapping.")
    if args.method is not None:
        config["method"] = args.method
    if args.tracks_csv is not None:
        config["data"]["tracks_csv"] = args.tracks_csv
    if args.video_id is not None:
        config["data"]["video_id"] = str(args.video_id)
    if args.track_id is not None:
        config["data"]["track_ids"] = [str(value) for value in args.track_id]
    if args.history_length is not None:
        config["data"]["history_length"] = args.history_length
    if args.horizons is not None:
        config["data"]["horizons"] = args.horizons
    if args.stride is not None:
        config["data"]["stride"] = args.stride
    if args.checkpoint is not None:
        config["model"]["checkpoint"] = args.checkpoint
    if args.train is not None:
        config["training"]["enabled"] = args.train
    if args.train_csv is not None:
        config["training"]["csv"] = args.train_csv
    if args.stage is not None:
        config["run"]["stage"] = args.stage
    if args.split is not None:
        config["run"]["split"] = args.split
    if args.seed is not None:
        config["run"]["seed"] = args.seed
    return resolve_config(
        defaults=config, overrides=_normalise_overrides(args.overrides)
    )


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _parse_annotation(value: object, *, row_number: int) -> bool | None:
    """Parse an authoritative, tri-state frame annotation value."""

    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "yes", "sim"}:
        return True
    if normalized in {"0", "false", "no", "nao", "não"}:
        return False
    raise ValueError(
        f"Valor annotated inválido no tracks.csv, linha {row_number}: {value!r}"
    )


def load_tracks_csv(
    path: str | Path,
    *,
    video_id: str | None = None,
    track_ids: Iterable[str] | None = None,
    include_predicted_rows: bool = False,
    require_flow: bool = False,
    allow_multiple_videos: bool = False,
    application_mode: bool = False,
) -> LoadedTracks:
    """Load grouped tracks without converting unknown labels into GT.

    Development/evaluation inputs require the canonical ``annotated`` column.
    Explicit ``0`` and unknown/blank values are ineligible for prediction
    windows.  Only the application split may consume a legacy/unannotated CSV;
    there, unknown values describe observable trajectory rows, not ground truth.
    """

    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"tracks.csv não encontrado: {csv_path}")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(_REQUIRED_TRACK_FIELDS - fields)
        if missing:
            raise ValueError(f"tracks.csv sem colunas obrigatórias: {missing}")
        has_u, has_v = "flow_u" in fields, "flow_v" in fields
        if has_u != has_v:
            raise ValueError("flow_u e flow_v devem existir juntas.")
        has_annotated = "annotated" in fields
        if not has_annotated and not application_mode:
            raise ValueError(
                "tracks.csv sem coluna annotated. Fora do split application, "
                "o estado de anotação é obrigatório para excluir lacunas."
            )
        rows = list(reader)
    if not rows:
        raise ValueError("tracks.csv está vazio.")
    available_videos = sorted(
        {(row.get("video_id") or "").strip() for row in rows if row.get("video_id")}
    )
    if video_id is not None:
        selected_videos = {str(video_id)}
        if not selected_videos <= set(available_videos):
            raise ValueError(
                f"video_id {video_id!r} ausente; disponíveis: {available_videos}"
            )
    elif allow_multiple_videos:
        selected_videos = set(available_videos)
    elif len(available_videos) == 1:
        selected_videos = {available_videos[0]}
    else:
        raise ValueError(
            "CSV contém múltiplos vídeos; informe --video-id. "
            f"Disponíveis: {available_videos}"
        )
    requested_tracks = None if track_ids is None else {str(value) for value in track_ids}
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    ignored_predicted = 0
    for row_number, row in enumerate(rows, start=2):
        row_video = (row.get("video_id") or "").strip()
        row_track = (row.get("track_id") or "").strip()
        if row_video not in selected_videos:
            continue
        if requested_tracks is not None and row_track not in requested_tracks:
            continue
        if not include_predicted_rows and _truthy(row.get("predicted")):
            ignored_predicted += 1
            continue
        if not row_track:
            raise ValueError("track_id vazio no CSV selecionado.")
        grouped[(row_video, row_track)].append((row_number, row))
    if not grouped:
        raise ValueError("Nenhuma trajetória restou após os filtros.")
    available_selected_tracks = {track for _, track in grouped}
    if requested_tracks is not None:
        absent = requested_tracks - available_selected_tracks
        if absent:
            raise ValueError(f"track_ids não encontrados após filtros: {sorted(absent)}")
    if require_flow and not (has_u and has_v):
        raise ValueError(
            "O método flow-aware exige colunas flow_u e flow_v no tracks.csv."
        )

    records: list[dict[str, Any]] = []
    frame_annotation_states: dict[tuple[str, int], bool | None] = {}
    for (record_video, track_id), track_rows in sorted(grouped.items()):
        parsed: list[tuple[int, float, float, bool | None, dict[str, str]]] = []
        for row_number, row in track_rows:
            try:
                frame = int(row["frame_index"])
                cx = float(row["cx"])
                cy = float(row["cy"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(
                    f"Linha inválida em vídeo={record_video}, track={track_id}: {exc}"
                ) from exc
            if frame < 0 or not np.isfinite([cx, cy]).all():
                raise ValueError("Frames devem ser não negativos e posições finitas.")
            annotation = (
                _parse_annotation(row.get("annotated"), row_number=row_number)
                if has_annotated
                else None
            )
            frame_key = (record_video, frame)
            if (
                frame_key in frame_annotation_states
                and frame_annotation_states[frame_key] is not annotation
            ):
                raise ValueError(
                    "Estado annotated inconsistente no mesmo vídeo/frame: "
                    f"vídeo={record_video}, frame={frame}."
                )
            frame_annotation_states[frame_key] = annotation
            parsed.append((frame, cx, cy, annotation, row))
        parsed.sort(key=lambda item: item[0])
        frames = np.asarray([item[0] for item in parsed], dtype=int)
        if len(np.unique(frames)) != len(frames):
            raise ValueError(
                f"Frames duplicados em vídeo={record_video}, track={track_id}."
            )
        positions = np.asarray([[item[1], item[2]] for item in parsed], dtype=np.float32)
        record: dict[str, Any] = {
            "video_id": record_video,
            "track_id": track_id,
            "frame_ids": frames,
            "positions": positions,
            # Unknown is excluded in every scientific split.  For the 65
            # application videos, it denotes an observable row without manual
            # GT and is therefore eligible only under application_mode.
            "annotated": np.asarray(
                [
                    annotation
                    if annotation is not None
                    else bool(application_mode)
                    for _, _, _, annotation, _ in parsed
                ],
                dtype=bool,
            ),
            "annotation_state": tuple(
                annotation for _, _, _, annotation, _ in parsed
            ),
        }
        if require_flow:
            # Row i describes environmental displacement frame_i -> frame_i+1.
            # A missing final value is harmless; an internal missing value on a
            # consecutive transition would corrupt a valid prediction window.
            flow = np.zeros((len(parsed), 2), dtype=np.float32)
            for index, (_, _, _, _, row) in enumerate(parsed[:-1]):
                if frames[index + 1] != frames[index] + 1:
                    continue
                if not record["annotated"][index : index + 2].all():
                    # This transition cannot participate in an eligible
                    # window, so an absent flow value inside an annotation gap
                    # is irrelevant rather than an input error.
                    continue
                try:
                    vector = np.asarray(
                        [float(row["flow_u"]), float(row["flow_v"])],
                        dtype=np.float32,
                    )
                except (TypeError, ValueError, KeyError) as exc:
                    raise ValueError(
                        f"Fluxo ausente na transição consecutiva "
                        f"vídeo={record_video}, track={track_id}, frame={frames[index]}."
                    ) from exc
                if not np.isfinite(vector).all():
                    raise ValueError("flow_u/flow_v devem ser finitos.")
                flow[index] = vector
            record["flow"] = flow
        records.append(record)
    annotation_states = [
        state
        for record in records
        for state in record["annotation_state"]
    ]
    unknown_annotations = sum(state is None for state in annotation_states)
    annotation_policy = (
        "unavailable_application"
        if application_mode and unknown_annotations
        else "explicit_unknown_excluded"
        if unknown_annotations
        else "explicit_frame_status"
    )
    return LoadedTracks(
        records=tuple(records),
        video_ids=tuple(sorted({record["video_id"] for record in records})),
        track_ids=tuple(sorted({record["track_id"] for record in records})),
        rows_read=len(rows),
        rows_used=sum(len(record["frame_ids"]) for record in records),
        predicted_rows_ignored=ignored_predicted,
        flow_columns_present=has_u and has_v,
        annotation_column_present=has_annotated,
        annotation_policy=annotation_policy,
        annotated_rows=sum(state is True for state in annotation_states),
        unannotated_rows=sum(state is False for state in annotation_states),
        unknown_annotation_rows=unknown_annotations,
    )


def _build_windows(
    loaded: LoadedTracks,
    *,
    split: str,
    history_length: int,
    forecast_horizon: int,
    stride: int,
) -> list[TrajectoryWindow]:
    windows: list[TrajectoryWindow] = []
    for record in loaded.records:
        windows.extend(
            make_trajectory_windows(
                record["positions"],
                record["frame_ids"],
                video_id=record["video_id"],
                track_id=record["track_id"],
                split=split,
                history_length=history_length,
                forecast_horizon=forecast_horizon,
                stride=stride,
                flow=record.get("flow"),
                annotated=record["annotated"],
            )
        )
    return windows


def _implementation_hash() -> str:
    digest = hashlib.sha256()
    package_root = Path(__file__).parent
    for source in sorted(package_root.rglob("*.py")):
        digest.update(source.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _make_predictor(
    method: str,
    params: dict[str, Any],
    *,
    seed: int,
) -> TrajectoryPredictor:
    resolved = dict(params)
    if method in {"particle_filter", "flow_aware_particle_filter", "lstm", "flow_aware_lstm"}:
        resolved["seed"] = seed
    return create_predictor(method, **resolved)


def _load_lstm_checkpoint(
    method: str, path: Path, params: dict[str, Any]
) -> LSTMPredictor:
    device = str(params.get("device", "auto"))
    predictor = (
        FlowAwareLSTMPredictor.load(path, device=device)
        if method == "flow_aware_lstm"
        else LSTMPredictor.load(path, device=device)
    )
    if bool(predictor.uses_flow) != (method == "flow_aware_lstm"):
        raise ValueError("Checkpoint LSTM não corresponde à variante solicitada.")
    return predictor


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    method = str(config.get("method") or "")
    if method not in PREDICTORS:
        raise SystemExit(
            f"Método desconhecido: {method!r}. Opções: {', '.join(sorted(PREDICTORS))}"
        )
    data_config = config["data"]
    tracks_value = data_config.get("tracks_csv")
    if not tracks_value:
        raise SystemExit("Informe --tracks-csv ou data.tracks_csv no YAML.")
    tracks_path = Path(tracks_value)
    if not tracks_path.is_file():
        raise SystemExit(f"tracks.csv não encontrado: {tracks_path}")
    history_length = int(data_config.get("history_length", 20))
    stride = int(data_config.get("stride", 1))
    horizons = np.unique(np.asarray(data_config.get("horizons", [1, 5, 10]), dtype=int))
    if history_length < 2 or stride <= 0 or len(horizons) == 0 or np.any(horizons <= 0):
        raise SystemExit("Histórico >=2, stride >0 e horizontes positivos são obrigatórios.")
    future_flow_mode = str(data_config.get("future_flow_mode", "last_observed"))
    if future_flow_mode not in {"last_observed", "observed"}:
        raise SystemExit("data.future_flow_mode deve ser last_observed ou observed.")

    training_config = config["training"]
    checkpoint_value = config["model"].get("checkpoint")
    training_enabled = bool(training_config.get("enabled", False))
    if method in _LSTM_METHODS:
        if bool(checkpoint_value) == training_enabled:
            raise SystemExit(
                "LSTM exige exatamente um modo: --checkpoint ou "
                "--train --train-csv com vídeos disjuntos."
            )
        if training_enabled and not training_config.get("csv"):
            raise SystemExit("--train exige --train-csv ou training.csv.")
    elif checkpoint_value or training_enabled:
        raise SystemExit("Checkpoint/treino explícito são exclusivos dos métodos LSTM.")

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
            if data_config.get("track_ids"):
                raise ProtocolViolation(
                    "Predição congelada não pode avaliar um subconjunto manual de track_ids."
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
    random.seed(seed)
    np.random.seed(seed)

    require_flow = method in _FLOW_METHODS
    application_mode = split.strip().lower() == "application"
    try:
        loaded = load_tracks_csv(
            tracks_path,
            video_id=data_config.get("video_id"),
            track_ids=data_config.get("track_ids") or None,
            include_predicted_rows=bool(data_config.get("include_predicted_rows", False)),
            require_flow=require_flow,
            application_mode=application_mode,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    try:
        assert_video_ids_in_split(loaded.video_ids, split=split)
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc
    windows = _build_windows(
        loaded,
        split=split,
        history_length=history_length,
        forecast_horizon=int(horizons[-1]),
        stride=stride,
    )
    if not windows:
        raise SystemExit(
            "Nenhuma janela totalmente anotada e contínua atende ao histórico "
            "e horizonte solicitados."
        )

    tracks_sha = _sha256(tracks_path)
    config["data"].update(
        {
            "tracks_csv": str(tracks_path.resolve()),
            "tracks_sha256": tracks_sha,
            "tracks_bytes": tracks_path.stat().st_size,
            "video_id": loaded.video_ids[0],
            "track_ids": list(data_config.get("track_ids") or []),
            "history_length": history_length,
            "horizons": horizons.tolist(),
            "stride": stride,
            "annotation_column_present": loaded.annotation_column_present,
            "annotation_policy": loaded.annotation_policy,
            "annotated_rows": loaded.annotated_rows,
            "unannotated_rows": loaded.unannotated_rows,
            "unknown_annotation_rows": loaded.unknown_annotation_rows,
        }
    )
    checkpoint_path = None
    if checkpoint_value:
        checkpoint_path = Path(checkpoint_value)
        if not checkpoint_path.is_file():
            raise SystemExit(f"Checkpoint não encontrado: {checkpoint_path}")
        config["model"]["checkpoint"] = str(checkpoint_path.resolve())
        config["model"]["checkpoint_sha256"] = _sha256(checkpoint_path)
    training_path = None
    if training_enabled:
        training_path = Path(training_config["csv"])
        if not training_path.is_file():
            raise SystemExit(f"CSV de treino não encontrado: {training_path}")
        config["training"]["csv"] = str(training_path.resolve())
        config["training"]["csv_sha256"] = _sha256(training_path)
    config["implementation_hash"] = _implementation_hash()

    create_kwargs: dict[str, Any] = {
        "module": "prediction",
        "method": method,
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        resources = ResourceMonitor()
        params = dict(config.get("params", {}))
        training_metadata: dict[str, Any] | None = None
        if checkpoint_path is not None:
            run_checkpoint = context.path / "model_checkpoint.pt"
            shutil.copy2(checkpoint_path, run_checkpoint)
            predictor = _load_lstm_checkpoint(method, run_checkpoint, params)
            training_metadata = {
                "mode": "external_checkpoint",
                "source": str(checkpoint_path.resolve()),
                "sha256": _sha256(checkpoint_path),
                "run_copy": str(run_checkpoint),
            }
        elif training_enabled:
            assert training_path is not None
            training_loaded = load_tracks_csv(
                training_path,
                include_predicted_rows=bool(
                    training_config.get("include_predicted_rows", False)
                ),
                require_flow=require_flow,
                allow_multiple_videos=True,
            )
            overlap = set(training_loaded.video_ids) & set(loaded.video_ids)
            if overlap:
                raise ValueError(
                    "Treino e avaliação compartilham vídeos: " + ", ".join(sorted(overlap))
                )
            predictor = _make_predictor(method, params, seed=seed)
            if not isinstance(predictor, LSTMPredictor):
                raise TypeError("Modo de treino requer LSTMPredictor.")
            if predictor.history_length != history_length:
                raise ValueError(
                    "params.history_length deve coincidir com data.history_length."
                )
            if predictor.max_horizon < int(horizons[-1]):
                raise ValueError("params.max_horizon não cobre o maior horizonte solicitado.")
            training_windows = _build_windows(
                training_loaded,
                split="training_fit",
                history_length=history_length,
                forecast_horizon=predictor.max_horizon,
                stride=stride,
            )
            if not training_windows:
                raise ValueError("O CSV de treino não produziu janelas válidas.")
            fit_keys = ("epochs", "batch_size", "learning_rate", "weight_decay", "patience")
            fit_params = {
                key: training_config[key]
                for key in fit_keys
                if key in training_config
            }
            fit_history = predictor.fit(training_windows, **fit_params)
            model_path = predictor.save(context.path / "model_checkpoint.pt")
            history_path = _write_json_new(
                context.path / "training_history.json", fit_history
            )
            training_metadata = {
                "mode": "explicit_training",
                "videos": list(training_loaded.video_ids),
                "windows": len(training_windows),
                "csv": str(training_path.resolve()),
                "csv_sha256": _sha256(training_path),
                "annotation_policy": training_loaded.annotation_policy,
                "annotated_rows": training_loaded.annotated_rows,
                "unannotated_rows": training_loaded.unannotated_rows,
                "unknown_annotation_rows": training_loaded.unknown_annotation_rows,
                "checkpoint": str(model_path),
                "history": str(history_path),
            }
        else:
            predictor = _make_predictor(method, params, seed=seed)

        if isinstance(predictor, LSTMPredictor):
            if predictor.history_length != history_length:
                raise ValueError(
                    "history_length do checkpoint/modelo difere de data.history_length."
                )
            if predictor.max_horizon < int(horizons[-1]):
                raise ValueError("Checkpoint/modelo não cobre o maior horizonte solicitado.")

        prediction_rows: list[dict[str, Any]] = []
        window_rows: list[dict[str, Any]] = []
        started = time.perf_counter()
        for window_index, window in enumerate(windows):
            future_flow = (
                window.future_flow
                if require_flow
                and method != "flow_aware_lstm"
                and future_flow_mode == "observed"
                else None
            )
            prediction = predictor.predict(
                window.history,
                horizons,
                flow_history=window.flow_history if require_flow else None,
                future_flow=future_flow,
            )
            targets = window.targets_at(horizons)
            errors = displacement_errors(prediction, targets)
            metrics = trajectory_metrics(prediction, targets)
            origin_frame = int(window.history_frames[-1])
            window_rows.append(
                {
                    "window_index": window_index,
                    "video_id": window.video_id,
                    "track_id": window.track_id,
                    "origin_frame": origin_frame,
                    "ade": metrics["ade"],
                    "fde": metrics["fde"],
                    **{
                        f"error_h{int(horizon)}": metrics[f"error_h{int(horizon)}"]
                        for horizon in horizons
                    },
                }
            )
            for horizon, predicted, target, error in zip(
                horizons, prediction.positions, targets, errors
            ):
                prediction_rows.append(
                    {
                        "window_index": window_index,
                        "video_id": window.video_id,
                        "track_id": window.track_id,
                        "origin_frame": origin_frame,
                        "horizon": int(horizon),
                        "target_frame": origin_frame + int(horizon),
                        "pred_x": float(predicted[0]),
                        "pred_y": float(predicted[1]),
                        "target_x": float(target[0]),
                        "target_y": float(target[1]),
                        "error_px": float(error),
                    }
                )
            if window_index % 100 == 0:
                resources.sample()
        prediction_seconds = time.perf_counter() - started
        resources.sample()

        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": stage,
            "split": split,
            "seed": seed,
            "method": method,
            "video_id": loaded.video_ids[0],
            "tracks_selected": len(loaded.track_ids),
            "track_rows_used": loaded.rows_used,
            "predicted_track_rows_ignored": loaded.predicted_rows_ignored,
            "annotation_policy": loaded.annotation_policy,
            "annotated_track_rows": loaded.annotated_rows,
            "unannotated_track_rows": loaded.unannotated_rows,
            "unknown_annotation_track_rows": loaded.unknown_annotation_rows,
            "history_length": history_length,
            "horizons": ",".join(str(int(value)) for value in horizons),
            "windows_evaluated": len(window_rows),
            "prediction_rows": len(prediction_rows),
            "ade": float(np.mean([row["ade"] for row in window_rows])),
            "fde": float(np.mean([row["fde"] for row in window_rows])),
            "prediction_seconds": prediction_seconds,
            "prediction_ms_per_window": 1000.0 * prediction_seconds / len(window_rows),
            "uses_flow": bool(predictor.uses_flow),
            "flow_columns_present": loaded.flow_columns_present,
            "future_flow_mode": (
                "historical_features_only"
                if method == "flow_aware_lstm"
                else future_flow_mode if require_flow else "not_used"
            ),
            "training_mode": (
                training_metadata["mode"] if training_metadata else "not_applicable"
            ),
        }
        for horizon in horizons:
            matching = [
                row["error_px"]
                for row in prediction_rows
                if row["horizon"] == int(horizon)
            ]
            summary[f"mean_error_h{int(horizon)}"] = float(np.mean(matching))
        summary.update(resources.summary())

        predictions_path = _write_csv_new(
            context.path / "predictions.csv", prediction_rows
        )
        windows_path = _write_csv_new(context.path / "window_metrics.csv", window_rows)
        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_csv_new(context.path / "summary.csv", [summary])
        artifacts: dict[str, str] = {
            "predictions_csv": str(predictions_path),
            "window_metrics_csv": str(windows_path),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
        }
        model_artifact = context.path / "model_checkpoint.pt"
        if model_artifact.is_file():
            artifacts["model_checkpoint"] = str(model_artifact)
        training_history = context.path / "training_history.json"
        if training_history.is_file():
            artifacts["training_history_json"] = str(training_history)
        input_metadata = {
            "path": str(tracks_path.resolve()),
            "sha256": tracks_sha,
            "bytes": config["data"]["tracks_bytes"],
            "video_ids": list(loaded.video_ids),
            "track_ids": list(loaded.track_ids),
            "rows_read": loaded.rows_read,
            "rows_used": loaded.rows_used,
            "predicted_rows_ignored": loaded.predicted_rows_ignored,
            "annotation_column_present": loaded.annotation_column_present,
            "annotation_policy": loaded.annotation_policy,
            "annotated_rows": loaded.annotated_rows,
            "unannotated_rows": loaded.unannotated_rows,
            "unknown_annotation_rows": loaded.unknown_annotation_rows,
        }
        metadata_path = _write_json_new(
            context.path / "metadata.json",
            {
                "summary": summary,
                "input": input_metadata,
                "training": training_metadata,
                "artifacts": artifacts,
            },
        )
        artifacts["metadata_json"] = str(metadata_path)
        context.complete(
            summary=summary,
            input=input_metadata,
            training=training_metadata,
            artifacts=artifacts,
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
