"""Detecção por limiarização, morfologia e componentes conectados.

O módulo recebe uma imagem e uma configuração explícita. Não lê arquivos,
não executa lotes e não grava resultados. A classificação inicial usa somente
a área segmentada; forma e intensidade são medidas para análises posteriores.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from .classificacao import ConfiguracaoArea
from .comum import Caixa, Deteccao, MedidasObjeto, ResultadoDeteccao


def _validar_inteiro(nome: str, valor: object, minimo: int) -> None:
    """Exige um inteiro Python, sem aceitar booleanos como números."""
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"{nome} deve ser um inteiro maior ou igual a {minimo}.")


@dataclass(frozen=True)
class ConfiguracaoMorfologia:
    """Uma operação morfológica com elemento estruturante quadrado.

    ``forma`` aceita ``elipse``, ``retangulo`` ou ``cruz``. ``tamanho`` é a
    largura e a altura do elemento, em pixels, e deve ser ímpar. Zero em
    ``iteracoes`` desativa a operação. Nenhum parâmetro é escolhido pelo módulo.
    """

    forma: str
    tamanho: int
    iteracoes: int

    def __post_init__(self) -> None:
        if self.forma not in ("elipse", "retangulo", "cruz"):
            raise ValueError("forma deve ser 'elipse', 'retangulo' ou 'cruz'.")
        _validar_inteiro("tamanho", self.tamanho, 1)
        if self.tamanho % 2 == 0:
            raise ValueError("tamanho deve ser ímpar.")
        _validar_inteiro("iteracoes", self.iteracoes, 0)


@dataclass(frozen=True)
class ConfiguracaoLimiarizacao:
    """Parâmetros explícitos do detector e do classificador por área.

    ``metodo`` aceita ``manual`` ou ``otsu``. ``polaridade='claro'`` seleciona
    pixels acima do limiar; ``'escuro'`` seleciona pixels até o limiar,
    inclusive. ``limiar_manual`` é inteiro de 0 a 255 no método manual e
    obrigatoriamente ``None`` em Otsu.

    A abertura é aplicada antes do fechamento. ``conectividade`` é 4 ou 8.
    Os filtros ``area_minima`` e ``area_maxima`` se referem à quantidade de
    pixels do componente após a morfologia, com ambos os limites inclusivos.
    ``area_maxima=None`` desativa apenas o limite superior. Os limites da
    classificação são independentes desses filtros e vêm de ``classificacao``.
    """

    metodo: str
    polaridade: str
    limiar_manual: int | None
    abertura: ConfiguracaoMorfologia
    fechamento: ConfiguracaoMorfologia
    conectividade: int
    area_minima: int
    area_maxima: int | None
    classificacao: ConfiguracaoArea

    def __post_init__(self) -> None:
        if self.metodo not in ("manual", "otsu"):
            raise ValueError("metodo deve ser 'manual' ou 'otsu'.")
        if self.polaridade not in ("claro", "escuro"):
            raise ValueError("polaridade deve ser 'claro' ou 'escuro'.")
        if self.metodo == "manual":
            _validar_inteiro("limiar_manual", self.limiar_manual, 0)
            if self.limiar_manual > 255:
                raise ValueError("limiar_manual deve estar entre 0 e 255.")
        elif self.limiar_manual is not None:
            raise ValueError("limiar_manual deve ser None no método Otsu.")
        if not isinstance(self.abertura, ConfiguracaoMorfologia):
            raise TypeError("abertura deve ser uma ConfiguracaoMorfologia.")
        if not isinstance(self.fechamento, ConfiguracaoMorfologia):
            raise TypeError("fechamento deve ser uma ConfiguracaoMorfologia.")
        if type(self.conectividade) is not int or self.conectividade not in (4, 8):
            raise ValueError("conectividade deve ser o inteiro 4 ou 8.")
        _validar_inteiro("area_minima", self.area_minima, 1)
        if self.area_maxima is not None:
            _validar_inteiro("area_maxima", self.area_maxima, self.area_minima)
        if not isinstance(self.classificacao, ConfiguracaoArea):
            raise TypeError("classificacao deve ser uma ConfiguracaoArea.")


def _imagem_cinza(imagem: np.ndarray) -> np.ndarray:
    """Valida a entrada e converte BGR para cinza sem alterar a imagem."""
    if not isinstance(imagem, np.ndarray):
        raise TypeError("imagem deve ser um array NumPy.")
    if imagem.dtype != np.uint8:
        raise ValueError("imagem deve ter tipo uint8, com valores de 0 a 255.")
    if imagem.size == 0:
        raise ValueError("imagem não pode ser vazia.")
    if imagem.ndim == 2:
        return imagem
    if imagem.ndim == 3 and imagem.shape[2] == 3:
        return cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    raise ValueError("imagem deve ser cinza 2D ou BGR com exatamente três canais.")


def _aplicar_morfologia(
    mascara: np.ndarray, configuracao: ConfiguracaoMorfologia, operacao: int
) -> np.ndarray:
    """Aplica uma operação sem modificar a máscara recebida."""
    if configuracao.iteracoes == 0:
        return mascara
    formas = {
        "elipse": cv2.MORPH_ELLIPSE,
        "retangulo": cv2.MORPH_RECT,
        "cruz": cv2.MORPH_CROSS,
    }
    elemento = cv2.getStructuringElement(
        formas[configuracao.forma], (configuracao.tamanho, configuracao.tamanho)
    )
    return cv2.morphologyEx(
        mascara, operacao, elemento, iterations=configuracao.iteracoes
    )


def detectar(
    imagem: np.ndarray, config: ConfiguracaoLimiarizacao
) -> ResultadoDeteccao:
    """Detecta e classifica os componentes de uma única imagem.

    A entrada deve ser ``uint8``, cinza 2D ou BGR com três canais. Nenhuma
    alteração é feita nela. Cada componente aceito produz uma caixa em pixels
    e uma classe definida pela área segmentada, sem consultar anotações.

    O centroide considera os pixels do componente após a morfologia. A
    intensidade média usa esses mesmos pixels na imagem cinza original,
    anterior à limiarização e à morfologia. Alongamento é a razão entre o maior
    e o menor lado da caixa; ocupação é a área segmentada dividida pela área da
    caixa. Esses descritores não participam da classificação inicial por área.

    As detecções são ordenadas pelo topo e pela esquerda das caixas. O limiar
    efetivamente utilizado é devolvido também quando calculado por Otsu. Uma
    imagem sem componentes aceitos produz uma tupla vazia de detecções.
    """
    if not isinstance(config, ConfiguracaoLimiarizacao):
        raise TypeError("config deve ser uma ConfiguracaoLimiarizacao.")
    cinza = _imagem_cinza(imagem)
    altura_imagem, largura_imagem = cinza.shape
    tipo_limiar = (
        cv2.THRESH_BINARY if config.polaridade == "claro" else cv2.THRESH_BINARY_INV
    )
    if config.metodo == "otsu":
        tipo_limiar |= cv2.THRESH_OTSU
        # O valor informado é ignorado pelo OpenCV quando THRESH_OTSU está ativo.
        limiar_entrada = 0
    else:
        limiar_entrada = config.limiar_manual
    limiar_utilizado, mascara = cv2.threshold(cinza, limiar_entrada, 255, tipo_limiar)
    mascara = _aplicar_morfologia(mascara, config.abertura, cv2.MORPH_OPEN)
    mascara = _aplicar_morfologia(mascara, config.fechamento, cv2.MORPH_CLOSE)
    quantidade, rotulos, estatisticas, centroides = cv2.connectedComponentsWithStats(
        mascara, connectivity=config.conectividade, ltype=cv2.CV_32S
    )

    deteccoes: list[Deteccao] = []
    # O rótulo zero é o fundo; somente os componentes de primeiro plano contam.
    for rotulo in range(1, quantidade):
        area = int(estatisticas[rotulo, cv2.CC_STAT_AREA])
        if area < config.area_minima:
            continue
        if config.area_maxima is not None and area > config.area_maxima:
            continue
        x = int(estatisticas[rotulo, cv2.CC_STAT_LEFT])
        y = int(estatisticas[rotulo, cv2.CC_STAT_TOP])
        largura = int(estatisticas[rotulo, cv2.CC_STAT_WIDTH])
        altura = int(estatisticas[rotulo, cv2.CC_STAT_HEIGHT])
        area_caixa = largura * altura
        # Restringe a seleção dos pixels à caixa, sem varrer a imagem toda por objeto.
        regiao_rotulos = rotulos[y : y + altura, x : x + largura]
        regiao_cinza = cinza[y : y + altura, x : x + largura]
        intensidade_media = float(regiao_cinza[regiao_rotulos == rotulo].mean())
        medidas = MedidasObjeto(
            area_pixels=area,
            centroide_x=float(centroides[rotulo, 0]),
            centroide_y=float(centroides[rotulo, 1]),
            area_caixa=area_caixa,
            alongamento=max(largura, altura) / min(largura, altura),
            ocupacao=area / area_caixa,
            intensidade_media=intensidade_media,
        )
        deteccoes.append(
            Deteccao(
                classe=config.classificacao.classificar(area),
                caixa=Caixa(x=x, y=y, largura=largura, altura=altura),
                medidas=medidas,
            )
        )
    deteccoes.sort(key=lambda deteccao: (deteccao.caixa.y, deteccao.caixa.x))
    return ResultadoDeteccao(
        algoritmo="limiarizacao",
        largura_imagem=largura_imagem,
        altura_imagem=altura_imagem,
        deteccoes=tuple(deteccoes),
        limiar_utilizado=float(limiar_utilizado),
    )
