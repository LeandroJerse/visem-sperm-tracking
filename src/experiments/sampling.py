"""Deterministic frame/clip sampling without treating frames as replicates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def evenly_spaced_indices(eligible_indices: Iterable[int], count: int) -> tuple[int, ...]:
    """Select up to ``count`` sorted indices across the full eligible range."""
    if count <= 0:
        raise ValueError("count must be positive")
    eligible = sorted({int(index) for index in eligible_indices})
    if any(index < 0 for index in eligible):
        raise ValueError("frame indices must be non-negative")
    if len(eligible) <= count:
        return tuple(eligible)
    if count == 1:
        return (eligible[len(eligible) // 2],)
    positions = [index * (len(eligible) - 1) // (count - 1) for index in range(count)]
    return tuple(eligible[position] for position in positions)


@dataclass(frozen=True)
class ClipWindow:
    """Half-open warm-up and evaluation ranges for a stateful algorithm."""

    warmup_start: int
    evaluation_start: int
    evaluation_stop: int

    @property
    def warmup_frames(self) -> int:
        return self.evaluation_start - self.warmup_start

    @property
    def evaluation_frames(self) -> int:
        return self.evaluation_stop - self.evaluation_start


def evenly_spaced_clips(
    total_frames: int,
    *,
    count: int,
    evaluation_frames: int,
    warmup_frames: int = 100,
) -> tuple[ClipWindow, ...]:
    """Plan clips with full warm-up, spread from early to late video."""
    if min(total_frames, count, evaluation_frames) <= 0 or warmup_frames < 0:
        raise ValueError("invalid clip dimensions")
    if total_frames < warmup_frames + evaluation_frames:
        raise ValueError("video is too short for the requested warm-up/evaluation clip")
    first_start = warmup_frames
    last_start = total_frames - evaluation_frames
    starts = evenly_spaced_indices(range(first_start, last_start + 1), count)
    return tuple(
        ClipWindow(
            warmup_start=start - warmup_frames,
            evaluation_start=start,
            evaluation_stop=start + evaluation_frames,
        )
        for start in starts
    )
