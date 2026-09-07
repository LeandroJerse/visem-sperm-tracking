"""Run ONE detector on ONE frame and save an immutable, identified test run.

This is the preserved threshold frame-screening bench — not pytest. Pick a
video/frame, override threshold parameters, and inspect the exact stages used
by the detector implementation.

Examples
--------
Threshold on the first frame of annotated video 11 (ground truth overlaid)::

    python -m script.detection.test.threshold.single_frame --method threshold --id 11 --frame 0

Threshold on a raw video, without quantitative ground truth::

    python -m script.detection.test.threshold.single_frame --method threshold \
        --video "data/sources/visem/videos/1_09.09.02_SSW.avi" --frame 100 \
        --set min_area=3 --set max_area=150

Output under ``data/tests/detection/<algorithm>/<config>/frame_screening/``:

    00_input.png            the raw frame
    NN_<stage>.png          intermediate stages (gray, mask, morphology, ...)
    detections.png          final boxes (green) + ground truth (red) overlaid
    detections.csv          one row per detection (unified schema)
    summary.json            params, counts, and the detection list
"""
from __future__ import annotations

import argparse
import csv
import inspect
import json
from datetime import datetime
from pathlib import Path

import cv2

from src.detection.io import detection_to_row, write_detections_csv
from src.detection.registry import DETECTORS
from src.detection.visualization import COLORS, draw_detections, draw_legend
from src.evaluation.detection import (
    DEFAULT_CENTER_GATE_PX,
    DEFAULT_CLASS_POLICY,
    DEFAULT_EVALUATION_PROTOCOL_ID,
    DEFAULT_SENSITIVITY_GATES_PX,
    evaluate_frame,
)
from src.core.paths import EXPERIMENT_TESTS_ROOT, REPOSITORY_ROOT, VISEM_TRACKING_TRAIN_ROOT
from src.experiments.config import config_hash
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext

from .frames import load_gt, read_frame, resolve_source


DEFAULT_TEST_ROOT = EXPERIMENT_TESTS_ROOT / "detection"
EVALUATION_PROTOCOL_ID = DEFAULT_EVALUATION_PROTOCOL_ID


def _cast(value: str):
    """Cast a CLI ``key=value`` string to bool / int / float / str."""
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_overrides(pairs: list[str] | None) -> dict:
    """Parse repeated ``--set key=value`` into a kwargs dict for the detector."""
    overrides: dict = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--set espera key=value, recebi: {item!r}")
        key, raw = item.split("=", 1)
        overrides[key.strip()] = _cast(raw.strip())
    return overrides


def build_detector(method: str, overrides: dict, weights: str | None):
    if method not in DETECTORS:
        raise SystemExit(f"Método desconhecido: {method}. Opções: {', '.join(DETECTORS)}")
    cls = DETECTORS[method]
    if method == "yolo":
        return cls(weights=weights, **overrides)
    return cls(**overrides)


def _json_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def _resolved_parameters(method: str, overrides: dict, weights: str | None) -> dict:
    """Resolve constructor defaults so the configuration hash is reproducible."""
    resolved: dict = {}
    detector_class = DETECTORS[method]
    for cls in reversed(detector_class.mro()):
        constructor = cls.__dict__.get("__init__")
        if constructor is None:
            continue
        for name, parameter in inspect.signature(constructor).parameters.items():
            if name == "self" or parameter.default is inspect.Parameter.empty:
                continue
            resolved[name] = _json_value(parameter.default)
    resolved.update({key: _json_value(value) for key, value in overrides.items()})
    if method == "yolo":
        resolved["weights"] = weights
    return resolved


