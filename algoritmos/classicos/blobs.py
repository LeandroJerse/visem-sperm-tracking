"""SimpleBlobDetector com caixas e medidas geométricas explicitamente estimadas.

Recebe uma imagem e parâmetros; não lê anotações, não grava arquivos e não faz
morfologia. A área do filtro interno do OpenCV não é a área estimada usada
na classificação, nem uma contagem de pixels segmentados.
"""

from dataclasses import dataclass, fields
from fractions import Fraction
from math import ceil, floor, isfinite, pi
import struct

import cv2
import numpy as np

from .classificacao import ConfiguracaoAreaEstimada
from .comum import (
    Caixa, Deteccao, MedidasBlob, ResultadoDeteccao, validar_real,
)


FLOAT32_MAX = 3.4028234663852886e38


def _float32(nome: str, valor: float) -> float:
    """Expõe o arredondamento dos campos float do OpenCV, sem overflow oculto."""
    validar_real(nome, valor)
    try:
        convertido = struct.unpack("f", struct.pack("f", valor))[0]
    except (OverflowError, struct.error) as erro:
        raise ValueError(f"{nome} não cabe em float32.") from erro
    if not isfinite(convertido):
        raise ValueError(f"{nome} não cabe em float32.")
    if valor != 0 and convertido == 0:
        raise ValueError(f"{nome} vira zero após conversão para float32.")
    return convertido


def _contar_limiares(minimo: float, maximo: float, passo: float) -> int:
    """Conta a faixa inclusiva/exclusiva com os valores float32 efetivos."""
    # Os parâmetros já passaram por float32. Frações evitam que a divisão
    # arredonde um número logo acima de um inteiro para esse mesmo inteiro.
    intervalo = Fraction(maximo) - Fraction(minimo)
    return ceil(intervalo / Fraction(passo))


@dataclass(frozen=True, slots=True)
class ConfiguracaoBlobs:
    """Parâmetros explícitos; nenhum valor é calibrado ou escolhido pelo módulo.

    Limiares pertencem a [0, 255], com início inclusivo e fim exclusivo.
    O passo deve ser pelo menos 1: valores menores repetem níveis de uma
    imagem uint8 e podem inflar a repetibilidade. Há no máximo 255 passagens.
    ``area_minima`` é inclusiva e ``area_maxima`` exclusiva, ambas relativas
    à geometria interna dos contornos do OpenCV. Os filtros de forma aceitam
    mínimos em (0, 1]; ``None`` desativa o filtro. Os limites da classificação
    se referem somente a pi * (diametro_blob / 2) ** 2.

    Os números informados são preservados. ``parametros_opencv`` fornece os
    valores efetivos após a conversão para float32 usada pela biblioteca.
    """

    polaridade: str
    limiar_minimo: float
    limiar_maximo: float
    passo_limiar: float
    repetibilidade_minima: int
    distancia_minima: float
    area_minima: float
    area_maxima: float
    circularidade_minima: float | None
    inercia_minima: float | None
    convexidade_minima: float | None
    classificacao: ConfiguracaoAreaEstimada

    def __post_init__(self) -> None:
        if self.polaridade not in ("claro", "escuro"):
            raise ValueError("polaridade deve ser 'claro' ou 'escuro'.")
        efetivos = {}
        for nome in (
            "limiar_minimo", "limiar_maximo", "passo_limiar",
            "distancia_minima", "area_minima", "area_maxima",
        ):
            efetivos[nome] = _float32(nome, getattr(self, nome))
        for nome in ("limiar_minimo", "limiar_maximo"):
            if not 0 <= getattr(self, nome) <= 255:
                raise ValueError(f"{nome} deve estar entre 0 e 255.")
        for nome in ("passo_limiar", "distancia_minima", "area_minima", "area_maxima"):
            if efetivos[nome] <= 0:
                raise ValueError(f"{nome} deve ser positivo em float32.")
        minimo, maximo = efetivos["limiar_minimo"], efetivos["limiar_maximo"]
        passo = efetivos["passo_limiar"]
        if minimo >= maximo:
            raise ValueError("limiar_minimo deve ser menor que limiar_maximo em float32.")
        if self.passo_limiar < 1 or passo < 1:
            raise ValueError("passo_limiar deve ser pelo menos 1 para imagens uint8.")
        quantidade = _contar_limiares(minimo, maximo, passo)
        if quantidade < 2:
            raise ValueError("A faixa precisa conter pelo menos dois limiares.")
        if type(self.repetibilidade_minima) is not int:
            raise TypeError("repetibilidade_minima deve ser um inteiro.")
        if not 1 <= self.repetibilidade_minima <= quantidade:
            raise ValueError("repetibilidade_minima deve estar entre 1 e a quantidade de limiares.")
        if efetivos["area_minima"] >= efetivos["area_maxima"]:
            raise ValueError("area_minima deve ser menor que area_maxima em float32.")
        for nome in ("circularidade_minima", "inercia_minima", "convexidade_minima"):
            valor = getattr(self, nome)
            if valor is not None:
                _float32(nome, valor)
                if not 0 < valor <= 1:
                    raise ValueError(f"{nome} deve estar no intervalo (0, 1], ou ser None.")
        if not isinstance(self.classificacao, ConfiguracaoAreaEstimada):
            raise TypeError("classificacao deve ser ConfiguracaoAreaEstimada.")


