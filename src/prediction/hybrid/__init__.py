"""Preditores híbridos que combinam movimento próprio e fluxo aparente."""

from .constant_velocity_with_flow import FlowAwareConstantVelocityPredictor
from .kalman_with_flow import FlowAwareKalmanPredictor
from .lstm_with_flow import FlowAwareLSTMPredictor
from .particle_filter_with_flow import FlowAwareParticleFilterPredictor

__all__ = [
    "FlowAwareConstantVelocityPredictor",
    "FlowAwareKalmanPredictor",
    "FlowAwareLSTMPredictor",
    "FlowAwareParticleFilterPredictor",
]
