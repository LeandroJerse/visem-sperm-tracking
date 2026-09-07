from __future__ import annotations

import builtins
import csv
import importlib
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest


def test_evaluate_yolo_module_import_is_neural_lazy(monkeypatch):
    sys.modules.pop("src.detection.yolo_evaluation", None)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "ultralytics"}:
            raise AssertionError(f"import antecipado de dependência neural: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module = importlib.import_module("src.detection.yolo_evaluation")
    assert callable(module.main)


def test_evaluate_yolo_blocks_test_before_files_or_neural_import(tmp_path, monkeypatch):
    from src.detection import yolo_evaluation as evaluate_yolo

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "ultralytics"}:
            raise AssertionError(f"guard deveria ocorrer antes de importar {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit, match="(?i)congel"):
        evaluate_yolo.main(
            [
                "--weights", str(tmp_path / "missing.pt"),
                "--data", str(tmp_path / "missing.yaml"),
                "--stage", "test",
                "--split", "test",
                "--out-dir", str(tmp_path / "runs"),
            ]
        )
    assert not (tmp_path / "runs").exists()


def test_evaluate_yolo_fake_val_records_global_and_per_class_metrics(
    tmp_path, monkeypatch
):
    from src.detection import yolo_evaluation as evaluate_yolo

    weights = tmp_path / "best.pt"
    weights.write_bytes(b"frozen-weights")
    data = tmp_path / "visem.yaml"
    data.write_text("test: test.txt\nnames: {0: normal, 1: cluster, 2: pinhead}\n", encoding="utf-8")
    frozen_config = (
        tmp_path / "configs" / "frozen" / "detection" / "yolo" / "winner.yaml"
    )
    frozen_config.parent.mkdir(parents=True)
    frozen_config.write_text(
        "method: yolo\n"
        "input:\n"
        f"  weights: '{weights.as_posix()}'\n"
        f"  data: '{data.as_posix()}'\n"
        "evaluation:\n"
        "  imgsz: 320\n"
        "  batch: 4\n"
        "  nms_iou: 0.55\n"
        "run:\n"
        "  stage: test\n"
        "  split: test\n"
        "  seed: 42\n"
        "  frozen: true\n",
        encoding="utf-8",
    )
    real_source_guard = evaluate_yolo.assert_frozen_config_source
    monkeypatch.setattr(
        evaluate_yolo,
        "assert_frozen_config_source",
        lambda path: real_source_guard(path, repo_root=tmp_path),
    )
    calls: list[dict] = []

    class FakeBoxMetrics:
        mp = 0.61
        mr = 0.72
        map50 = 0.81
        map = 0.57
        ap_class_index = np.asarray([0, 2])
        p = np.asarray([0.70, 0.52])
        r = np.asarray([0.80, 0.48])
        ap50 = np.asarray([0.90, 0.60])
        ap = np.asarray([[0.70, 0.60, 0.50], [0.45, 0.35, 0.25]])

    class FakeMetrics:
        box = FakeBoxMetrics()
        fitness = 0.54
        results_dict = {}

    class FakeYOLO:
        names = {0: "normal", 1: "cluster", 2: "pinhead"}

        def __init__(self, path):
            assert path == str(weights.resolve())

        def val(self, **kwargs):
            calls.append(kwargs)
            (Path(kwargs["project"]) / kwargs["name"]).mkdir()
            return FakeMetrics()

    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    summary = evaluate_yolo.main(
        [
            "--config", str(frozen_config),
            "--stage", "test",
            "--split", "test",
            "--seed", "2026",
            "--frozen",
            "--out-dir", str(tmp_path / "runs"),
        ]
    )

    assert summary["map50"] == pytest.approx(0.81)
    assert summary["map50_95"] == pytest.approx(0.57)
    assert summary["classes_reported"] == 2
    assert summary["metric_scope"] == "secondary_iou_map_not_primary_center_f1"
    assert calls[0]["split"] == "test"
    assert calls[0]["seed"] == 2026
    assert calls[0]["imgsz"] == 320
    assert calls[0]["batch"] == 4
    assert calls[0]["iou"] == pytest.approx(0.55)

    manifests = list((tmp_path / "runs").rglob("manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["config"]["run"] == {
        "stage": "test", "split": "test", "seed": 2026, "frozen": True
    }
    assert manifest["config"]["input"]["weights_sha256"]
    with (manifests[0].parent / "metrics_per_class.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert [row["class_name"] for row in rows] == ["normal", "pinhead"]
    assert float(rows[0]["map50_95"]) == pytest.approx(0.60)
    assert float(rows[1]["map50_95"]) == pytest.approx(0.35)


def test_evaluate_yolo_frozen_rejects_scientific_cli_override_before_import(
    tmp_path, monkeypatch
):
    from src.detection import yolo_evaluation as evaluate_yolo

    config = tmp_path / "configs" / "frozen" / "detection" / "yolo" / "winner.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "method: yolo\n"
        "input: {weights: missing.pt, data: missing.yaml}\n"
        "run: {stage: test, split: test, frozen: true}\n",
        encoding="utf-8",
    )
    real_source_guard = evaluate_yolo.assert_frozen_config_source
    monkeypatch.setattr(
        evaluate_yolo,
        "assert_frozen_config_source",
        lambda path: real_source_guard(path, repo_root=tmp_path),
    )
    with pytest.raises(SystemExit, match="parâmetros científicos via CLI"):
        evaluate_yolo.main(
            [
                "--config", str(config),
                "--frozen",
                "--conf", "0.2",
                "--out-dir", str(tmp_path / "runs"),
            ]
        )
    assert not (tmp_path / "runs").exists()
