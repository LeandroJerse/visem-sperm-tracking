"""Otsu com deslocamento explícito, conservando o watershed original."""

from dataclasses import dataclass, replace

import cv2
import numpy as np

from .limiarizacao import _imagem_cinza
from .watershed import ConfiguracaoWatershed, configuracao_de_dict as ler_base, inspecionar as original


@dataclass(frozen=True)
class ConfiguracaoOtsuAjustado:
    watershed: ConfiguracaoWatershed
    deslocamento_otsu: int

    def __post_init__(self):
        if not isinstance(self.watershed, ConfiguracaoWatershed):
            raise TypeError("watershed deve ser ConfiguracaoWatershed.")
        if self.watershed.segmentacao.metodo != "otsu":
            raise ValueError("O deslocamento exige segmentação Otsu.")
        if type(self.deslocamento_otsu) is not int or not -255 <= self.deslocamento_otsu <= 255:
            raise ValueError("deslocamento_otsu deve ser inteiro entre -255 e 255.")


def configuracao_de_dict(dados):
    if not isinstance(dados, dict) or set(dados) != {"watershed", "deslocamento_otsu"}:
        raise ValueError("Informe watershed e deslocamento_otsu, sem outros campos.")
    return ConfiguracaoOtsuAjustado(ler_base(dados["watershed"]), dados["deslocamento_otsu"])


def inspecionar(imagem, config):
    """Retorna inspeção e metadados; não recebe nem consulta anotações.

    Com deslocamento zero, usa diretamente a implementação histórica. Nos
    demais casos calcula Otsu na imagem original e aplica o limiar ajustado
    pelo caminho manual da mesma implementação, antes da morfologia.
    """
    if not isinstance(config, ConfiguracaoOtsuAjustado):
        raise TypeError("config deve ser ConfiguracaoOtsuAjustado.")
    if config.deslocamento_otsu == 0:
        d = original(imagem, config.watershed)
        limiar = int(d.resultado.limiar_utilizado)
        efetivo = limiar
    else:
        cinza = _imagem_cinza(imagem)
        limiar = int(cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[0])
        efetivo = min(255, max(0, limiar + config.deslocamento_otsu))
        segmentacao = replace(config.watershed.segmentacao, metodo="manual", limiar_manual=efetivo)
        d = original(imagem, replace(config.watershed, segmentacao=segmentacao))
    pixels = int(np.count_nonzero(d.mascara))
    return d, {"limiar_otsu_original": limiar, "deslocamento_otsu": config.deslocamento_otsu,
               "limiar_efetivo": efetivo, "pixels_mascara": pixels, "pixels_imagem": int(d.mascara.size),
               "fracao_pixels_mascara": pixels / d.mascara.size}
