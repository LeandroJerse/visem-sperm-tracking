"""Multi-objective Pareto frontiers without subjective weighted scores."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


Direction = Literal["max", "min"]


@dataclass(frozen=True)
class Objective:
    name: str
    direction: Direction


@dataclass(frozen=True)
class ParetoPoint:
    identifier: str
    values: tuple[tuple[str, float], ...]

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)


@dataclass(frozen=True)
class DominatedPoint:
    identifier: str
    dominators: tuple[str, ...]


@dataclass(frozen=True)
class ParetoResult:
    objectives: tuple[Objective, ...]
    frontier: tuple[ParetoPoint, ...]
    dominated: tuple[DominatedPoint, ...]
    excluded_nonfinite: tuple[str, ...]

    @property
    def frontier_ids(self) -> tuple[str, ...]:
        return tuple(point.identifier for point in self.frontier)


def normalise_objectives(
    objectives: Mapping[str, str] | Sequence[Objective],
) -> tuple[Objective, ...]:
    """Validate and preserve the declared objective order."""
    if isinstance(objectives, Mapping):
        result = tuple(
            Objective(str(name), str(direction).lower())  # type: ignore[arg-type]
            for name, direction in objectives.items()
        )
    else:
        result = tuple(objectives)
    if not result:
        raise ValueError("At least one Pareto objective is required")
    names = [objective.name for objective in result]
    if any(not name.strip() for name in names):
        raise ValueError("Objective names cannot be empty")
    if len(names) != len(set(names)):
        raise ValueError("Objective names must be unique")
    for objective in result:
        if objective.direction not in {"max", "min"}:
            raise ValueError(
                f"Objective {objective.name!r} direction must be 'max' or 'min'"
            )
    return result


def dominates(
    first: Mapping[str, float],
    second: Mapping[str, float],
    objectives: Mapping[str, str] | Sequence[Objective],
) -> bool:
    """Return true iff ``first`` is no worse everywhere and better somewhere."""
    resolved = normalise_objectives(objectives)
    no_worse = True
    strictly_better = False
    for objective in resolved:
        try:
            first_value = float(first[objective.name])
            second_value = float(second[objective.name])
        except KeyError as exc:
            raise ValueError(f"Missing objective value: {exc.args[0]!r}") from exc
        if not math.isfinite(first_value) or not math.isfinite(second_value):
            raise ValueError("Dominance is undefined for non-finite objective values")
        if objective.direction == "max":
            no_worse &= first_value >= second_value
            strictly_better |= first_value > second_value
        else:
            no_worse &= first_value <= second_value
            strictly_better |= first_value < second_value
        if not no_worse:
            return False
    return no_worse and strictly_better


def pareto_frontier(
    records: Iterable[Mapping[str, Any]],
    objectives: Mapping[str, str] | Sequence[Objective],
    *,
    id_key: str = "method",
    nan_policy: Literal["drop", "raise"] = "raise",
) -> ParetoResult:
    """Return every non-dominated candidate and explicit domination relations.

    Candidates are never collapsed into a weighted score. Identical objective
    vectors are ties: neither candidate dominates the other, so both remain on
    the frontier.
    """
    resolved = normalise_objectives(objectives)
    if nan_policy not in {"drop", "raise"}:
        raise ValueError("nan_policy must be 'drop' or 'raise'")

    points: list[ParetoPoint] = []
    excluded: list[str] = []
    seen_ids: set[str] = set()
    for record in records:
        if id_key not in record:
            raise ValueError(f"Every Pareto record needs identifier key {id_key!r}")
        identifier = str(record[id_key])
        if not identifier:
            raise ValueError("Pareto candidate identifier cannot be empty")
        if identifier in seen_ids:
            raise ValueError(f"Duplicate Pareto candidate identifier: {identifier}")
        seen_ids.add(identifier)
        values: list[tuple[str, float]] = []
        for objective in resolved:
            if objective.name not in record:
                raise ValueError(
                    f"Candidate {identifier!r} lacks objective {objective.name!r}"
                )
            try:
                value = float(record[objective.name])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Candidate {identifier!r} has invalid {objective.name!r}"
                ) from exc
            values.append((objective.name, value))
        if any(not math.isfinite(value) for _, value in values):
            if nan_policy == "raise":
                raise ValueError(
                    f"Candidate {identifier!r} has non-finite objective value"
                )
            excluded.append(identifier)
            continue
        points.append(ParetoPoint(identifier, tuple(values)))

    frontier: list[ParetoPoint] = []
    dominated_points: list[DominatedPoint] = []
    for candidate in points:
        candidate_values = candidate.as_dict()
        dominators = tuple(
            other.identifier
            for other in points
            if other.identifier != candidate.identifier
            and dominates(other.as_dict(), candidate_values, resolved)
        )
        if dominators:
            dominated_points.append(DominatedPoint(candidate.identifier, dominators))
        else:
            frontier.append(candidate)
    return ParetoResult(
        objectives=resolved,
        frontier=tuple(frontier),
        dominated=tuple(dominated_points),
        excluded_nonfinite=tuple(excluded),
    )
