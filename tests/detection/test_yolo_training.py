from __future__ import annotations

import builtins
import json
import sys
import types
from pathlib import Path

import pytest

from src.detection import yolo_training as train_yolo


def _mock_video_tree(root: Path, video_ids: tuple[str, ...]) -> None:
    for video_id in video_ids:
        images = root / video_id / "images"
        labels = root / video_id / "labels"
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        for frame in (0, 1):
            stem = f"{video_id}_frame_{frame}"
            (images / f"{stem}.jpg").write_bytes(b"mock-jpeg")
            (labels / f"{stem}.txt").write_text(
                "0 0.5 0.5 0.1 0.1\n", encoding="utf-8"
            )


def _ids_in_list(path: Path) -> set[str]:
    return {
        Path(line).parent.parent.name
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _mock_protocol(tmp_path: Path) -> tuple[Path, Path, Path]:
    train_root = tmp_path / "Train"
    _mock_video_tree(train_root, ("11", "12", "14", "24"))
    splits = tmp_path / "splits.yaml"
    splits.write_text(
        "seeds: [42, 123, 2026]\n"
        "fixed_split:\n"
        "  train: [11, 12]\n"
        "  val: [14]\n"
        "  test: [24]\n"
        "oof_folds:\n"
        "  A: [24]\n"
        "  B: [11]\n"
        "  C: [12]\n"
        "  D: [14]\n"
        "  E: []\n",
        encoding="utf-8",
    )
    return train_root, splits, tmp_path / "prepared"


def _fake_torch_module() -> types.ModuleType:
    module = types.ModuleType("torch")
    module.cuda = types.SimpleNamespace(is_available=lambda: False)
    return module


def test_prepare_only_uses_fixed_train_val_excludes_test_and_imports_no_ml(
    tmp_path, monkeypatch
):
    train_root = tmp_path / "Train"
    _mock_video_tree(train_root, ("11", "12", "14", "24"))
    splits = tmp_path / "splits.yaml"
    splits.write_text(
        "seeds: [42, 123, 2026]\n"
        "fixed_split:\n"
        "  train: [11, 12]\n"
        "  val: [14]\n"
        "  test: [24]\n"
        "oof_folds:\n"
        "  A: [24]\n"
        "  B: [11]\n"
        "  C: [12]\n"
        "  D: [14]\n"
        "  E: []\n",
        encoding="utf-8",
    )
    config = tmp_path / "yolo.yaml"
    config.write_text(
        "method: yolo\n"
        "training:\n"
        "  patience: 9\n"
        "  seeds: [42, 123, 2026]\n"
        "run:\n"
        "  seed: 123\n",
        encoding="utf-8",
    )
    dataset_dir = tmp_path / "prepared"

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "ultralytics"}:
            raise AssertionError(f"prepare-only tentou importar {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = train_yolo.main(
        [
            "--config", str(config),
            "--train-root", str(train_root),
            "--dataset-dir", str(dataset_dir),
            "--splits-config", str(splits),
            "--seed", "123",
            "--prepare-only",
            "--out-dir", str(tmp_path / "runs"),
        ]
    )

    assert result is None
    assert _ids_in_list(dataset_dir / "train.txt") == {"11", "12"}
    assert _ids_in_list(dataset_dir / "val.txt") == {"14"}
    assert _ids_in_list(dataset_dir / "test.txt") == {"24"}
    combined = (dataset_dir / "train.txt").read_text(encoding="utf-8") + (
        dataset_dir / "val.txt"
    ).read_text(encoding="utf-8")
    assert f"{Path('24')}/images" not in combined.replace("\\", "/")
    descriptor = (dataset_dir / "visem.yaml").read_text(encoding="utf-8")
    assert "test:" in descriptor
    assert not (tmp_path / "runs").exists()


def test_training_kwargs_forward_one_seed_and_patience_without_hidden_loop(tmp_path):
    config_path = tmp_path / "yolo.yaml"
    config_path.write_text(
        "method: yolo\n"
        "training:\n"
        "  epochs: 20\n"
        "  patience: 5\n"
        "  seeds: [42, 123, 2026]\n"
        "run:\n"
        "  seed: 42\n",
        encoding="utf-8",
    )
    args = train_yolo.parse_args(
        [
            "--config", str(config_path),
            "--seed", "2026",
            "--patience", "7",
            "--set", "epochs=3",
        ]
    )
    config = train_yolo.resolve_cli_config(args)
    kwargs = train_yolo._training_kwargs(
        config, yaml_path=tmp_path / "visem.yaml", seed=config["run"]["seed"], device="cpu"
    )

    assert kwargs["seed"] == 2026
    assert kwargs["patience"] == 7
    assert kwargs["epochs"] == 3
    assert "seeds" not in kwargs
    assert config["run"]["stage"] == "training"


