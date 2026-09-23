"""Pré-processamento explícito e blobs LoG/DoG em imagens, sem estado temporal.

LoG e DoG recebem cinza uint8 dividido por 255, sem normalização por imagem.
O raio sqrt(2) * sigma é uma estimativa circular, não uma segmentação da cabeça.
As caixas seguem o mesmo contrato do SimpleBlobDetector e não usam anotações.
"""

from dataclasses import dataclass
from math import ceil, floor, isfinite, pi, sqrt

import cv2
import numpy as np

from .blobs import _exigir_chaves, _imagem_cinza
from .classificacao import ConfiguracaoAreaEstimada
from .comum import (
    Caixa, Deteccao, MedidasBlob, ResultadoDeteccao, validar_inteiro, validar_real,
)


def _real(nome: str, valor: object) -> float:
    try:
        validar_real(nome, valor)
        numero = float(valor)
    except (OverflowError, ValueError) as erro:
        raise ValueError(f"{nome} deve ser representável como float.") from erro
    if not isfinite(numero):
        raise ValueError(f"{nome} deve ser finito.")
    return numero


def validar_preprocessamento(dados: dict) -> dict:
    """Valida e copia a regra, sem valores implícitos ou alteração da entrada."""
    if not isinstance(dados, dict):
        raise TypeError("preprocessamento deve ser um objeto JSON.")
    metodo = dados.get("metodo")
    if not isinstance(metodo, str) or metodo not in ("nenhum", "clahe"):
        raise ValueError("O pré-processamento deve ser 'nenhum' ou 'clahe'.")
    esperadas = {"metodo"}
    if metodo == "clahe":
        esperadas.update(("limite_contraste", "grade"))
    _exigir_chaves(dados, esperadas, "preprocessamento")
    if metodo == "nenhum":
        return {"metodo": "nenhum"}
    contraste = _real("limite_contraste", dados["limite_contraste"])
    if contraste <= 0:
        raise ValueError("limite_contraste deve ser positivo.")
    grade = dados["grade"]
    if not isinstance(grade, list) or len(grade) != 2:
        raise TypeError("grade deve ser uma lista [colunas, linhas] com dois inteiros.")
    for valor in grade:
        validar_inteiro("grade", valor, 1)
        if valor > np.iinfo(np.int32).max:
            raise ValueError("Os valores da grade devem caber em int32.")
    return {"metodo": "clahe", "limite_contraste": contraste, "grade": [int(v) for v in grade]}


def aplicar_preprocessamento(imagem: np.ndarray, dados: dict) -> np.ndarray:
    """Produz uma nova imagem cinza uint8; a grade CLAHE é dada em células."""
    config = validar_preprocessamento(dados)
    cinza = _imagem_cinza(imagem)
    if config["metodo"] == "nenhum":
        return cinza
    backend = cv2.createCLAHE(
        clipLimit=config["limite_contraste"], tileGridSize=tuple(config["grade"]),
    )
    return backend.apply(cinza)


@dataclass(frozen=True, slots=True)
class ConfiguracaoEscalaBlobs:
    """Faixa isotrópica de sigma em pixels e limiar absoluto da resposta.

    ``numero_escalas`` pertence somente a LoG, com espaçamento linear.
    ``razao_sigma`` pertence somente a DoG, com espaçamento geométrico.
    O limiar não representa intensidade uint8 nem probabilidade de confiança.
    """

    metodo: str
    polaridade: str
    sigma_minimo: float
    sigma_maximo: float
    limiar_resposta: float
    sobreposicao: float
    classificacao: ConfiguracaoAreaEstimada
    numero_escalas: int | None = None
    razao_sigma: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metodo, str) or self.metodo not in ("log", "dog"):
            raise ValueError("metodo deve ser 'log' ou 'dog'.")
        if not isinstance(self.polaridade, str) or self.polaridade not in ("claro", "escuro"):
            raise ValueError("polaridade deve ser 'claro' ou 'escuro'.")
        for nome in ("sigma_minimo", "sigma_maximo", "limiar_resposta", "sobreposicao"):
            object.__setattr__(self, nome, _real(nome, getattr(self, nome)))
        if not 0 < self.sigma_minimo < self.sigma_maximo:
            raise ValueError("Exige-se 0 < sigma_minimo < sigma_maximo.")
        if self.limiar_resposta <= 0:
            raise ValueError("limiar_resposta deve ser positivo.")
        if not 0 <= self.sobreposicao <= 1:
            raise ValueError("sobreposicao deve estar entre 0 e 1.")
        for sigma in (self.sigma_minimo, self.sigma_maximo):
            raio = sqrt(2) * sigma
            area = pi * raio * raio
            if not isfinite(area) or area <= 0:
                raise ValueError("A área estimada dos sigmas deve ser positiva e finita.")
        if not isinstance(self.classificacao, ConfiguracaoAreaEstimada):
            raise TypeError("classificacao deve ser ConfiguracaoAreaEstimada.")
        if self.metodo == "log":
            validar_inteiro("numero_escalas", self.numero_escalas, 2)
            object.__setattr__(self, "numero_escalas", int(self.numero_escalas))
            if self.razao_sigma is not None:
                raise ValueError("LoG não recebe razao_sigma.")
        else:
            if self.numero_escalas is not None:
                raise ValueError("DoG não recebe numero_escalas.")
            razao = _real("razao_sigma", self.razao_sigma)
            if razao <= 1:
                raise ValueError("razao_sigma deve ser maior que 1.")
            object.__setattr__(self, "razao_sigma", razao)


