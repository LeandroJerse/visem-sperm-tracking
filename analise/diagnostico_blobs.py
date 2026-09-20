"""Diagnóstico geométrico de caixas e centros de blobs já exportados.

Incidência significa somente que o centro bruto pertence à caixa anotada.
Não há pareamento exclusivo, acertos, classificação automática de ruído,
supressão de duplicatas ou alteração das métricas de avaliação.
"""

from math import isclose, isfinite, pi
from numbers import Integral, Real


CAMPOS_CAIXA = (
    "caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px",
)
CAMPOS_ESTIMADOS = (
    "centro_blob_x_px", "centro_blob_y_px", "diametro_blob_px", "area_estimada_blob_px2",
)


def _inteiro(valor, nome: str, minimo: int = 0) -> int:
    if isinstance(valor, bool) or not isinstance(valor, Integral):
        raise TypeError(f"{nome} deve ser inteiro.")
    if valor < minimo:
        raise ValueError(f"{nome} deve ser maior ou igual a {minimo}.")
    return int(valor)


def _real(valor, nome: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, Real):
        raise TypeError(f"{nome} deve ser um número real.")
    try:
        convertido = float(valor)
    except (OverflowError, ValueError) as erro:
        raise ValueError(f"{nome} deve ser finito.") from erro
    if not isfinite(convertido):
        raise ValueError(f"{nome} deve ser finito.")
    return convertido


def _grupo(classe: int) -> str:
    return "aglomerados" if classe == 1 else "individuos"


def _categoria(quantidade: int) -> str:
    return "zero" if quantidade == 0 else "um" if quantidade == 1 else "multiplos"


def _area(caixa: dict) -> float:
    return caixa["caixa_largura_px"] * caixa["caixa_altura_px"]


def _preparar(registros: list[dict], indice: str, largura: int, altura: int) -> list[dict]:
    if not isinstance(registros, list):
        raise TypeError(f"A coleção de {indice} deve ser uma lista.")
    deteccao = indice == "indice_deteccao"
    obrigatorios = {indice, "classe", *CAMPOS_CAIXA}
    if deteccao:
        obrigatorios.update(CAMPOS_ESTIMADOS)
    preparados, indices = [], set()
    for posicao, registro in enumerate(registros):
        if not isinstance(registro, dict):
            raise TypeError(f"{indice}, posição {posicao}: esperado um dicionário.")
        faltantes = obrigatorios - registro.keys()
        if faltantes:
            raise ValueError(f"{indice}, posição {posicao}: campos ausentes {sorted(faltantes)}.")
        numero = _inteiro(registro[indice], indice)
        if numero in indices:
            raise ValueError(f"{indice} repetido: {numero}.")
        indices.add(numero)
        classe = _inteiro(registro["classe"], "classe")
        if classe not in (0, 1, 2):
            raise ValueError("classe deve ser 0, 1 ou 2.")
        copia = {indice: numero, "classe": classe, "grupo": _grupo(classe)}
        copia.update({campo: _real(registro[campo], campo) for campo in CAMPOS_CAIXA})
        x, y, w, h = (copia[campo] for campo in CAMPOS_CAIXA)
        if w <= 0 or h <= 0 or not isfinite(w * h) or w * h <= 0:
            raise ValueError("A caixa deve ter dimensões e área positivas e finitas.")
        if not isfinite(x + w) or not isfinite(y + h):
            raise ValueError("Os limites da caixa devem ser finitos.")
        # Mesma tolerância decimal das anotações normalizadas originais.
        # As coordenadas são preservadas: não há recorte nem deslocamento.
        tolerancia = 0.0 if deteccao else 1e-8
        if (x < -largura * tolerancia or y < -altura * tolerancia
                or x + w > largura * (1 + tolerancia)
                or y + h > altura * (1 + tolerancia)):
            raise ValueError("A caixa ultrapassa as dimensões da imagem.")
        if deteccao:
            copia.update({campo: _real(registro[campo], campo) for campo in CAMPOS_ESTIMADOS})
            cx, cy, diametro, area_estimada = (copia[campo] for campo in CAMPOS_ESTIMADOS)
            if not 0 <= cx < largura or not 0 <= cy < altura:
                raise ValueError("O centro bruto do blob deve pertencer à imagem.")
            if not x <= cx < x + w or not y <= cy < y + h:
                raise ValueError("O centro bruto do blob deve pertencer à sua caixa.")
            if diametro <= 0 or area_estimada <= 0:
                raise ValueError("Diâmetro e área estimada devem ser positivos.")
            raio = diametro / 2
            esperada = pi * (raio * raio)
            if not isfinite(esperada) or not isclose(area_estimada, esperada, rel_tol=1e-12, abs_tol=0.0):
                raise ValueError("A área estimada não corresponde ao diâmetro bruto do blob.")
            if "origem_medidas" in registro:
                if registro["origem_medidas"] != "simpleblob_keypoint":
                    raise ValueError("origem_medidas deve identificar simpleblob_keypoint.")
                copia["origem_medidas"] = registro["origem_medidas"]
        preparados.append(copia)
    return sorted(preparados, key=lambda item: item[indice])