def test_legacy_validation_flags_require_explicit_pilot_mode(tmp_path):
    with pytest.raises(SystemExit, match="piloto legado"):
        train_yolo.main(
            [
                "--train-root", str(tmp_path),
                "--val-frac", "0.25",
                "--prepare-only",
            ]
        )


def test_fake_training_creates_immutable_run_provenance_and_checkpoint_hashes(
    tmp_path, monkeypatch
):
    train_root, splits, dataset_dir = _mock_protocol(tmp_path)
    base_checkpoint = tmp_path / "base.pt"
    base_checkpoint.write_bytes(b"base-checkpoint")
    historical = tmp_path / "results" / "yolo"
    historical.mkdir(parents=True)
    marker = historical / "historical-run.txt"
    marker.write_text("do not mutate", encoding="utf-8")
    calls: list[dict] = []

    class FakeYOLO:
        def __init__(self, model):
            assert model == str(base_checkpoint)

        def train(self, **kwargs):
            calls.append(kwargs)
            save_dir = Path(kwargs["project"]) / kwargs["name"]
            (save_dir / "weights").mkdir(parents=True)
            (save_dir / "weights" / "best.pt").write_bytes(b"best-checkpoint")
            (save_dir / "weights" / "last.pt").write_bytes(b"last-checkpoint")
            (save_dir / "results.csv").write_text("epoch,metric\n0,0.1\n", encoding="utf-8")
            (save_dir / "args.yaml").write_text("seed: 42\n", encoding="utf-8")
            return types.SimpleNamespace(save_dir=save_dir)

    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "torch", _fake_torch_module())
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    argv = [
        "--train-root", str(train_root),
        "--dataset-dir", str(dataset_dir),
        "--splits-config", str(splits),
        "--model", str(base_checkpoint),
        "--project", str(historical),
        "--name", "ignored-folder-name",
        "--epochs", "3",
        "--patience", "2",
        "--seed", "42",
        "--stage", "search",
        "--out-dir", str(tmp_path / "runs"),
    ]
    first_best = train_yolo.main(argv)
    second_best = train_yolo.main(argv)

    assert first_best is not None and second_best is not None
    assert first_best != second_best
    assert first_best.read_bytes() == b"best-checkpoint"
    assert marker.read_text(encoding="utf-8") == "do not mutate"
    assert len(calls) == 2
    assert all(call["name"] == "ultralytics" for call in calls)
    assert all(call["exist_ok"] is False for call in calls)
    assert all(Path(call["project"]).is_relative_to(tmp_path / "runs") for call in calls)

    manifests = sorted((tmp_path / "runs").rglob("manifest.json"))
    assert len(manifests) == 2
    run_ids: set[str] = set()
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_ids.add(manifest["run_id"])
        assert manifest["status"] == "complete"
        assert manifest["module"] == "detection"
        assert manifest["method"] == "yolo_train"
        assert manifest["config"]["run"]["split"] == "train_val"
        assert manifest["config"]["run"]["seed"] == 42
        assert manifest["config"]["training"]["name"] == "ignored-folder-name"
        assert manifest["dataset"]["visem.yaml"]["sha256"]
        assert manifest["input_checkpoint"]["sha256"]
        assert manifest["output_checkpoints"]["best"]["sha256"]
        assert (manifest_path.parent / "dataset_definition" / "train.txt").is_file()
        summary = json.loads(
            (manifest_path.parent / "summary.json").read_text(encoding="utf-8")
        )
        assert summary["epochs_requested"] == 3
        assert summary["patience"] == 2
        assert summary["ram_rss_peak_mb"] is None or summary["ram_rss_peak_mb"] > 0
    assert len(run_ids) == 2


def test_fake_training_failure_marks_manifest_failed(tmp_path, monkeypatch):
    train_root, splits, dataset_dir = _mock_protocol(tmp_path)
    base_checkpoint = tmp_path / "base.pt"
    base_checkpoint.write_bytes(b"base")

    class FailingYOLO:
        def __init__(self, _model):
            pass

        def train(self, **_kwargs):
            raise RuntimeError("synthetic training failure")

    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = FailingYOLO
    monkeypatch.setitem(sys.modules, "torch", _fake_torch_module())
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    with pytest.raises(RuntimeError, match="synthetic training failure"):
        train_yolo.main(
            [
                "--train-root", str(train_root),
                "--dataset-dir", str(dataset_dir),
                "--splits-config", str(splits),
                "--model", str(base_checkpoint),
                "--out-dir", str(tmp_path / "runs"),
            ]
        )
    manifests = list((tmp_path / "runs").rglob("manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["stage"] == "training"
    assert "synthetic training failure" in manifest["error"]


def test_resume_is_blocked_to_preserve_historical_run(tmp_path):
    with pytest.raises(SystemExit, match="imutável"):
        train_yolo.main(["--resume", "--out-dir", str(tmp_path / "runs")])
    assert not (tmp_path / "runs").exists()
