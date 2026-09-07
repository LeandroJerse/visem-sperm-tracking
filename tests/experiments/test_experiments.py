from __future__ import annotations

import pytest

from src.experiments import runs as run_module
from src.experiments.protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_overrides,
    assert_protocol_access,
    assert_video_ids_in_split,
)
from src.experiments.resources import ResourceMonitor
from src.experiments.sampling import evenly_spaced_clips, evenly_spaced_indices
from src.experiments.sweep import deterministic_subset, parameter_grid


def test_even_frame_sampling_spans_the_available_sequence():
    assert evenly_spaced_indices(range(100), 5) == (0, 24, 49, 74, 99)
    assert evenly_spaced_indices([0, 1, 50], 9) == (0, 1, 50)


def test_stateful_clips_have_full_warmup_and_no_overrun():
    clips = evenly_spaced_clips(
        1000, count=3, evaluation_frames=200, warmup_frames=100
    )
    assert clips[0].warmup_start == 0
    assert clips[-1].evaluation_stop == 1000
    assert all(clip.warmup_frames == 100 for clip in clips)


def test_grid_and_subset_are_reproducible():
    grid = list(parameter_grid({"a": [1, 2], "b": ["x", "y"]}))
    assert grid[0] == {"a": 1, "b": "x"}
    assert deterministic_subset(grid, maximum=2, seed=42) == deterministic_subset(
        grid, maximum=2, seed=42
    )


def test_test_set_and_late_stages_require_frozen_configuration():
    assert_protocol_access(stage="validation", split="val", frozen=False)
    with pytest.raises(ProtocolViolation):
        assert_protocol_access(stage="search", split="test", frozen=False)
    with pytest.raises(ProtocolViolation):
        assert_protocol_access(stage="five_fold", split="A", frozen=False)
    with pytest.raises(ProtocolViolation):
        assert_protocol_access(stage="application", split="application", frozen=False)
    assert_protocol_access(stage="test", split="test", frozen=True)
    assert_protocol_access(stage="application", split="application", frozen=True)


@pytest.mark.parametrize("stage", ["five_fold", "oof", "cross-validation"])
@pytest.mark.parametrize("fold", ["A", "b", "E"])
def test_oof_folds_require_frozen_oof_stage(stage, fold):
    with pytest.raises(ProtocolViolation, match="congelada"):
        assert_protocol_access(stage=stage, split=fold, frozen=False)
    assert_protocol_access(stage=stage, split=fold, frozen=True)


@pytest.mark.parametrize("stage", ["smoke", "search", "refine", "validation", "test"])
def test_oof_folds_cannot_alias_development_or_validation(stage):
    with pytest.raises(ProtocolViolation, match="fold|Fold|split='test'"):
        assert_protocol_access(stage=stage, split="A", frozen=True)


@pytest.mark.parametrize("stage", ["search", "validation", "final", "oof"])
def test_test_split_has_exactly_one_legal_stage(stage):
    with pytest.raises(ProtocolViolation, match="só pode"):
        assert_protocol_access(stage=stage, split="test", frozen=True)


def test_oof_stage_requires_a_real_fold():
    with pytest.raises(ProtocolViolation, match="fold A-E"):
        assert_protocol_access(stage="oof", split="val", frozen=True)


@pytest.mark.parametrize(
    ("stage", "frozen"),
    [("search", False), ("search", True), ("validation", True), ("final", False)],
)
def test_all_alias_is_reserved_for_frozen_final(stage, frozen):
    with pytest.raises(ProtocolViolation, match="inclui o teste"):
        assert_protocol_access(stage=stage, split="all", frozen=frozen)
    assert_protocol_access(stage="final", split="all", frozen=True)


def test_application_stage_and_split_are_an_exact_pair():
    with pytest.raises(ProtocolViolation, match="só pode"):
        assert_protocol_access(stage="search", split="application", frozen=False)
    with pytest.raises(ProtocolViolation, match="deve registrar"):
        assert_protocol_access(stage="application", split="val", frozen=True)
    assert_protocol_access(stage="application", split="application", frozen=True)


def test_actual_video_ids_must_belong_to_declared_split():
    assert assert_video_ids_in_split([14, "52"], split="val") == ("14", "52")
    assert assert_video_ids_in_split([24, 38], split="A") == ("24", "38")
    with pytest.raises(ProtocolViolation, match="não pertencem"):
        assert_video_ids_in_split([24], split="train")
    # The 65 untracked application videos are not members of the annotated split.
    assert assert_video_ids_in_split(["65"], split="application") == ("65",)


