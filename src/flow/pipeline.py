"""Reproducible pairwise optical-flow CLI for real videos.

The CLI intentionally does not compute EPE for a real video because VISEM has
no physical flow ground truth.  Every invocation creates a new immutable run
with pair metrics, summary, input fingerprint, resources, and optional cached
fields.

Example
-------
python -m script.flow.application.run_flow --config configs/flow/farneback/search.yaml \
    --input-video data/sources/visem_tracking/dataset/Train/11/11.mp4 --max-pairs 300 \
    --stage validation --split val
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from src.core.artifacts import (
    sha256_file as _sha256,
    write_csv_exclusive as _write_csv_new,
    write_json_exclusive as _write_json_new,
)
from src.core.paths import DERIVED_FLOW_CACHE

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

from .base import FlowEstimator, FlowResult
from .cache import FlowCache, make_cache_key
from .metrics import (
    forward_backward_consistency,
    photometric_warp_error,
    temporal_flow_change,
)
from .registry import FLOW_ESTIMATORS, create_flow_estimator


DEFAULT_CONFIG: dict[str, Any] = {
    "method": None,
    "params": {},
    "evaluation": {
        "compute_backward": True,
        "consistency_threshold": 1.5,
    },
    "input": {"video": None, "video_id": None, "max_pairs": None},
    "mask": {
        "csv": None,
        "source": "detection",
        "margin_px": 3.0,
        "video_id": None,
    },
    "run": {
        "stage": "development",
        "split": "unspecified",
        "seed": 42,
        "frozen": False,
        "cache": False,
        "cache_dir": str(DERIVED_FLOW_CACHE),
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fluxo óptico em pares consecutivos com run imutável."
    )
    parser.add_argument("--config", default=None, help="YAML do método de fluxo.")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="key=value",
        help="Override repetível; chave simples entra em params.",
    )
    parser.add_argument("--method", choices=sorted(FLOW_ESTIMATORS), default=None)
    parser.add_argument("--input-video", default=None, help="Vídeo de entrada.")
    parser.add_argument("--video-id", default=None, help="ID usado no CSV de máscara/cache.")
    parser.add_argument(
        "--max-pairs", type=int, default=None, help="Limite de pares consecutivos."
    )
    parser.add_argument(
        "--mask-csv",
        default=None,
        help="CSV opcional de detecções/GT cujas caixas serão excluídas.",
    )
    parser.add_argument(
        "--mask-source",
        choices=("detection", "manual", "ground_truth", "gt", "all"),
        default=None,
        help="Fonte das caixas; CSV sem coluna source é tratado como fonte única.",
    )
    parser.add_argument(
        "--mask-margin", type=float, default=None, help="Margem em pixels ao redor das caixas."
    )
    parser.add_argument("--mask-video-id", default=None)
    parser.add_argument("--stage", default=None, help="Etapa experimental.")
    parser.add_argument("--split", default=None, help="Split/fold da run.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Ativa/desativa cache de campos forward.",
    )
    parser.add_argument("--cache-dir", default=None, help="Raiz do cache opcional.")
    parser.add_argument(
        "--out-dir", default=None, help="Raiz opcional; default por etapa em data/tests ou data/results."
    )
    return parser.parse_args(argv)


def _normalise_overrides(overrides: list[str] | None) -> list[str]:
    top_level = {"method", "base_method", "optional_refiner", "refiner_method"}
    normalised: list[str] = []
    for expression in overrides or []:
        key, separator, raw_value = expression.partition("=")
        key = key.strip()
        if "." in key or key in top_level:
            normalised.append(expression)
        else:
            normalised.append(f"params.{key}{separator}{raw_value}")
    return normalised


_FROZEN_FLOW_OVERRIDE_KEYS = frozenset(
    {
        "input.video",
        "input.video_id",
        "mask.csv",
        "mask.video_id",
        "run.stage",
        "run.split",
        "run.seed",
        "run.frozen",
        "run.cache",
        "run.cache_dir",
    }
)


def _assert_frozen_cli_is_operational(args: argparse.Namespace) -> None:
    """Keep estimator, evaluation, masking policy and sample size frozen."""

    forbidden = [
        flag
        for flag, value in (
            ("--method", args.method),
            ("--max-pairs", args.max_pairs),
            ("--mask-source", args.mask_source),
            ("--mask-margin", args.mask_margin),
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
        allowed_keys=_FROZEN_FLOW_OVERRIDE_KEYS,
    )


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in ("params", "evaluation", "input", "mask", "run"):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config[section], dict):
            raise ConfigError(f"A seção {section!r} deve ser um mapping.")
    if args.method is not None:
        config["method"] = args.method
    if args.input_video is not None:
        config["input"]["video"] = args.input_video
    if args.video_id is not None:
        config["input"]["video_id"] = str(args.video_id)
    if args.max_pairs is not None:
        config["input"]["max_pairs"] = args.max_pairs
    if args.mask_csv is not None:
        config["mask"]["csv"] = args.mask_csv
    if args.mask_source is not None:
        config["mask"]["source"] = args.mask_source
    if args.mask_margin is not None:
        config["mask"]["margin_px"] = args.mask_margin
    if args.mask_video_id is not None:
        config["mask"]["video_id"] = str(args.mask_video_id)
    if args.stage is not None:
        config["run"]["stage"] = args.stage
    if args.split is not None:
        config["run"]["split"] = args.split
    if args.seed is not None:
        config["run"]["seed"] = args.seed
    if args.cache is not None:
        config["run"]["cache"] = args.cache
    if args.cache_dir is not None:
        config["run"]["cache"] = True
        config["run"]["cache_dir"] = args.cache_dir
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


def iter_video_pairs(
    path: str | Path, *, max_pairs: int | None = None
) -> Iterator[tuple[int, int, np.ndarray, np.ndarray]]:
    """Yield consecutive decoded frames without loading the video into RAM."""

    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError("A CLI de fluxo requer opencv-python para ler vídeos.") from exc
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Não foi possível abrir o vídeo: {path}")
    try:
        ok, previous = capture.read()
        if not ok or previous is None:
            raise ValueError(f"Vídeo sem frame decodificável: {path}")
        previous_index = 0
        emitted = 0
        while max_pairs is None or emitted < max_pairs:
            ok, following = capture.read()
            if not ok or following is None:
                break
            following_index = previous_index + 1
            yield previous_index, following_index, previous, following
            emitted += 1
            previous = following
            previous_index = following_index
    finally:
        capture.release()


@dataclass(frozen=True)
class ExclusionBoxes:
    """Pixel-space boxes grouped by zero-based video frame."""

    by_frame: dict[int, tuple[tuple[float, float, float, float], ...]]
    selected_video_id: str | None
    requested_source: str
    source_filter_applied: bool
    rows_read: int
    boxes_used: int


def _canonical_mask_source(source: object) -> str:
    normalized = str(source or "detection").strip().lower()
    aliases = {"ground_truth": "manual", "gt": "manual"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"detection", "manual", "all"}:
        raise ValueError("mask.source deve ser detection, manual/ground_truth ou all.")
    return normalized


def load_exclusion_boxes(
    path: str | Path,
    *,
    source: str = "detection",
    video_id: str | None = None,
) -> ExclusionBoxes:
    """Load boxes from unified detection/GT CSV or a single-source box CSV.

    Supported coordinates are ``x,y,w,h`` or ``cx,cy,w,h``.  The frame column
    can be ``frame`` (detection CSV) or ``frame_index`` (tracking-style CSV).
    """

    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV de máscara não encontrado: {csv_path}")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        rows = list(reader)
    if not rows:
        raise ValueError("CSV de máscara está vazio.")
    frame_field = (
        "frame"
        if "frame" in fields
        else "frame_index"
        if "frame_index" in fields
        else None
    )
    if frame_field is None:
        raise ValueError("CSV de máscara requer coluna frame ou frame_index.")
    if not {"w", "h"} <= fields:
        raise ValueError("CSV de máscara requer w e h.")
    has_xy = {"x", "y"} <= fields
    has_center = {"cx", "cy"} <= fields
    if not has_xy and not has_center:
        raise ValueError("CSV de máscara requer x/y ou cx/cy.")

    canonical_source = _canonical_mask_source(source)
    source_filter_applied = "source" in fields
    source_filtered: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, start=2):
        if source_filter_applied:
            raw_source = (row.get("source") or "").strip()
            if not raw_source:
                raise ValueError(f"source vazio na linha {row_number} do CSV de máscara.")
            row_source = _canonical_mask_source(raw_source)
            if canonical_source != "all" and row_source != canonical_source:
                continue
        source_filtered.append(row)
    if source_filter_applied and not source_filtered:
        raise ValueError(
            f"Nenhuma caixa com source={canonical_source!r} no CSV de máscara."
        )
    if "video_id" in fields:
        blank_video_rows = [
            row_number
            for row_number, row in enumerate(source_filtered, start=2)
            if not (row.get("video_id") or "").strip()
        ]
        if blank_video_rows:
            raise ValueError(
                "video_id vazio no CSV de máscara; primeira linha inválida: "
                f"{blank_video_rows[0]}."
            )
    available_videos = sorted(
        {
            (row.get("video_id") or "").strip()
            for row in source_filtered
            if (row.get("video_id") or "").strip()
        }
    )
    selected_video = str(video_id).strip() if video_id is not None else None
    if selected_video == "":
        selected_video = None
    if selected_video is not None and available_videos and selected_video not in available_videos:
        raise ValueError(
            f"Vídeo {selected_video!r} ausente no CSV de máscara; disponíveis: {available_videos}"
        )
    if selected_video is None:
        if len(available_videos) == 1:
            selected_video = available_videos[0]
        elif len(available_videos) > 1:
            raise ValueError(
                "CSV de máscara contém múltiplos vídeos; informe --mask-video-id/--video-id."
            )

    grouped: dict[int, list[tuple[float, float, float, float]]] = {}
    for row_number, row in enumerate(source_filtered, start=2):
        row_video = (row.get("video_id") or "").strip()
        if selected_video is not None and row_video and row_video != selected_video:
            continue
        try:
            frame = int(row[frame_field])
            width = float(row["w"])
            height = float(row["h"])
            if has_xy:
                x, y = float(row["x"]), float(row["y"])
            else:
                cx, cy = float(row["cx"]), float(row["cy"])
                x, y = cx - width / 2.0, cy - height / 2.0
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Caixa inválida na linha {row_number}: {exc}") from exc
        if (
            frame < 0
            or width <= 0
            or height <= 0
            or not np.isfinite([x, y, width, height]).all()
        ):
            raise ValueError(f"Caixa inválida na linha {row_number}.")
        grouped.setdefault(frame, []).append((x, y, width, height))
    if not grouped:
        requested = selected_video if selected_video is not None else "fonte selecionada"
        raise ValueError(f"Nenhuma caixa encontrada para {requested!r} no CSV de máscara.")
    return ExclusionBoxes(
        by_frame={frame: tuple(boxes) for frame, boxes in grouped.items()},
        selected_video_id=selected_video,
        requested_source=canonical_source,
        source_filter_applied=source_filter_applied,
        rows_read=len(rows),
        boxes_used=sum(len(boxes) for boxes in grouped.values()),
    )


def build_pair_include_mask(
    shape: tuple[int, int],
    boxes: ExclusionBoxes | None,
    previous_frame: int,
    next_frame: int,
    *,
    margin_px: float = 0.0,
) -> tuple[np.ndarray, int]:
    """Exclude the union of expanded boxes from both frames of a pair."""

    if margin_px < 0:
        raise ValueError("mask.margin_px deve ser não negativo.")
    height, width = int(shape[0]), int(shape[1])
    include = np.ones((height, width), dtype=bool)
    selected = () if boxes is None else (
        boxes.by_frame.get(int(previous_frame), ())
        + boxes.by_frame.get(int(next_frame), ())
    )
    for x, y, box_width, box_height in selected:
        x0 = max(0, int(np.floor(x - margin_px)))
        y0 = max(0, int(np.floor(y - margin_px)))
        x1 = min(width, int(np.ceil(x + box_width + margin_px)))
        y1 = min(height, int(np.ceil(y + box_height + margin_px)))
        if x0 < x1 and y0 < y1:
            include[y0:y1, x0:x1] = False
    return include, len(selected)


def _create_estimator(config: dict[str, Any]) -> FlowEstimator:
    method = str(config["method"])
    params = dict(config.get("params", {}))
    if method != "robust_hybrid":
        return create_flow_estimator(method, **params)
    base_method = str(config.get("base_method") or "farneback")
    if base_method == "robust_hybrid":
        raise ConfigError("robust_hybrid não pode usar a si próprio como base.")
    base_params = config.get("base_params", {}) or {}
    if not isinstance(base_params, dict):
        raise ConfigError("base_params deve ser um mapping.")
    base = create_flow_estimator(base_method, **base_params)
    refiner_name = config.get("refiner_method", config.get("optional_refiner"))
    refiner_params = config.get("refiner_params", {}) or {}
    if not isinstance(refiner_params, dict):
        raise ConfigError("refiner_params deve ser um mapping.")
    normalized_refiner = (
        str(refiner_name).strip().lower() if refiner_name is not None else ""
    )
    refiner = (
        None
        if refiner_name is False or normalized_refiner in {"", "none", "null"}
        else create_flow_estimator(str(refiner_name), **refiner_params)
    )
    return create_flow_estimator(method, base=base, refiner=refiner, **params)


def _implementation_hash() -> str:
    digest = hashlib.sha256()
    package_root = Path(__file__).parent
    for source in sorted(package_root.rglob("*.py")):
        digest.update(source.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = np.asarray([row.get(key, np.nan) for row in rows], dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.mean()) if len(finite) else None


def _pair_metrics(
    result: FlowResult,
    previous: np.ndarray,
    following: np.ndarray,
) -> dict[str, Any]:
    valid_magnitude = result.magnitude[result.valid]
    return {
        "photometric_mae": photometric_warp_error(previous, following, result),
        "valid_fraction": float(result.valid.mean()),
        "mean_magnitude": (
            float(valid_magnitude.mean()) if len(valid_magnitude) else None
        ),
        "median_magnitude": (
            float(np.median(valid_magnitude)) if len(valid_magnitude) else None
        ),
        "p95_magnitude": (
            float(np.percentile(valid_magnitude, 95)) if len(valid_magnitude) else None
        ),
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except (ConfigError, ProtocolViolation) as exc:
        raise SystemExit(str(exc)) from exc
    method = str(config.get("method") or "")
    if method not in FLOW_ESTIMATORS:
        raise SystemExit(
            f"Método desconhecido: {method!r}. Opções: {', '.join(sorted(FLOW_ESTIMATORS))}"
        )
    video_value = config["input"].get("video")
    if not video_value:
        raise SystemExit("Informe --input-video ou input.video no YAML.")
    video_path = Path(video_value)
    if not video_path.is_file():
        raise SystemExit(f"Vídeo não encontrado: {video_path}")
    max_pairs_raw = config["input"].get("max_pairs")
    max_pairs = None if max_pairs_raw in (None, "") else int(max_pairs_raw)
    if max_pairs is not None and max_pairs <= 0:
        raise SystemExit("max_pairs deve ser positivo ou null.")

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
            if max_pairs is not None:
                raise ProtocolViolation(
                    "Fluxo congelado deve processar o vídeo completo; max_pairs é proibido."
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

    flow_video_id = str(config["input"].get("video_id") or video_path.stem)
    try:
        assert_video_ids_in_split([flow_video_id], split=split)
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc
    input_sha = _sha256(video_path)
    mask_config = config["mask"]
    mask_margin = float(mask_config.get("margin_px", 3.0))
    if mask_margin < 0:
        raise SystemExit("mask.margin_px deve ser não negativo.")
    exclusion_boxes: ExclusionBoxes | None = None
    mask_metadata: dict[str, Any] = {"enabled": False}
    mask_value = mask_config.get("csv")
    if mask_value:
        mask_path = Path(mask_value)
        requested_mask_video = str(
            mask_config.get("video_id") or flow_video_id
        )
        try:
            exclusion_boxes = load_exclusion_boxes(
                mask_path,
                source=str(mask_config.get("source", "detection")),
                video_id=requested_mask_video,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        mask_sha = _sha256(mask_path)
        mask_metadata = {
            "enabled": True,
            "path": str(mask_path.resolve()),
            "sha256": mask_sha,
            "bytes": mask_path.stat().st_size,
            "source": exclusion_boxes.requested_source,
            "source_filter_applied": exclusion_boxes.source_filter_applied,
            "video_id": exclusion_boxes.selected_video_id,
            "margin_px": mask_margin,
            "rows_read": exclusion_boxes.rows_read,
            "boxes_used": exclusion_boxes.boxes_used,
            "pair_policy": "union_previous_and_next_frame_boxes",
        }
        config["mask"].update(mask_metadata)
    else:
        mask_metadata = {
            "enabled": False,
            "source": _canonical_mask_source(mask_config.get("source")),
            "video_id": flow_video_id,
            "margin_px": mask_margin,
            "pair_policy": "disabled_no_csv",
        }
        config["mask"].update(mask_metadata)
    config["input"]["video"] = str(video_path.resolve())
    config["input"]["video_id"] = flow_video_id
    config["input"]["sha256"] = input_sha
    config["input"]["bytes"] = video_path.stat().st_size
    config["input"]["max_pairs"] = max_pairs
    config["implementation_hash"] = _implementation_hash()
    create_kwargs: dict[str, Any] = {
        "module": "flow",
        "method": method,
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        estimator = _create_estimator(config)
        evaluation = config["evaluation"]
        compute_backward = bool(evaluation.get("compute_backward", True))
        consistency_threshold = float(evaluation.get("consistency_threshold", 1.5))
        cache_enabled = bool(run_config.get("cache", False))
        cache = None
        if cache_enabled:
            cache_dir = Path(run_config.get("cache_dir") or DERIVED_FLOW_CACHE)
            cache = FlowCache(cache_dir)
        resources = ResourceMonitor()
        pair_rows: list[dict[str, Any]] = []
        cache_rows: list[dict[str, Any]] = []
        previous_result: FlowResult | None = None
        total_started = time.perf_counter()

        for previous_index, next_index, previous, following in iter_video_pairs(
            video_path, max_pairs=max_pairs
        ):
            include_mask, mask_box_count = build_pair_include_mask(
                previous.shape[:2],
                exclusion_boxes,
                previous_index,
                next_index,
                margin_px=mask_margin,
            )
            excluded_fraction = float(1.0 - include_mask.mean())
            key = make_cache_key(
                input_sha,
                previous_index,
                next_index,
                config={
                    "method": method,
                    "params": config.get("params", {}),
                    "base_method": config.get("base_method"),
                    "base_params": config.get("base_params"),
                    "refiner": config.get("refiner_method", config.get("optional_refiner")),
                    "refiner_params": config.get("refiner_params"),
                    "mask": {
                        "sha256": mask_metadata.get("sha256"),
                        "source": mask_metadata.get("source"),
                        "video_id": mask_metadata.get("video_id"),
                        "margin_px": mask_margin,
                        "policy": mask_metadata.get("pair_policy"),
                    },
                    "implementation_hash": config["implementation_hash"],
                },
            )
            result = cache.load(key) if cache is not None else None
            cache_hit = result is not None
            started = time.perf_counter()
            if result is None:
                result = estimator.estimate(previous, following, mask=include_mask)
                result.metadata = {
                    **result.metadata,
                    "cache_provenance": {
                        "key": key,
                        "video_id": flow_video_id,
                        "video_sha256": input_sha,
                        "previous_frame": previous_index,
                        "next_frame": next_index,
                        "method": method,
                        "params": config.get("params", {}),
                        "base_method": config.get("base_method"),
                        "base_params": config.get("base_params"),
                        "refiner_method": config.get(
                            "refiner_method", config.get("optional_refiner")
                        ),
                        "refiner_params": config.get("refiner_params"),
                        "implementation_hash": config["implementation_hash"],
                        "exclusion_mask": {
                            "enabled": bool(mask_metadata["enabled"]),
                            "sha256": mask_metadata.get("sha256"),
                            "source": mask_metadata.get("source"),
                            "video_id": mask_metadata.get("video_id"),
                            "margin_px": mask_margin,
                            "pair_policy": mask_metadata.get("pair_policy"),
                            "boxes_in_pair": mask_box_count,
                            "excluded_fraction": excluded_fraction,
                        },
                    },
                }
            estimate_seconds = time.perf_counter() - started
            if cache is not None and not cache_hit:
                cache.save(key, result)

            row: dict[str, Any] = {
                "previous_frame": previous_index,
                "next_frame": next_index,
                "cache_hit": int(cache_hit),
                "estimate_seconds": estimate_seconds,
                "estimate_ms": estimate_seconds * 1000.0,
                "mask_boxes": mask_box_count,
                "mask_excluded_fraction": excluded_fraction,
                **_pair_metrics(result, previous, following),
            }
            if compute_backward:
                backward = estimator.estimate(following, previous, mask=include_mask)
                consistency = forward_backward_consistency(
                    result, backward, threshold=consistency_threshold
                )
                row.update(
                    {
                        "forward_backward_mae": consistency.mean_error,
                        "consistent_fraction": consistency.fraction_consistent,
                    }
                )
            if previous_result is not None:
                temporal = temporal_flow_change(previous_result, result)
                row.update(
                    {
                        "temporal_mean_change": temporal["mean_change"],
                        "temporal_p95_change": temporal["p95_change"],
                    }
                )
            pair_rows.append(row)
            if cache is not None:
                cache_rows.append(
                    {
                        "previous_frame": previous_index,
                        "next_frame": next_index,
                        "video_id": flow_video_id,
                        "key": key,
                        "path": str(cache.path_for(key).resolve()),
                        "cache_hit": int(cache_hit),
                        "mask_enabled": int(bool(mask_metadata["enabled"])),
                        "mask_sha256": mask_metadata.get("sha256"),
                        "mask_source": mask_metadata.get("source"),
                        "mask_margin_px": mask_margin,
                        "mask_boxes": mask_box_count,
                        "mask_excluded_fraction": excluded_fraction,
                        "implementation_hash": config["implementation_hash"],
                    }
                )
            previous_result = result
            resources.sample()

        elapsed = time.perf_counter() - total_started
        if not pair_rows:
            raise ValueError("O vídeo não produziu nenhum par consecutivo.")
        first_shape = previous.shape[:2]  # assigned by the non-empty loop above
        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": stage,
            "split": split,
            "seed": seed,
            "method": method,
            "video_id": flow_video_id,
            "input_video": str(video_path.resolve()),
            "pairs_processed": len(pair_rows),
            "frame_height": int(first_shape[0]),
            "frame_width": int(first_shape[1]),
            "elapsed_seconds": elapsed,
            "mean_estimate_ms": 1000.0 * (_mean(pair_rows, "estimate_seconds") or 0.0),
            "mean_photometric_mae": _mean(pair_rows, "photometric_mae"),
            "mean_valid_fraction": _mean(pair_rows, "valid_fraction"),
            "mean_forward_backward_mae": _mean(pair_rows, "forward_backward_mae"),
            "mean_consistent_fraction": _mean(pair_rows, "consistent_fraction"),
            "mean_temporal_change": _mean(pair_rows, "temporal_mean_change"),
            "mask_enabled": bool(mask_metadata["enabled"]),
            "mask_source": mask_metadata.get("source"),
            "mask_margin_px": mask_margin,
            "mean_mask_excluded_fraction": _mean(pair_rows, "mask_excluded_fraction"),
            "cache_enabled": cache_enabled,
            "cache_hits": sum(row["cache_hit"] for row in pair_rows),
            "epe_status": "not_computed_real_video_no_ground_truth",
        }
        summary.update(resources.summary())

        pair_path = _write_csv_new(context.path / "pair_metrics.csv", pair_rows)
        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_csv_new(context.path / "summary.csv", [summary])
        artifacts: dict[str, str] = {
            "pair_metrics_csv": str(pair_path),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
        }
        if cache_rows:
            cache_index = _write_csv_new(context.path / "cache_index.csv", cache_rows)
            artifacts["cache_index_csv"] = str(cache_index)
        input_metadata = {
            "path": str(video_path.resolve()),
            "sha256": input_sha,
            "bytes": config["input"]["bytes"],
            "max_pairs": max_pairs,
            "video_id": flow_video_id,
            "exclusion_mask": mask_metadata,
        }
        metadata_path = _write_json_new(
            context.path / "metadata.json",
            {
                "summary": summary,
                "input": input_metadata,
                "artifacts": artifacts,
                "metric_scope": {
                    "epe": "disabled_on_real_video",
                    "photometric": "brightness-constancy diagnostic",
                    "forward_backward": "self-consistency diagnostic",
                },
            },
        )
        artifacts["metadata_json"] = str(metadata_path)
        context.complete(
            summary=summary,
            input=input_metadata,
            exclusion_mask=mask_metadata,
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
