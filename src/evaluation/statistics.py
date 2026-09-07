"""Video-level paired statistics for reproducible algorithm comparisons.

Frames and trajectories are intentionally not accepted as independent units.
Callers provide one metric observation per ``video_id/method/seed``; seeds are
first aggregated within a video, and every inferential test then pairs methods
by video ID.
"""
from __future__ import annotations

import itertools
import math
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


NanPolicy = Literal["omit", "raise"]
UnmatchedPolicy = Literal["drop", "raise"]
Reducer = Literal["mean", "median"]


@dataclass(frozen=True)
class VideoMetric:
    """One video-level metric, optionally for one stochastic seed."""

    video_id: str
    method: str
    value: float
    seed: int | str | None = None


@dataclass(frozen=True)
class AggregatedVideoMetric:
    """One method value per video after equal-weight seed aggregation."""

    video_id: str
    method: str
    value: float
    n_seeds: int
    seeds: tuple[int | str | None, ...]


@dataclass(frozen=True)
class SeedAggregationResult:
    metrics: tuple[AggregatedVideoMetric, ...]
    reducer: Reducer
    dropped_nonfinite: tuple[VideoMetric, ...]
    dropped_groups: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExcludedVideo:
    video_id: str
    missing_methods: tuple[str, ...]


@dataclass(frozen=True)
class PairingReport:
    methods: tuple[str, ...]
    video_ids: tuple[str, ...]
    excluded_videos: tuple[ExcludedVideo, ...]
    dropped_nonfinite: tuple[VideoMetric, ...] = ()
    dropped_groups: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FriedmanResult:
    statistic: float
    pvalue: float
    n_videos: int
    pairing: PairingReport
    status: str = "ok"


@dataclass(frozen=True)
class PairedDifferenceResult:
    method_a: str
    method_b: str
    differences: tuple[float, ...]
    mean_difference: float
    median_difference: float
    pairing: PairingReport


@dataclass(frozen=True)
class WilcoxonResult:
    method_a: str
    method_b: str
    statistic: float
    pvalue: float
    alternative: str
    n_videos: int
    mean_difference: float
    median_difference: float
    pairing: PairingReport
    status: str = "ok"


@dataclass(frozen=True)
class HolmCorrection:
    raw_pvalues: tuple[float, ...]
    adjusted_pvalues: tuple[float, ...]
    reject: tuple[bool, ...]
    alpha: float


@dataclass(frozen=True)
class PairwiseWilcoxonResult:
    method_a: str
    method_b: str
    statistic: float
    raw_pvalue: float
    holm_pvalue: float
    reject: bool
    n_videos: int
    mean_difference: float
    median_difference: float
    alternative: str
    status: str


@dataclass(frozen=True)
class PairwiseWilcoxonTable:
    comparisons: tuple[PairwiseWilcoxonResult, ...]
    pairing: PairingReport
    alpha: float


@dataclass(frozen=True)
class BootstrapCI:
    method_a: str
    method_b: str
    statistic: str
    estimate: float
    lower: float
    upper: float
    confidence: float
    n_videos: int
    n_resamples: int
    seed: int
    pairing: PairingReport


MetricInput = VideoMetric | AggregatedVideoMetric | Mapping[str, Any]
PreparedInput = SeedAggregationResult | Iterable[MetricInput]


def _coerce_metric(
    item: VideoMetric | Mapping[str, Any],
    *,
    video_key: str,
    method_key: str,
    value_key: str,
    seed_key: str,
) -> VideoMetric:
    if isinstance(item, VideoMetric):
        metric = item
    elif isinstance(item, Mapping):
        try:
            metric = VideoMetric(
                video_id=str(item[video_key]),
                method=str(item[method_key]),
                value=float(item[value_key]),
                seed=item.get(seed_key),
            )
        except KeyError as exc:
            raise ValueError(
                f"Every observation needs {video_key!r}, {method_key!r} and "
                f"{value_key!r}; missing {exc.args[0]!r}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid video-level metric: {item!r}") from exc
    else:
        raise TypeError(f"Unsupported metric type: {type(item).__name__}")
    if not metric.video_id.strip():
        raise ValueError("video_id cannot be empty")
    if not metric.method.strip():
        raise ValueError("method cannot be empty")
    try:
        hash(metric.seed)
    except TypeError as exc:
        raise ValueError("seed must be a hashable scalar or None") from exc
    return metric