def _exigir_chaves(dados: dict, esperadas: set[str], nome: str) -> None:
    if not isinstance(dados, dict):
        raise TypeError(f"{nome} deve ser um objeto JSON.")
    if any(not isinstance(chave, str) for chave in dados):
        raise TypeError(f"As chaves de {nome} devem ser texto.")
    ausentes = esperadas - dados.keys()
    extras = dados.keys() - esperadas
    if ausentes or extras:
        raise ValueError(
            f"Chaves inválidas em {nome}: ausentes={sorted(ausentes)}, "
            f"extras={sorted(extras)}."
        )


def configuracao_de_dict(dados: dict) -> ConfiguracaoBlobs:
    """Carrega todos os campos explícitos, rejeitando omissões e nomes extras."""
    _exigir_chaves(dados, {campo.name for campo in fields(ConfiguracaoBlobs)}, "configuracao")
    classificacao = dados["classificacao"]
    _exigir_chaves(
        classificacao, {"area_maxima_pequeno", "area_minima_aglomerado"}, "classificacao"
    )
    return ConfiguracaoBlobs(
        **{nome: valor for nome, valor in dados.items() if nome != "classificacao"},
        classificacao=ConfiguracaoAreaEstimada(**classificacao),
    )


def parametros_opencv(config: ConfiguracaoBlobs) -> dict[str, bool | int | float]:
    """Todos os campos do backend, serializáveis para o registro da execução."""
    if not isinstance(config, ConfiguracaoBlobs):
        raise TypeError("config deve ser ConfiguracaoBlobs.")
    parametros = {
        "minThreshold": _float32("limiar_minimo", config.limiar_minimo),
        "maxThreshold": _float32("limiar_maximo", config.limiar_maximo),
        "thresholdStep": _float32("passo_limiar", config.passo_limiar),
        "minRepeatability": config.repetibilidade_minima,
        "minDistBetweenBlobs": _float32("distancia_minima", config.distancia_minima),
        "filterByColor": True,
        "blobColor": 255 if config.polaridade == "claro" else 0,
        "filterByArea": True,
        "minArea": _float32("area_minima", config.area_minima),
        "maxArea": _float32("area_maxima", config.area_maxima),
        "collectContours": False,
    }
    for nome, sufixo in (
        ("circularidade_minima", "Circularity"),
        ("inercia_minima", "InertiaRatio"),
        ("convexidade_minima", "Convexity"),
    ):
        valor = getattr(config, nome)
        flag = "Inertia" if sufixo == "InertiaRatio" else sufixo
        parametros[f"filterBy{flag}"] = valor is not None
        # O OpenCV valida os limites mesmo com o filtro desligado.
        parametros[f"min{sufixo}"] = 1.0 if valor is None else _float32(nome, valor)
        parametros[f"max{sufixo}"] = FLOAT32_MAX
    return parametros


def quantidade_limiares(config: ConfiguracaoBlobs) -> int:
    """Quantidade planejada de passagens, após conversão dos campos float32."""
    parametros = parametros_opencv(config)
    return _contar_limiares(
        parametros["minThreshold"], parametros["maxThreshold"], parametros["thresholdStep"]
    )


