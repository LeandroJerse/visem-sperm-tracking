from __future__ import annotations

from pathlib import Path

import pytest

from src.detection.registry import build_detector
from src.experiments.config import load_config
from src.flow import create_flow_estimator
from src.prediction import create_predictor
from src.tracking import create_tracker


CONFIG_ROOT = Path("configs")


def test_every_yaml_configuration_is_a_mapping_with_a_method():
    files = sorted(CONFIG_ROOT.rglob("*.yaml"))
    assert files
    for path in files:
        config = load_config(path)
        if path.name != "splits.yaml":
            assert config.get("method"), path
            assert isinstance(config.get("params", {}), dict), path


@pytest.mark.parametrize(
    "relative_path",
    [
        "threshold/t200_o1_c2.yaml",
        "threshold/t190_o1_c1.yaml",
        "otsu/search.yaml",
        "adaptive_threshold/search.yaml",
        "hybrid_threshold/search.yaml",
        "blob/search.yaml",
        "mog2/search.yaml",
        "knn/search.yaml",
        "watershed/search.yaml",
    ],
)
def test_classical_detection_configs_instantiate(relative_path):
    config = load_config(CONFIG_ROOT / "detection" / relative_path)
    detector = build_detector(config["method"], params=config.get("params"))
    assert detector.name


@pytest.mark.parametrize("path", sorted((CONFIG_ROOT / "tracking").rglob("*.yaml")))
def test_tracking_configs_instantiate(path):
    config = load_config(path)
    assert create_tracker(config["method"], **config.get("params", {})).name


@pytest.mark.parametrize(
    "relative_path",
    [
        "lucas_kanade/search.yaml",
        "farneback/search.yaml",
        "horn_schunck/search.yaml",
        "robust_hybrid/search.yaml",
    ],
)
def test_non_neural_flow_configs_instantiate(relative_path):
    config = load_config(CONFIG_ROOT / "flow" / relative_path)
    assert create_flow_estimator(config["method"], **config.get("params", {})).name


@pytest.mark.parametrize("path", sorted((CONFIG_ROOT / "prediction").rglob("*.yaml")))
def test_prediction_configs_instantiate_without_loading_torch(path):
    config = load_config(path)
    predictor = create_predictor(config["method"], **config.get("params", {}))
    assert predictor.name