def aggregate_seeds_by_video(
    observations: Iterable[VideoMetric | Mapping[str, Any]],
    *,
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    video_key: str = "video_id",
    method_key: str = "method",
    value_key: str = "value",
    seed_key: str = "seed",
) -> SeedAggregationResult:
    """Collapse seeds within each video/method before any statistical test.

    Duplicate ``video_id/method/seed`` keys are rejected because silently
    averaging them would give that seed extra weight. Non-finite observations
    are either reported and omitted or rejected according to ``nan_policy``.
    """
    if reducer not in {"mean", "median"}:
        raise ValueError("reducer must be 'mean' or 'median'")
    if nan_policy not in {"omit", "raise"}:
        raise ValueError("nan_policy must be 'omit' or 'raise'")

    grouped: dict[tuple[str, str], list[VideoMetric]] = {}
    all_groups: set[tuple[str, str]] = set()
    seen: set[tuple[str, str, int | str | None]] = set()
    dropped: list[VideoMetric] = []
    for raw in observations:
        if isinstance(raw, AggregatedVideoMetric):
            raise TypeError(
                "aggregate_seeds_by_video expects seed-level VideoMetric rows, "
                "not AggregatedVideoMetric"
            )
        metric = _coerce_metric(
            raw,
            video_key=video_key,
            method_key=method_key,
            value_key=value_key,
            seed_key=seed_key,
        )
        key = (metric.video_id, metric.method, metric.seed)
        if key in seen:
            raise ValueError(
                "Duplicate video/method/seed observation: "
                f"{metric.video_id}/{metric.method}/{metric.seed}"
            )
        seen.add(key)
        group = (metric.video_id, metric.method)
        all_groups.add(group)
        if not math.isfinite(metric.value):
            if nan_policy == "raise":
                raise ValueError(f"Non-finite metric for {key}: {metric.value}")
            dropped.append(metric)
            continue
        grouped.setdefault(group, []).append(metric)

    aggregate_function = np.mean if reducer == "mean" else np.median
    aggregated: list[AggregatedVideoMetric] = []
    for (video_id, method), metrics in sorted(grouped.items()):
        seeds = tuple(sorted((metric.seed for metric in metrics), key=repr))
        aggregated.append(
            AggregatedVideoMetric(
                video_id=video_id,
                method=method,
                value=float(aggregate_function([metric.value for metric in metrics])),
                n_seeds=len(metrics),
                seeds=seeds,
            )
        )
    dropped_groups = tuple(sorted(all_groups - set(grouped)))
    return SeedAggregationResult(
        metrics=tuple(aggregated),
        reducer=reducer,
        dropped_nonfinite=tuple(dropped),
        dropped_groups=dropped_groups,
    )


def _prepare_metrics(
    data: PreparedInput,
    *,
    reducer: Reducer,
    nan_policy: NanPolicy,
    value_key: str,
) -> SeedAggregationResult:
    if isinstance(data, SeedAggregationResult):
        return data
    items = list(data)
    if items and all(isinstance(item, AggregatedVideoMetric) for item in items):
        metrics = tuple(items)  # type: ignore[arg-type]
        keys = [(item.video_id, item.method) for item in metrics]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate aggregated video/method value")
        if any(not math.isfinite(item.value) for item in metrics):
            raise ValueError("AggregatedVideoMetric values must be finite")
        return SeedAggregationResult(metrics, reducer, (), ())
    if any(isinstance(item, AggregatedVideoMetric) for item in items):
        raise TypeError("Do not mix seed-level and AggregatedVideoMetric rows")
    return aggregate_seeds_by_video(
        items, reducer=reducer, nan_policy=nan_policy, value_key=value_key
    )


