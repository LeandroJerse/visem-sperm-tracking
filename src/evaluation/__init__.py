"""Evaluation utilities shared by the experimental pipelines.

The detection evaluator intentionally has no SciPy dependency at import time.
It contains a small O(n^3) Hungarian implementation so the official matching
policy is also available in lightweight environments.
"""

from .detection import (
    DEFAULT_CENTER_GATE_PX,
    DetectionEvaluator,
    DetectionMatch,
    MatchingResult,
    aggregate_by_video,
    aggregate_frame_metrics,
    evaluate_frame,
    hungarian_match,
    match_detections,
    write_frame_metrics_csv,
)
from .pareto import Objective, dominates, pareto_frontier
from .statistics import (
    VideoMetric,
    aggregate_seeds_by_video,
    friedman_test,
    holm_correction,
    paired_bootstrap_ci,
    paired_difference,
    pairwise_wilcoxon_holm,
    wilcoxon_paired,
)
from .tracking import TrackEvalHOTAAdapter

__all__ = [
    "DEFAULT_CENTER_GATE_PX",
    "DetectionEvaluator",
    "DetectionMatch",
    "MatchingResult",
    "aggregate_by_video",
    "aggregate_frame_metrics",
    "evaluate_frame",
    "hungarian_match",
    "match_detections",
    "write_frame_metrics_csv",
    "Objective",
    "dominates",
    "pareto_frontier",
    "VideoMetric",
    "aggregate_seeds_by_video",
    "friedman_test",
    "holm_correction",
    "paired_bootstrap_ci",
    "paired_difference",
    "pairwise_wilcoxon_holm",
    "wilcoxon_paired",
    "TrackEvalHOTAAdapter",
]
