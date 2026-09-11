"""Synthetic lineage, numerical QA and hostile-artifact coverage for refinement.

Production evaluation is imported only here to emit synthetic geometry outputs.
No video, cached image or historical experimental result is executed by tests.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from script.detection.test import verify_classical_refinement as qa
from src.evaluation.detection import evaluate_frame, aggregate_frame_metrics
from src.experiments.detection_search import summarize_candidate

q = qa.q
PARENT_IDS = ("otsu_v1_004", "otsu_v1_003", "adaptive_threshold_v1_002", "adaptive_threshold_v1_008",
              "hybrid_threshold_v1_002", "hybrid_threshold_v1_001", "blob_v1_003", "blob_v1_002",
              "watershed_v1_005", "watershed_v1_002")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def seal(path, manifest):
    files = {p.name: str(p.resolve()) for p in path.parent.iterdir() if p.is_file() and p.name != "manifest.json"}
    manifest["artifacts"] = files
    manifest["artifact_hashes"] = {key: digest(raw) for key, raw in files.items()}
    manifest["config_hash"] = q.canonical_hash(manifest["config"])[:12]
    write_json(path, manifest)


def actual_plans_and_parent_parameters():
    plan = yaml.safe_load((qa.ROOT / qa.PLAN).read_text(encoding="utf-8"))
    comparison = yaml.safe_load((qa.ROOT / q.PLAN).read_text(encoding="utf-8"))
    by_id = {p["configuration_id"]: p for p in q.independent_candidates(comparison)}
    return plan, comparison, [copy.deepcopy(by_id[identifier]) for identifier in PARENT_IDS]


def test_decimal_neighborhood_exact_counts_lineage_and_single_axis():
    plan, _, parents = actual_plans_and_parent_parameters()
    candidates, metadata = qa.independent_neighborhood(plan, parents)
    assert (metadata["proposals"], metadata["valid_proposals"], metadata["unique_candidates"]) == (54, 51, 45)
    assert len(metadata["excluded_proposals"]) == 3
    assert metadata["by_family"] == dict(zip(qa.FAMILIES, qa.COUNTS))
    index = {p["configuration_id"]: p for p in parents}
    assert candidates == qa.independent_neighborhood(plan, parents)[0]
    assert any(c["family"] == "hybrid_threshold" and c["params"]["clip_limit"] == 0.5 for c in candidates)
    assert any(c["family"] == "watershed" and c["params"]["dist_ratio"] == 0.3 for c in candidates)
    assert sum(len(c["refinement_lineage"]) for c in candidates) == 51
    for candidate in candidates:
        assert candidate["family"] != "threshold"
        for origin in candidate["refinement_lineage"]:
            parent = index[origin["parent_configuration_id"]]
            changed = [key for key in parent["params"] if parent["params"][key] != candidate["params"][key]]
            assert changed == ([] if origin["axis"] is None else [origin["axis"]])
            assert candidate["method"] == parent["method"]


@pytest.mark.parametrize("fault", ["lost_parent", "duplicate_parent", "family", "step", "limits", "axis"])
def test_neighborhood_rejects_incomplete_or_altered_universe(fault):
    plan, _, parents = actual_plans_and_parent_parameters()
    if fault == "lost_parent":
        parents.pop()
    elif fault == "duplicate_parent":
        parents[1] = parents[0]
    elif fault == "family":
        plan["neighborhood"].reverse()
    elif fault == "step":
        plan["neighborhood"][0]["axes"][0]["step"] = 0
    elif fault == "limits":
        plan["neighborhood"][0]["axes"][0]["max"] = 0
    else:
        plan["neighborhood"][0]["axes"][0]["parameter"] = "missing"
    with pytest.raises(q.VerificationError):
        qa.independent_neighborhood(plan, parents)


def box(cx=10, cy=10, *, cls=0, identity="", manual=False, w=4, h=4):
    return {"video_id": "11", "frame": 0, "source": "manual" if manual else "detection", "object_id": identity,
            "class_id": cls, "class_name": {0: "normal", 1: "cluster", 2: "pinhead"}[cls],
            "cx": float(cx), "cy": float(cy), "w": float(w), "h": float(h),
            "x": cx - w / 2, "y": cy - h / 2, "score": 1.0}


def geometry(extra, video, frame):
    gt = [box(manual=True, identity="individual"), box(35, 40, cls=2, manual=True, identity="small"),
          box(40, 40, cls=1, manual=True, identity="cluster", w=50, h=50)]
    preds = [box(), box(35, 40), box(55, 40)] + [box(90 + i, 90) for i in range(extra)]
    for row in preds + gt:
        row.update(video_id=video, frame=frame)
    return preds, gt


def make_child(root, candidate, mode, plan, batch_path, capture, common, input_reference, pairs, extra):
    path = root / f"synthetic/{mode}/{candidate['configuration_id']}/manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(candidate)
    config["run"]["stage"] = mode
    config["provenance"] = {"plan_id": plan["plan_id"], "plan_hash": q.canonical_hash(plan), **input_reference,
                            "sample_mode": "benchmark" if mode == qa.MODES[0] else "master", "batch_manifest_path": str(batch_path)}
    raw, rows, videos = [], [], []
    template = evaluate_frame(*geometry(extra, "11", 0), video_id="11", frame=0, detection_ms=1.0)
    for video, frame in pairs:
        preds, gt = geometry(extra, video, frame)
        raw.extend(preds + gt)
        row = {**template, "video_id": video, "frame": frame}
        row.update(configuration_id=candidate["configuration_id"], family=candidate["family"],
                   evaluation_protocol_id=q.PROTOCOL, sample_hash=plan["input"]["sample_hash"])
        rows.append(row)
    for video in q.TRAIN:
        row = aggregate_frame_metrics([r for r in rows if r["video_id"] == video], video_id=video)
        row.update(configuration_id=candidate["configuration_id"], family=candidate["family"], evaluation_protocol_id=q.PROTOCOL,
                   class_policy="individuals_ignore_clusters", center_gate_px=10, sensitivity_gates_px=[15, 20],
                   sample_hash=plan["input"]["sample_hash"])
        videos.append(row)
    summary = summarize_candidate(videos, q.TRAIN, len(pairs) // 12)
    summary.update(mode=mode, family=candidate["family"], method=candidate["method"], run_id=candidate["configuration_id"],
                   manifest_path=str(path), plan_hash=q.canonical_hash(plan), sample_hash=plan["input"]["sample_hash"],
                   detector_seconds=len(pairs) / 1000, evaluation_seconds=0.1, export_seconds=0.1,
                   ram_rss_peak_mb=100.0, resource_samples=len(pairs), vram_allocated_peak_mb=None, vram_reserved_peak_mb=None)
    for filename, data in (("detections.csv", raw), ("frame_metrics.csv", rows), ("video_summary.csv", videos)):
        write_csv(path.parent / filename, data)
    write_json(path.parent / "summary.json", summary)
    manifest = {**common, "stage": mode, "run_id": candidate["configuration_id"], "config": config,
                "summary": summary, "provenance_capture": capture}
    seal(path, manifest)
    return {"path": str(path), "sha256": digest(path)}, summary, manifest


@pytest.fixture
def synthetic_batch(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    plan, old_plan, _ = actual_plans_and_parent_parameters()
    source_plan = yaml.safe_load((qa.ROOT / plan["input"]["sample_plan"]).read_text(encoding="utf-8"))
    write_json(root / plan["input"]["sample_plan"], source_plan)
    cache_path = root / plan["input"]["cache_manifest"]
    cache = {"schema_version": 1, "kind": "canonical_training_detection_sample", "status": "complete",
             "plan_sha256": q.canonical_hash(source_plan), "video_ids": list(q.TRAIN), "sampling": source_plan["sampling"],
             "split": {"synthetic": True}, "audit": {"synthetic": True}, "selections": {}, "videos": {}, "frames": []}
    gt, master, smoke = [], [], []
    for video in q.TRAIN:
        cache["selections"][video] = {"master": list(range(48)), "coarse": list(range(0, 48, 4)), "benchmark": [24]}
        path = cache_path.parent / f"frames/{video}.npy"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic opaque cache, never decoded")
        cache["videos"][video] = {"array_path": f"frames/{video}.npy", "array_sha256": digest(path),
                                   "array_bytes": path.stat().st_size, "shape": [48, 480, 640, 3], "dtype": "uint8"}
        smoke.append((video, 24))
        for frame in range(48):
            master.append((video, frame))
            gt.extend(geometry(1, video, frame)[1])
            cache["frames"].append({"video_id": video, "frame": frame, "array_index": frame, "label": {"nonempty_lines": 3}})
    gt_path = cache_path.parent / "ground_truth.csv"
    write_csv(gt_path, gt)
    cache["ground_truth"] = {"path": "ground_truth.csv", "sha256": digest(gt_path), "rows": len(gt), "bytes": gt_path.stat().st_size}
    keys = ("schema_version", "plan_sha256", "split", "audit", "video_ids", "sampling", "selections", "videos", "ground_truth", "frames")
    cache["sample_hash"] = q.canonical_hash({key: cache[key] for key in keys})
    write_json(cache_path, cache)
    plan["input"].update(cache_manifest_sha256=digest(cache_path), sample_hash=cache["sample_hash"],
                         sample_plan_canonical_sha256=q.canonical_hash(source_plan))
    old_plan["input"] = copy.deepcopy(plan["input"])
    write_json(root / q.PLAN, old_plan)
    comparison_hash = q.canonical_hash(old_plan)
    monkeypatch.setattr(qa, "COMPARISON_CANONICAL_SHA256", comparison_hash)
    plan["parents"]["comparison_plan"] = {"path": q.PLAN, "canonical_sha256": comparison_hash}
    input_reference = {"sample_manifest_path": str(cache_path), "sample_manifest_sha256": digest(cache_path), "sample_hash": cache["sample_hash"]}
    historical_source = root / "src/synthetic_historical.py"
    historical_source.parent.mkdir(parents=True)
    historical_source.write_bytes(b"# synthetic source fingerprint\n")
    name = b"src/synthetic_historical.py"
    old_source_hash = hashlib.sha256(len(name).to_bytes(4, "big") + name + historical_source.read_bytes()).hexdigest()
    monkeypatch.setattr(qa.subprocess, "run", lambda *a, source_name=name, **kw: SimpleNamespace(stdout=source_name + b"\n"))
    common = {"status": "complete", "git_dirty": False, "git_sha": "b" * 40, "source_hash": old_source_hash,
              "seed": 42, "module": "detection", "environment": {"synthetic": True}}
    old_path = root / "synthetic/search_batch/manifest.json"
    old_path.parent.mkdir(parents=True)
    capture = {"mode": "shared_batch", "snapshot_sha256": "a" * 64, "process_id": 1, "captured_at": "2026-09-11",
               "recheck_policy": "batch_end_before_ranking", "origin_batch_manifest": str(old_path)}
    candidates = q.independent_candidates(old_plan)
    all_records, all_summaries = [], []
    for index, candidate in enumerate(candidates, 1):
        identifier = candidate["configuration_id"]
        extra = 1 + PARENT_IDS.index(identifier) % 2 if identifier in PARENT_IDS else 3
        reference, summary, _ = make_child(root, candidate, "search", old_plan, old_path, capture, common, input_reference, master, extra)
        all_records.append(reference)
        all_summaries.append(summary)
        write_json(old_path.parent / f"candidate_{index:03d}.json", summary)
    write_json(old_path.parent / "planned_candidates.json", candidates)
    write_json(old_path.parent / "planned_frames.json", master)
    write_csv(old_path.parent / "candidate_metrics.csv", all_summaries)
    ranked = qa.ranking(all_summaries)
    write_csv(old_path.parent / "ranking.csv", ranked)
    finalists = [r for family in q.FAMILIES for r in [row for row in ranked if row["family"] == family][:2]]
    finalists_path = write_json(old_path.parent / "family_finalists.json", finalists)
    old_summary = {"complete": True, "mode": "search", "completed_candidates": 43, "frames_per_candidate": 576,
                   "frame_evaluations": 24768, "selection_allowed": True, "promotion_allowed": False,
                   "validation_released": False, "plan_hash": comparison_hash, "sample_hash": cache["sample_hash"]}
    old_manifest = {**common, "stage": "search", "config": {"plan": old_plan}, "summary": old_summary,
                    "provenance_capture": capture, "candidate_manifests": all_records,
                    "provenance_verification": {"status": "verified", "scope": "batch_end_before_ranking", "snapshot_sha256": "a" * 64}}
    seal(old_path, old_manifest)
    old_files = {str(path): {"sha256": digest(path), "bytes": path.stat().st_size}
                 for path in (root / "synthetic").rglob("*") if path.is_file()}
    old_qa = {"status": "passed", "mode": "search", "manifest": str(old_path), "manifest_sha256": digest(old_path),
              "plan_hash": comparison_hash, "frame_evaluations": 24768, "new_detector_runs": 0,
              "comparisons": 100, "scipy_matchings": 148608, "files": old_files,
              "family_finalist_ids": [r["configuration_id"] for r in finalists]}
    old_qa_path = write_json(root / "synthetic/search_qa.json", old_qa)
    plan["parents"].update(search_manifest={"path": str(old_path), "sha256": digest(old_path)},
                           search_qa={"path": str(old_qa_path), "sha256": digest(old_qa_path)},
                           finalists={"path": str(finalists_path), "sha256": digest(finalists_path)})
    monkeypatch.setattr(qa, "SEARCH_SHA256", digest(old_path))
    monkeypatch.setattr(qa, "SEARCH_QA_SHA256", digest(old_qa_path))
    write_json(root / qa.PLAN, plan)
    monkeypatch.setattr(qa, "PLAN_CANONICAL_SHA256", q.canonical_hash(plan))
    audit = q.Audit()
    parents, history, _, authentication = qa.authenticated_parents(root, plan, audit)
    candidates, _ = qa.independent_neighborhood(plan, parents)
    batch_path = root / "synthetic/refinement_batch/manifest.json"
    batch_path.parent.mkdir(parents=True)
    capture = {**capture, "origin_batch_manifest": str(batch_path), "snapshot_sha256": "d" * 64}
    common = {**common, "source_hash": "c" * 64}
    records, summaries, parity, byte_count = [], [], [], 0
    for index, candidate in enumerate(candidates, 1):
        anchors = [o["parent_configuration_id"] for o in candidate["refinement_lineage"] if o["axis"] is None]
        extra = 1 + PARENT_IDS.index(anchors[0]) % 2 if anchors else 2
        reference, summary, _ = make_child(root, candidate, qa.MODES[0], plan, batch_path, capture, common, input_reference, smoke, extra)
        records.append(reference)
        summaries.append(summary)
        byte_count += sum(p.stat().st_size for p in Path(reference["path"]).parent.iterdir())
        write_json(batch_path.parent / f"candidate_{index:03d}.json", summary)
        for identifier in anchors:
            parent = next(p for p in parents if p["configuration_id"] == identifier)
            parity.append({"parent_configuration_id": identifier, "configuration_id": candidate["configuration_id"],
                           "parent_manifest": parent["parent_manifest"], "status": "passed", "frames_compared": 12,
                           "rows_compared": {"detections.csv": (6 + extra) * 12, "frame_metrics.csv": 12},
                           "excluded_fields": ["configuration_id", "detection_ms"], "absolute_tolerance": q.ATOL, "relative_tolerance": q.RTOL})
    for name, value in (("planned_candidates.json", candidates), ("planned_frames.json", smoke), ("parents.json", parents),
                        ("historical_reference.json", history), ("parent_authentication.json", authentication), ("parent_parity.json", parity)):
        write_json(batch_path.parent / name, value)
    write_csv(batch_path.parent / "candidate_metrics.csv", summaries)
    summary = {"complete": True, "mode": qa.MODES[0], "plan_hash": q.canonical_hash(plan), "sample_hash": cache["sample_hash"],
               "completed_candidates": 45, "frames_per_candidate": 12, "frame_evaluations": 540, "selection_allowed": False,
               "promotion_allowed": False, "validation_released": False, "historical_threshold_reference_reexecuted": False,
               "parent_parity_controls": 10, "wall_seconds_limit": None, "cache_validation_seconds": 0.1,
               "parent_validation_seconds": 0.1, "candidate_loop_seconds": 1.0, "ram_rss_peak_mb": 100.0,
               "resource_samples": 10, "candidate_artifact_bytes": byte_count}
    batch = {**common, "stage": qa.MODES[0], "config": {"plan": plan, "input": input_reference, "mode": qa.MODES[0],
                                                        "provenance": {"smoke": None, "smoke_qa": None}},
             "summary": summary, "candidate_manifests": records, "provenance_capture": capture,
             "provenance_verification": {"status": "verified", "scope": "batch_end_before_ranking", "snapshot_sha256": "d" * 64}}
    seal(batch_path, batch)
    return root, batch_path


def test_complete_synthetic_smoke_reconstructs_metrics_and_ten_parent_controls(synthetic_batch):
    root, path = synthetic_batch
    result = qa.verify_batch(path, root=root)
    assert result["status"] == "passed"
    assert result["scipy_matchings"] == 540 * 6
    assert result["parent_parity"]["controls"] == 10
    assert result["parent_parity"]["frames_per_control"] == 12
    assert result["historical_parent_qa_repeated"] is False
    assert result["historical_threshold_reference_reexecuted"] is False
    assert result["distance_tie_limits"] == []


@pytest.mark.parametrize("fault", ["hash", "fp", "ignored", "sensitivity", "secondary", "gt", "frame", "lineage", "parent", "parity", "plan", "missing", "rss", "history"])
def test_tampering_rejected_even_after_artifact_resealing(synthetic_batch, fault):
    root, path = synthetic_batch
    batch = json.loads(path.read_text())
    child_path = Path(batch["candidate_manifests"][0]["path"])
    child = json.loads(child_path.read_text())
    if fault == "hash":
        (child_path.parent / "frame_metrics.csv").write_bytes(b"forged")
    elif fault in {"fp", "ignored", "sensitivity", "secondary", "frame"}:
        file = child_path.parent / "frame_metrics.csv"
        rows = q.csv_rows(file.read_bytes())
        key = {"fp": "fp", "ignored": "n_predictions_ignored", "sensitivity": "f1_at_15px",
               "secondary": "secondary_all_objects_tp_at_20px", "frame": "frame"}[fault]
        rows[0][key] = "999"
        write_csv(file, rows)
        seal(child_path, child)
    elif fault == "gt":
        file = child_path.parent / "detections.csv"
        rows = q.csv_rows(file.read_bytes())
        next(r for r in rows if r["source"] == "manual")["object_id"] = "forged"
        write_csv(file, rows)
        seal(child_path, child)
    elif fault == "lineage":
        child["config"]["refinement_lineage"][0]["parent_configuration_id"] = "forged"
        seal(child_path, child)
    elif fault in {"parent", "parity", "history"}:
        filename = {"parent": "parents.json", "parity": "parent_parity.json", "history": "historical_reference.json"}[fault]
        value = json.loads((path.parent / filename).read_text())
        if isinstance(value, list):
            value.pop()
        else:
            value["reexecuted"] = True
        write_json(path.parent / filename, value)
    elif fault == "plan":
        batch["config"]["plan"]["evaluation"]["center_gate_px"] = 20
    elif fault == "missing":
        batch["candidate_manifests"].pop()
    elif fault == "rss":
        batch["summary"]["ram_rss_peak_mb"] = 2048.1
    if fault != "missing":
        batch["candidate_manifests"][0]["sha256"] = digest(child_path)
    seal(path, batch)
    with pytest.raises(q.VerificationError):
        qa.verify_batch(path, root=root)


@pytest.mark.parametrize("fault", [None, "order", "rank", "finalists", "threshold"])
def test_refinement_ranking_exact_quality_order_and_family_finalists(tmp_path, fault):
    summaries = [{"configuration_id": f"{family}_{i:03d}", "family": family, "macro_video_f1": 0.5 + i % 2 / 10,
                  "macro_video_recall": 0.8, "macro_video_count_mae": float(i), "detector_seconds": 100.0 - i}
                 for family, count in zip(qa.FAMILIES, qa.COUNTS) for i in range(count)]
    ranked = qa.ranking(summaries)
    finalists = [r for family in qa.FAMILIES for r in [row for row in ranked if row["family"] == family][:2]]
    if fault == "order":
        ranked[0], ranked[1] = ranked[1], ranked[0]
    elif fault == "rank":
        ranked[0]["rank"] = 999
    elif fault == "finalists":
        finalists.pop()
    elif fault == "threshold":
        summaries[0]["family"] = "threshold"
    write_csv(tmp_path / "ranking.csv", ranked)
    write_json(tmp_path / "family_finalists.json", finalists)
    files = {name: (tmp_path / name).read_bytes() for name in ("ranking.csv", "family_finalists.json")}
    if fault:
        with pytest.raises(q.VerificationError):
            qa.verify_ranking(files, summaries, q.Audit())
    else:
        assert len(qa.verify_ranking(files, summaries, q.Audit())) == 10


def test_verifier_has_no_production_imports():
    import ast
    tree = ast.parse(Path(qa.__file__).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert not any(name.startswith("src.") for name in imports)


def test_historical_source_inventory_accepts_new_files_but_rejects_changed_old_bytes(tmp_path, monkeypatch):
    path = tmp_path / "src/old.py"
    path.parent.mkdir()
    path.write_bytes(b"old content\r\n")
    (path.parent / "new.py").write_bytes(b"allowed new implementation")
    name = b"src/old.py"
    monkeypatch.setattr(qa.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=name + b"\n"))
    manifest = {"git_sha": "a" * 7, "source_hash": hashlib.sha256(len(name).to_bytes(4, "big") + name + path.read_bytes()).hexdigest()}
    assert qa.historical_sources(tmp_path, manifest, q.Audit()) == {str(path): digest(path)}
    path.write_bytes(b"old content\n")
    with pytest.raises(q.VerificationError, match="byte equivalence"):
        qa.historical_sources(tmp_path, manifest, q.Audit())


@pytest.mark.parametrize("field", ["evaluation", "sampling", "budget", "selection", "neighborhood", "input"])
def test_registered_plan_rejects_changes_even_with_same_path(tmp_path, field):
    plan, _, _ = actual_plans_and_parent_parameters()
    write_json(tmp_path / qa.PLAN, plan)
    assert qa.authenticated_plan(tmp_path, tmp_path / qa.PLAN, q.Audit()) == plan
    if isinstance(plan[field], dict):
        plan[field]["extra"] = True
    else:
        plan[field].append({"extra": True})
    write_json(tmp_path / qa.PLAN, plan)
    with pytest.raises(q.VerificationError, match="canonical hash"):
        qa.authenticated_plan(tmp_path, tmp_path / qa.PLAN, q.Audit())


def test_smoke_prerequisite_authenticates_qa_and_all_child_artifacts(synthetic_batch):
    root, path = synthetic_batch
    smoke = json.loads(path.read_text())
    plan = smoke["config"]["plan"]
    candidates = json.loads((path.parent / "planned_candidates.json").read_text())
    pairs = [tuple(pair) for pair in json.loads((path.parent / "planned_frames.json").read_text())]
    report = {"status": "passed", "mode": qa.MODES[0], "manifest": str(path), "manifest_sha256": digest(path),
              "plan_hash": q.canonical_hash(plan), "frame_evaluations": 540, "new_detector_runs": 0,
              "comparisons": 100, "scipy_matchings": 3240}
    report_path = write_json(root / "synthetic/smoke_qa.json", report)
    future_batch = {"source_hash": smoke["source_hash"], "config": {"provenance": {
        "smoke": {"path": str(path), "sha256": digest(path)},
        "smoke_qa": {"path": str(report_path), "sha256": digest(report_path)}}}}
    def verify():
        qa.smoke_prerequisite(root, future_batch, plan, candidates, smoke["config"]["input"], pairs, q.Audit())
    verify()
    for key, invalid in (("status", "failed"), ("frame_evaluations", True), ("mode", "smoke"),
                          ("manifest_sha256", "e" * 64), ("plan_hash", "e" * 64)):
        changed = {**report, key: invalid}
        write_json(report_path, changed)
        future_batch["config"]["provenance"]["smoke_qa"]["sha256"] = digest(report_path)
        with pytest.raises(q.VerificationError):
            verify()
    write_json(report_path, report)
    future_batch["config"]["provenance"]["smoke_qa"]["sha256"] = digest(report_path)
    child_path = Path(smoke["candidate_manifests"][0]["path"])
    (child_path.parent / "detections.csv").write_bytes(b"forged after approved QA")
    with pytest.raises(q.VerificationError, match="SHA256"):
        verify()
