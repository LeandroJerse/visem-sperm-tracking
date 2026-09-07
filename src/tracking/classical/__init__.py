"""Trackers clássicos de associação geométrica e dinâmica linear."""

from .centroid import CentroidGreedyTracker
from .hungarian import HungarianTracker
from .sort import SortTracker

__all__ = ["CentroidGreedyTracker", "HungarianTracker", "SortTracker"]
