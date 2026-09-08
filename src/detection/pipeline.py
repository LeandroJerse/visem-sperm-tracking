"""CLI entry point for sperm detection.

Examples
--------
Classical baseline on the first 300 frames of one video::

    python -m script.detection.application.run_detection --method threshold \
        --video "Dataset/visem-dataset/visem-dataset/videos/1_09.09.02_SSW.avi" \
        --max-frames 300

Compare against VISEM-Tracking ground truth (overlaid in red)::

    python -m script.detection.application.run_detection --method threshold \
        --video path/to/52/52.mp4 --gt-dir path/to/52/labels_ftid --max-frames 300

Each invocation creates an immutable run below ``data/tests`` during tuning or
validation, and below ``data/results`` only for frozen test/OOF/application.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Any

import numpy as np

from src.core.artifacts import (
    normalize_parameter_overrides as _normalise_overrides,
    sha256_file,
    write_json_exclusive as _write_json_new,
)
from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    DEFAULT_SENSITIVITY_GATES_PX,
)
from src.experiments.config import ConfigError, resolve_config
from src.experiments.dataset import load_split_spec
from src.experiments.protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_overrides,
    assert_frozen_release,
    assert_protocol_access,
)
from src.experiments.runs import RunContext

from .registry import DETECTORS, build_detector, scientific_algorithm_id
from .runner import run_on_video
from .metadata import CLINICAL_FIELDS, load_clinical_row, resolve_video_id


DEFAULT_CONFIG: dict[str, Any] = {
    "method": None,
    "params": {},
    "evaluation": {
        "center_gate_px": DEFAULT_CENTER_GATE_PX,
        "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
        "class_policy": DEFAULT_CLASS_POLICY,
    },
    "run": {
        "stage": "development",
        "split": "unspecified",
        "seed": 42,
        "save_video": True,
        "max_frames": None,
        "draw_mode": "both",
        "frozen": False,
    },
    "input": {"video": None, "gt_dir": None, "videos_csv": None},
    "protocol": {"splits_config": "configs/protocol/splits.yaml"},
    "provenance": {},
}

_SAMPLED_STAGES = frozenset({"smoke", "screen", "search", "refine"})


def _set_seed(seed: int, *, include_torch: bool = False) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if include_torch:
        try:
            import torch
        except ImportError:  # pragma: no cover - YOLO will raise a clearer error later
            return
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detecção de espermatozoides (baselines clássicos + YOLO).")
    p.add_argument("--config", default=None,
                   help="Configuração YAML (method/params/evaluation/run).")
    p.add_argument("--set", dest="overrides", action="append", default=[], metavar="key=value",
                   help="Override YAML repetível; chave simples entra em params, ou use a.b=value.")
    p.add_argument("--method", default=None, choices=list(DETECTORS),
                   help="Algoritmo de detecção (sobrescreve o YAML).")
    p.add_argument("--video", default=None, help="Caminho do vídeo de entrada.")
    p.add_argument("--out-dir", default=None,
                   help="Raiz opcional; por padrão usa data/tests ou data/results conforme a etapa.")
    p.add_argument("--gt-dir", default=None,
                   help="Pasta de labels do VISEM-Tracking para sobrepor o ground truth.")
    p.add_argument("--max-frames", type=int, default=None,
                   help="Limita o número de frames processados.")
    p.add_argument("--draw-mode", default=None, choices=["box", "centroid", "circle", "both"],
                   help="Como desenhar as detecções no vídeo.")
    p.add_argument("--no-video", action="store_true",
                   help="Não gerar vídeo anotado (apenas CSV).")
    p.add_argument("--weights", default=None, help="Pesos do modelo YOLO (apenas --method yolo).")
    p.add_argument("--videos-csv", default=None,
                   help="Caminho de videos.csv para resolver o ID do dataset (default: VISEM original).")
    p.add_argument("--splits-config", default=None,
                   help="Definição versionada dos splits (default: configs/protocol/splits.yaml).")
    p.add_argument("--stage", default=None,
                   help="Etapa experimental (smoke, search, validation, test, five_fold, final).")
    p.add_argument("--split", default=None,
                   help="Nome do split/fold registrado na proveniência.")
    p.add_argument("--seed", type=int, default=None, help="Semente reprodutível da run.")
    return p.parse_args(argv)


def write_summary_csv(summary: dict, path: Path) -> None:
    """Append/write a one-row per-video summary CSV (count stats + clinical join)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve YAML, explicit CLI flags and final ``--set`` overrides."""
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in (
        "params",
        "evaluation",
        "run",
        "input",
        "protocol",
        "provenance",
    ):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config.get(section), dict):
            raise ConfigError(f"A seção YAML {section!r} deve ser um mapping.")

    if args.method is not None:
        config["method"] = args.method
    if args.video is not None:
        config["input"]["video"] = args.video
    if args.gt_dir is not None:
        config["input"]["gt_dir"] = args.gt_dir
    if args.videos_csv is not None:
        config["input"]["videos_csv"] = args.videos_csv
    if args.splits_config is not None:
        config["protocol"]["splits_config"] = args.splits_config
    if args.weights is not None and config.get("method") == "yolo":
        config["params"]["weights"] = args.weights
    if args.max_frames is not None:
        config["run"]["max_frames"] = args.max_frames
    if args.draw_mode is not None:
        config["run"]["draw_mode"] = args.draw_mode
    if args.no_video:
        config["run"]["save_video"] = False
    if args.stage is not None:
        config["run"]["stage"] = args.stage
    if args.split is not None:
        config["run"]["split"] = args.split
    if args.seed is not None:
        config["run"]["seed"] = args.seed

    # Explicit --set is intentionally the final/highest-precedence layer.
    config = resolve_config(defaults=config, overrides=_normalise_overrides(args.overrides))
    evaluation = config["evaluation"]
    current_policy = (
        evaluation.get("class_policy") == DEFAULT_CLASS_POLICY
        and evaluation.get("center_gate_px") == DEFAULT_CENTER_GATE_PX
        and sorted(evaluation.get("sensitivity_gates_px") or []) == sorted(DEFAULT_SENSITIVITY_GATES_PX)
    )
    if current_policy:
        if evaluation.get("protocol_id") not in (None, DEFAULT_EVALUATION_PROTOCOL_ID):
            raise ConfigError("A política V3 resolvida não pode usar o protocol_id de outra avaliação.")
        evaluation.setdefault("protocol_id", DEFAULT_EVALUATION_PROTOCOL_ID)
    elif evaluation.get("protocol_id") == DEFAULT_EVALUATION_PROTOCOL_ID:
        raise ConfigError("O protocol_id V3 não corresponde à política de classes ou aos raios resolvidos.")
    assert_frozen_release(
        args.config,
        stage=config["run"].get("stage", "development"),
        split=config["run"].get("split", "unspecified"),
        frozen=config["run"].get("frozen", False),
        splits_config=config["protocol"].get("splits_config"),
    )
    return config


def _assert_frozen_cli_is_operational(args: argparse.Namespace) -> None:
    """Keep a promoted detector scientifically identical to its YAML source."""

    forbidden_flags: list[str] = []
    if args.method is not None:
        forbidden_flags.append("--method")
    if args.weights is not None:
        forbidden_flags.append("--weights")
    if args.max_frames is not None:
        forbidden_flags.append("--max-frames")
    if forbidden_flags:
        raise ProtocolViolation(
            "Configuração congelada não permite overrides científicos/amostrais: "
            f"{forbidden_flags}. Crie/promova outro YAML."
        )
    assert_frozen_overrides(args.overrides)


def _validate_video_against_split(
    *,
    video_path: Path,
    split: str,
    splits_config: str | Path,
    videos_csv: str | Path | None,
) -> int | None:
    """Resolve the actual input identity and fail before video decoding on mismatch."""

    normalized_split = str(split).strip().lower().replace("-", "_")
    # Application videos and ad-hoc smoke diagnostics are not members of the
    # 20-video annotated split.  Every named fixed split/fold is checked.
    if normalized_split in {"", "unspecified", "application"}:
        return (
            resolve_video_id(video_path, videos_csv)
            if videos_csv
            else resolve_video_id(video_path)
        )
    spec = load_split_spec(splits_config)
    try:
        expected_ids = set(spec.ids_for(normalized_split))
    except KeyError as exc:
        raise ProtocolViolation(str(exc)) from exc
    dataset_id = (
        resolve_video_id(video_path, videos_csv)
        if videos_csv
        else resolve_video_id(video_path)
    )
    if dataset_id is None:
        raise ProtocolViolation(
            f"Não foi possível resolver o video_id real de {video_path} antes da decodificação."
        )
    if str(dataset_id) not in expected_ids:
        raise ProtocolViolation(
            f"Vídeo {dataset_id} não pertence ao split/fold {split!r}; "
            f"IDs permitidos: {sorted(expected_ids, key=int)}."
        )
    return dataset_id


def _resolve_frame_limit(
    *,
    stage: str,
    configured_max_frames: int | None,
    sampling: dict[str, Any],
) -> tuple[int | None, str]:
    """Resolve the total decode limit and record why it was selected.

    ``sampling.scored_frames`` describes frames *after* a stateful detector's
    warmup.  It is therefore converted to a total cap only during exploratory
    stages.  Validation and later stages remain full-video unless the caller
    deliberately supplied ``run.max_frames``/``--max-frames``.
    """
    if configured_max_frames not in (None, ""):
        limit = int(configured_max_frames)
        if limit <= 0:
            raise ValueError("run.max_frames/--max-frames deve ser positivo.")
        return limit, "explicit"

    normalized_stage = str(stage).strip().lower().replace("-", "_")
    scored_raw = sampling.get("scored_frames")
    if normalized_stage not in _SAMPLED_STAGES or scored_raw in (None, ""):
        return None, "full_video"

    warmup = int(sampling.get("warmup_frames", 0))
    scored = int(scored_raw)
    if warmup < 0:
        raise ValueError("sampling.warmup_frames deve ser não negativo.")
    if scored <= 0:
        raise ValueError("sampling.scored_frames deve ser positivo.")
    return warmup + scored, "sampling_warmup_plus_scored"


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except (ConfigError, ProtocolViolation) as exc:
        raise SystemExit(str(exc)) from exc

    method = config.get("method")
    video = config.get("input", {}).get("video")
    if not method:
        raise SystemExit("Informe --method ou defina 'method' no YAML.")
    if method not in DETECTORS:
        raise SystemExit(f"Método desconhecido: {method}. Opções: {', '.join(DETECTORS)}")
    if not video:
        raise SystemExit("Informe --video ou defina 'input.video' no YAML.")

    video_path = Path(video)
    run_cfg = config["run"]
    eval_cfg = config["evaluation"]
    sampling_cfg = config.get("sampling") or {}
    if not isinstance(sampling_cfg, dict):
        raise SystemExit("A seção YAML 'sampling' deve ser um mapping.")
    seed = int(run_cfg.get("seed", 42))
    stage = str(run_cfg.get("stage", "development"))
    frozen = bool(run_cfg.get("frozen", False))
    try:
        max_frames, frame_limit_source = _resolve_frame_limit(
            stage=stage,
            configured_max_frames=run_cfg.get("max_frames"),
            sampling=sampling_cfg,
        )
    except (TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    # The effective cap belongs in the resolved config/hash, rather than being
    # an implicit runner decision that cannot be reproduced from the manifest.
    run_cfg["max_frames"] = max_frames
    run_cfg["frame_limit_source"] = frame_limit_source
    try:
        assert_protocol_access(
            stage=stage,
            split=str(run_cfg.get("split", "unspecified")),
            frozen=frozen,
        )
        if frozen:
            frozen_source = assert_frozen_config_source(args.config)
            _assert_frozen_cli_is_operational(args)
            config["provenance"] = {
                **config["provenance"],
                "frozen_config_source": str(frozen_source),
                "frozen_config_sha256": sha256_file(frozen_source),
            }
        dataset_id = _validate_video_against_split(
            video_path=video_path,
            split=str(run_cfg.get("split", "unspecified")),
            splits_config=config["protocol"].get(
                "splits_config", "configs/protocol/splits.yaml"
            ),
            videos_csv=config["input"].get("videos_csv"),
        )
    except (ProtocolViolation, ConfigError) as exc:
        raise SystemExit(str(exc)) from exc
    _set_seed(seed, include_torch=method == "yolo")

    algorithm = scientific_algorithm_id(
        str(method), params=config.get("params"), variant=config.get("variant")
    )
    create_kwargs: dict[str, Any] = {
        "module": "detection",
        "method": method,
        "algorithm": algorithm,
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    out_csv = context.path / "detections.csv"
    out_frames_csv = context.path / "frame_metrics.csv"
    out_video = context.path / "annotated.mp4" if bool(run_cfg.get("save_video", True)) else None
    try:
        detector = build_detector(method, params=config.get("params", {}))
        summary = run_on_video(
            detector,
            video_path=video_path,
            out_csv=out_csv,
            out_frames_csv=out_frames_csv,
            out_video=out_video,
            gt_dir=config["input"].get("gt_dir"),
            max_frames=max_frames,
            draw_mode=str(run_cfg.get("draw_mode", "both")),
            center_gate_px=float(eval_cfg.get("center_gate_px", DEFAULT_CENTER_GATE_PX)),
            class_policy=str(eval_cfg.get("class_policy", DEFAULT_CLASS_POLICY)),
            sensitivity_gates_px=tuple(
                float(value) for value in eval_cfg.get(
                    "sensitivity_gates_px", DEFAULT_SENSITIVITY_GATES_PX
                )
            ),
            warmup_frames=int(sampling_cfg.get("warmup_frames", 0)),
        )

        # ``dataset_id`` was resolved and, for fixed splits/folds, checked
        # before detector construction and video decoding.
        clinical = load_clinical_row(dataset_id, fields=CLINICAL_FIELDS) if dataset_id else {}
        summary = {
            "run_id": context.run_id,
            "stage": stage,
            "split": run_cfg.get("split", "unspecified"),
            "seed": seed,
            "frame_limit_source": frame_limit_source,
            "max_frames": max_frames,
            "dataset_id": dataset_id,
            **summary,
            "evaluation_protocol_id": eval_cfg.get("protocol_id"),
            **clinical,
        }

        out_summary = context.path / "summary.csv"
        write_summary_csv(summary, out_summary)
        artifacts = {
            "detections_csv": str(out_csv),
            "frame_metrics_csv": str(out_frames_csv),
            "summary_csv": str(out_summary),
            "annotated_video": str(out_video) if out_video else None,
        }
        _write_json_new(
            context.path / "metadata.json",
            {"summary": summary, "artifacts": artifacts},
        )
        context.complete(summary=summary, artifacts=artifacts)
    except BaseException as exc:
        context.fail(exc)
        raise

    print("Run:", context.run_id)
    print("Resumo:", summary)
    print("Artefatos:", context.path)
    return summary


if __name__ == "__main__":
    main()