def _configuration_identity(
    method: str, resolved: dict
) -> tuple[str, str]:
    """Return canonical ``(algorithm, human_label__cfgHASH)`` components."""
    algorithm = method
    human = method
    if method == "threshold":
        opening = int(resolved.get("morph_iterations", 1))
        closing = int(resolved.get("close_iterations", 1))
        if bool(resolved.get("adaptive", False)):
            algorithm, human = "adaptive_threshold", f"adaptive_o{opening}_c{closing}"
        elif resolved.get("threshold_value") in (None, ""):
            algorithm, human = "otsu", f"otsu_o{opening}_c{closing}"
        else:
            human = f"t{int(resolved['threshold_value'])}_o{opening}_c{closing}"
    elif method == "bgsub":
        algorithm = str(resolved.get("method", "mog2")).lower()
        human = algorithm
    payload = {"method": method, "params": resolved}
    return algorithm, f"{human}__cfg{config_hash(payload, length=8)}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Triagem histórica: roda threshold em 1 frame e salva as etapas."
    )
    p.add_argument("--method", required=True, choices=["threshold"])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--id", dest="video_id", help="ID do vídeo anotado (VISEM-Tracking).")
    src.add_argument("--video", help="Caminho de um vídeo bruto.")
    p.add_argument("--frame", type=int, default=0, help="Índice do frame (0-based).")
    p.add_argument("--set", dest="overrides", action="append", default=[],
                   metavar="key=value", help="Sobrescreve um parâmetro do detector. Repetível.")
    p.add_argument("--draw-mode", default="both", choices=["box", "centroid", "circle", "both"])
    p.add_argument("--no-stages", action="store_true",
                   help="Não salva imagens de etapas intermediárias (útil em baterias).")
    p.add_argument("--seed", type=int, default=42, help="Semente registrada na run.")
    return p.parse_args(argv)


COMPARISON_FIELDS = [
    "timestamp", "method", "video", "frame", "warmup",
    "evaluation_protocol_id", "metric_primary", "center_gate_px", "sensitivity_gates_px",
    "n_detections", "n_ground_truth", "count_diff", "count_ratio",
    "tp", "fp", "fn", "precision", "recall", "f1",
    "center_error_mean_px",
    "tp_at_15px", "fp_at_15px", "fn_at_15px", "precision_at_15px", "recall_at_15px", "f1_at_15px",
    "tp_at_20px", "fp_at_20px", "fn_at_20px", "precision_at_20px", "recall_at_20px", "f1_at_20px",
    "overrides", "run_dir",
]


