"""Local SQLite analytical store for datasets and immutable experiment runs."""

from typing import Any

from .run_ingest import (
    load_costs,
    load_metrics_frame,
    load_metrics_video,
    load_run_tables,
    load_runs,
)


def build_database(*args: Any, **kwargs: Any) -> Any:
    """Lazy public wrapper that keeps ``python -m src.db.build_db`` warning-free."""
    from .build_db import build_database as implementation

    return implementation(*args, **kwargs)


__all__ = [
    "build_database",
    "load_costs",
    "load_metrics_frame",
    "load_metrics_video",
    "load_run_tables",
    "load_runs",
]
