"""Deterministic synthetic tests for video-level statistics and Pareto fronts."""
from __future__ import annotations

import math

import pytest

from src.evaluation.pareto import Objective, dominates, pareto_frontier
from src.evaluation.statistics import (
    VideoMetric,
    aggregate_seeds_by_video,
    friedman_test,
    holm_correction,
    paired_bootstrap_ci,
    paired_difference,
    pairwise_wilcoxon_holm,
    wilcoxon_paired,
)


def test_seed_aggregation_is_per_video_and_reports_nonfinite_values():
    rows = [
        VideoMetric("v1", "A", 1.0, 42),
        VideoMetric("v1", "A", 3.0, 123),
        VideoMetric("v1", "B", math.nan, 42),
        VideoMetric("v1", "B", 4.0, 123),
        VideoMetric("v2", "C", math.nan, 42),
    ]
    result = aggregate_seeds_by_video(rows, nan_policy="omit")
    values = {(item.video_id, item.method): item.value for item in result.metrics}
    assert values == {("v1", "A"): 2.0, ("v1", "B"): 4.0}
    assert len(result.dropped_nonfinite) == 2
    assert result.dropped_groups == (("v2", "C"),)

    with pytest.raises(ValueError, match="Non-finite"):
        aggregate_seeds_by_video(rows, nan_policy="raise")
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_seeds_by_video(
            [VideoMetric("v1", "A", 1, 42), VideoMetric("v1", "A", 2, 42)]
        )
    with pytest.raises(ValueError, match="video_id"):
        aggregate_seeds_by_video([{"method": "A", "value": 1.0}])


def _ordered_three_method_rows() -> list[VideoMetric]:
    rows: list[VideoMetric] = []
    for video in range(1, 9):
        for method, base in (("A", 10.0 + video), ("B", 5.0 + video), ("C", video)):
            rows.append(VideoMetric(f"v{video}", method, base - 0.1, 42))
            rows.append(VideoMetric(f"v{video}", method, base + 0.1, 123))
    # An explicitly unpaired video must be reported and removed as one block.
    rows.extend(
        [VideoMetric("v9", "A", 19.0, 42), VideoMetric("v9", "A", 19.0, 123)]
    )
    return rows


def test_friedman_and_wilcoxon_pair_strictly_by_video_after_seed_aggregation():
    rows = _ordered_three_method_rows()
    friedman = friedman_test(rows)
    assert friedman.n_videos == 8
    assert friedman.pvalue < 0.001
    assert friedman.pairing.video_ids == tuple(f"v{i}" for i in range(1, 9))
    assert friedman.pairing.excluded_videos[0].video_id == "v9"
    assert friedman.pairing.excluded_videos[0].missing_methods == ("B", "C")

    paired = paired_difference(rows, "A", "B")
    assert paired.differences == (5.0,) * 8
    assert paired.mean_difference == 5.0
    wilcoxon = wilcoxon_paired(rows, "A", "B")
    assert wilcoxon.n_videos == 8
    assert wilcoxon.pvalue == pytest.approx(0.0078125)
    assert wilcoxon.mean_difference == 5.0

    with pytest.raises(ValueError, match="Unpaired video IDs"):
        friedman_test(rows, unmatched_policy="raise")


def test_holm_adjustment_and_pairwise_posthoc_are_deterministic():
    correction = holm_correction([0.01, 0.04, 0.03], alpha=0.05)
    assert correction.adjusted_pvalues == pytest.approx((0.03, 0.06, 0.06))
    assert correction.reject == (True, False, False)

    table = pairwise_wilcoxon_holm(_ordered_three_method_rows())
    assert [(item.method_a, item.method_b) for item in table.comparisons] == [
        ("A", "B"),
        ("A", "C"),
        ("B", "C"),
    ]
    assert all(item.n_videos == 8 for item in table.comparisons)
    assert all(item.holm_pvalue >= item.raw_pvalue for item in table.comparisons)
    assert all(item.reject for item in table.comparisons)


