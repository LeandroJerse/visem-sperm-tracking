from __future__ import annotations

import hashlib

import pytest
import yaml

from src.experiments import protocol


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "REPOSITORY_ROOT", tmp_path)
    path = tmp_path / "configs/frozen/detection/baseline.yaml"
    path.parent.mkdir(parents=True)
    raw = {
        "method": "threshold",
        "run": {"frozen": True, "stage": "development", "split": "train"},
        "freeze": {"scope": "development_only", "allowed_splits": ["train", "val"],
                   "confirmatory_plan": None},
    }
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path, raw


def check(path, stage="development", split="train", frozen=True, **kwargs):
    return protocol.assert_frozen_release(
        path, stage=stage, split=split, frozen=frozen, **kwargs
    )


@pytest.mark.parametrize("stage,split", [
    ("development", "train"), ("smoke", "train"), ("validation", "val"),
])
def test_development_release_allows_only_registered_pairs(source, stage, split):
    check(source[0], stage, split)


@pytest.mark.parametrize("stage,split", [
    ("test", "test"), ("final", "all"), ("application", "application"),
    *[(stage, fold) for stage in ("five_fold", "oof", "cross_validation") for fold in "ABCDE"],
    ("search", "train"), ("refine", "train"), ("development", "val"),
    ("validation", "train"), ("smoke", "val"), ("development", "unspecified"),
])
def test_development_release_does_not_authorize_other_stages(source, stage, split):
    with pytest.raises(protocol.ProtocolViolation, match="development_only"):
        check(source[0], stage, split)


@pytest.mark.parametrize("frozen", [False, None, 1, "true"])
def test_resolved_frozen_flag_cannot_be_disabled_or_coerced(source, frozen):
    with pytest.raises(protocol.ProtocolViolation, match="run.frozen=true"):
        check(source[0], frozen=frozen)


@pytest.mark.parametrize("raw_flag", [False, None, "true", 1])
def test_original_source_must_explicitly_be_frozen(source, raw_flag):
    path, raw = source
    raw["run"]["frozen"] = raw_flag
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(protocol.ProtocolViolation, match="run.frozen=true"):
        check(path)


@pytest.mark.parametrize("block", [
    None, {}, {"scope": "confirmation"},
    {"scope": "development_only", "allowed_splits": ["train", "val"], "confirmatory_plan": "test.yaml"},
    {"scope": "development_only", "allowed_splits": ["train", "test"], "confirmatory_plan": None},
    {"scope": "development_only", "allowed_splits": ["train", "train"], "confirmatory_plan": None},
    {"scope": "development_only", "allowed_splits": [], "confirmatory_plan": None},
    {"scope": "development_only", "allowed_splits": "train", "confirmatory_plan": None},
    {"scope": "development_only", "allowed_splits": ["train"], "confirmatory_plan": None, "allow_test": True},
])
def test_malformed_or_broadened_scope_fails_closed(source, block):
    path, raw = source
    raw["freeze"] = block
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(protocol.ProtocolViolation):
        check(path)


def test_source_must_be_inside_frozen_directory(source, tmp_path):
    outside = tmp_path / "candidate.yaml"
    outside.write_bytes(source[0].read_bytes())
    with pytest.raises(protocol.ProtocolViolation, match="configs/frozen"):
        check(outside)


def test_allowed_subset_is_enforced(source):
    path, raw = source
    raw["freeze"]["allowed_splits"] = ["train"]
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(protocol.ProtocolViolation, match="development_only"):
        check(path, "validation", "val")


def test_split_identity_and_registered_content_cannot_be_replaced(source, tmp_path):
    path, raw = source
    split_path = tmp_path / "configs/protocol/splits.yaml"
    split_path.parent.mkdir(parents=True)
    split_path.write_text("train: [11]\nval: [14]\n", encoding="utf-8")
    raw["protocol"] = {
        "splits_config": "configs/protocol/splits.yaml",
        "splits_sha256": hashlib.sha256(split_path.read_bytes()).hexdigest(),
    }
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    check(path, splits_config=split_path)
    with pytest.raises(protocol.ProtocolViolation, match="trocar"):
        check(path, splits_config=tmp_path / "renamed_test_as_train.yaml")
    split_path.write_text("train: [24]\nval: [14]\n", encoding="utf-8")
    with pytest.raises(protocol.ProtocolViolation, match="hash"):
        check(path)


def test_legacy_source_without_scope_is_unchanged(source):
    path, raw = source
    del raw["freeze"]
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    check(path, "test", "test")
    check(path, "five_fold", "B")
    check(path, frozen=False)
    check(None, frozen=False)
