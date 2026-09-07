"""Reproducible experiment infrastructure shared by every TCC module."""

from .config import config_hash, load_config, resolve_config
from .dataset import SplitSpec, load_split_spec
from .runs import RunContext
from .protocol import (
    ProtocolViolation,
    assert_frozen_config_source,
    assert_frozen_overrides,
    assert_protocol_access,
    assert_video_ids_in_split,
)
from .resources import ResourceMonitor
from .sampling import ClipWindow, evenly_spaced_clips, evenly_spaced_indices
from .sweep import deterministic_subset, parameter_grid

__all__ = [
    "RunContext",
    "ProtocolViolation",
    "assert_frozen_config_source",
    "assert_frozen_overrides",
    "assert_protocol_access",
    "assert_video_ids_in_split",
    "ResourceMonitor",
    "ClipWindow",
    "evenly_spaced_clips",
    "evenly_spaced_indices",
    "deterministic_subset",
    "parameter_grid",
    "SplitSpec",
    "config_hash",
    "load_config",
    "load_split_spec",
    "resolve_config",
]
