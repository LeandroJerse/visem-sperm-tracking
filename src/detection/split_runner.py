"""Run one frozen/configured detector over complete annotated video splits."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.experiments.dataset import load_split_spec
from src.experiments.protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_overrides,
    assert_protocol_access,
)

from . import pipeline as detection_pipeline


from src.core.paths import VISEM_TRACKING_TRAIN_ROOT

DEFAULT_TRAIN_ROOT = VISEM_TRACKING_TRAIN_ROOT

_RESERVED_SPLIT_OVERRIDE_KEYS = frozenset(
    {
        "input.video",
        "input.gt_dir",
        "run.stage",
        "run.split",
        "run.seed",
        "run.frozen",
    }
)
_FROZEN_SPLIT_OVERRIDE_KEYS = frozenset(
    {"run.save_video", "run.draw_mode", "run.render"}
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa uma configuração de detecção em todos os vídeos de um split."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--split", required=True, help="train, val, test, all ou fold A-E")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--save-video", action="store_true")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    parser.add_argument("--splits-config", default="configs/protocol/splits.yaml")
    parser.add_argument("--train-root", default=str(DEFAULT_TRAIN_ROOT))
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args(argv)


def _default_stage(split: str) -> str:
    normalized = split.lower()
    if normalized == "val":
        return "validation"
    if normalized == "test":
        return "test"
    if normalized in {"a", "b", "c", "d", "e"}:
        return "five_fold"
    return "search"


def _video_paths(train_root: Path, video_id: str) -> tuple[Path, Path]:
    folder = train_root / video_id
    video = folder / f"{video_id}.mp4"
    labels = folder / "labels_ftid"
    if not video.is_file() or not labels.is_dir():
        raise FileNotFoundError(
            f"Dados anotados incompletos para vídeo {video_id}: {video}, {labels}"
        )
    return video, labels


def _override_key(expression: str) -> str:
    if "=" not in expression:
        raise SystemExit(f"Override deve usar chave=valor: {expression!r}")
    return expression.split("=", 1)[0].strip()


def _validate_wrapper_overrides(overrides: list[str], *, frozen: bool) -> None:
    reserved = sorted(
        key for key in map(_override_key, overrides) if key in _RESERVED_SPLIT_OVERRIDE_KEYS
    )
    if reserved:
        raise SystemExit(
            "No executor por split, vídeo/stage/split/seed/frozen devem usar os "
            f"argumentos dedicados; --set não pode alterar {reserved}."
        )
    if frozen:
        try:
            assert_frozen_overrides(
                overrides, allowed_keys=_FROZEN_SPLIT_OVERRIDE_KEYS
            )
        except ProtocolViolation as exc:
            raise SystemExit(str(exc)) from exc


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    args = parse_args(argv)
    _validate_wrapper_overrides(args.overrides, frozen=bool(args.frozen))
    spec = load_split_spec(args.splits_config)
    try:
        selected = list(spec.ids_for(args.split))
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    if args.video_id:
        requested = {str(video_id) for video_id in args.video_id}
        outside = requested - set(selected)
        if outside:
            raise SystemExit(
                f"Vídeos fora do split {args.split}: {sorted(outside)}"
            )
        selected = [video_id for video_id in selected if video_id in requested]
    if not selected:
        raise SystemExit("Nenhum vídeo selecionado.")

    stage = args.stage or _default_stage(args.split)
    try:
        assert_protocol_access(stage=stage, split=args.split, frozen=args.frozen)
        if args.frozen:
            assert_frozen_config_source(args.config)
    except ProtocolViolation as exc:
        raise SystemExit(str(exc)) from exc
    if args.frozen and args.max_frames is not None:
        raise SystemExit(
            "Runs congeladas devem processar o vídeo completo; remova --max-frames."
        )

    summaries: list[dict[str, Any]] = []
    root = Path(args.train_root)
    for video_id in selected:
        video, labels = _video_paths(root, video_id)
        command = [
            "--config", args.config,
            "--video", str(video),
            "--gt-dir", str(labels),
            "--stage", stage,
            "--split", args.split,
            "--seed", str(args.seed),
            "--splits-config", args.splits_config,
            "--set", f"run.frozen={str(args.frozen).lower()}",
        ]
        if not args.save_video:
            command.append("--no-video")
        else:
            command.extend(["--set", "run.save_video=true"])
        if args.max_frames is not None:
            command.extend(["--max-frames", str(args.max_frames)])
        if args.out_dir is not None:
            command.extend(["--out-dir", args.out_dir])
        for override in args.overrides:
            command.extend(["--set", override])
        print(f"\n=== vídeo {video_id} ({stage}/{args.split}) ===")
        summaries.append(detection_pipeline.main(command))
    return summaries


if __name__ == "__main__":
    main()
