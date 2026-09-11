"""Independent QA of the registered local classical-detector refinement.

Only authenticated derivatives are consumed. No production detector, evaluator,
refinement expansion or cache loader is imported. The previous independent QA's
pure geometry, SciPy matching, aggregation and byte-authentication primitives
are reused; local neighborhoods and historical selection are reconstructed here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import scipy
import yaml

from script.detection.test import verify_classical_comparison as q

ROOT = q.ROOT
PLAN = "configs/detection/comparison/classical_refinement_v1.yaml"
FAMILIES = q.FAMILIES[1:]
COUNTS = (8, 13, 11, 6, 7)
MODES = ("refinement_smoke", "refinement")
SEARCH_SHA256 = "8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0"
SEARCH_QA_SHA256 = "c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792"
COMPARISON_CANONICAL_SHA256 = "a86c8a68180e89802150a2cb3d354a5dc9657e64270d820d9fb7269f64a6dbf5"
PLAN_CANONICAL_SHA256 = "89b2b7e88c99f16d7016d17a6197cba266ce53f0706d357b016473cc6e5b5d15"


def authenticated_plan(root: Path, path: Path, audit: q.Audit) -> dict:
    path = q.under(root, str(path))
    q.require(path == root / PLAN, "only the canonical registered refinement plan is accepted")
    plan = yaml.load(audit.read(path), Loader=q.StrictYaml)
    audit.equal(q.canonical_hash(plan), PLAN_CANONICAL_SHA256, "registered refinement plan canonical hash")
    audit.subset(plan, {"kind": "static_classical_detection_refinement_v1", "expected_candidates": 45,
                       "expected_proposals": 54, "expected_valid_proposals": 51,
                       "expected_by_family": dict(zip(FAMILIES, COUNTS))}, "refinement contract")
    for role, expected in (("search_manifest", SEARCH_SHA256), ("search_qa", SEARCH_QA_SHA256)):
        audit.equal(plan["parents"][role]["sha256"], expected, "pinned historical " + role)
    audit.equal(plan["parents"]["comparison_plan"]["canonical_sha256"], COMPARISON_CANONICAL_SHA256,
                "pinned historical comparison plan")
    return plan


def qa_receipt(root: Path, reference: dict, manifest_path: Path, manifest_hash: str,
               audit: q.Audit, *, mode: str, plan_hash: str, evaluations: int) -> dict:
    report = q._json(audit.read(q.under(root, reference["path"]), reference["sha256"]))
    audit.subset(report, {"status": "passed", "mode": mode, "manifest_sha256": manifest_hash,
                          "plan_hash": plan_hash, "frame_evaluations": evaluations,
                          "new_detector_runs": 0}, "independent prerequisite QA")
    audit.equal(str(q.under(root, report["manifest"])), str(manifest_path), "QA belongs to prerequisite manifest")
    q.require(integer_positive(report["comparisons"]) and integer_positive(report["scipy_matchings"]), "empty prerequisite QA")
    return report


def integer_positive(value) -> bool:
    return q.integer(value) > 0


def parent_record(candidate: dict, manifest: dict, reference: dict) -> dict:
    return {**{key: copy.deepcopy(candidate[key]) for key in ("configuration_id", "family", "method", "params", "evaluation", "run")},
            "parent_manifest": copy.deepcopy(reference), "parent_source_hash": manifest["source_hash"],
            "parent_git_sha": manifest["git_sha"]}


def historical_sources(root: Path, manifest: dict, audit: q.Audit) -> dict[str, str]:
    """Verify the old executable/config bytes on the historical Git file list."""
    result = subprocess.run(["git", "ls-tree", "-r", "--name-only", manifest["git_sha"]],
                            cwd=root, capture_output=True, check=True, timeout=30)
    paths = result.stdout.decode("utf-8").splitlines()
    paths = [name for name in paths if (name.split("/", 1)[0] in {"src", "script", "configs"}
             and Path(name).suffix.lower() in {".py", ".yaml", ".yml"} and "__pycache__" not in Path(name).parts)
             or name in {"pyproject.toml", "requirements.txt", "requirements-core.lock"}]
    q.require(paths and len(paths) == len(set(paths)), "empty or duplicate historical source inventory")
    fingerprint, records = hashlib.sha256(), {}
    for name in sorted(paths, key=str.lower):
        path = q.under(root, name)
        raw = audit.read(path)
        encoded = name.encode("utf-8")
        fingerprint.update(len(encoded).to_bytes(4, "big"))
        fingerprint.update(encoded)
        fingerprint.update(raw)
        records[str(path)] = hashlib.sha256(raw).hexdigest()
    audit.equal(fingerprint.hexdigest(), manifest["source_hash"], "historical source byte equivalence")
    return records


def authenticated_parents(root: Path, plan: dict, audit: q.Audit):
    """Authenticate closed history and derive its parents, without rerunning old QA."""
    refs = plan["parents"]
    old_plan = yaml.load(audit.read(q.under(root, refs["comparison_plan"]["path"])), Loader=q.StrictYaml)
    audit.equal(q.canonical_hash(old_plan), refs["comparison_plan"]["canonical_sha256"], "comparison plan hash")
    for key in ("input", "evaluation", "run", "train_ids", "budget"):
        audit.equal(plan[key], old_plan[key], "refinement preserves " + key)
    candidates = q.independent_candidates(old_plan)
    path = q.under(root, refs["search_manifest"]["path"])
    old = q._json(audit.read(path, refs["search_manifest"]["sha256"]))
    q.provenance(old, audit, mode="search")
    audit.equal(old["config"]["plan"], old_plan, "historical resolved comparison plan")
    audit.subset(old["summary"], {"complete": True, "completed_candidates": 43, "frames_per_candidate": 576,
                 "frame_evaluations": 24768, "selection_allowed": True, "promotion_allowed": False,
                 "validation_released": False, "plan_hash": q.canonical_hash(old_plan),
                 "sample_hash": plan["input"]["sample_hash"]}, "closed historical search")
    old_qa = qa_receipt(root, refs["search_qa"], path, refs["search_manifest"]["sha256"], audit,
                        mode="search", plan_hash=q.canonical_hash(old_plan), evaluations=24768)
    files = q.authenticated_artifacts(old, path.parent, audit)
    audit.equal(q._json(files["planned_candidates.json"]), candidates, "historical candidate universe")
    audit.equal(audit.read(q.under(root, refs["finalists"]["path"]), refs["finalists"]["sha256"]),
                files["family_finalists.json"], "pinned historical finalists file")
    q.require(len(old["candidate_manifests"]) == 43, "historical child count differs")
    records, summaries, manifests = {}, [], {}
    consumed = {str(q.under(root, ref["path"])) for ref in refs.values()}
    consumed.update(str(q.under(path.parent, raw)) for raw in old["artifacts"].values())
    qa_files = {str(Path(raw).resolve()): value for raw, value in old_qa["files"].items()}
    for index, (candidate, reference) in enumerate(zip(candidates, old["candidate_manifests"]), 1):
        child_path = q.under(root, reference["path"])
        consumed.add(str(child_path))
        child = q._json(audit.read(child_path, reference["sha256"]))
        q.provenance(child, audit, mode="search", parent=old)
        q.require(str(child_path) in qa_files, "historical child absent from its QA")
        audit.equal(qa_files[str(child_path)]["sha256"], reference["sha256"], "historical QA child hash")
        expected = copy.deepcopy(candidate)
        expected["run"]["stage"] = "search"
        audit.subset(child["config"], expected, "historical resolved candidate")
        q.require(set(child["artifacts"]) == set(child["artifact_hashes"]), "historical artifact hash keys differ")
        declared, summary = set(), None
        for key, raw in child["artifacts"].items():
            artifact = q.under(child_path.parent, raw)
            consumed.add(str(artifact))
            q.require(artifact.parent == child_path.parent and artifact.name not in declared, "foreign historical child artifact")
            declared.add(artifact.name)
            data = audit.read(artifact, child["artifact_hashes"][key], retain=artifact.name == "summary.json")
            q.require(str(artifact) in qa_files, "historical artifact absent from its QA")
            audit.equal(qa_files[str(artifact)]["sha256"], child["artifact_hashes"][key], "historical QA artifact hash")
            if artifact.name == "summary.json":
                summary = q._json(data)
        q.require(declared == {"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"}, "historical child artifact schema differs")
        q.require(declared == {f.name for f in child_path.parent.iterdir() if f.is_file() and f.name != "manifest.json"},
                  "undeclared historical child artifact")
        audit.equal(summary, child["summary"], "historical summary vs manifest")
        audit.equal(summary, q._json(files[f"candidate_{index:03d}.json"]), "historical checkpoint")
        audit.subset(summary, {"configuration_id": candidate["configuration_id"], "family": candidate["family"],
                              "method": candidate["method"], "complete": True, "frames_total": 576}, "historical summary identity")
        summaries.append(summary)
        identifier = candidate["configuration_id"]
        q.require(identifier not in records, "duplicate historical candidate")
        records[identifier] = parent_record(candidate, child, {"path": str(child_path), "sha256": reference["sha256"]})
        manifests[identifier] = child
    finalist_ids = q.verify_ranking(files, summaries, audit)
    audit.equal(old_qa["family_finalist_ids"], finalist_ids, "historical QA family selection")
    observed_metrics = q.csv_rows(files["candidate_metrics.csv"])
    q.require(len(observed_metrics) == 43, "historical candidate metrics size differs")
    for observed, expected in zip(observed_metrics, summaries):
        audit.equal(observed, {k: "" if v is None else str(v) for k, v in expected.items()}, "historical candidate metrics")
    parents = [records[identifier] for identifier in finalist_ids if records[identifier]["family"] != "threshold"]
    history = {**records["t218_o0_c2_reference_v1"], "reexecuted": False,
               "interpretation": "historical_development_reference_not_ranked"}
    q.require(len(parents) == 10, "historical finalist parents incomplete")
    sources = historical_sources(root, old, audit)
    consumed.update(sources)
    authentication = {"search_manifest": {"path": str(path), "sha256": refs["search_manifest"]["sha256"]},
                      "search_qa": {"path": str(q.under(root, refs["search_qa"]["path"])), "sha256": refs["search_qa"]["sha256"]},
                      "authenticated_files": {name: audit.files[name]["sha256"] for name in consumed},
                      "historical_source_files": sources, "historical_source_hash": old["source_hash"],
                      "historical_git_sha": old["git_sha"], "numerical_parent_qa_repeated": False}
    return parents, history, manifests, authentication


def ranking(summaries: list[dict]) -> list[dict]:
    """Unrounded quality ordering; runtime never contributes to selection."""
    q.require(len({r["configuration_id"] for r in summaries}) == len(summaries), "duplicate ranking candidate")
    ordered = sorted(summaries, key=lambda r: (-q.number(r["macro_video_f1"]),
                     -q.number(r["macro_video_recall"]), q.number(r["macro_video_count_mae"]), r["configuration_id"]))
    return [{**row, "rank": i} for i, row in enumerate(ordered, 1)]


def independent_neighborhood(plan: dict, parents: list[dict]) -> tuple[list[dict], dict]:
    """Reconstruct a one-axis neighborhood, without producer expansion helpers."""
    q.require(tuple(group["family"] for group in plan["neighborhood"]) == FAMILIES, "neighborhood family order differs")
    q.require(Counter(p["family"] for p in parents) == Counter({f: 2 for f in FAMILIES}), "requires two parents for each of five families")
    q.require(len({p["configuration_id"] for p in parents}) == 10, "duplicate historical parent")
    candidates, proposals, valid, excluded = [], 0, 0, []
    for group in plan["neighborhood"]:
        family, unique = group["family"], {}
        axes = group["axes"]
        q.require(len({a["parameter"] for a in axes}) == len(axes), "duplicate refinement axis")
        for parent in (p for p in parents if p["family"] == family):
            variants = [(None, 0, copy.deepcopy(parent["params"]))]
            for axis in axes:
                parameter = axis["parameter"]
                q.require(parameter in parent["params"], "refinement axis missing in parent")
                original = parent["params"][parameter]
                q.require(not isinstance(original, bool) and isinstance(original, (int, float)), "nonnumeric refinement axis")
                step = Decimal(str(axis["step"]))
                q.require(step.is_finite() and step > 0, "invalid refinement step")
                for sign in (-1, 1):
                    changed = Decimal(str(original)) + sign * step
                    delta = sign * step
                    inside = ((axis["min"] is None or changed >= Decimal(str(axis["min"])))
                              and (axis["max"] is None or changed <= Decimal(str(axis["max"]))))
                    if axis.get("odd", False):
                        inside = inside and changed == changed.to_integral_value() and int(changed) % 2 == 1
                    value = int(changed) if isinstance(original, int) and changed == changed.to_integral_value() else float(changed)
                    delta_value = int(delta) if delta == delta.to_integral_value() else float(delta)
                    params = copy.deepcopy(parent["params"])
                    params[parameter] = value
                    if inside:
                        variants.append((parameter, delta_value, params))
                    else:
                        excluded.append({"parent_configuration_id": parent["configuration_id"], "axis": parameter,
                                         "delta": delta_value, "value": value})
            proposals += 1 + 2 * len(axes)
            valid += len(variants)
            for axis, delta, params in variants:
                key = q.canonical_hash({"method": parent["method"], "params": params})
                lineage = {"parent_configuration_id": parent["configuration_id"], "axis": axis, "delta": delta}
                if key not in unique:
                    unique[key] = {"configuration_id": f"{family}_refinement_v1_{len(unique) + 1:03d}",
                                   "family": family, "method": parent["method"], "params": params,
                                   "evaluation": copy.deepcopy(plan["evaluation"]), "run": copy.deepcopy(plan["run"]),
                                   "refinement_lineage": []}
                unique[key]["refinement_lineage"].append(lineage)
        candidates.extend(unique.values())
    q.require(proposals == 54 and valid == 51 and len(candidates) == 45, "registered neighborhood cardinalities differ")
    q.require(tuple(sum(c["family"] == f for c in candidates) for f in FAMILIES) == COUNTS, "refinement family sizes differ")
    anchors = [origin["parent_configuration_id"] for c in candidates for origin in c["refinement_lineage"] if origin["axis"] is None]
    q.require(sorted(anchors) == sorted(p["configuration_id"] for p in parents), "parent anchors were lost in deduplication")
    random.Random(42).shuffle(candidates)
    return candidates, {"proposals": proposals, "valid_proposals": valid, "unique_candidates": len(candidates),
                        "excluded_proposals": excluded, "by_family": dict(zip(FAMILIES, COUNTS))}


def verify_ranking(files: dict[str, bytes], summaries: list[dict], audit: q.Audit) -> list[str]:
    q.require(len(summaries) == 45 and Counter(r["family"] for r in summaries) == Counter(dict(zip(FAMILIES, COUNTS))),
              "ranking universe differs")
    ranked = ranking(summaries)
    observed = q.csv_rows(files["ranking.csv"])
    q.require(len(observed) == len(ranked), "ranking size differs")
    for actual, expected in zip(observed, ranked):
        audit.equal(actual, {key: "" if value is None else str(value) for key, value in expected.items()}, "ranking serialization")
    finalists = [row for family in FAMILIES for row in [r for r in ranked if r["family"] == family][:2]]
    audit.equal(q._json(files["family_finalists.json"]), finalists, "refinement family finalists")
    q.require(len(finalists) == 10, "finalist count differs")
    return [row["configuration_id"] for row in finalists]


def parent_parity_inputs(parent: dict, pairs: list[tuple[str, int]], master: list[tuple[str, int]], audit: q.Audit):
    path = Path(parent["parent_manifest"]["path"])
    manifest = q._json(audit.read(path, parent["parent_manifest"]["sha256"]))
    files = q.authenticated_artifacts(manifest, path.parent, audit)
    objects = {pair: [] for pair in pairs}
    universe = set(master)
    for raw in q.csv_rows(files["detections.csv"]):
        pair = raw["video_id"], q.integer(raw["frame"])
        q.require(pair in universe, "historical parent raw frame outside master plan")
        if pair in objects:
            objects[pair].append(q.object_row(raw, audit))
    frames = q.csv_rows(files["frame_metrics.csv"])
    q.require([(r["video_id"], q.integer(r["frame"])) for r in frames] == master,
              "historical parent metric frame universe differs")
    return objects, {pair: row for pair, row in zip(master, frames) if pair in objects}


def verify_candidate(root: Path, record: dict, candidate: dict, batch_path: Path, batch: dict,
                     plan: dict, pairs: list[tuple[str, int]], cached_gt: dict, input_reference: dict,
                     audit: q.Audit, *, parity: list[tuple[dict, dict, dict]] = ()) -> tuple[dict, int]:
    path = q.under(root, record["path"])
    child = q._json(audit.read(path, record["sha256"]))
    mode, plan_hash = batch["summary"]["mode"], q.canonical_hash(plan)
    q.provenance(child, audit, mode=mode, parent=batch)
    config = copy.deepcopy(candidate)
    config["run"]["stage"] = mode
    audit.subset(child["config"], config, "refinement candidate config")
    audit.subset(child["config"]["provenance"], {"plan_id": plan["plan_id"], "plan_hash": plan_hash,
                 **input_reference, "sample_mode": "benchmark" if mode == MODES[0] else "master",
                 "batch_manifest_path": str(batch_path)}, "candidate cache provenance")
    audit.equal(child["provenance_capture"]["origin_batch_manifest"], str(batch_path), "candidate origin batch")
    files = q.authenticated_artifacts(child, path.parent, audit)
    q.require(set(files) == {"detections.csv", "frame_metrics.csv", "video_summary.csv", "summary.json"}, "candidate artifact schema differs")
    predictions, gt = {pair: [] for pair in pairs}, {pair: [] for pair in pairs}
    for raw in q.csv_rows(files["detections.csv"]):
        row = q.object_row(raw, audit)
        pair = row["video_id"], row["frame"]
        q.require(pair in gt, "exported object outside refinement frame plan")
        (gt if row["source"] == "manual" else predictions)[pair].append(row)
    identifier = candidate["configuration_id"]
    for pair in pairs:
        audit.equal(gt[pair], cached_gt[pair], f"{identifier}/{pair}: authenticated raw GT")
        q.require(len(predictions[pair]) <= plan["budget"]["max_predictions_per_frame"], "prediction ceiling exceeded")
        for parent, objects, _ in parity:
            audit.equal(predictions[pair] + gt[pair], objects[pair], f"{parent['configuration_id']}/{pair}: historical raw parity")
    observed_frames = q.csv_rows(files["frame_metrics.csv"])
    q.require([(r["video_id"], q.integer(r["frame"])) for r in observed_frames] == pairs, "frame metric universe differs")
    reconstructed = []
    for observed, pair in zip(observed_frames, pairs):
        row, witnesses = q.frame_metrics(predictions[pair], gt[pair], *pair, audit)
        for parent, _, parent_frames in parity:
            q.compare_frame(parent_frames[pair], row, witnesses, audit, f"{parent['configuration_id']}/{pair}: historical scientific parity")
        row.update(configuration_id=identifier, family=candidate["family"], evaluation_protocol_id=q.PROTOCOL,
                   sample_hash=plan["input"]["sample_hash"])
        q.compare_frame(observed, row, witnesses, audit, f"{identifier}/{pair}")
        row["detection_ms"] = q.number(observed["detection_ms"], "detection time")
        q.require(row["detection_ms"] >= 0, "negative detection time")
        reconstructed.append(row)
    observed_videos = q.csv_rows(files["video_summary.csv"])
    q.require([r["video_id"] for r in observed_videos] == list(q.TRAIN), "video summary universe differs")
    videos = []
    for observed, video in zip(observed_videos, q.TRAIN):
        row = q.video_metrics([r for r in reconstructed if r["video_id"] == video], video)
        row.update(configuration_id=identifier, family=candidate["family"], evaluation_protocol_id=q.PROTOCOL,
                   class_policy="individuals_ignore_clusters", center_gate_px=10,
                   sensitivity_gates_px=[15, 20], sample_hash=plan["input"]["sample_hash"])
        audit.subset(observed, row, f"{identifier}/{video}: aggregation")
        videos.append(row)
    expected = q.candidate_metrics(videos, identifier, 1 if mode == MODES[0] else 48)
    expected.update(mode=mode, family=candidate["family"], method=candidate["method"], run_id=child["run_id"],
                    manifest_path=str(path), plan_hash=plan_hash, sample_hash=plan["input"]["sample_hash"])
    summary = q._json(files["summary.json"])
    audit.subset(summary, expected, f"{identifier}: summary")
    audit.equal(summary, child["summary"], "child summary vs manifest")
    audit.equal(sum(r["detection_ms"] for r in reconstructed) / 1000, summary["detector_seconds"], "detector timing sum")
    for key in ("evaluation_seconds", "export_seconds", "ram_rss_peak_mb"):
        q.require(q.number(summary[key]) >= 0, "negative candidate resource/timing")
    q.require(q.number(summary["ram_rss_peak_mb"]) <= plan["budget"]["max_rss_mb"], "candidate RSS exceeded")
    q.require(q.integer(summary["resource_samples"]) > 0, "candidate RSS has no samples")
    return summary, sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())


def smoke_prerequisite(root: Path, batch: dict, plan: dict, candidates: list[dict], input_reference: dict,
                       pairs: list[tuple[str, int]], audit: q.Audit) -> None:
    refs = batch["config"]["provenance"]
    q.require(set(refs) == {"smoke", "smoke_qa"} and all(isinstance(v, dict) for v in refs.values()),
              "refinement requires smoke manifest and independent QA")
    path = q.under(root, refs["smoke"]["path"])
    smoke = q._json(audit.read(path, refs["smoke"]["sha256"]))
    q.provenance(smoke, audit, mode=MODES[0])
    audit.equal(smoke["source_hash"], batch["source_hash"], "smoke source compatibility")
    audit.subset(smoke["config"], {"plan": plan, "input": input_reference, "mode": MODES[0]}, "smoke resolved inputs")
    audit.subset(smoke["summary"], {"complete": True, "mode": MODES[0], "completed_candidates": 45,
                    "frames_per_candidate": 12, "frame_evaluations": 540, "selection_allowed": False,
                    "promotion_allowed": False, "validation_released": False, "parent_parity_controls": 10,
                    "plan_hash": q.canonical_hash(plan), "sample_hash": plan["input"]["sample_hash"]}, "smoke prerequisite")
    qa_receipt(root, refs["smoke_qa"], path, refs["smoke"]["sha256"], audit,
               mode=MODES[0], plan_hash=q.canonical_hash(plan), evaluations=540)
    files = q.authenticated_artifacts(smoke, path.parent, audit)
    audit.equal(q._json(files["planned_candidates.json"]), candidates, "smoke candidate plan")
    audit.equal(q._json(files["planned_frames.json"]), [list(pair) for pair in pairs], "smoke frame plan")
    q.require(len(smoke["candidate_manifests"]) == 45, "smoke candidate count differs")
    seen = set()
    for reference, candidate in zip(smoke["candidate_manifests"], candidates):
        child_path = q.under(root, reference["path"])
        q.require(child_path not in seen, "duplicate smoke child")
        seen.add(child_path)
        child = q._json(audit.read(child_path, reference["sha256"]))
        q.provenance(child, audit, mode=MODES[0], parent=smoke)
        expected = copy.deepcopy(candidate)
        expected["run"]["stage"] = MODES[0]
        audit.subset(child["config"], expected, "smoke candidate config")
        child_files = q.authenticated_artifacts(child, child_path.parent, audit)
        audit.equal(q._json(child_files["summary.json"]), child["summary"], "smoke child summary")


def verify_batch(manifest_path: Path, *, root: Path = ROOT, plan_path: Path | None = None,
                 audit: q.Audit | None = None) -> dict:
    root, audit = Path(root).resolve(), audit or q.Audit()
    manifest_path = q.under(root, str(manifest_path))
    plan = authenticated_plan(root, q.under(root, str(plan_path or root / PLAN)), audit)
    parents, history, _, parent_authentication = authenticated_parents(root, plan, audit)
    candidates, neighborhood = independent_neighborhood(plan, parents)
    pair_modes, cached_gt, input_reference = q.authenticated_cache(root, plan, audit)
    raw_manifest = audit.read(manifest_path)
    manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    batch = q._json(raw_manifest)
    mode, plan_hash = batch.get("summary", {}).get("mode"), q.canonical_hash(plan)
    q.require(mode in MODES, "only complete refinement_smoke/refinement can be verified")
    q.provenance(batch, audit, mode=mode)
    pairs = pair_modes["smoke" if mode == MODES[0] else "search"]
    audit.subset(batch["config"], {"plan": plan, "mode": mode, "input": input_reference}, "batch resolved inputs")
    summary = batch["summary"]
    audit.subset(summary, {"complete": True, "mode": mode, "plan_hash": plan_hash, "sample_hash": plan["input"]["sample_hash"],
                  "completed_candidates": 45, "frames_per_candidate": len(pairs), "frame_evaluations": 45 * len(pairs),
                  "selection_allowed": mode == MODES[1], "promotion_allowed": False, "validation_released": False,
                  "historical_threshold_reference_reexecuted": False, "parent_parity_controls": 10,
                  "wall_seconds_limit": None}, "batch summary")
    for key in ("cache_validation_seconds", "parent_validation_seconds", "candidate_loop_seconds", "ram_rss_peak_mb"):
        q.require(q.number(summary[key]) >= 0, "negative batch resource/timing")
    q.require(q.number(summary["ram_rss_peak_mb"]) <= plan["budget"]["max_rss_mb"] and q.integer(summary["resource_samples"]) > 0,
              "batch RSS limit/sampling failed")
    files = q.authenticated_artifacts(batch, manifest_path.parent, audit)
    expected_files = {"planned_candidates.json", "planned_frames.json", "parents.json", "historical_reference.json",
                      "parent_authentication.json", "parent_parity.json", "candidate_metrics.csv"}
    expected_files |= {f"candidate_{i:03d}.json" for i in range(1, 46)}
    if mode == MODES[1]:
        expected_files |= {"ranking.csv", "family_finalists.json"}
    q.require(set(files) == expected_files, "batch artifact schema differs")
    for name, expected in (("planned_candidates.json", candidates), ("planned_frames.json", [list(pair) for pair in pairs]),
                           ("parents.json", parents), ("historical_reference.json", history),
                           ("parent_authentication.json", parent_authentication)):
        audit.equal(q._json(files[name]), expected, "batch " + name)
    records = batch["candidate_manifests"]
    q.require(len(records) == 45, "candidate manifest universe incomplete")
    summaries, parity_records, seen, total_bytes = [], [], set(), 0
    parent_index = {p["configuration_id"]: p for p in parents}
    for index, (record, candidate) in enumerate(zip(records, candidates), 1):
        path = q.under(root, record["path"])
        q.require(path not in seen and path != manifest_path, "duplicate candidate manifest")
        seen.add(path)
        anchors = [origin["parent_configuration_id"] for origin in candidate["refinement_lineage"] if origin["axis"] is None]
        parity = []
        for identifier in anchors:
            parent = parent_index[identifier]
            audit.equal(candidate["params"], parent["params"], "parent anchor retains all parameters")
            objects, frames = parent_parity_inputs(parent, pairs, pair_modes["search"], audit)
            parity.append((parent, objects, frames))
        child_summary, child_bytes = verify_candidate(root, record, candidate, manifest_path, batch, plan,
                                      pairs, cached_gt, input_reference, audit, parity=parity)
        audit.equal(q._json(files[f"candidate_{index:03d}.json"]), child_summary, "candidate checkpoint")
        summaries.append(child_summary)
        total_bytes += child_bytes
        for parent, objects, _ in parity:
            parity_records.append({"parent_configuration_id": parent["configuration_id"], "configuration_id": candidate["configuration_id"],
                    "parent_manifest": parent["parent_manifest"], "status": "passed", "frames_compared": len(pairs),
                    "rows_compared": {"detections.csv": sum(map(len, objects.values())), "frame_metrics.csv": len(pairs)},
                    "excluded_fields": ["configuration_id", "detection_ms"], "absolute_tolerance": q.ATOL, "relative_tolerance": q.RTOL})
        print(json.dumps({"verification_candidate": index, "planned": 45, "configuration_id": candidate["configuration_id"]}), flush=True)
    q.require(len(parity_records) == 10 and {r["parent_configuration_id"] for r in parity_records} == set(parent_index),
              "not all ten historical parents were independently compared")
    audit.equal(q._json(files["parent_parity.json"]), parity_records, "independent parent parity witnesses")
    audit.equal(total_bytes, summary["candidate_artifact_bytes"], "candidate artifact bytes")
    batch_bytes = sum(p.stat().st_size for p in manifest_path.parent.iterdir() if p.is_file())
    q.require(total_bytes + batch_bytes <= plan["budget"]["max_batch_artifact_mb"] * 1024**2, "final artifact limit exceeded")
    observed = q.csv_rows(files["candidate_metrics.csv"])
    q.require(len(observed) == 45, "candidate metrics count differs")
    for actual, expected in zip(observed, summaries):
        audit.equal(actual, {key: "" if value is None else str(value) for key, value in expected.items()}, "candidate metrics serialization")
    finalists = []
    if mode == MODES[1]:
        finalists = verify_ranking(files, summaries, audit)
        smoke_prerequisite(root, batch, plan, candidates, input_reference, pair_modes["smoke"], audit)
    else:
        audit.equal(batch["config"]["provenance"], {"smoke": None, "smoke_qa": None}, "smoke has no prerequisite smoke")
    audit.read(manifest_path, manifest_hash)
    return {"status": "passed", "mode": mode, "manifest": str(manifest_path), "manifest_sha256": manifest_hash,
            "plan_hash": plan_hash, "candidates": 45, "frames_per_candidate": len(pairs), "frame_evaluations": 45 * len(pairs),
            "family_finalist_ids": finalists, "neighborhood": neighborhood, "new_detector_runs": 0,
            "historical_parent_qa_repeated": False, "historical_threshold_reference_reexecuted": False,
            "parent_parity": {"status": "passed", "controls": 10, "frames_per_control": len(pairs), "records": parity_records},
            "limitations": ["Original videos and labels are not reread; pixel decoding and detector inference are not reproduced.",
                "Previous search metrics rely on its pinned approved QA; historical selection is independently reconstructed without rerunning that numerical battery.",
                "Ten repeated parents are compared on raw objects and scientific frame metrics; they are reproducibility controls, not independent replicates.",
                "Wall time and sampled RSS are checked as recorded; instantaneous resource peaks and actual inference timing are not reproduced.",
                "Counts, F1 and optimal total matching distance are reconstructed at all gates; any cooptimal median/max exception is explicitly listed.",
                "Training refinement does not promote a detector, release validation/test or establish generalization or tracking quality."],
            **audit.summary()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=Path(PLAN))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    q.require(output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "data/sources"), "QA output outside derived workspace")
    q.require(not output.exists(), "QA output already exists; preserve previous attempts")
    started, audit = time.perf_counter(), q.Audit()
    result = {"started_at": datetime.now(timezone.utc).isoformat(),
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "shared_independent_core_sha256": hashlib.sha256(Path(q.__file__).read_bytes()).hexdigest(),
              "numpy_version": np.__version__, "scipy_version": scipy.__version__}
    code = 0
    try:
        result.update(verify_batch(args.manifest, plan_path=args.plan, audit=audit))
    except Exception as exc:
        code = 1
        result.update(status="failed", error=str(exc), error_type=type(exc).__name__, **audit.summary())
    result["elapsed_seconds"] = time.perf_counter() - started
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"status": result["status"], "output": str(output), "comparisons": audit.comparisons,
                      "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
