"""Run the preregistered threshold screening on an immutable training sample.

Official commands and interpretation belong in script/README.md. Benchmarks
measure cost; only complete coarse/refinement batches can select candidates.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.artifacts import sha256_file, write_csv_exclusive, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT, resolve_from_repository
from src.detection.io import CSV_FIELDS, detection_to_row
from src.detection.registry import build_detector
from src.evaluation.detection import DetectionEvaluator
from src.experiments.config import config_hash, load_config
from src.experiments.detection_sample import load_sample, prepare_sample
from src.experiments.detection_refinement import load_refinement_candidates
from src.experiments.detection_search import (
    expand_coarse_candidates, rank_candidates, summarize_candidate,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext, RunSnapshot, _git_dirty, _source_hash


DEFAULT_PLAN = "configs/detection/threshold/search_v3.yaml"
DEFAULT_REFINEMENT = "configs/detection/threshold/refinement_v3.yaml"
REFINEMENT_MODES = frozenset({"refinement_benchmark", "refine"})


def _is_benchmark(mode: str) -> bool:
    return mode in {"benchmark", "refinement_benchmark"}


def _sample_mode(mode: str) -> str:
    return "benchmark" if _is_benchmark(mode) else "master" if mode == "refine" else mode


def _load_refinement(path: Path, plan: dict) -> dict:
    """Bind an operational budget to immutable, independently selected parents."""
    started = time.perf_counter()
    execution = load_config(path)
    if (execution.get("kind") != "execution_of_registered_refinement"
            or execution.get("method") != "threshold"
            or execution.get("base_plan_hash") != config_hash(plan, 64)
            or load_config(resolve_from_repository(execution["base_plan"])) != plan):
        raise ValueError("Execução de refinamento incompatível com o plano original.")
    expected_sampling = {"benchmark_mode": "benchmark", "refinement_mode": "master",
                         "benchmark_frames_per_video": 1, "refinement_frames_per_video": 48}
    expected_selection = {"finalists": 2, "inherit_ranking_rule_from_base_plan": True,
                          "interpretation": "training_finalists_for_later_full_validation_not_promoted"}
    expected_benchmark = {
        "candidate_policy": "all_refinement_candidates", "selection_allowed": False,
        "projection_safety_factor": 2,
        "projection_formula": "cache_validation_seconds + parent_validation_seconds + 2 * 48 * candidate_loop_seconds",
        "interpretation": "operational_projection_not_temporal_worst_case_bound",
    }
    expected_budget = {"benchmark_soft_wall_seconds": 600, "refine_soft_wall_seconds": 7200,
                       "allow_refine_if_projection_seconds_at_most": 4800,
                       "inherit_resource_limits_from_base_plan": True}
    for name, expected in (("sampling", expected_sampling), ("selection", expected_selection),
                           ("benchmark", expected_benchmark), ("budget", expected_budget)):
        if config_hash(execution.get(name), 64) != config_hash(expected, 64):
            raise ValueError(f"Regra operacional de refinamento divergente: {name}.")
    if plan["refinement_plan"]["soft_wall_seconds"] != 7200:
        raise ValueError("Orçamento diverge do refinamento registrado.")
    coarse = resolve_from_repository(execution["coarse_manifest"])
    derived = resolve_from_repository(execution["derived_plan"])
    if sha256_file(coarse) != execution["coarse_manifest_sha256"] or sha256_file(derived) != execution["derived_plan_sha256"]:
        raise ValueError("Entradas do refinamento alteradas.")
    candidates, provenance = load_refinement_candidates(coarse, derived, plan)
    budget = {**plan["budget"], **execution["budget"]}
    return {"execution": execution, "execution_hash": config_hash(execution, 64),
            "execution_path": str(path.resolve()), "execution_sha256": sha256_file(path),
            "candidates": candidates, "provenance": provenance, "budget": budget,
            "parent_validation_seconds": time.perf_counter() - started}


class SearchBudgetExceeded(RuntimeError):
    """Stop a whole batch; never rank an incomplete comparison."""


def require_clean_repository() -> None:
    if _git_dirty(REPOSITORY_ROOT) is not False:
        raise RuntimeError("Registre o código e o plano em um commit limpo antes da execução.")


def _artifact_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _sample_manifest_reference(sample: Any) -> dict[str, str]:
    path = (Path(sample.cache_dir) / "manifest.json").resolve()
    return {"sample_manifest_path": str(path), "sample_manifest_sha256": sha256_file(path)}


def _check_budget(plan: dict, mode: str, start: float, monitor: ResourceMonitor,
                  artifact_bytes: int = 0, *, budget: dict | None = None) -> None:
    budget = plan["budget"] if budget is None else budget
    budget_mode = "benchmark" if _is_benchmark(mode) else mode
    seconds = float(budget[f"{budget_mode}_soft_wall_seconds"])
    if time.perf_counter() - start > seconds:
        raise SearchBudgetExceeded(f"Orçamento de {seconds:g} s excedido; comparação incompleta.")
    resource = monitor.summary()
    rss = resource["ram_rss_peak_mb"]
    if rss is not None and rss > float(budget["max_rss_mb"]):
        raise SearchBudgetExceeded("Orçamento de memória excedido; comparação incompleta.")
    if artifact_bytes > float(budget["max_batch_artifact_mb"]) * 1024**2:
        raise SearchBudgetExceeded("Orçamento de artefatos excedido; comparação incompleta.")


def _check_benchmark(path: Path, plan: dict, sample: Any, *, refinement: dict | None = None) -> dict:
    """A cost projection is valid only for this code, plan and exact sample."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    expected_mode = "refinement_benchmark" if refinement is not None else "benchmark"
    candidates = refinement["candidates"] if refinement else expand_coarse_candidates(plan)
    if manifest.get("status") != "complete" or summary.get("mode") != expected_mode:
        raise ValueError("É obrigatório um benchmark completo da mesma etapa antes da busca.")
    if refinement and summary.get("refinement_execution_hash") != refinement["execution_hash"]:
        raise ValueError("Benchmark de outro plano operacional de refinamento.")
    verification = manifest.get("provenance_verification", {})
    if (verification.get("status") != "verified"
            or verification.get("snapshot_sha256") != manifest.get("provenance_capture", {}).get("snapshot_sha256")):
        raise ValueError("Benchmark sem conferência final do snapshot compartilhado.")
    if (summary.get("plan_hash") != config_hash(plan, 64)
            or summary.get("sample_hash") != sample.sample_hash
            or manifest.get("source_hash") != _source_hash(REPOSITORY_ROOT)):
        raise ValueError("Benchmark pertence a outro plano, amostra ou código.")
    if summary.get("completed_candidates") != len(candidates):
        raise ValueError("Benchmark sem todos os candidatos planejados.")
    for artifact, digest in manifest.get("artifact_hashes", {}).items():
        if sha256_file(Path(manifest["artifacts"][artifact])) != digest:
            raise ValueError("Artefato do batch de benchmark alterado.")
    records = manifest.get("candidate_manifests", [])
    if len(records) != summary["completed_candidates"]:
        raise ValueError("Benchmark sem manifestos dos candidatos completos.")
    candidate_ids = []
    expected_configs = {item["configuration_id"]: item for item in candidates}
    expected_frames = [(str(vid), int(idx)) for vid in sample.video_ids
                       for idx in sample.indices("benchmark", vid)]
    planned_frames = json.loads(Path(manifest["artifacts"]["planned_frames.json"]).read_text(encoding="utf-8"))
    if planned_frames != [list(pair) for pair in expected_frames]:
        raise ValueError("Benchmark usa outros quadros.")
    if (summary.get("frames_per_candidate") != len(expected_frames)
            or summary.get("frame_evaluations") != len(candidates) * len(expected_frames)):
        raise ValueError("Universo do benchmark incompleto.")
    for record in records:
        child_path = Path(record["path"])
        if sha256_file(child_path) != record["sha256"]:
            raise ValueError("Manifesto de candidato do benchmark alterado.")
        child = json.loads(child_path.read_text(encoding="utf-8"))
        child_summary = child.get("summary", {})
        if (child.get("status") != "complete" or child_summary.get("mode") != expected_mode
                or child_summary.get("plan_hash") != summary["plan_hash"]
                or child_summary.get("sample_hash") != sample.sample_hash):
            raise ValueError("Candidato incompatível no benchmark.")
        candidate_id = child_summary["configuration_id"]
        expected_config = expected_configs.get(candidate_id)
        if (expected_config is None or child["config"].get("params") != expected_config["params"]
                or child["config"].get("evaluation") != expected_config["evaluation"]
                or child_summary.get("frames_total") != len(expected_frames)
                or child.get("source_hash") != manifest.get("source_hash")):
            raise ValueError("Parâmetros, avaliação ou quadros divergentes no benchmark.")
        if refinement and child_summary.get("refinement_execution_hash") != refinement["execution_hash"]:
            raise ValueError("Candidato de outro refinamento no benchmark.")
        candidate_ids.append(candidate_id)
        for artifact, digest in child.get("artifact_hashes", {}).items():
            if sha256_file(Path(child["artifacts"][artifact])) != digest:
                raise ValueError("Artefato de candidato do benchmark alterado.")
    expected_ids = [item["configuration_id"] for item in candidates]
    if sorted(candidate_ids) != sorted(expected_ids):
        raise ValueError("Benchmark não cobre exatamente os candidatos planejados.")
    projection_field = "projected_refinement_seconds" if refinement else "projected_coarse_seconds"
    projected = float(summary[projection_field])
    if not np.isfinite(projected) or projected < 0:
        raise ValueError("Projeção de custo inválida.")
    components = {key: float(summary[key]) for key in
                  ("cache_validation_seconds", "candidate_loop_seconds")}
    if refinement:
        components["parent_validation_seconds"] = float(summary["parent_validation_seconds"])
    if any(not np.isfinite(value) or value < 0 for value in components.values()):
        raise ValueError("Componente de tempo inválido no benchmark.")
    ratio = plan["sampling"]["master_frames_per_video" if refinement else "coarse_frames_per_video"] / plan["sampling"]["benchmark_frames_per_video"]
    reconstructed = (components["cache_validation_seconds"]
                     + components.get("parent_validation_seconds", 0)
                     + plan["budget"]["projection_safety_factor"] * ratio * components["candidate_loop_seconds"])
    if not np.isfinite(reconstructed) or abs(projected - reconstructed) > 1e-9:
        raise ValueError("Projeção do benchmark não corresponde aos tempos registrados.")
    ceiling = float(refinement["budget"]["allow_refine_if_projection_seconds_at_most"] if refinement else
                    plan["budget"]["allow_coarse_after_benchmark_if_projection_seconds_at_most"])
    if projected > ceiling:
        raise SearchBudgetExceeded(
            f"Projeção {projected:.1f} s excede o limite operacional {ceiling:g} s. "
            "Preserve o benchmark e registre uma revisão de orçamento antes de prosseguir."
        )
    return {"path": str(path), "sha256": sha256_file(path), projection_field: projected}


