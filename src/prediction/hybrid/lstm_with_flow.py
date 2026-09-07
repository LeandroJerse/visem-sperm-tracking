"""LSTM híbrida que recebe o fluxo aparente como atributo auxiliar."""
from __future__ import annotations

from typing import Any

from ..learned.lstm import LSTMPredictor


class FlowAwareLSTMPredictor(LSTMPredictor):
    """Variante pareada da LSTM que concatena atributos históricos de fluxo."""

    name = "flow_aware_lstm"
    uses_flow = True

    def __init__(self, **parameters: Any) -> None:
        parameters.pop("use_flow", None)
        super().__init__(use_flow=True, **parameters)
