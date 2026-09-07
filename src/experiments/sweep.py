"""Reproducible expansion/subsampling of YAML search spaces."""
from __future__ import annotations

import itertools
import random
from collections.abc import Iterator, Mapping, Sequence
from typing import Any


def parameter_grid(search_space: Mapping[str, Sequence[Any]]) -> Iterator[dict[str, Any]]:
    """Yield a stable Cartesian product in YAML key/value order."""
    keys = tuple(search_space)
    values = tuple(tuple(search_space[key]) for key in keys)
    if any(not options for options in values):
        raise ValueError("every search-space parameter needs at least one value")
    for combination in itertools.product(*values):
        yield dict(zip(keys, combination))


def deterministic_subset(
    candidates: Sequence[Mapping[str, Any]], *, maximum: int, seed: int
) -> list[dict[str, Any]]:
    """Keep a reproducible subset while preserving output order."""
    if maximum <= 0:
        raise ValueError("maximum must be positive")
    copied = [dict(candidate) for candidate in candidates]
    if len(copied) <= maximum:
        return copied
    rng = random.Random(int(seed))
    selected = sorted(rng.sample(range(len(copied)), maximum))
    return [copied[index] for index in selected]
