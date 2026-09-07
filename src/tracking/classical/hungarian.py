"""Globally optimal center-distance association baseline."""
from __future__ import annotations

import numpy as np

from ..assignment import match_cost_matrix
from .centroid import _DistanceTracker


class HungarianTracker(_DistanceTracker):
    """Tracker with no motion model and Hungarian one-to-one association."""

    name = "hungarian"

    def _associate(
        self, cost: np.ndarray
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        return match_cost_matrix(cost, max_cost=self.max_distance)
