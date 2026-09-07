"""Registro central dos detectores disponíveis no pipeline."""

from __future__ import annotations

from typing import Any

from .base import Detector
from .classical import (
    BackgroundSubtractionDetector,
    BlobDetector,
    KNNDetector,
    MOG2Detector,
    ThresholdContourDetector,
    WatershedDetector,
)
from .hybrid import HybridThresholdDetector
from .learned import YoloDetector

DETECTORS: dict[str, type[Detector]] = {
    "threshold": ThresholdContourDetector,
    "blob": BlobDetector,
    "hybrid_threshold": HybridThresholdDetector,
    "bgsub": BackgroundSubtractionDetector,
    "mog2": MOG2Detector,
    "knn": KNNDetector,
    "watershed": WatershedDetector,
    "yolo": YoloDetector,
}


def build_detector(
    method: str,
    weights: str | None = None,
    params: dict[str, Any] | None = None,
) -> Detector:
    """Instancia um detector registrado com parâmetros validados pelo construtor."""
    if method not in DETECTORS:
        raise SystemExit(
            f"Método desconhecido: {method}. Opções: {', '.join(DETECTORS)}"
        )
    kwargs = dict(params or {})
    if weights is not None and method == "yolo":
        kwargs["weights"] = weights
    try:
        return DETECTORS[method](**kwargs)
    except TypeError as exc:
        raise SystemExit(f"Parâmetros inválidos para {method}: {exc}") from exc


def scientific_algorithm_id(
    method: str,
    *,
    params: dict[str, Any] | None = None,
    variant: str | None = None,
) -> str:
    """Nome científico usado na árvore de dados, sem misturar variantes.

    Otsu e threshold adaptativo compartilham a implementação de contornos, mas
    são algoritmos experimentais distintos e portanto recebem pastas próprias.
    """
    values = params or {}
    normalized_variant = str(variant or "").strip().lower()
    if method == "threshold":
        if bool(values.get("adaptive")) or normalized_variant.startswith("adaptive"):
            return "adaptive_threshold"
        if values.get("threshold_value") is None or normalized_variant == "otsu":
            return "otsu"
        return "threshold"
    if method == "bgsub":
        backend = str(values.get("algorithm") or values.get("method") or "").lower()
        if backend in {"mog2", "knn"}:
            return backend
    return method


__all__ = ["DETECTORS", "build_detector", "scientific_algorithm_id"]
