"""Low-overhead sampled RAM/VRAM accounting for experiment summaries."""
from __future__ import annotations

import sys
from typing import Any


class ResourceMonitor:
    """Track sampled process RSS and CUDA peaks without requiring a GPU."""

    def __init__(self) -> None:
        try:
            import psutil
        except ImportError:  # pragma: no cover - optional in minimal installs
            self._process = None
        else:
            self._process = psutil.Process()
        self._rss_peak = 0
        self._samples = 0
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        self.sample()

    def sample(self) -> None:
        if self._process is not None:
            self._rss_peak = max(self._rss_peak, int(self._process.memory_info().rss))
        self._samples += 1

    def summary(self) -> dict[str, Any]:
        self.sample()
        result: dict[str, Any] = {
            "resource_samples": self._samples,
            "ram_rss_peak_mb": round(self._rss_peak / (1024**2), 3)
            if self._process is not None
            else None,
            "vram_allocated_peak_mb": None,
            "vram_reserved_peak_mb": None,
        }
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            result["vram_allocated_peak_mb"] = round(
                torch.cuda.max_memory_allocated() / (1024**2), 3
            )
            result["vram_reserved_peak_mb"] = round(
                torch.cuda.max_memory_reserved() / (1024**2), 3
            )
        return result
