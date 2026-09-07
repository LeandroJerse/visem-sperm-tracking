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


def test_new_detection_searches_share_the_approved_evaluation():
    from src.evaluation.detection import (
        DEFAULT_CENTER_GATE_PX, DEFAULT_SENSITIVITY_GATES_PX,
        DEFAULT_CLASS_POLICY, DEFAULT_EVALUATION_PROTOCOL_ID,
    )

    protocol = load_config(CONFIG_ROOT / "protocol" / "splits.yaml")["evaluation"]
    assert protocol["protocol_id"] == DEFAULT_EVALUATION_PROTOCOL_ID == "center_distance_v3_individuals_ignore_clusters_10px"
    assert protocol["primary_detection_metric"] == "f1_individuals_center_10px"
    assert protocol["class_policy"] == DEFAULT_CLASS_POLICY == "individuals_ignore_clusters"
    assert protocol["center_gate_px"] == DEFAULT_CENTER_GATE_PX == 10
    assert tuple(protocol["sensitivity_gates_px"]) == DEFAULT_SENSITIVITY_GATES_PX == (15, 20)
    searches = sorted((CONFIG_ROOT / "detection").rglob("search.yaml"))
    assert searches
    for path in searches:
        evaluation = load_config(path)["evaluation"]
        for key in ("protocol_id", "class_policy", "center_gate_px", "sensitivity_gates_px"):
            assert evaluation[key] == protocol[key], (path, key)


def test_named_historical_threshold_configs_keep_their_original_evaluation():
    for relative in (
        "detection/threshold/t190_o1_c1.yaml",
        "detection/threshold/t200_o1_c2.yaml",
        "frozen/detection/threshold/t200_o1_c2.yaml",
    ):
        evaluation = load_config(CONFIG_ROOT / relative)["evaluation"]
        assert evaluation["center_gate_px"] == 15
        assert evaluation["sensitivity_gates_px"] == [10, 20]
        assert evaluation["class_policy"] == "binary"
        assert evaluation.get("protocol_id") != "center_distance_v3_individuals_ignore_clusters_10px"


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
