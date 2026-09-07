"""Optical flow baselines, robust hybrids, cache, and evaluation utilities.

All heavy dependencies are lazy.  Importing this package only requires NumPy;
OpenCV is checked when LK/Farneback/global compensation is executed and PyTorch
is checked only when RAFT is executed.
"""
from .base import FlowEstimator, FlowResult, OptionalDependencyError
from .cache import (
    FlowCache,
    SampledFlow,
    load_flow_file,
    make_cache_key,
    sample_background_flow,
    sample_flow,
    sample_trajectory_features,
)
from .classical import FarnebackFlow, HornSchunckFlow, LucasKanadeFlow
from .hybrid import GlobalMotion, RobustHybridFlow, estimate_global_motion
from .metrics import (
    ConsistencyResult,
    endpoint_error,
    evaluate_flow_pair,
    forward_backward_consistency,
    photometric_warp_error,
    sample_field,
    temporal_flow_change,
    warp_next_to_previous,
)
from .learned import RAFTFlow
from .registry import FLOW_ESTIMATORS, create_flow_estimator
from .synthetic import constant_translation_flow, translate_frame, translation_case

__all__ = [
    "ConsistencyResult",
    "FLOW_ESTIMATORS",
    "FarnebackFlow",
    "FlowCache",
    "FlowEstimator",
    "FlowResult",
    "GlobalMotion",
    "HornSchunckFlow",
    "LucasKanadeFlow",
    "OptionalDependencyError",
    "RAFTFlow",
    "RobustHybridFlow",
    "SampledFlow",
    "create_flow_estimator",
    "constant_translation_flow",
    "endpoint_error",
    "estimate_global_motion",
    "evaluate_flow_pair",
    "forward_backward_consistency",
    "make_cache_key",
    "load_flow_file",
    "photometric_warp_error",
    "sample_background_flow",
    "sample_field",
    "sample_flow",
    "sample_trajectory_features",
    "temporal_flow_change",
    "translate_frame",
    "translation_case",
    "warp_next_to_previous",
]