def test_clustered_video_bootstrap_aggregates_seeds_and_repeats_with_seed():
    rows: list[VideoMetric] = []
    for video, difference in enumerate((1.0, 2.0, 3.0, 4.0, 5.0), start=1):
        rows.extend(
            [
                VideoMetric(str(video), "A", difference - 0.2, 42),
                VideoMetric(str(video), "A", difference + 0.2, 123),
                VideoMetric(str(video), "B", 0.0, 42),
                VideoMetric(str(video), "B", 0.0, 123),
            ]
        )
    first = paired_bootstrap_ci(
        rows, "A", "B", n_resamples=4_000, seed=2026
    )
    second = paired_bootstrap_ci(
        rows, "A", "B", n_resamples=4_000, seed=2026
    )
    assert first == second
    assert first.estimate == pytest.approx(3.0)
    assert first.n_videos == 5  # seeds did not become pseudo-replicates
    assert first.lower < first.estimate < first.upper
    assert first.confidence == 0.95


def test_nan_and_unpaired_ids_are_never_silently_used_as_pairs():
    rows = [
        VideoMetric("v1", "A", 2.0, 42),
        VideoMetric("v1", "B", 1.0, 42),
        VideoMetric("v2", "A", math.nan, 42),
        VideoMetric("v2", "B", 1.0, 42),
    ]
    paired = paired_difference(rows, "A", "B", nan_policy="omit")
    assert paired.pairing.video_ids == ("v1",)
    assert paired.pairing.excluded_videos[0].video_id == "v2"
    assert paired.pairing.dropped_groups == (("v2", "A"),)
    assert len(paired.pairing.dropped_nonfinite) == 1
    with pytest.raises(ValueError, match="Unpaired video IDs"):
        paired_difference(rows, "A", "B", unmatched_policy="raise")

    equal = [
        VideoMetric("v1", "A", 1),
        VideoMetric("v1", "B", 1),
        VideoMetric("v2", "A", 2),
        VideoMetric("v2", "B", 2),
    ]
    result = wilcoxon_paired(equal, "A", "B")
    assert result.pvalue == 1.0
    assert result.status == "all_differences_zero"


def test_pareto_mixed_directions_dominance_ties_and_nan_policy():
    objectives = {
        "quality": "max",
        "latency_ms": "min",
        "complexity": "min",
    }
    records = [
        {"method": "A", "quality": 0.90, "latency_ms": 10, "complexity": 2},
        {"method": "B", "quality": 0.80, "latency_ms": 12, "complexity": 3},
        {"method": "C", "quality": 0.95, "latency_ms": 20, "complexity": 4},
        {"method": "D", "quality": 0.70, "latency_ms": 5, "complexity": 1},
        {"method": "E", "quality": 0.90, "latency_ms": 10, "complexity": 2},
        {"method": "bad", "quality": math.nan, "latency_ms": 1, "complexity": 1},
    ]
    assert dominates(records[0], records[1], objectives)
    assert not dominates(records[0], records[2], objectives)

    result = pareto_frontier(records, objectives, nan_policy="drop")
    assert result.frontier_ids == ("A", "C", "D", "E")
    assert result.excluded_nonfinite == ("bad",)
    dominated = {item.identifier: item.dominators for item in result.dominated}
    assert dominated == {"B": ("A", "E")}
    assert [objective.direction for objective in result.objectives] == [
        "max",
        "min",
        "min",
    ]

    with pytest.raises(ValueError, match="non-finite"):
        pareto_frontier(records, objectives, nan_policy="raise")


def test_pareto_rejects_ambiguous_schema_instead_of_building_a_score():
    with pytest.raises(ValueError, match="direction"):
        pareto_frontier(
            [{"method": "A", "quality": 1.0}],
            [Objective("quality", "higher")],  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="Duplicate"):
        pareto_frontier(
            [
                {"method": "A", "quality": 1.0},
                {"method": "A", "quality": 2.0},
            ],
            {"quality": "max"},
        )