def _append_comparison(summary: dict, out_root: Path) -> None:
    """Append one row to the canonical cross-configuration comparison table."""
    csv_path = (
        out_root / "threshold" / "_comparisons" / "frame_screening"
        / EVALUATION_PROTOCOL_ID
        / "by_video" / f"video_{Path(summary['video']).stem}.csv"
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    spatial_fields = [key for key in evaluate_frame([], None) if key not in {"video_id", "frame"}]
    fields = list(dict.fromkeys(COMPARISON_FIELDS + ["count_scope"] + spatial_fields))
    row = {
        **{key: summary.get(key) for key in spatial_fields},
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": summary["method"],
        "video": Path(summary["video"]).stem,
        "frame": summary["frame"],
        "warmup": summary["warmup"],
        "evaluation_protocol_id": summary["evaluation_protocol_id"],
        "metric_primary": summary["metric_primary"],
        "center_gate_px": summary["center_gate_px"],
        "sensitivity_gates_px": json.dumps(summary["sensitivity_gates_px"]),
        "n_detections": summary["n_detections"],
        "n_ground_truth": summary["n_ground_truth"],
        "count_diff": summary["count_diff"],
        "count_scope": summary["count_scope"],
        "count_ratio": summary["count_ratio"] if summary["count_ratio"] is not None else "",
        "tp": summary["tp"],
        "fp": summary["fp"],
        "fn": summary["fn"],
        "precision": summary["precision"],
        "recall": summary["recall"],
        "f1": summary["f1"],
        "center_error_mean_px": (
            summary["center_error_mean_px"]
            if summary["center_error_mean_px"] is not None else ""
        ),
        **{
            key: summary[key]
            for key in COMPARISON_FIELDS
            if "_at_" in key
        },
        "overrides": json.dumps(summary["overrides"], ensure_ascii=False),
        "run_dir": Path(summary["out_dir"]).relative_to(out_root).as_posix(),
    }
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _known_tracking_video_id(video_path: Path) -> str | None:
    """Identify files inside the known VISEM-Tracking acquisition directories."""
    try:
        relative = video_path.resolve().relative_to(VISEM_TRACKING_TRAIN_ROOT.resolve())
    except ValueError:
        return None
    if len(relative.parts) >= 2 and relative.parts[0].isdigit():
        return relative.parts[0]
    return None


def _assert_screening_video_allowed(video_id: str | None, blocked_ids) -> None:
    if video_id in blocked_ids:
        raise ValueError(
            f"O vídeo {video_id} pertence ao teste bloqueado. "
            "A bancada de tuning frame a frame não pode abri-lo."
        )


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    overrides = parse_overrides(args.overrides)

    split_spec = load_split_spec(REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml")
    _assert_screening_video_allowed(args.video_id, split_spec.test)
    video_path, gt_dir, stem = resolve_source(args.video, args.video_id)
    known_id = _known_tracking_video_id(video_path)
    _assert_screening_video_allowed(known_id, split_spec.test)
    source_id = args.video_id or known_id
    if source_id in split_spec.train:
        split_name = "train"
    elif source_id in split_spec.val:
        split_name = "val"
    else:
        split_name = "external_unannotated"

    frame, w, h = read_frame(video_path, args.frame)
    ground_truth = load_gt(gt_dir, args.frame, w, h)
    if ground_truth is not None and not ground_truth.annotated:
        raise ValueError(
            f"Frame {args.frame} do vídeo {stem} não possui label. "
            "Ele é uma lacuna não anotada e foi excluído da triagem."
        )
    gt = list(ground_truth.detections) if ground_truth is not None else []
    metrics_valid = ground_truth is not None and ground_truth.annotated

    resolved_params = _resolved_parameters(args.method, overrides, None)
    algorithm, config_id = _configuration_identity(args.method, resolved_params)
    config = {
        "configuration_id": config_id.split("__cfg", 1)[0],
        "method": args.method,
        "params": resolved_params,
        "evaluation": {
            "protocol_id": EVALUATION_PROTOCOL_ID,
            "center_gate_px": DEFAULT_CENTER_GATE_PX,
            "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
            "class_policy": DEFAULT_CLASS_POLICY,
        },
        "run": {
            "stage": "frame_screening",
            "split": split_name,
            "seed": int(args.seed),
            "frozen": False,
            "save_video": False,
        },
        "input": {
            "video": str(video_path),
            "video_id": stem,
            "frame": int(args.frame),
            "gt_dir": str(gt_dir) if gt_dir is not None else None,
        },
    }
    context = RunContext.create(
        module="detection",
        method=args.method,
        algorithm=algorithm,
        stage="frame_screening",
        seed=int(args.seed),
        config=config,
        repo_root=REPOSITORY_ROOT,
    )
    out_dir = context.path
    monitor = ResourceMonitor()
    try:
        detector = build_detector(args.method, overrides, None)
        dets = detector.detect(frame)
        for i, detection in enumerate(dets):
            if detection.object_id is None or detection.object_id == -1:
                detection.object_id = i

        shared_input = (
            DEFAULT_TEST_ROOT / "_shared_inputs" / f"video_{stem}"
            / f"frame_{args.frame}.png"
        )
        shared_input.parent.mkdir(parents=True, exist_ok=True)
        if not shared_input.exists():
            cv2.imwrite(str(shared_input), frame)

        stages = [] if args.no_stages else detector.diagnostic_stages(frame)
        if stages:
            for idx, (name, image) in enumerate(stages, start=1):
                cv2.imwrite(str(out_dir / f"{idx:02d}_{name}.png"), image)

        annotated = frame.copy()
        draw_detections(annotated, dets, COLORS["detection"], args.draw_mode)
        legend = [(f"detection ({detector.name}): {len(dets)}", COLORS["detection"])]
        if metrics_valid:
            draw_detections(annotated, gt, COLORS["manual"], "box", draw_id=True)
            legend.append((f"manual GT: {len(gt)}", COLORS["manual"]))
        draw_legend(annotated, legend)
        cv2.imwrite(str(out_dir / "detections.png"), annotated)

        rows = [detection_to_row(stem, args.frame, "detection", item) for item in dets]
        rows += [detection_to_row(stem, args.frame, "manual", item) for item in gt]
        detections_csv = write_detections_csv(rows, out_dir / "detections.csv")

        n_det = len(dets)
        n_gt = len(gt) if metrics_valid else None
        spatial = evaluate_frame(
            dets,
            gt if metrics_valid else None,
            video_id=stem,
            frame=args.frame,
            annotated=metrics_valid,
            center_gate_px=DEFAULT_CENTER_GATE_PX,
            class_policy=DEFAULT_CLASS_POLICY,
            sensitivity_gates_px=DEFAULT_SENSITIVITY_GATES_PX,
        )
        diff = spatial["count_error"]
        scored_gt = spatial["n_ground_truth_scored"]
        scored_predictions = spatial["n_predictions_scored"]
        ratio = scored_predictions / scored_gt if scored_gt else None
        resources = monitor.summary()
        summary = {
            **spatial,
            "run_id": context.run_id,
            "algorithm": algorithm,
            "config_id": context.configuration_id,
            "method": detector.name,
            "split": split_name,
            "seed": int(args.seed),
            "video": str(video_path),
            "frame": args.frame,
            "frame_size": [w, h],
            "annotation_status": (
                "annotated" if metrics_valid else "ground_truth_unavailable"
            ),
            "metrics_valid": metrics_valid,
            "warmup": 0,
            "overrides": overrides,
            "resolved_params": resolved_params,
            "shared_input": str(shared_input),
            "n_detections": n_det,
            "n_ground_truth": n_gt,
            "count_diff": diff,
            "count_scope": "scored_predictions_minus_individually_annotated_gt",
            "count_diff_raw": n_det - n_gt if n_gt is not None else None,
            "count_ratio": round(ratio, 3) if ratio is not None else None,
            "evaluation_protocol_id": EVALUATION_PROTOCOL_ID,
            "metric_primary": f"f1_individuals_center_{DEFAULT_CENTER_GATE_PX:g}px",
            "center_gate_px": DEFAULT_CENTER_GATE_PX,
            "sensitivity_gates_px": list(DEFAULT_SENSITIVITY_GATES_PX),
            "tp": spatial["tp"],
            "fp": spatial["fp"],
            "fn": spatial["fn"],
            "precision": spatial["precision"],
            "recall": spatial["recall"],
            "f1": spatial["f1"],
            "center_error_mean_px": spatial["center_error_mean_px"],
            "detections": [
                {
                    "cx": round(item.cx, 2),
                    "cy": round(item.cy, 2),
                    "w": round(item.w, 2),
                    "h": round(item.h, 2),
                    "score": round(item.score, 3),
                }
                for item in dets
            ],
            "stages": [
                f"{i:02d}_{name}.png" for i, (name, _) in enumerate(stages, start=1)
            ] if not args.no_stages else [],
            "out_dir": str(out_dir),
            **resources,
        }
        summary_path = out_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if metrics_valid:
            _append_comparison(summary, DEFAULT_TEST_ROOT)
        context.complete(
            summary=summary,
            artifacts={
                "summary_json": str(summary_path),
                "detections_csv": str(detections_csv),
                "annotated_frame": str(out_dir / "detections.png"),
                "shared_input": str(shared_input),
            },
            costs=resources,
        )
    except BaseException as exc:
        context.fail(exc)
        raise

    # Console report.
    if overrides:
        print("  overrides:", overrides)
    print(f"  etapas:", ", ".join(n for n, _ in stages) or "(nenhuma)")

    print(f"\n  saídas brutas: {n_det}; objetos anotados: {n_gt}")
    if metrics_valid and scored_gt and scored_gt > 0:
        sign = "+" if diff > 0 else ""
        bar_len = 20
        filled = round(min(scored_predictions / scored_gt, 2.0) * (bar_len / 2))
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\n  contagem avaliada (não estima células ocultas em clusters)")
        print(f"    previsões pontuadas : {scored_predictions:>4}")
        print(f"    GT individual      : {scored_gt:>4}")
        print(f"    previsões ignoradas: {summary['n_predictions_ignored']:>4}")
        print(f"    diferença : {sign}{diff:>4}  ({sign}{diff/scored_gt*100:.1f}%)")
        print(f"    ratio     : {ratio:.3f}  [{bar}]")
        print(
            f"    F1@{DEFAULT_CENTER_GATE_PX:g}px   : "
            f"{summary['f1']:.4f}  "
            f"(P={summary['precision']:.4f}, R={summary['recall']:.4f})"
        )
    elif metrics_valid:
        print(
            f"\n  previsões pontuadas: {scored_predictions}; GT individual: 0; "
            f"ignoradas: {summary['n_predictions_ignored']}; diferença: {diff}"
        )
    else:
        print(f"\n  detectado: {n_det}  (sem GT disponível)")

    print(f"\n  saída: {out_dir}")
    return summary


if __name__ == "__main__":
    main()