def _normalise_methods(
    prepared: SeedAggregationResult, methods: Sequence[str] | None
) -> tuple[str, ...]:
    available = {metric.method for metric in prepared.metrics}
    available.update(method for _, method in prepared.dropped_groups)
    available.update(metric.method for metric in prepared.dropped_nonfinite)
    selected = tuple(methods) if methods is not None else tuple(sorted(available))
    if len(selected) != len(set(selected)):
        raise ValueError("methods contains duplicates")
    if not selected:
        raise ValueError("No methods available for comparison")
    missing = [method for method in selected if method not in available]
    if missing:
        raise ValueError(f"Methods absent from data: {missing}")
    return selected


def _paired_matrix(
    prepared: SeedAggregationResult,
    *,
    methods: Sequence[str] | None,
    unmatched_policy: UnmatchedPolicy,
) -> tuple[np.ndarray, PairingReport]:
    if unmatched_policy not in {"drop", "raise"}:
        raise ValueError("unmatched_policy must be 'drop' or 'raise'")
    selected = _normalise_methods(prepared, methods)
    lookup = {
        (metric.video_id, metric.method): metric.value for metric in prepared.metrics
    }
    video_ids = sorted(
        {
            metric.video_id
            for metric in prepared.metrics
            if metric.method in selected
        }
        | {
            video_id
            for video_id, method in prepared.dropped_groups
            if method in selected
        }
        | {
            metric.video_id
            for metric in prepared.dropped_nonfinite
            if metric.method in selected
        }
    )
    complete_ids: list[str] = []
    rows: list[list[float]] = []
    excluded: list[ExcludedVideo] = []
    for video_id in video_ids:
        missing = tuple(
            method for method in selected if (video_id, method) not in lookup
        )
        if missing:
            excluded.append(ExcludedVideo(video_id, missing))
            continue
        complete_ids.append(video_id)
        rows.append([lookup[(video_id, method)] for method in selected])
    if excluded and unmatched_policy == "raise":
        detail = "; ".join(
            f"{item.video_id}: {list(item.missing_methods)}" for item in excluded
        )
        raise ValueError(f"Unpaired video IDs: {detail}")
    matrix = np.asarray(rows, dtype=float).reshape(-1, len(selected))
    return matrix, PairingReport(
        selected,
        tuple(complete_ids),
        tuple(excluded),
        prepared.dropped_nonfinite,
        prepared.dropped_groups,
    )


def _scipy_stats():
    try:
        from scipy import stats
    except ImportError as exc:  # pragma: no cover - project requirements include SciPy
        raise RuntimeError(
            "Statistical tests require SciPy; install the project requirements"
        ) from exc
    return stats


def friedman_test(
    data: PreparedInput,
    *,
    methods: Sequence[str] | None = None,
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    unmatched_policy: UnmatchedPolicy = "drop",
    value_key: str = "value",
) -> FriedmanResult:
    """Run SciPy's Friedman test on complete, seed-aggregated video blocks."""
    prepared = _prepare_metrics(
        data, reducer=reducer, nan_policy=nan_policy, value_key=value_key
    )
    matrix, pairing = _paired_matrix(
        prepared, methods=methods, unmatched_policy=unmatched_policy
    )
    if len(pairing.methods) < 3:
        raise ValueError("Friedman requires at least three methods")
    if len(matrix) < 2:
        raise ValueError("Friedman requires at least two paired videos")
    stats = _scipy_stats()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = stats.friedmanchisquare(
            *(matrix[:, index] for index in range(matrix.shape[1]))
        )
    statistic, pvalue = float(result.statistic), float(result.pvalue)
    status = "ok"
    if not math.isfinite(statistic) or not math.isfinite(pvalue):
        if np.all(matrix == matrix[:, [0]]):
            status = "degenerate_all_methods_equal"
        else:
            status = "scipy_returned_nonfinite"
    return FriedmanResult(statistic, pvalue, len(matrix), pairing, status)


