from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.detection import pipeline, split_runner, yolo_evaluation
from src.experiments import protocol


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "REPOSITORY_ROOT", tmp_path)
    path = tmp_path / "configs/frozen/detection/baseline.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({
        "method": "threshold", "params": {"threshold_value": 218},
        "run": {"frozen": True, "stage": "development", "split": "train"},
        "freeze": {"scope": "development_only", "allowed_splits": ["train", "val"],
                   "confirmatory_plan": None},
    }), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("module_name", [
    "src.detection.pipeline", "src.tracking.pipeline", "src.flow.pipeline",
    "src.prediction.pipeline", "src.integration.enrich_tracks_with_flow",
])
@pytest.mark.parametrize("overrides", [
    ["--stage", "test", "--split", "test"],
    ["--set", "run.frozen=false"],
    ["--set", "freeze=null", "--set", "run.frozen=false"],
    ["--set", "freeze.scope=confirmation", "--stage", "test", "--split", "test"],
])
def test_original_scope_is_enforced_before_other_executor_inputs(baseline, module_name, overrides):
    # No input path is supplied. A missing method/CSV/video error would show
    # that the release guard ran too late or was bypassed by another executor.
    module = importlib.import_module(module_name)
    with pytest.raises(SystemExit, match="development_only"):
        module.main(["--config", baseline, *overrides])


def test_yolo_scope_is_checked_before_incompatible_method_or_weights(baseline):
    with pytest.raises(SystemExit, match="development_only"):
        yolo_evaluation.main([
            "--config", baseline, "--stage", "test", "--split", "test", "--frozen",
        ])


@pytest.mark.parametrize("flags", [
    ["--set", "threshold_value=200"],
    ["--set", "evaluation.center_gate_px=15"],
    ["--set", "freeze=null"],
    ["--method", "mog2"],
    ["--max-frames", "2"],
])
def test_development_scope_keeps_scientific_parameters_frozen(baseline, monkeypatch, flags):
    monkeypatch.setattr(pipeline, "_validate_video_against_split", lambda **kwargs: pytest.fail("input access"))
    with pytest.raises(SystemExit, match="congelada|protocol_id"):
        pipeline.main(["--config", baseline, "--video", "11.mp4", *flags])


def test_detection_cannot_replace_split_identity_via_dedicated_flag(baseline):
    with pytest.raises(SystemExit, match="trocar protocol.splits_config"):
        pipeline.main(["--config", baseline, "--splits-config", "relabelled_test.yaml"])


def test_detection_resolver_preserves_development_configuration(baseline):
    config = pipeline.resolve_cli_config(pipeline.parse_args(["--config", baseline]))
    assert config["params"] == {"threshold_value": 218}
    assert config["run"]["frozen"] is True
    assert config["run"]["stage"] == "development"
    assert config["run"]["split"] == "train"


@pytest.mark.parametrize("args", [
    ["--split", "test", "--frozen"],
    ["--split", "A", "--frozen"],
    ["--split", "all", "--stage", "final", "--frozen"],
    ["--split", "application", "--stage", "application", "--frozen"],
    ["--split", "train", "--stage", "development"],
    ["--split", "train", "--stage", "development", "--frozen", "--splits-config", "changed.yaml"],
])
def test_split_wrapper_rejects_scope_escape_before_split_or_input_read(baseline, monkeypatch, args):
    monkeypatch.setattr(split_runner, "load_split_spec", lambda *args: pytest.fail("split read"))
    monkeypatch.setattr(split_runner, "_video_paths", lambda *args: pytest.fail("video tree access"))
    with pytest.raises(SystemExit, match="development_only"):
        split_runner.main(["--config", baseline, *args])


def test_split_wrapper_allows_development_and_forwards_frozen_flag(baseline, monkeypatch):
    monkeypatch.setattr(split_runner, "load_split_spec", lambda *args: SimpleNamespace(ids_for=lambda split: ("11",)))
    monkeypatch.setattr(split_runner, "_video_paths", lambda root, video_id: (Path("11.mp4"), Path("labels")))
    calls = []
    monkeypatch.setattr(split_runner.detection_pipeline, "main", lambda argv: calls.append(argv) or {"ok": True})
    assert split_runner.main([
        "--config", baseline, "--split", "train", "--stage", "development", "--frozen",
    ]) == [{"ok": True}]
    assert "run.frozen=true" in calls[0]
    assert calls[0][calls[0].index("--split") + 1] == "train"