def _imagem_cinza(imagem: np.ndarray) -> np.ndarray:
    if not isinstance(imagem, np.ndarray):
        raise TypeError("imagem deve ser um array NumPy.")
    if imagem.dtype != np.uint8:
        raise ValueError("imagem deve ter tipo uint8.")
    if imagem.size == 0:
        raise ValueError("imagem não pode ser vazia.")
    if imagem.ndim == 2:
        return imagem.copy(order="C")
    if imagem.ndim == 3 and imagem.shape[2] == 3:
        return cv2.cvtColor(imagem.copy(order="C"), cv2.COLOR_BGR2GRAY)
    raise ValueError("imagem deve ser cinza 2D ou BGR com exatamente três canais.")


def _deteccao(keypoint, largura: int, altura: int, config: ConfiguracaoBlobs) -> Deteccao:
    try:
        cx, cy = keypoint.pt
        diametro = keypoint.size
    except (AttributeError, TypeError, ValueError) as erro:
        raise ValueError("O detector retornou um keypoint sem centro ou diâmetro válidos.") from erro
    for nome, valor in (("centro_blob_x", cx), ("centro_blob_y", cy), ("diametro_blob", diametro)):
        validar_real(nome, valor)
    cx, cy, diametro = float(cx), float(cy), float(diametro)
    if not 0 <= cx < largura or not 0 <= cy < altura:
        raise ValueError("O centro retornado pelo detector está fora da imagem.")
    if diametro <= 0:
        raise ValueError("O diâmetro retornado pelo detector deve ser positivo.")
    raio = diametro / 2
    area_estimada = pi * (raio * raio)
    if not isfinite(area_estimada) or area_estimada <= 0:
        raise ValueError("A área estimada do blob deve ser positiva e finita.")
    original = (floor(cx - raio), floor(cy - raio), ceil(cx + raio), ceil(cy + raio))
    x0, y0, x1, y1 = (
        max(0, min(largura, original[0])), max(0, min(altura, original[1])),
        max(0, min(largura, original[2])), max(0, min(altura, original[3])),
    )
    if x1 <= x0 or y1 <= y0:
        raise ValueError("O keypoint não produz uma caixa de dimensões positivas.")
    caixa = Caixa(x0, y0, x1 - x0, y1 - y0)
    medidas = MedidasBlob(
        centro_blob_x=cx, centro_blob_y=cy, diametro_blob=diametro,
        area_estimada_blob=area_estimada, area_caixa=caixa.largura * caixa.altura,
        caixa_recortada_na_borda=original != (x0, y0, x1, y1),
    )
    return Deteccao(config.classificacao.classificar(area_estimada), caixa, medidas)


def detectar(imagem: np.ndarray, config: ConfiguracaoBlobs) -> ResultadoDeteccao:
    """Detecta em cinza e converte keypoints em caixas, sem alterar a entrada.

    A caixa envolve o círculo estimado antes do recorte nas bordas, sem afirmar
    que contém a região real. Área e centro estimados permanecem intactos após
    o recorte. Não há máscara, centroide de pixels ou limiar único disponível.
    """
    if not isinstance(config, ConfiguracaoBlobs):
        raise TypeError("config deve ser ConfiguracaoBlobs.")
    cinza = _imagem_cinza(imagem)
    parametros = cv2.SimpleBlobDetector_Params()
    for nome, valor in parametros_opencv(config).items():
        if not hasattr(parametros, nome):
            raise RuntimeError(
                f"O OpenCV instalado não oferece o parâmetro {nome}; "
                "use a versão de referência registrada para blobs."
            )
        setattr(parametros, nome, valor)
    backend = cv2.SimpleBlobDetector_create(parametros)
    altura, largura = cinza.shape
    deteccoes = [_deteccao(ponto, largura, altura, config) for ponto in backend.detect(cinza)]
    deteccoes.sort(key=lambda deteccao: (
        deteccao.caixa.y, deteccao.caixa.x, deteccao.medidas.centro_blob_y,
        deteccao.medidas.centro_blob_x, deteccao.medidas.diametro_blob, int(deteccao.classe),
    ))
    return ResultadoDeteccao(
        algoritmo="blobs", largura_imagem=largura, altura_imagem=altura,
        deteccoes=tuple(deteccoes), limiar_utilizado=None,
    )