def run_candidate(candidate: dict, sample: Any, plan: dict, mode: str,
                  batch_id: str, batch_start: float, batch_monitor: ResourceMonitor,
                  output_root: Path | None = None, *,
                  batch_manifest_path: Path | None = None,
                  provenance_snapshot: RunSnapshot | None = None,
                  refinement: dict | None = None) -> dict:
    config = copy.deepcopy(candidate)
    sample_mode = _sample_mode(mode)
    budget = refinement["budget"] if refinement else plan["budget"]
    stage = "refinement_benchmark" if mode == "refinement_benchmark" else "refinement" if mode == "refine" else "benchmark" if mode == "benchmark" else "search"
    config.setdefault("run", {}).update(stage=stage)
    config.setdefault("provenance", {}).update(
        search_plan_id=plan["plan_id"], search_plan_hash=config_hash(plan, 64),
        sample_hash=sample.sample_hash, batch_id=batch_id, sample_mode=sample_mode,
        interpretation="cost_calibration_do_not_select" if _is_benchmark(mode) else "training_screening",
        opencv_threads=plan["run"]["opencv_threads"],
        **_sample_manifest_reference(sample),
    )
    if refinement:
        config["provenance"].update(refinement_execution_hash=refinement["execution_hash"],
                                     refinement_provenance=refinement["provenance"])
    if batch_manifest_path is not None:
        config["provenance"]["batch_manifest_path"] = str(batch_manifest_path.resolve())
    context = RunContext.create(
        module="detection", method="threshold", algorithm="threshold",
        stage=config["run"]["stage"], seed=int(plan["run"]["seed"]), config=config,
        output_root=output_root, provenance_snapshot=provenance_snapshot,
        snapshot_origin_batch_manifest=batch_manifest_path if provenance_snapshot is not None else None,
    )
    evaluation = plan["evaluation"]
    evaluator = DetectionEvaluator(
        center_gate_px=evaluation["center_gate_px"],
        class_policy=evaluation["class_policy"],
        sensitivity_gates_px=evaluation["sensitivity_gates_px"],
    )
    monitor = ResourceMonitor()
    raw: list[dict] = []
    observed: list[tuple[str, int]] = []
    expected = [(str(vid), int(idx)) for vid in sample.video_ids
                for idx in sample.indices(sample_mode, vid)]
    detector_seconds = evaluation_seconds = 0.0
    attempted_exports: set[str] = set()
    export_errors: list[dict[str, str]] = []
    artifacts = {"detections_csv": str(context.path / "detections.csv"),
                 "frame_metrics_csv": str(context.path / "frame_metrics.csv")}

    def write_observed(*, best_effort: bool = False) -> None:
        for key, rows, fields in (("detections_csv", raw, CSV_FIELDS),
                                  ("frame_metrics_csv", evaluator.frames, None)):
            if key in attempted_exports:
                continue
            # A failed write can leave partial bytes. Preserve them and never
            # reopen the same exclusive destination while handling the failure.
            attempted_exports.add(key)
            try:
                write_csv_exclusive(artifacts[key], rows, fields)
            except BaseException as error:
                export_errors.append({"artifact": key, "error": str(error),
                                      "error_type": type(error).__name__})
                if not best_effort:
                    raise

    try:
        detector = build_detector("threshold", params=config["params"])
        for video_id, frame, pixels, gt in sample.frames(sample_mode):
            _check_budget(plan, mode, batch_start, batch_monitor, budget=budget)
            started = time.perf_counter()
            detections = detector.detect(pixels)
            detect_elapsed = time.perf_counter() - started
            detector_seconds += detect_elapsed
            if len(detections) > int(budget["max_predictions_per_frame"]):
                raise SearchBudgetExceeded(
                    f"Vídeo {video_id}, quadro {frame}: {len(detections)} previsões excedem "
                    "o teto operacional; não truncar detecções para produzir métricas."
                )
            started = time.perf_counter()
            record = evaluator.add_frame(
                detections, gt, video_id=str(video_id), frame=frame,
                annotated=True, detection_ms=1000 * detect_elapsed,
            )
            evaluation_seconds += time.perf_counter() - started
            record.update(configuration_id=config["configuration_id"],
                          evaluation_protocol_id=evaluation["protocol_id"],
                          sample_hash=sample.sample_hash)
            raw.extend(detection_to_row(str(video_id), frame, "detection", det) for det in detections)
            raw.extend(detection_to_row(str(video_id), frame, "manual", det) for det in gt)
            observed.append((str(video_id), int(frame)))
            monitor.sample()
            batch_monitor.sample()
        if len(observed) != len(expected) or set(observed) != set(expected):
            raise ValueError("Universo observado diferente da amostra planejada; comparação inválida.")
        video_summaries = []
        by_video = evaluator.by_video()
        for vid in sample.video_ids:
            summary = by_video[str(vid)]
            summary.update(configuration_id=config["configuration_id"],
                           evaluation_protocol_id=evaluation["protocol_id"],
                           class_policy=evaluation["class_policy"],
                           center_gate_px=evaluation["center_gate_px"],
                           sensitivity_gates_px=evaluation["sensitivity_gates_px"],
                           sample_hash=sample.sample_hash)
            video_summaries.append(summary)
        summary = summarize_candidate(
            video_summaries, expected_video_ids=sample.video_ids,
            expected_frames_per_video={str(vid): len(sample.indices(sample_mode, vid)) for vid in sample.video_ids},
        )
        write_started = time.perf_counter()
        write_observed()
        write_csv_exclusive(context.path / "video_summary.csv", video_summaries)
        summary.update(
            mode=mode, run_id=context.run_id, manifest_path=str(context.path / "manifest.json"),
            plan_hash=config_hash(plan, 64), sample_hash=sample.sample_hash,
            detector_seconds=detector_seconds, evaluation_seconds=evaluation_seconds,
            export_seconds=time.perf_counter() - write_started, **monitor.summary(),
        )
        if refinement:
            summary["refinement_execution_hash"] = refinement["execution_hash"]
        write_json_exclusive(context.path / "summary.json", summary)
        artifacts.update(video_summary_csv=str(context.path / "video_summary.csv"),
                         summary_json=str(context.path / "summary.json"))
        context.complete(summary=summary, artifacts=artifacts,
                         artifact_hashes={key: sha256_file(Path(path)) for key, path in artifacts.items()})
        return summary
    except BaseException as exc:
        write_observed(best_effort=True)
        try:
            context.fail(exc, artifacts=artifacts, observed_frames=len(observed),
                         expected_frames=len(expected), export_errors=export_errors)
        except BaseException as manifest_error:
            # If the destination is unavailable even for the failure manifest,
            # still propagate the original execution/export error to the batch.
            exc.add_note(f"Failure manifest could not be written: {manifest_error}")
        raise


