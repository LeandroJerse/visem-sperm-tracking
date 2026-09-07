"""Registry and factory for trajectory predictors."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .base import TrajectoryPredictor
from .classical.constant_velocity import ConstantVelocityPredictor
from .classical.kalman import KalmanPredictor
from .classical.particle_filter import ParticleFilterPredictor
from .classical.persistence import PersistencePredictor
from .hybrid import (
    FlowAwareConstantVelocityPredictor,
    FlowAwareKalmanPredictor,
    FlowAwareLSTMPredictor,
    FlowAwareParticleFilterPredictor,
)
from .learned.lstm import LSTMPredictor


PREDICTORS: Mapping[str, Callable[..., TrajectoryPredictor]] = {
    "persistence": PersistencePredictor,
    "constant_velocity": ConstantVelocityPredictor,
    "flow_aware_constant_velocity": FlowAwareConstantVelocityPredictor,
    "kalman": KalmanPredictor,
    "flow_aware_kalman": FlowAwareKalmanPredictor,
    "particle_filter": ParticleFilterPredictor,
    "flow_aware_particle_filter": FlowAwareParticleFilterPredictor,
    "lstm": LSTMPredictor,
    "flow_aware_lstm": FlowAwareLSTMPredictor,
}


def create_predictor(name: str, **parameters: Any) -> TrajectoryPredictor:
    key = name.strip().lower().replace("-", "_")
    try:
        constructor = PREDICTORS[key]
    except KeyError as exc:
        available = ", ".join(sorted(PREDICTORS))
        raise ValueError(f"unknown predictor '{name}'; available: {available}") from exc
    return constructor(**parameters)
