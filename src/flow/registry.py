"""Registry and factory for optical-flow estimators."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .base import FlowEstimator
from .classical import FarnebackFlow, HornSchunckFlow, LucasKanadeFlow
from .hybrid import RobustHybridFlow
from .learned import RAFTFlow


FLOW_ESTIMATORS: Mapping[str, Callable[..., FlowEstimator]] = {
    "lucas_kanade": LucasKanadeFlow,
    "lk": LucasKanadeFlow,
    "farneback": FarnebackFlow,
    "horn_schunck": HornSchunckFlow,
    "hs": HornSchunckFlow,
    "raft": RAFTFlow,
    "robust_hybrid": RobustHybridFlow,
}


def create_flow_estimator(name: str, **parameters: Any) -> FlowEstimator:
    """Instantiate a registered estimator by a case-insensitive name."""

    key = name.strip().lower().replace("-", "_")
    try:
        constructor = FLOW_ESTIMATORS[key]
    except KeyError as exc:
        available = ", ".join(sorted(set(FLOW_ESTIMATORS)))
        raise ValueError(f"unknown flow estimator '{name}'; available: {available}") from exc
    return constructor(**parameters)