def run_batch(plan: dict, sample: Any, mode: str, *, cache_validation_seconds: float,
              benchmark: dict | None = None, output_root: Path | None = None,
              refinement_config: Path | None = None) -> Path:
    if mode not in {"benchmark", "coarse", *REFINEMENT_MODES}:
        raise ValueError("Modo de busca desconhecido.")
    require_clean_repository()
    refinement = None
    if mode in REFINEMENT_MODES:
        if refinement_config is None:
            raise ValueError("Refinamento exige configuração operacional explícita.")
        refinement = _load_refinement(refinement_config, plan)
        if refinement["provenance"]["sample_hash"] != sample.sample_hash:
            raise ValueError("Refinamento deve reutilizar exatamente a amostra dos pais.")
    elif refinement_config is not None:
        raise ValueError("Configuração de refinamento não se aplica à busca grossa.")
    if mode in {"coarse", "refine"}:
        if not benchmark or "path" not in benchmark:
            raise ValueError("Busca grossa exige benchmark completo e compatível.")
        benchmark = _check_benchmark(Path(benchmark["path"]), plan, sample, refinement=refinement)
    candidates = copy.deepcopy(refinement["candidates"]) if refinement else expand_coarse_candidates(plan)
    budget = refinement["budget"] if refinement else plan["budget"]
    sample_mode = _sample_mode(mode)
    random.Random(int(plan["run"]["seed"])).shuffle(candidates)
    started = time.perf_counter()
    monitor = ResourceMonitor()
    provenance_snapshot = RunSnapshot.capture(REPOSITORY_ROOT)
    batch_config = {"configuration_id": plan["plan_id"] + "_batch", "plan": plan,
                    "input": {"sample_hash": sample.sample_hash, **_sample_manifest_reference(sample)},
                    "mode": mode, "provenance": {"benchmark": benchmark}}
    if refinement:
        batch_config.update(configuration_id=refinement["execution"]["configuration_id"] + "_batch",
                            refinement_execution=refinement["execution"],
                            refinement_provenance=refinement["provenance"])
        batch_config["provenance"].update(refinement_execution_path=refinement["execution_path"],
                                           refinement_execution_sha256=refinement["execution_sha256"])
    batch = RunContext.create(
        module="detection", method="threshold_search", algorithm="threshold",
        stage="refinement_benchmark" if mode == "refinement_benchmark" else "refinement" if mode == "refine" else "benchmark" if mode == "benchmark" else "search",
        seed=int(plan["run"]["seed"]), output_root=output_root,
        provenance_snapshot=provenance_snapshot,
        config=batch_config,
    )
    expected_pairs = [(str(vid), int(idx)) for vid in sample.video_ids
                      for idx in sample.indices(sample_mode, vid)]
    write_json_exclusive(batch.path / "planned_candidates.json", candidates)
    write_json_exclusive(batch.path / "planned_frames.json", expected_pairs)
    summaries = []
    artifact_bytes = 0
    provenance_verification = {"status": "not_performed", "scope": "batch_end_before_ranking"}
    loop_start = time.perf_counter()
    try:
        for i, candidate in enumerate(candidates, 1):
            _check_budget(plan, mode, started, monitor, artifact_bytes, budget=budget)
            summary = run_candidate(candidate, sample, plan, mode, batch.run_id,
                                    started, monitor, output_root,
                                    batch_manifest_path=batch.path / "manifest.json",
                                    provenance_snapshot=provenance_snapshot, refinement=refinement)
            summaries.append(summary)
            artifact_bytes += _artifact_bytes(Path(summary["manifest_path"]).parent)
            write_json_exclusive(batch.path / f"candidate_{i:03d}.json", summary)
            print(json.dumps({"mode": mode, "completed": i, "planned": len(candidates),
                              "elapsed_seconds": round(time.perf_counter() - started, 2)}, ensure_ascii=False), flush=True)
        loop_seconds = time.perf_counter() - loop_start
        _check_budget(plan, mode, started, monitor, artifact_bytes + _artifact_bytes(batch.path), budget=budget)
        try:
            provenance_verification = provenance_snapshot.verify_current()
        except BaseException as exc:
            provenance_verification = {"status": "failed", "scope": "batch_end_before_ranking", "error": str(exc)}
            raise
        _check_budget(plan, mode, started, monitor, artifact_bytes + _artifact_bytes(batch.path), budget=budget)
        # Completeness is checked in benchmark too, but its ranking is not saved.
        ranked = rank_candidates(summaries, [item["configuration_id"] for item in candidates])
        write_csv_exclusive(batch.path / "candidate_metrics.csv", summaries)
        batch_summary = {
            "mode": mode, "complete": True, "plan_hash": config_hash(plan, 64),
            "sample_hash": sample.sample_hash, "completed_candidates": len(summaries),
            "frames_per_candidate": len(expected_pairs),
            "frame_evaluations": len(summaries) * len(expected_pairs),
            "cache_validation_seconds": cache_validation_seconds,
            "candidate_loop_seconds": loop_seconds, "artifact_bytes": artifact_bytes,
            **monitor.summary(),
        }
        if refinement:
            batch_summary.update(refinement_execution_hash=refinement["execution_hash"],
                                 parent_validation_seconds=refinement["parent_validation_seconds"])
        if _is_benchmark(mode):
            frames = plan["sampling"]["master_frames_per_video" if refinement else "coarse_frames_per_video"]
            ratio = frames / plan["sampling"]["benchmark_frames_per_video"]
            field = "projected_refinement_seconds" if refinement else "projected_coarse_seconds"
            batch_summary[field] = (
                cache_validation_seconds + (refinement["parent_validation_seconds"] if refinement else 0)
                + budget["projection_safety_factor"] * ratio * loop_seconds
            )
            batch_summary["selection_allowed"] = False
        else:
            for i, row in enumerate(ranked, 1):
                row["rank"] = i
            write_csv_exclusive(batch.path / "ranking.csv", ranked)
            filename = "finalists.json" if refinement else "shortlist.json"
            count = int(plan["refinement_plan"]["finalists_for_later_full_validation"] if refinement else plan["selection"]["coarse_shortlist_size"])
            write_json_exclusive(batch.path / filename, ranked[:count])
            batch_summary.update(selection_allowed=True, interpretation="training_finalists_not_promoted" if refinement else "training_shortlist_not_promoted")
        batch_artifacts = {
            path.name: str(path) for path in sorted(batch.path.iterdir())
            if path.is_file() and path.name != "manifest.json"
        }
        batch.complete(summary=batch_summary, artifacts=batch_artifacts,
                       provenance_verification=provenance_verification,
                       artifact_hashes={key: sha256_file(Path(path)) for key, path in batch_artifacts.items()},
                       candidate_manifests=[
            {"path": row["manifest_path"], "sha256": sha256_file(Path(row["manifest_path"]))}
            for row in summaries
        ])
    except BaseException as exc:
        try:
            batch.fail(exc, completed_candidates=len(summaries), selection_allowed=False,
                       provenance_verification=provenance_verification)
        except BaseException as manifest_error:
            exc.add_note(f"Batch failure manifest could not be written: {manifest_error}")
        raise
    print(json.dumps({"batch_manifest": str(batch.path / "manifest.json"), **batch_summary}, ensure_ascii=False), flush=True)
    return batch.path / "manifest.json"