def paired_difference(
    data: PreparedInput,
    method_a: str,
    method_b: str,
    *,
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    unmatched_policy: UnmatchedPolicy = "drop",
    value_key: str = "value",
) -> PairedDifferenceResult:
    """Return per-video ``method_a - method_b`` differences."""
    prepared = _prepare_metrics(
        data, reducer=reducer, nan_policy=nan_policy, value_key=value_key
    )
    matrix, pairing = _paired_matrix(
        prepared, methods=(method_a, method_b), unmatched_policy=unmatched_policy
    )
    if not len(matrix):
        raise ValueError("No paired videos remain for the requested methods")
    differences = matrix[:, 0] - matrix[:, 1]
    return PairedDifferenceResult(
        method_a=method_a,
        method_b=method_b,
        differences=tuple(float(value) for value in differences),
        mean_difference=float(np.mean(differences)),
        median_difference=float(np.median(differences)),
        pairing=pairing,
    )


def _wilcoxon_arrays(
    first: np.ndarray,
    second: np.ndarray,
    *,
    alternative: str,
) -> tuple[float, float, str]:
    if alternative not in {"two-sided", "greater", "less"}:
        raise ValueError("alternative must be two-sided, greater or less")
    differences = first - second
    if np.all(differences == 0):
        return 0.0, 1.0, "all_differences_zero"
    stats = _scipy_stats()
    result = stats.wilcoxon(
        first,
        second,
        alternative=alternative,
        zero_method="wilcox",
        method="auto",
    )
    return float(result.statistic), float(result.pvalue), "ok"


def wilcoxon_paired(
    data: PreparedInput,
    method_a: str,
    method_b: str,
    *,
    alternative: str = "two-sided",
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    unmatched_policy: UnmatchedPolicy = "drop",
    value_key: str = "value",
) -> WilcoxonResult:
    """Run SciPy's paired Wilcoxon test after pairing videos."""
    prepared = _prepare_metrics(
        data, reducer=reducer, nan_policy=nan_policy, value_key=value_key
    )
    matrix, pairing = _paired_matrix(
        prepared, methods=(method_a, method_b), unmatched_policy=unmatched_policy
    )
    if not len(matrix):
        raise ValueError("No paired videos remain for Wilcoxon")
    statistic, pvalue, status = _wilcoxon_arrays(
        matrix[:, 0], matrix[:, 1], alternative=alternative
    )
    differences = matrix[:, 0] - matrix[:, 1]
    return WilcoxonResult(
        method_a,
        method_b,
        statistic,
        pvalue,
        alternative,
        len(matrix),
        float(np.mean(differences)),
        float(np.median(differences)),
        pairing,
        status,
    )


