"""Synthetic provenance checks: opt-in sharing never replaces final validation."""
from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError

import pytest

from src.experiments import runs


@pytest.fixture
def provenance(tmp_path, monkeypatch):
    state = {
        "git_sha": "1234567", "git_dirty": False, "source_hash": "source-before",
        "environment": {"python": "synthetic", "packages": {"numpy": "test-version"}},
    }
    calls = dict.fromkeys(state, 0)

    def read(key):
        calls[key] += 1
        return copy.deepcopy(state[key])

    monkeypatch.setattr(runs, "_git_sha", lambda _: read("git_sha"))
    monkeypatch.setattr(runs, "_git_dirty", lambda _: read("git_dirty"))
    monkeypatch.setattr(runs, "_source_hash", lambda _: read("source_hash"))
    monkeypatch.setattr(runs, "environment_snapshot", lambda: read("environment"))
    return tmp_path, state, calls


def create(root, **kwargs):
    return runs.RunContext.create(
        module="detection", method="threshold", stage="benchmark", seed=42,
        config={"params": {"threshold_value": 200}}, repo_root=root,
        output_root=root / "outputs", **kwargs,
    )


def test_one_capture_serves_batch_and_candidates_and_final_check_is_fresh(provenance):
    root, state, calls = provenance
    snapshot = runs.RunSnapshot.capture(root)
    capture_hash = snapshot.snapshot_hash
    batch = create(root, provenance_snapshot=snapshot)
    batch_manifest = batch.path / "manifest.json"
    children = []
    for index in range(5):
        child = create(root, provenance_snapshot=snapshot, snapshot_origin_batch_manifest=batch_manifest)
        children.append(child)
        if index == 4:
            child.fail(ValueError("synthetic candidate failure"))
        else:
            child.complete(summary={"synthetic": True})
        record = json.loads((child.path / "manifest.json").read_text())
        assert record["git_sha"] == snapshot.git_sha
        assert record["source_hash"] == snapshot.source_hash
        assert record["environment"] == state["environment"]
        capture = record["provenance_capture"]
        assert capture == {
            "mode": "shared_batch", "captured_at": snapshot.captured_at,
            "snapshot_sha256": capture_hash, "process_id": snapshot.process_id,
            "origin_batch_manifest": str(batch_manifest.resolve()),
            "per_candidate_recheck": False, "recheck_policy": "batch_end_before_ranking",
        }
        assert "provenance_verification" not in record
    assert len({child.run_id for child in children}) == 5
    assert calls == dict.fromkeys(calls, 1)
    verification = snapshot.verify_current()
    assert calls == dict.fromkeys(calls, 2)
    assert verification["status"] == "verified"
    assert verification["snapshot_sha256"] == capture_hash
    assert set(verification["checks"]) == set(state)
    assert verification["checked_at"] >= snapshot.captured_at
    batch.complete(provenance_verification=verification)
    assert calls == dict.fromkeys(calls, 2)
    record = json.loads(batch_manifest.read_text())
    assert record["provenance_capture"]["origin_batch_manifest"] == str(batch_manifest.resolve())
    assert record["provenance_verification"] == verification


def test_without_snapshot_existing_manifest_collection_behavior_is_unchanged(provenance):
    root, state, calls = provenance
    context = create(root)
    context.complete()
    assert calls == {"git_sha": 3, "git_dirty": 1, "source_hash": 1, "environment": 2}
    record = json.loads((context.path / "manifest.json").read_text())
    assert "provenance_capture" not in record
    assert record["environment"] == state["environment"]
    assert record["git_sha"] == state["git_sha"]


def test_shared_snapshot_does_not_change_scientific_configuration_identity(provenance):
    root, _, _ = provenance
    snapshot = runs.RunSnapshot.capture(root)
    shared = create(root, provenance_snapshot=snapshot)
    ordinary = create(root)
    assert shared.configuration_hash == ordinary.configuration_hash
    assert shared.configuration_id == ordinary.configuration_id
    assert shared.config == ordinary.config


def test_capture_and_returned_environment_are_isolated_from_mutation(provenance):
    root, state, _ = provenance
    snapshot = runs.RunSnapshot.capture(root)
    digest = snapshot.snapshot_hash
    state["environment"]["packages"]["numpy"] = "changed externally"
    snapshot.environment["packages"]["numpy"] = "changed by consumer"
    assert snapshot.environment["packages"]["numpy"] == "test-version"
    assert snapshot.snapshot_hash == digest
    with pytest.raises(FrozenInstanceError):
        snapshot.git_sha = "modified"


@pytest.mark.parametrize(("key", "value"), [
    ("git_sha", "nogit"), ("git_dirty", True), ("git_dirty", None),
])
def test_shared_capture_requires_available_clean_git(provenance, key, value):
    root, state, calls = provenance
    state[key] = value
    with pytest.raises(RuntimeError, match="clean Git"):
        runs.RunSnapshot.capture(root)
    assert calls["source_hash"] == calls["environment"] == 0
    assert not (root / "outputs").exists()


@pytest.mark.parametrize(("key", "value"), [
    ("git_sha", "7654321"), ("git_dirty", True), ("git_dirty", None),
    ("source_hash", "changed-source"), ("environment", {"packages": {"numpy": "changed"}}),
])
def test_final_verification_rejects_each_kind_of_provenance_drift(provenance, key, value):
    root, state, calls = provenance
    snapshot = runs.RunSnapshot.capture(root)
    digest = snapshot.snapshot_hash
    state[key] = value
    with pytest.raises(RuntimeError, match=key):
        snapshot.verify_current()
    assert calls == dict.fromkeys(calls, 2)
    assert snapshot.snapshot_hash == digest


@pytest.mark.parametrize("mismatch", ["repository", "process"])
def test_snapshot_cannot_be_reused_in_another_repository_or_process(provenance, monkeypatch, mismatch):
    root, _, _ = provenance
    snapshot = runs.RunSnapshot.capture(root)
    if mismatch == "repository":
        root = root / "other-repository"
    else:
        monkeypatch.setattr(runs.os, "getpid", lambda: snapshot.process_id + 1)
    with pytest.raises(ValueError, match="original repository and process"):
        create(root, provenance_snapshot=snapshot)
    assert not (root / "outputs").exists()


def test_origin_cannot_imply_sharing_without_an_explicit_snapshot(provenance):
    root, _, calls = provenance
    with pytest.raises(ValueError, match="explicit provenance_snapshot"):
        create(root, snapshot_origin_batch_manifest=root / "batch-manifest.json")
    assert calls == dict.fromkeys(calls, 0)
    assert not (root / "outputs").exists()
