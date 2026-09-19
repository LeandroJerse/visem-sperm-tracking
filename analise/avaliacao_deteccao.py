"""Avaliação de caixas anotadas e detectadas, sem leitura ou gravação de arquivos."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real


LIMIAR_IOU = 0.5
CLASSES = (0, 1, 2)


@dataclass(frozen=True, slots=True)
class Objeto:
    """Caixa em pixels, com índice local ao respectivo lado da comparação.

    A origem é o canto superior esquerdo; os limites direito e inferior são
    exclusivos. O índice identifica uma anotação ou detecção, não uma trajetória.
    Os limites da imagem devem ser verificados por quem fornece as caixas.
    """

    indice: int
    classe: int
    x: float
    y: float
    largura: float
    altura: float

    def __post_init__(self) -> None:
        for nome in ("indice", "classe"):
            valor = getattr(self, nome)
            if isinstance(valor, bool) or not isinstance(valor, Integral):
                raise TypeError(f"{nome} deve ser um inteiro.")
        if self.indice < 0:
            raise ValueError("indice deve ser maior ou igual a zero.")
        if self.classe not in CLASSES:
            raise ValueError("classe deve ser 0, 1 ou 2.")
        for nome in ("x", "y", "largura", "altura"):
            valor = getattr(self, nome)
            if isinstance(valor, bool) or not isinstance(valor, Real):
                raise TypeError(f"{nome} deve ser um número real.")
            if not isfinite(valor):
                raise ValueError(f"{nome} deve ser finito.")
        if self.largura <= 0 or self.altura <= 0:
            raise ValueError("largura e altura devem ser positivas.")


def iou(a: Objeto, b: Objeto) -> float:
    """Calcula a área da interseção dividida pela área da união de duas caixas."""
    if not isinstance(a, Objeto) or not isinstance(b, Objeto):
        raise TypeError("As caixas devem ser objetos Objeto.")
    ax, ay, al, aa = map(float, (a.x, a.y, a.largura, a.altura))
    bx, by, bl, ba = map(float, (b.x, b.y, b.largura, b.altura))
    limites = (ax + al, ay + aa, bx + bl, by + ba)
    if not all(isfinite(valor) for valor in limites):
        raise ValueError("As coordenadas excedem a faixa numérica do cálculo de IoU.")
    largura_intersecao = max(0.0, min(limites[0], limites[2]) - max(ax, bx))
    altura_intersecao = max(0.0, min(limites[1], limites[3]) - max(ay, by))
    intersecao = largura_intersecao * altura_intersecao
    uniao = al * aa + bl * ba - intersecao
    if not isfinite(uniao) or uniao <= 0:
        raise ValueError("As áreas excedem a faixa numérica do cálculo de IoU.")
    return intersecao / uniao


def _preparar_objetos(objetos: Iterable[Objeto], nome: str) -> tuple[Objeto, ...]:
    itens = tuple(objetos)
    indices = set()
    for objeto in itens:
        if not isinstance(objeto, Objeto):
            raise TypeError(f"Todos os itens de {nome} devem ser objetos Objeto.")
        if objeto.indice in indices:
            raise ValueError(f"Índice duplicado em {nome}: {objeto.indice}.")
        indices.add(objeto.indice)
    return tuple(sorted(itens, key=lambda objeto: objeto.indice))


def _parear(
    anotacoes: tuple[Objeto, ...],
    deteccoes: tuple[Objeto, ...],
    sobreposicoes: list[list[float]],
    exigir_mesma_classe: bool,
) -> dict:
    pares = []
    if anotacoes and deteccoes:
        from scipy.optimize import linear_sum_assignment

        # Um par adicional vale mais que qualquer diferença possível na soma
        # das IoUs. Entre matchings com a mesma cardinalidade, prevalece a soma.
        bonus = min(len(anotacoes), len(deteccoes)) + 1
        pesos = [
            [
                bonus + sobreposicoes[i][j]
                if sobreposicoes[i][j] >= LIMIAR_IOU
                and (not exigir_mesma_classe or anotacao.classe == deteccao.classe)
                else 0.0
                for j, deteccao in enumerate(deteccoes)
            ]
            for i, anotacao in enumerate(anotacoes)
        ]
        linhas, colunas = linear_sum_assignment(pesos, maximize=True)
        for i, j in zip(linhas, colunas):
            # O solver completa a atribuição retangular com arestas de peso
            # zero; essas arestas não constituem correspondências válidas.
            if pesos[i][j] == 0.0:
                continue
            anotacao, deteccao = anotacoes[i], deteccoes[j]
            pares.append({
                "indice_anotacao": int(anotacao.indice),
                "indice_deteccao": int(deteccao.indice),
                "classe_anotacao": int(anotacao.classe),
                "classe_deteccao": int(deteccao.classe),
                "iou": sobreposicoes[i][j],
            })
    pares.sort(key=lambda par: (par["indice_anotacao"], par["indice_deteccao"]))
    indices_anotacoes = {par["indice_anotacao"] for par in pares}
    indices_deteccoes = {par["indice_deteccao"] for par in pares}
    return {
        "pares": pares,
        "anotacoes_sem_par": [
            int(objeto.indice) for objeto in anotacoes
            if objeto.indice not in indices_anotacoes
        ],
        "deteccoes_sem_par": [
            int(objeto.indice) for objeto in deteccoes
            if objeto.indice not in indices_deteccoes
        ],
    }


def _metricas(tp: int, fp: int, fn: int) -> dict:
    tp, fp, fn = int(tp), int(fp), int(fn)
    denominador_f1 = 2 * tp + fp + fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precisao": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / denominador_f1 if denominador_f1 else None,
        "situacao_f1": "definido" if denominador_f1 else "sem_casos",
    }


def avaliar(anotacoes: Iterable[Objeto], deteccoes: Iterable[Objeto]) -> dict:
    """Avalia uma imagem pelo critério principal e pelo diagnóstico de localização.

    Ambos usam IoU >= 0,50 e correspondências um-para-um. A avaliação principal
    exige classes iguais. O diagnóstico ignora as classes e calcula um novo
    matching independente, sem alterar os resultados principais.

    Os índices de cada lado devem ser únicos e são ordenados antes do matching.
    Em soluções exatamente equivalentes, não há garantia de desempate
    lexicográfico entre versões do solver. A matriz de confusão auxiliar usa
    classes anotadas nas linhas e classes previstas nas colunas, na ordem 0, 1, 2.

    Divisões por zero retornam None. O macro-F1 só existe quando o F1 das três
    classes está definido; nenhuma classe é removida automaticamente da média.
    """
    anotacoes = _preparar_objetos(anotacoes, "anotacoes")
    deteccoes = _preparar_objetos(deteccoes, "deteccoes")
    sobreposicoes = [
        [iou(anotacao, deteccao) for deteccao in deteccoes]
        for anotacao in anotacoes
    ]
    principal = _parear(anotacoes, deteccoes, sobreposicoes, exigir_mesma_classe=True)
    localizacao = _parear(
        anotacoes, deteccoes, sobreposicoes, exigir_mesma_classe=False
    )

    por_classe = {}
    for classe in CLASSES:
        tp = sum(par["classe_anotacao"] == classe for par in principal["pares"])
        fp = sum(1 for objeto in deteccoes if objeto.classe == classe) - tp
        fn = sum(1 for objeto in anotacoes if objeto.classe == classe) - tp
        por_classe[str(classe)] = _metricas(tp, fp, fn)
    f1_classes = [por_classe[str(classe)]["f1"] for classe in CLASSES]
    macro_definido = all(f1 is not None for f1 in f1_classes)
    principal.update({
        "por_classe": por_classe,
        "macro_f1": sum(f1_classes) / len(CLASSES) if macro_definido else None,
        "situacao_macro_f1": "definido" if macro_definido else "classes_sem_casos",
        "totais": {
            nome: sum(metricas[nome] for metricas in por_classe.values())
            for nome in ("tp", "fp", "fn")
        },
    })

    quantidade_pares = len(localizacao["pares"])
    matriz_confusao = [[0 for _ in CLASSES] for _ in CLASSES]
    for par in localizacao["pares"]:
        matriz_confusao[par["classe_anotacao"]][par["classe_deteccao"]] += 1
    classes_corretas = sum(matriz_confusao[classe][classe] for classe in CLASSES)
    localizacao.update({
        "metricas": _metricas(
            quantidade_pares,
            len(deteccoes) - quantidade_pares,
            len(anotacoes) - quantidade_pares,
        ),
        "matriz_confusao_pares": matriz_confusao,
        "pares_com_classe_correta": classes_corretas,
        "pares_com_classe_incorreta": quantidade_pares - classes_corretas,
    })
    return {
        "criterios": {
            "limiar_iou": LIMIAR_IOU,
            "descricao_matching": (
                "Correspondência um-para-um: maximiza o número de pares válidos; "
                "entre soluções de mesma cardinalidade, maximiza a soma das IoUs. "
                "A avaliação principal exige a mesma classe; a localização "
                "refaz o matching ignorando a classe."
            ),
            "politica_sem_casos": (
                "Divisão por zero resulta em null. F1 é 2TP/(2TP+FP+FN), "
                "com null somente se TP=FP=FN=0. Macro-F1 é a média das três "
                "classes e resulta em null se alguma delas estiver sem casos."
            ),
        },
        "principal": principal,
        "localizacao": localizacao,
    }