def main(argv: list[str] | None = None) -> Path | None:
    parser = argparse.ArgumentParser(description="Busca prospectiva de threshold, somente no treino.")
    parser.add_argument("--plan", default=DEFAULT_PLAN)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--mode", required=True, choices=("prepare", "benchmark", "coarse", "refinement_benchmark", "refine"))
    parser.add_argument("--refinement-config", default=None)
    parser.add_argument("--benchmark-manifest", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    plan = load_config(resolve_from_repository(args.plan))
    candidates = expand_coarse_candidates(plan)
    refinement_path = resolve_from_repository(args.refinement_config or DEFAULT_REFINEMENT) if args.mode in REFINEMENT_MODES else None
    if args.refinement_config and refinement_path is None:
        raise ValueError("--refinement-config exige modo de refinamento.")
    if args.dry_run:
        refinement = None
        if refinement_path:
            refinement = _load_refinement(refinement_path, plan)
            candidates = refinement["candidates"]
        print(json.dumps({"plan_id": plan["plan_id"], "candidates": len(candidates),
                          "training_videos": plan["protocol"]["train_ids"],
                          "sampling": plan["sampling"], "sample_mode": _sample_mode(args.mode),
                          "budget": refinement["budget"] if refinement else plan["budget"]}, ensure_ascii=False, indent=2))
        return None
    require_clean_repository()
    cv2.setNumThreads(int(plan["run"]["opencv_threads"]))
    np.random.seed(int(plan["run"]["seed"]))
    cache_dir = resolve_from_repository(args.cache) if args.cache else (
        REPOSITORY_ROOT / "data/derived/detection/frame_samples" / plan["plan_id"]
    )
    if args.mode == "prepare":
        prepare_sample(plan, cache_dir)
        print(json.dumps({"cache_manifest": str(cache_dir / "manifest.json")}, ensure_ascii=False))
        return cache_dir / "manifest.json"
    started = time.perf_counter()
    sample = load_sample(cache_dir, plan)
    cache_validation_seconds = time.perf_counter() - started
    benchmark = None
    if args.mode in {"coarse", "refine"}:
        if not args.benchmark_manifest:
            raise ValueError("Informe --benchmark-manifest completo para conferir o orçamento.")
        benchmark = {"path": str(resolve_from_repository(args.benchmark_manifest))}
    return run_batch(plan, sample, args.mode, cache_validation_seconds=cache_validation_seconds,
                     benchmark=benchmark, refinement_config=refinement_path)


if __name__ == "__main__":
    main()