def holm_correction(
    pvalues: Sequence[float], *, alpha: float = 0.05
) -> HolmCorrection:
    """Holm step-down family-wise correction, returned in original order."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    raw = np.asarray(pvalues, dtype=float)
    if raw.ndim != 1 or not len(raw):
        raise ValueError("pvalues must be a non-empty one-dimensional sequence")
    if np.any(~np.isfinite(raw)) or np.any((raw < 0) | (raw > 1)):
        raise ValueError("pvalues must be finite and in [0, 1]")

    order = np.argsort(raw, kind="stable")
    adjusted = np.empty_like(raw)
    running_max = 0.0
    total = len(raw)
    for rank, original_index in enumerate(order):
        candidate = min(1.0, (total - rank) * raw[original_index])
        running_max = max(running_max, candidate)
        adjusted[original_index] = running_max
    reject = adjusted <= alpha
    return HolmCorrection(
        raw_pvalues=tuple(float(value) for value in raw),
        adjusted_pvalues=tuple(float(value) for value in adjusted),
        reject=tuple(bool(value) for value in reject),
        alpha=float(alpha),
    )


def pairwise_wilcoxon_holm(
    data: PreparedInput,
    *,
    methods: Sequence[str] | None = None,
    alternative: str = "two-sided",
    alpha: float = 0.05,
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    unmatched_policy: UnmatchedPolicy = "drop",
    value_key: str = "value",
) -> PairwiseWilcoxonTable:
    """All pairwise Wilcoxon tests on one common video set, corrected by Holm."""
    prepared = _prepare_metrics(
        data, reducer=reducer, nan_policy=nan_policy, value_key=value_key
    )
    matrix, pairing = _paired_matrix(
        prepared, methods=methods, unmatched_policy=unmatched_policy
    )
    if len(pairing.methods) < 2:
        raise ValueError("Pairwise Wilcoxon requires at least two methods")
    if not len(matrix):
        raise ValueError("No common paired videos remain")
    raw_results: list[tuple[str, str, float, float, float, float, str]] = []
    for first_index, second_index in itertools.combinations(
        range(len(pairing.methods)), 2
    ):
        first = matrix[:, first_index]
        second = matrix[:, second_index]
        statistic, pvalue, status = _wilcoxon_arrays(
            first, second, alternative=alternative
        )
        differences = first - second
        raw_results.append(
            (
                pairing.methods[first_index],
                pairing.methods[second_index],
                statistic,
                pvalue,
                float(np.mean(differences)),
                float(np.median(differences)),
                status,
            )
        )
    correction = holm_correction(
        [result[3] for result in raw_results], alpha=alpha
    )
    comparisons = tuple(
        PairwiseWilcoxonResult(
            method_a=result[0],
            method_b=result[1],
            statistic=result[2],
            raw_pvalue=result[3],
            holm_pvalue=correction.adjusted_pvalues[index],
            reject=correction.reject[index],
            n_videos=len(matrix),
            mean_difference=result[4],
            median_difference=result[5],
            alternative=alternative,
            status=result[6],
        )
        for index, result in enumerate(raw_results)
    )
    return PairwiseWilcoxonTable(comparisons, pairing, float(alpha))


def paired_bootstrap_ci(
    data: PreparedInput,
    method_a: str,
    method_b: str,
    *,
    statistic: Literal["mean", "median"] = "mean",
    confidence: float = 0.95,
    n_resamples: int = 10_000,
    seed: int = 42,
    reducer: Reducer = "mean",
    nan_policy: NanPolicy = "omit",
    unmatched_policy: UnmatchedPolicy = "drop",
    value_key: str = "value",
) -> BootstrapCI:
    """Percentile CI by resampling paired video differences as whole clusters."""
    if statistic not in {"mean", "median"}:
        raise ValueError("statistic must be mean or median")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    paired = paired_difference(
        data,
        method_a,
        method_b,
        reducer=reducer,
        nan_policy=nan_policy,
        unmatched_policy=unmatched_policy,
        value_key=value_key,
    )
    differences = np.asarray(paired.differences, dtype=float)
    if len(differences) < 2:
        raise ValueError("Bootstrap CI requires at least two paired videos")
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, len(differences), size=(int(n_resamples), len(differences))
    )
    resampled = differences[indices]
    reducer_function = np.mean if statistic == "mean" else np.median
    estimates = reducer_function(resampled, axis=1)
    estimate = float(reducer_function(differences))
    tail = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [tail, 1.0 - tail])
    return BootstrapCI(
        method_a=method_a,
        method_b=method_b,
        statistic=statistic,
        estimate=estimate,
        lower=float(lower),
        upper=float(upper),
        confidence=float(confidence),
        n_videos=len(differences),
        n_resamples=int(n_resamples),
        seed=int(seed),
        pairing=paired.pairing,
    )