def test_frozen_config_source_must_be_an_existing_yaml_below_promoted_root(tmp_path):
    promoted = tmp_path / "configs" / "frozen" / "detection" / "winner.yaml"
    promoted.parent.mkdir(parents=True)
    promoted.write_text("method: threshold\n", encoding="utf-8")
    outside = tmp_path / "configs" / "detection" / "candidate.yaml"
    outside.parent.mkdir(parents=True)
    outside.write_text("method: threshold\n", encoding="utf-8")

    assert assert_frozen_config_source(
        "configs/frozen/detection/winner.yaml", repo_root=tmp_path
    ) == promoted.resolve()
    with pytest.raises(ProtocolViolation, match="configs/frozen"):
        assert_frozen_config_source(outside, repo_root=tmp_path)
    with pytest.raises(ProtocolViolation, match="YAML existente"):
        assert_frozen_config_source(
            "configs/frozen/detection/missing.yaml", repo_root=tmp_path
        )


def test_frozen_overrides_allow_only_operational_fields():
    assert_frozen_overrides(
        [
            "run.stage=oof",
            "run.split=A",
            "run.seed=123",
            "input.video=11.mp4",
            "run.save_video=false",
        ]
    )
    with pytest.raises(ProtocolViolation, match="parâmetros científicos"):
        assert_frozen_overrides(["threshold_value=190"])
    with pytest.raises(ProtocolViolation, match="parâmetros científicos"):
        assert_frozen_overrides(["evaluation.center_gate_px=20"])


def test_resource_monitor_returns_machine_readable_cost_fields():
    monitor = ResourceMonitor()
    monitor.sample()
    summary = monitor.summary()
    assert summary["resource_samples"] >= 3
    assert summary["ram_rss_peak_mb"] is None or summary["ram_rss_peak_mb"] > 0


def test_run_context_routes_stage_and_uses_scientific_algorithm(tmp_path, monkeypatch):
    tests_root = tmp_path / "data" / "tests"
    results_root = tmp_path / "data" / "results"
    monkeypatch.setattr(run_module, "EXPERIMENT_TESTS_ROOT", tests_root)
    monkeypatch.setattr(run_module, "EXPERIMENT_RESULTS_ROOT", results_root)
    config = {
        "configuration_id": "otsu_search",
        "method": "threshold",
        "variant": "otsu",
        "params": {"threshold_value": None},
        "run": {"stage": "validation", "split": "val", "seed": 42},
    }

    validation = run_module.RunContext.create(
        module="detection",
        method="threshold",
        algorithm="otsu",
        stage="validation",
        seed=42,
        config=config,
        repo_root=tmp_path,
    )
    validation.complete()
    assert validation.storage_class == "tests"
    assert validation.algorithm == "otsu"
    assert validation.path.is_relative_to(tests_root / "detection" / "otsu")

    frozen = {
        **config,
        "run": {"stage": "test", "split": "test", "seed": 42, "frozen": True},
    }
    test_run = run_module.RunContext.create(
        module="detection",
        method="threshold",
        algorithm="otsu",
        stage="test",
        seed=42,
        config=frozen,
        repo_root=tmp_path,
    )
    test_run.complete()
    assert test_run.storage_class == "results"
    assert test_run.path.is_relative_to(results_root / "detection" / "otsu")


def test_scientific_configuration_groups_videos_but_not_algorithm_parameters():
    base = {
        "configuration_id": "kalman_eval",
        "method": "kalman",
        "params": {"process_noise": 0.1},
        "data": {
            "tracks_csv": "video_14.csv",
            "tracks_sha256": "a" * 64,
            "video_id": "14",
            "history_length": 20,
            "horizons": [1, 5, 10],
            "stride": 1,
        },
        "run": {
            "stage": "validation",
            "split": "val",
            "seed": 42,
            "cache": False,
        },
        "provenance": {"frozen_config_source": "candidate.yaml"},
    }
    other_video = {
        **base,
        "data": {
            **base["data"],
            "tracks_csv": "video_52.csv",
            "tracks_sha256": "b" * 64,
            "video_id": "52",
        },
        "run": {
            **base["run"],
            "stage": "test",
            "split": "test",
            "seed": 2026,
            "cache": True,
            "cache_dir": "machine-specific-cache",
        },
        "provenance": {"frozen_config_source": "frozen.yaml"},
    }
    changed_algorithm = {
        **other_video,
        "params": {"process_noise": 0.2},
    }

    assert run_module.configuration_hash(base) == run_module.configuration_hash(
        other_video
    )
    assert run_module.configuration_hash(base) != run_module.configuration_hash(
        changed_algorithm
    )