def configuracao_escala_de_dict(metodo: str, dados: dict) -> ConfiguracaoEscalaBlobs:
    """Converte o esquema específico de cada método, rejeitando campos extras."""
    if not isinstance(metodo, str) or metodo not in ("log", "dog"):
        raise ValueError("metodo deve ser 'log' ou 'dog'.")
    esperadas = {
        "polaridade", "sigma_minimo", "sigma_maximo", "limiar_resposta",
        "sobreposicao", "classificacao",
        "numero_escalas" if metodo == "log" else "razao_sigma",
    }
    _exigir_chaves(dados, esperadas, "configuracao_escala")
    _exigir_chaves(
        dados["classificacao"], {"area_maxima_pequeno", "area_minima_aglomerado"},
        "classificacao",
    )
    classificacao = ConfiguracaoAreaEstimada(**{
        chave: _real(chave, valor) for chave, valor in dados["classificacao"].items()
    })
    return ConfiguracaoEscalaBlobs(
        metodo=metodo, classificacao=classificacao,
        **{chave: valor for chave, valor in dados.items() if chave != "classificacao"},
    )


def parametros_escala(config: ConfiguracaoEscalaBlobs) -> dict:
    """Expõe os argumentos exatos do backend para o registro da execução."""
    if not isinstance(config, ConfiguracaoEscalaBlobs):
        raise TypeError("config deve ser ConfiguracaoEscalaBlobs.")
    parametros = {
        "min_sigma": config.sigma_minimo,
        "max_sigma": config.sigma_maximo,
        "threshold": config.limiar_resposta,
        "overlap": config.sobreposicao,
        "threshold_rel": None,
        "exclude_border": False,
    }
    if config.metodo == "log":
        parametros.update(num_sigma=config.numero_escalas, log_scale=False)
    else:
        parametros["sigma_ratio"] = config.razao_sigma
    return parametros


def _deteccao_escala(
    ponto: np.ndarray, largura: int, altura: int, config: ConfiguracaoEscalaBlobs,
) -> Deteccao:
    if len(ponto) != 3:
        raise ValueError("O backend deve retornar exatamente (y, x, sigma).")
    cy, cx, sigma = (_real(nome, valor) for nome, valor in zip(
        ("centro_blob_y", "centro_blob_x", "sigma_blob"), ponto,
    ))
    if not 0 <= cx < largura or not 0 <= cy < altura:
        raise ValueError("O centro retornado pelo backend está fora da imagem.")
    if sigma <= 0:
        raise ValueError("O sigma retornado pelo backend deve ser positivo.")
    raio = sqrt(2) * sigma
    area = pi * raio * raio
    if not isfinite(area) or area <= 0:
        raise ValueError("A área estimada retornada deve ser positiva e finita.")
    original = (floor(cx - raio), floor(cy - raio), ceil(cx + raio), ceil(cy + raio))
    limites = (
        max(0, min(largura, original[0])), max(0, min(altura, original[1])),
        max(0, min(largura, original[2])), max(0, min(altura, original[3])),
    )
    x0, y0, x1, y1 = limites
    caixa = Caixa(x0, y0, x1 - x0, y1 - y0)
    medidas = MedidasBlob(
        centro_blob_x=cx, centro_blob_y=cy, diametro_blob=2 * raio,
        area_estimada_blob=area, area_caixa=caixa.largura * caixa.altura,
        caixa_recortada_na_borda=original != limites,
        origem_medidas=f"{config.metodo}_sigma", sigma_blob=sigma,
    )
    return Deteccao(config.classificacao.classificar(area), caixa, medidas)


def detectar_escala(imagem: np.ndarray, config: ConfiguracaoEscalaBlobs) -> ResultadoDeteccao:
    """Detecta LoG/DoG, preservando sigma bruto, ordem determinística e entrada."""
    parametros = parametros_escala(config)
    cinza = _imagem_cinza(imagem)
    normalizada = cinza.astype(np.float64) / 255.0
    if config.polaridade == "escuro":
        normalizada = 1.0 - normalizada
    try:
        from skimage.feature import blob_dog, blob_log
    except ImportError as erro:
        raise RuntimeError("LoG/DoG exigem scikit-image, listado em requirements-blobs.txt.") from erro
    backend = blob_log if config.metodo == "log" else blob_dog
    pontos = np.asarray(backend(normalizada, **parametros))
    if pontos.ndim != 2 or pontos.shape[1] != 3:
        raise ValueError("O backend deve retornar uma matriz de três colunas (y, x, sigma).")
    altura, largura = cinza.shape
    deteccoes = [_deteccao_escala(ponto, largura, altura, config) for ponto in pontos]
    deteccoes.sort(key=lambda deteccao: (
        deteccao.caixa.y, deteccao.caixa.x, deteccao.medidas.centro_blob_y,
        deteccao.medidas.centro_blob_x, deteccao.medidas.diametro_blob, int(deteccao.classe),
    ))
    return ResultadoDeteccao("blobs", largura, altura, tuple(deteccoes), None)
