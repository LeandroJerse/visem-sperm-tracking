"""Única definição dos caminhos oficiais do projeto.

Os executores podem ser chamados fora da raiz do repositório sem criarem uma
segunda árvore ``data/`` acidental no diretório de trabalho. Entradas informadas
explicitamente pelo usuário continuam sendo respeitadas.
"""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPOSITORY_ROOT / "data"

VISEM_ROOT = DATA_ROOT / "sources" / "visem"
VISEM_VIDEOS_ROOT = VISEM_ROOT / "videos"
VISEM_CLINICAL_ROOT = VISEM_ROOT / "clinical"
VISEM_METADATA_ROOT = VISEM_ROOT / "metadata"

VISEM_TRACKING_ROOT = DATA_ROOT / "sources" / "visem_tracking"
VISEM_TRACKING_TRAIN_ROOT = VISEM_TRACKING_ROOT / "dataset" / "Train"
VISEM_TRACKING_METADATA_ROOT = VISEM_TRACKING_ROOT / "metadata"

YOLO_DATASET_ROOT = DATA_ROOT / "datasets" / "yolo" / "official_12_4_4"
YOLO_PRETRAINED_ROOT = DATA_ROOT / "models" / "detection" / "yolo" / "pretrained"

DERIVED_FLOW_CACHE = DATA_ROOT / "derived" / "flow" / "cache"
DERIVED_TRACKS = DATA_ROOT / "derived" / "tracking" / "tracks"

EXPERIMENT_TESTS_ROOT = DATA_ROOT / "tests"
EXPERIMENT_RESULTS_ROOT = DATA_ROOT / "results"
CATALOG_DB = DATA_ROOT / "catalog" / "visem.db"


def resolve_from_repository(path: str | Path) -> Path:
    """Resolve um caminho explícito relativamente à raiz oficial."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPOSITORY_ROOT / candidate


__all__ = [name for name in globals() if name.isupper()] + ["resolve_from_repository"]