def _iou(a: dict, b: dict) -> float:
    ax, ay, aw, ah = (a[campo] for campo in CAMPOS_CAIXA)
    bx, by, bw, bh = (b[campo] for campo in CAMPOS_CAIXA)
    iw = min(aw, bw, max(0.0, min(ax + aw, bx + bw) - max(ax, bx)))
    ih = min(ah, bh, max(0.0, min(ay + ah, by + bh) - max(ay, by)))
    intersecao = iw * ih
    uniao = _area(a) + _area(b) - intersecao
    if not isfinite(uniao) or uniao <= 0:
        raise ValueError("Área da união fora da faixa numérica do diagnóstico.")
    return intersecao / uniao


def diagnosticar_quadro(
    anotacoes: list[dict], deteccoes: list[dict], largura: int, altura: int,
) -> dict:
    """Inspeciona saídas salvas, sem ler imagens ou chamar o detector/avaliador.

    As caixas são (x, y, largura, altura), em pixels. O teste de incidência usa
    o centro bruto e o intervalo [x, x + largura) × [y, y + altura), ignorando
    classes. Uma detecção pode incidir em várias anotações e vice-versa.

    Os máximos de IoU consideram todas as detecções do universo indicado,
    inclusive aquelas sem centro dentro da anotação. ``None`` indica universo
    vazio; ``0.0`` indica detecções existentes sem sobreposição. Classes 0/2
    formam o grupo indivíduos e 1 forma aglomerados somente nesse diagnóstico
    por grupo. Nenhum máximo atribui correspondência, acerto ou preferência.

    A razão de áreas usa a caixa detectada dividida pela caixa anotada, nunca
    a área estimada do disco. Listas e incidências são ordenadas por índice.
    Os dados de entrada permanecem inalterados.
    """
    largura = _inteiro(largura, "largura", 1)
    altura = _inteiro(altura, "altura", 1)
    _real(largura, "largura")
    _real(altura, "altura")
    anotacoes = _preparar(anotacoes, "indice_anotacao", largura, altura)
    deteccoes = _preparar(deteccoes, "indice_deteccao", largura, altura)
    por_deteccao = {d["indice_deteccao"]: [] for d in deteccoes}
    saida_anotacoes = []
    for anotacao in anotacoes:
        x, y, w, h = (anotacao[campo] for campo in CAMPOS_CAIXA)
        incidencias, ious, ious_grupo = [], [], []
        for deteccao in deteccoes:
            valor_iou = _iou(anotacao, deteccao)
            ious.append(valor_iou)
            mesmo_grupo = anotacao["grupo"] == deteccao["grupo"]
            if mesmo_grupo:
                ious_grupo.append(valor_iou)
            cx, cy = deteccao["centro_blob_x_px"], deteccao["centro_blob_y_px"]
            if x <= cx < x + w and y <= cy < y + h:
                razao = _area(deteccao) / _area(anotacao)
                if not isfinite(razao):
                    raise ValueError("Razão de áreas fora da faixa numérica do diagnóstico.")
                incidencias.append({
                    "indice_deteccao": deteccao["indice_deteccao"],
                    "classe_deteccao": deteccao["classe"],
                    "mesmo_grupo": mesmo_grupo,
                    "razao_area_caixa": razao,
                    "iou": valor_iou,
                })
                por_deteccao[deteccao["indice_deteccao"]].append(anotacao["indice_anotacao"])
        saida_anotacoes.append({
            **anotacao,
            "quantidade_centros": len(incidencias),
            "indices_deteccoes": [x["indice_deteccao"] for x in incidencias],
            "incidencias": incidencias,
            "melhor_iou_qualquer_classe": max(ious, default=None),
            "melhor_iou_mesmo_grupo": max(ious_grupo, default=None),
        })
    saida_deteccoes = []
    for deteccao in deteccoes:
        indices = por_deteccao[deteccao["indice_deteccao"]]
        saida_deteccoes.append({
            **deteccao,
            "quantidade_anotacoes": len(indices),
            "indices_anotacoes": indices,
            "categoria_incidencia": _categoria(len(indices)),
        })
    resumo = {
        "quantidade_anotacoes": len(anotacoes),
        "quantidade_deteccoes": len(deteccoes),
        "quantidade_incidencias": sum(a["quantidade_centros"] for a in saida_anotacoes),
        "anotacoes_por_quantidade_centros": {
            categoria: sum(_categoria(a["quantidade_centros"]) == categoria for a in saida_anotacoes)
            for categoria in ("zero", "um", "multiplos")
        },
        "deteccoes_por_quantidade_anotacoes": {
            categoria: sum(d["categoria_incidencia"] == categoria for d in saida_deteccoes)
            for categoria in ("zero", "um", "multiplos")
        },
        "anotacoes_por_classe": {
            str(classe): sum(a["classe"] == classe for a in anotacoes) for classe in (0, 1, 2)
        },
        "deteccoes_por_classe": {
            str(classe): sum(d["classe"] == classe for d in deteccoes) for classe in (0, 1, 2)
        },
    }
    return {"anotacoes": saida_anotacoes, "deteccoes": saida_deteccoes, "resumo": resumo}
