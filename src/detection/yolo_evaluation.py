"""Secondary IoU/mAP evaluation for a trained Ultralytics YOLO detector.

The official detector-promotion metric remains center-distance F1 in
``src.evaluation.detection``.  This entry point deliberately keeps YOLO's
native IoU metrics separate and calls :meth:`ultralytics.YOLO.val` only when
executed, so importing the classical pipeline does not require neural extras.
"""
from __future__ import annotations

import argparse
import math
import random
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.core.artifacts import (
    sha256_file as _sha256,
    write_csv_exclusive as _write_csv_new,
    write_json_exclusive as _write_json_new,
)
from src.core.paths import YOLO_DATASET_ROOT
from src.experiments.config import ConfigError, load_config
from src.experiments.protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_release,
    assert_protocol_access,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Avaliação secundária YOLO via Ultralytics val (mAP por IoU)."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="YAML promovido; obrigatório para qualquer execução congelada.",
    )
    parser.add_argument("--weights", default=None, help="Checkpoint best.pt (somente runs não congeladas).")
    parser.add_argument("--data", default=None, help="Dataset YAML (somente runs não congeladas).")
    parser.add_argument("--stage", default=None, help="Etapa experimental.")
    parser.add_argument(
        "--split", default=None, choices=["train", "val", "test"],
        help="Seção do YAML avaliada pelo Ultralytics.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--frozen", action="store_true",
        help="Confirma que pesos/hiperparâmetros foram congelados antes de test/final.",
    )
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--iou", type=float, default=None, help="IoU usado pelo NMS.")
    parser.add_argument("--out-dir", default=None, help="Raiz opcional; default por etapa em data/tests ou data/results.")
    return parser.parse_args(argv)


