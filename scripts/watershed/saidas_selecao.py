"""Despacha parâmetros históricos sem alterar os detectores nem suas caixas."""

import numpy as np

from algoritmos.classicos.variantes_watershed import ConfiguracaoOtsuAjustado
from scripts.blobs.arquivos import gravar_json
from scripts.watershed import executar_inspecao as original
from scripts.watershed import saidas_round2 as ajustado


def executar_quadro(entrada, item, config, pasta):
    if isinstance(config, ConfiguracaoOtsuAjustado):
        return ajustado.executar_quadro(entrada, item, config, pasta)
    linha, avaliacao = original.executar_quadro(entrada, item, config, pasta)
    # Reaproveita a máscara salva pelo caminho manual histórico, sem nova detecção.
    with np.load(pasta / "mapas.npz", allow_pickle=False) as mapas:
        mascara = mapas["mascara"]
        pixels, total = int(np.count_nonzero(mascara)), int(mascara.size)
    meta = {"limiar_otsu_original": None, "deslocamento_otsu": 0,
            "limiar_efetivo": config.segmentacao.limiar_manual,
            "pixels_mascara": pixels, "pixels_imagem": total, "fracao_pixels_mascara":pixels/total}
    gravar_json(pasta / "segmentacao.json", meta)
    return {**linha, **meta}, avaliacao
