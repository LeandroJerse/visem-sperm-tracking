"""Conversões explícitas de caixas de blobs, preservando as medidas brutas.

O módulo não consulta anotações, não segmenta imagens e não executa detecção.
Escala e margem partem sempre do centro e diâmetro do keypoint, nunca da
caixa já arredondada ou recortada. As variantes não reclassificam objetos.
"""

from dataclasses import dataclass, replace
from math import ceil, floor, isfinite
from numbers import Real

from .comum import Caixa, MedidasBlob, ResultadoDeteccao


def _real_finito(nome: str, valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, Real):
        raise TypeError(f"{nome} deve ser um número real.")
    try:
        numero = float(valor)
    except (OverflowError, ValueError) as erro:
        raise ValueError(f"{nome} deve ser finito e representável como float.") from erro
    if not isfinite(numero):
        raise ValueError(f"{nome} deve ser finito.")
    return numero


@dataclass(frozen=True, slots=True)
class ConfiguracaoCaixaBlobs:
    """Regra de caixa independente da configuração original do detector.

    ``original`` conserva a saída recebida. ``escala`` usa lado = fator ×
    diâmetro; ``margem`` usa lado = diâmetro + 2 × pixels. Somente o campo
    correspondente ao modo pode estar preenchido. A configuração armazena
    números float; identidades são normalizadas por ``configuracao_canonica``.
    """

    modo: str
    fator: float | None = None
    pixels: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.modo, str) or self.modo not in ("original", "escala", "margem"):
            raise ValueError("modo deve ser 'original', 'escala' ou 'margem'.")
        if self.modo == "original":
            if self.fator is not None or self.pixels is not None:
                raise ValueError("O modo original não recebe fator nem pixels.")
        elif self.modo == "escala":
            if self.pixels is not None:
                raise ValueError("O modo escala não recebe pixels.")
            fator = _real_finito("fator", self.fator)
            if fator <= 0:
                raise ValueError("fator deve ser positivo.")
            object.__setattr__(self, "fator", fator)
        else:
            if self.fator is not None:
                raise ValueError("O modo margem não recebe fator.")
            pixels = _real_finito("pixels", self.pixels)
            if pixels < 0:
                raise ValueError("pixels deve ser maior ou igual a zero.")
            object.__setattr__(self, "pixels", pixels)


def configuracao_caixa_de_dict(dados: dict) -> ConfiguracaoCaixaBlobs:
    """Exige exatamente as chaves do modo, sem alterar o dicionário recebido."""
    if not isinstance(dados, dict):
        raise TypeError("A configuração de caixa deve ser um objeto JSON.")
    if any(not isinstance(chave, str) for chave in dados):
        raise TypeError("As chaves da configuração de caixa devem ser texto.")
    modo = dados.get("modo")
    if not isinstance(modo, str) or modo not in ("original", "escala", "margem"):
        raise ValueError("modo deve ser 'original', 'escala' ou 'margem'.")
    esperadas = {"modo"}
    if modo == "escala":
        esperadas.add("fator")
    elif modo == "margem":
        esperadas.add("pixels")
    if set(dados) != esperadas:
        raise ValueError(
            f"Chaves inválidas para {modo}: ausentes={sorted(esperadas - dados.keys())}, "
            f"extras={sorted(dados.keys() - esperadas)}."
        )
    return ConfiguracaoCaixaBlobs(**dados)


def configuracao_canonica(config: ConfiguracaoCaixaBlobs) -> dict:
    """Identifica configurações equivalentes, incluindo escala 1 e margem 0."""
    if not isinstance(config, ConfiguracaoCaixaBlobs):
        raise TypeError("config deve ser ConfiguracaoCaixaBlobs.")
    if (config.modo == "original" or config.modo == "escala" and config.fator == 1
            or config.modo == "margem" and config.pixels == 0):
        return {"modo": "original"}
    if config.modo == "escala":
        return {"modo": "escala", "fator": config.fator}
    return {"modo": "margem", "pixels": config.pixels}


def adaptar_caixas(
    resultado: ResultadoDeteccao, config: ConfiguracaoCaixaBlobs,
) -> ResultadoDeteccao:
    """Adapta somente caixas, áreas das caixas e indicadores de recorte.

    Preserva a ordem, as classes e os valores brutos dos keypoints. A ordem
    permanece intacta mesmo se o novo tamanho alterar a posição dos cantos,
    mantendo os índices locais produzidos por ``registros``. As caixas usam
    floor/ceil, seguidos de recorte, com limites direito/inferior exclusivos.

    Original, escala 1 e margem 0 devolvem o próprio resultado validado. Uma
    transformação posterior também parte das medidas brutas; não multiplica
    nem soma margens sobre uma caixa anteriormente adaptada. Sem detecções,
    a saída permanece vazia. Não há leitura, gravação ou alteração da entrada.
    """
    if not isinstance(resultado, ResultadoDeteccao):
        raise TypeError("resultado deve ser ResultadoDeteccao.")
    canonica = configuracao_canonica(config)
    if resultado.algoritmo != "blobs" or resultado.limiar_utilizado is not None:
        raise ValueError("A adaptação exige resultado de blobs, sem limiar único.")
    if any(not isinstance(d.medidas, MedidasBlob) for d in resultado.deteccoes):
        raise TypeError("Todas as detecções devem conter MedidasBlob.")
    if canonica["modo"] == "original":
        return resultado

    largura, altura = resultado.largura_imagem, resultado.altura_imagem
    deteccoes = []
    for deteccao in resultado.deteccoes:
        medidas = deteccao.medidas
        diametro = medidas.diametro_blob
        if config.modo == "escala":
            lado = diametro * config.fator
        else:
            lado = diametro + 2 * config.pixels
        if not isfinite(lado) or lado <= 0:
            raise ValueError("O lado adaptado deve ser positivo e finito.")
        raio = lado / 2
        cx, cy = medidas.centro_blob_x, medidas.centro_blob_y
        limites = (cx - raio, cy - raio, cx + raio, cy + raio)
        if not all(isfinite(valor) for valor in limites):
            raise ValueError("Os limites da caixa adaptada excedem a faixa numérica.")
        original = (floor(limites[0]), floor(limites[1]), ceil(limites[2]), ceil(limites[3]))
        x0, y0, x1, y1 = (
            max(0, min(largura, original[0])), max(0, min(altura, original[1])),
            max(0, min(largura, original[2])), max(0, min(altura, original[3])),
        )
        if x1 <= x0 or y1 <= y0:
            raise ValueError("A caixa adaptada não possui dimensões positivas.")
        caixa = Caixa(x0, y0, x1 - x0, y1 - y0)
        # O raio adaptado nunca participa da área circular ou da classificação.
        novas_medidas = replace(
            medidas, area_caixa=caixa.largura * caixa.altura,
            caixa_recortada_na_borda=original != (x0, y0, x1, y1),
        )
        deteccoes.append(replace(deteccao, caixa=caixa, medidas=novas_medidas))
    return replace(resultado, deteccoes=tuple(deteccoes))