def _resolve_cli(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve evaluation values while retaining which layer supplied them."""

    raw: dict[str, Any] = {}
    if args.config is not None:
        raw = load_config(args.config)
    input_cfg = raw.get("input") or {}
    params_cfg = raw.get("params") or {}
    evaluation_cfg = raw.get("evaluation") or {}
    run_cfg = raw.get("run") or {}
    for name, value in (
        ("input", input_cfg),
        ("params", params_cfg),
        ("evaluation", evaluation_cfg),
        ("run", run_cfg),
    ):
        if not isinstance(value, dict):
            raise ConfigError(f"A seção YAML {name!r} deve ser um mapping.")

    frozen = bool(args.frozen or run_cfg.get("frozen", False))
    assert_frozen_release(
        args.config, stage=args.stage or run_cfg.get("stage") or "validation",
        split=args.split or run_cfg.get("split") or "val", frozen=frozen,
        splits_config=(raw.get("protocol") or {}).get("splits_config"),
    )
    if frozen:
        source = assert_frozen_config_source(args.config)
        if str(raw.get("method", "")).strip().lower() not in {"yolo", "yolo_val"}:
            raise ProtocolViolation(
                "O YAML congelado da avaliação YOLO deve declarar method: yolo."
            )
        scientific_flags = [
            flag
            for flag, value in (
                ("--weights", args.weights),
                ("--data", args.data),
                ("--imgsz", args.imgsz),
                ("--batch", args.batch),
                ("--device", args.device),
                ("--conf", args.conf),
                ("--iou", args.iou),
            )
            if value is not None
        ]
        if scientific_flags:
            raise ProtocolViolation(
                "Avaliação YOLO congelada não permite parâmetros científicos via CLI: "
                f"{scientific_flags}. Registre-os no YAML promovido."
            )
    else:
        source = None

    return {
        "weights": args.weights or input_cfg.get("weights") or params_cfg.get("weights"),
        "data": args.data or input_cfg.get("data") or str(YOLO_DATASET_ROOT / "visem.yaml"),
        "stage": args.stage or run_cfg.get("stage") or "validation",
        "split": args.split or run_cfg.get("split") or "val",
        "seed": int(args.seed if args.seed is not None else run_cfg.get("seed", 42)),
        "frozen": frozen,
        "imgsz": int(
            args.imgsz
            if args.imgsz is not None
            else evaluation_cfg.get("imgsz", params_cfg.get("imgsz", 640))
        ),
        "batch": int(
            args.batch
            if args.batch is not None
            else evaluation_cfg.get("batch", 16)
        ),
        "device": args.device if args.device is not None else evaluation_cfg.get("device"),
        "conf": args.conf if args.conf is not None else evaluation_cfg.get(
            "conf", params_cfg.get("conf")
        ),
        "iou": float(
            args.iou
            if args.iou is not None
            else evaluation_cfg.get("nms_iou", params_cfg.get("nms_iou", 0.7))
        ),
        "config_source": source,
    }


def _scalar(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _result_value(results: Any, attribute: str, *keys: str) -> float | None:
    box = getattr(results, "box", None)
    value = _scalar(getattr(box, attribute, None)) if box is not None else None
    if value is not None:
        return value
    result_dict = getattr(results, "results_dict", {}) or {}
    for key in keys:
        value = _scalar(result_dict.get(key))
        if value is not None:
            return value
    return None


def _array(value: Any) -> np.ndarray:
    if value is None:
        return np.asarray([], dtype=float)
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return np.asarray([], dtype=float)
    return result


def _class_names(results: Any, model: Any) -> dict[int, str]:
    raw = getattr(results, "names", None) or getattr(model, "names", None) or {}
    if isinstance(raw, dict):
        return {int(key): str(value) for key, value in raw.items()}
    if isinstance(raw, (list, tuple)):
        return {index: str(value) for index, value in enumerate(raw)}
    return {}


def extract_metrics(results: Any, model: Any) -> tuple[dict[str, float | None], list[dict[str, Any]]]:
    """Extract stable global/per-class fields across Ultralytics releases."""
    global_metrics: dict[str, float | None] = {
        "precision": _result_value(results, "mp", "metrics/precision(B)"),
        "recall": _result_value(results, "mr", "metrics/recall(B)"),
        "map50": _result_value(results, "map50", "metrics/mAP50(B)"),
        "map50_95": _result_value(results, "map", "metrics/mAP50-95(B)"),
        "fitness": _scalar(getattr(results, "fitness", None)),
    }
    if global_metrics["fitness"] is None:
        global_metrics["fitness"] = _scalar(
            (getattr(results, "results_dict", {}) or {}).get("fitness")
        )

    box = getattr(results, "box", None)
    if box is None:
        return global_metrics, []
    class_ids_raw = _array(getattr(box, "ap_class_index", None)).reshape(-1)
    p = _array(getattr(box, "p", None)).reshape(-1)
    r = _array(getattr(box, "r", None)).reshape(-1)
    ap50 = _array(getattr(box, "ap50", None)).reshape(-1)
    ap = _array(getattr(box, "ap", None))
    maps = _array(getattr(box, "maps", None)).reshape(-1)
    available = max(len(p), len(r), len(ap50), ap.shape[0] if ap.ndim else 0)
    if class_ids_raw.size:
        class_ids = [int(value) for value in class_ids_raw]
    else:
        class_ids = list(range(available or len(maps)))
    names = _class_names(results, model)

    rows: list[dict[str, Any]] = []
    for position, class_id in enumerate(class_ids):
        class_map = None
        if ap.ndim == 2 and position < ap.shape[0]:
            finite_ap = ap[position][np.isfinite(ap[position])]
            class_map = float(np.mean(finite_ap)) if finite_ap.size else None
        elif ap.ndim == 1 and position < len(ap):
            class_map = _scalar(ap[position])
        elif class_id < len(maps):
            class_map = _scalar(maps[class_id])
        elif position < len(maps):
            class_map = _scalar(maps[position])
        rows.append(
            {
                "class_id": class_id,
                "class_name": names.get(class_id, str(class_id)),
                "precision": _scalar(p[position]) if position < len(p) else None,
                "recall": _scalar(r[position]) if position < len(r) else None,
                "map50": _scalar(ap50[position]) if position < len(ap50) else None,
                "map50_95": class_map,
            }
        )
    return global_metrics, rows


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    try:
        resolved = _resolve_cli(args)
        assert_protocol_access(
            stage=resolved["stage"],
            split=resolved["split"],
            frozen=bool(resolved["frozen"]),
        )
    except (ConfigError, ProtocolViolation, TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if not resolved["weights"]:
        raise SystemExit("Informe --weights ou registre input.weights/params.weights no YAML.")
    weights = Path(resolved["weights"])
    data = Path(resolved["data"])
    if not weights.is_file():
        raise SystemExit(f"Pesos YOLO não encontrados: {weights}")
    if not data.is_file():
        raise SystemExit(f"Dataset YAML não encontrado: {data}")
    if resolved["imgsz"] <= 0 or resolved["batch"] == 0:
        raise SystemExit("imgsz deve ser positivo e batch não pode ser zero.")
    if not 0.0 < resolved["iou"] <= 1.0:
        raise SystemExit("iou deve estar no intervalo (0, 1].")
    if resolved["conf"] is not None and not 0.0 <= float(resolved["conf"]) <= 1.0:
        raise SystemExit("conf deve estar no intervalo [0, 1].")

    random.seed(resolved["seed"])
    np.random.seed(resolved["seed"])
    config: dict[str, Any] = {
        "method": "yolo_val",
        "input": {
            "weights": str(weights.resolve()),
            "weights_sha256": _sha256(weights),
            "data": str(data.resolve()),
            "data_sha256": _sha256(data),
            "frozen_config_source": (
                str(resolved["config_source"])
                if resolved["config_source"] is not None
                else None
            ),
            "frozen_config_sha256": (
                _sha256(resolved["config_source"])
                if resolved["config_source"] is not None
                else None
            ),
        },
        "evaluation": {
            "kind": "secondary_iou_map_ultralytics",
            "split": resolved["split"],
            "imgsz": resolved["imgsz"],
            "batch": resolved["batch"],
            "device": resolved["device"],
            "conf": resolved["conf"],
            "nms_iou": resolved["iou"],
        },
        "run": {
            "stage": resolved["stage"],
            "split": resolved["split"],
            "seed": resolved["seed"],
            "frozen": bool(resolved["frozen"]),
        },
    }
    create_kwargs: dict[str, Any] = {
        "module": "detection",
        "method": "yolo_val",
        "algorithm": "yolo",
        "stage": resolved["stage"],
        "seed": resolved["seed"],
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Avaliação YOLO requer 'ultralytics' e seu PyTorch compatível."
            ) from exc

        resources = ResourceMonitor()
        model = YOLO(str(weights.resolve()))
        val_kwargs: dict[str, Any] = {
            "data": str(data.resolve()),
            "split": resolved["split"],
            "seed": resolved["seed"],
            "imgsz": resolved["imgsz"],
            "batch": resolved["batch"],
            "iou": resolved["iou"],
            "project": str(context.path.resolve()),
            "name": "ultralytics",
            "exist_ok": False,
            "verbose": False,
        }
        if resolved["device"] is not None:
            val_kwargs["device"] = resolved["device"]
        if resolved["conf"] is not None:
            val_kwargs["conf"] = resolved["conf"]
        started = time.perf_counter()
        results = model.val(**val_kwargs)
        validation_seconds = time.perf_counter() - started
        resources.sample()

        global_metrics, class_rows = extract_metrics(results, model)
        if global_metrics["map50"] is None or global_metrics["map50_95"] is None:
            raise RuntimeError("Ultralytics não retornou mAP50/mAP50-95 reconhecíveis.")
        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": resolved["stage"],
            "split": resolved["split"],
            "seed": resolved["seed"],
            "frozen": bool(resolved["frozen"]),
            "metric_scope": "secondary_iou_map_not_primary_center_f1",
            **global_metrics,
            "classes_reported": len(class_rows),
            "validation_seconds": validation_seconds,
        }
        summary.update(resources.summary())
        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_csv_new(
            context.path / "summary.csv", [summary], list(summary)
        )
        class_csv = _write_csv_new(
            context.path / "metrics_per_class.csv",
            class_rows,
            ["class_id", "class_name", "precision", "recall", "map50", "map50_95"],
        )
        artifacts = {
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
            "metrics_per_class_csv": str(class_csv),
            "ultralytics_dir": str((context.path / "ultralytics").resolve()),
        }
        metadata = {
            "summary": summary,
            "input": config["input"],
            "evaluation": config["evaluation"],
            "per_class": class_rows,
            "artifacts": artifacts,
        }
        metadata_json = _write_json_new(context.path / "metadata.json", metadata)
        artifacts["metadata_json"] = str(metadata_json)
        context.complete(
            summary=summary,
            input=config["input"],
            artifacts=artifacts,
        )
    except BaseException as exc:
        context.fail(exc)
        raise

    print("Run:", context.run_id)
    print("mAP50:", summary["map50"], "| mAP50-95:", summary["map50_95"])
    print("Artefatos:", context.path)
    return summary


if __name__ == "__main__":
    main()
