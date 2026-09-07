"""Contratos transversais e caminhos canônicos do repositório."""

from .artifacts import (
    normalize_parameter_overrides,
    sha256_file,
    write_csv_exclusive,
    write_json_exclusive,
)
from .paths import (
    CATALOG_DB,
    DATA_ROOT,
    DERIVED_FLOW_CACHE,
    DERIVED_TRACKS,
    EXPERIMENT_RESULTS_ROOT,
    EXPERIMENT_TESTS_ROOT,
    REPOSITORY_ROOT,
    VISEM_CLINICAL_ROOT,
    VISEM_METADATA_ROOT,
    VISEM_TRACKING_METADATA_ROOT,
    VISEM_TRACKING_TRAIN_ROOT,
    VISEM_VIDEOS_ROOT,
    YOLO_DATASET_ROOT,
    YOLO_PRETRAINED_ROOT,
)
from .relocation import PathMigrationMap, resolve_migrated_path

__all__ = [
    "normalize_parameter_overrides",
    "sha256_file",
    "write_csv_exclusive",
    "write_json_exclusive",
    "CATALOG_DB",
    "DATA_ROOT",
    "DERIVED_FLOW_CACHE",
    "DERIVED_TRACKS",
    "EXPERIMENT_RESULTS_ROOT",
    "EXPERIMENT_TESTS_ROOT",
    "REPOSITORY_ROOT",
    "VISEM_CLINICAL_ROOT",
    "VISEM_METADATA_ROOT",
    "VISEM_TRACKING_METADATA_ROOT",
    "VISEM_TRACKING_TRAIN_ROOT",
    "VISEM_VIDEOS_ROOT",
    "YOLO_DATASET_ROOT",
    "YOLO_PRETRAINED_ROOT",
    "PathMigrationMap",
    "resolve_migrated_path",
]
