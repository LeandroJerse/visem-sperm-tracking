"""Avaliação de indivíduos (classes 0 e 2) e aglomerados, sem acesso a arquivos."""

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import replace
from numbers import Integral

from analise.avaliacao_deteccao import (
    LIMIAR_IOU,
    Objeto,
    _metricas,
    _parear,
    _preparar_objetos,
    iou,
)


GRUPOS = {"individuos": (0, 2), "aglomerados": (1,)}
CLASSES_INDIVIDUOS = (0, 2)
CRITERIOS = {
    "versao": 1,
    "limiar_iou": LIMIAR_IOU,
    "grupos": {"individuos": [0, 2], "aglomerados": [1]},
    "descricao_matching": (
        "Correspondência um-para-um entre objetos do mesmo grupo, com IoU >= 0,5. "
        "Maximiza o número de pares válidos e depois a soma das IoUs. "
        "A classe original não é critério de desempate."
    ),
    "classificacao": (
        "Trocas entre 0 e 2 são acertos de localização de indivíduos e erros de "
        "classificação. Trocas entre indivíduo e aglomerado não formam pares: "
        "geram FN no grupo anotado e FP no grupo previsto. Os três rótulos "
        "originais são preservados."
    ),
    "matriz_classificacao": (
        "Somente pares de indivíduos; linhas são classes anotadas e colunas "
        "são classes previstas, na ordem [0, 2]. Acurácia condicional aos pares, "
        "sem incluir objetos perdidos ou falsas detecções."
    ),
    "cobertura": (
        "Por classe original da anotação: localizada quando possui par no mesmo "
        "grupo, mesmo que haja troca entre 0 e 2; recall = localizadas/anotacoes."
    ),
    "agregacao": "Somar contagens antes de calcular métricas, sem médias de F1 por quadro.",
    "politica_sem_casos": (
        "Divisão por zero resulta em null. F1 = 2TP/(2TP+FP+FN), com null "
        "somente se TP=FP=FN=0. Previsões sem anotação contam como FP e dão F1 zero."
    ),
}


def _classificacao(matriz: list[list[int]]) -> dict:
    total = sum(sum(linha) for linha in matriz)
    corretos = matriz[0][0] + matriz[1][1]
    return {
        "ordem_classes": list(CLASSES_INDIVIDUOS),
        "matriz_confusao": [linha.copy() for linha in matriz],
        "pares_corretos": corretos,
        "pares_incorretos": total - corretos,
        "total": total,
        "acuracia_condicional": corretos / total if total else None,
    }


def _cobertura(anotacoes: int, localizadas: int) -> dict:
    return {
        "anotacoes": anotacoes,
        "localizadas": localizadas,
        "perdidas": anotacoes - localizadas,
        "recall": localizadas / anotacoes if anotacoes else None,
    }


def avaliar(anotacoes: Iterable[Objeto], deteccoes: Iterable[Objeto]) -> dict:
    """Avalia um quadro por grupo e preserva as classes originais nos pares.

    Apenas cópias das caixas recebem classes 0 (indivíduos) ou 1 (aglomerados)
    para reutilizar o pareamento existente. O pareamento é refeito; os pares de
    avaliações anteriores não são utilizados. Uma caixa só pode formar um par.

    A matriz 2x2 mede classificação entre indivíduos já pareados. Não é acurácia
    sobre todas as anotações. A cobertura mede separadamente quantas anotações
    de cada classe original foram localizadas. Empates exatos de cardinalidade
    e IoU não recebem preferência pela classe original e podem depender do
    solver, como no avaliador de três classes.
    """
    anotacoes = _preparar_objetos(anotacoes, "anotacoes")
    deteccoes = _preparar_objetos(deteccoes, "deteccoes")
    por_indice_anotacao = {objeto.indice: objeto for objeto in anotacoes}
    por_indice_deteccao = {objeto.indice: objeto for objeto in deteccoes}
    anotacoes_agrupadas = tuple(
        replace(objeto, classe=1 if objeto.classe == 1 else 0)
        for objeto in anotacoes
    )
    deteccoes_agrupadas = tuple(
        replace(objeto, classe=1 if objeto.classe == 1 else 0)
        for objeto in deteccoes
    )
    sobreposicoes = [
        [iou(anotacao, deteccao) for deteccao in deteccoes]
        for anotacao in anotacoes
    ]
    pareamento = _parear(
        anotacoes_agrupadas, deteccoes_agrupadas, sobreposicoes,
        exigir_mesma_classe=True,
    )
    pares = []
    matriz = [[0, 0], [0, 0]]
    for par in pareamento["pares"]:
        classe_anotacao = int(por_indice_anotacao[par["indice_anotacao"]].classe)
        classe_deteccao = int(por_indice_deteccao[par["indice_deteccao"]].classe)
        grupo = "aglomerados" if classe_anotacao == 1 else "individuos"
        pares.append({
            **par,
            "classe_anotacao": classe_anotacao,
            "classe_deteccao": classe_deteccao,
            "grupo": grupo,
            "classe_correta": classe_anotacao == classe_deteccao,
        })
        if grupo == "individuos":
            linha = CLASSES_INDIVIDUOS.index(classe_anotacao)
            coluna = CLASSES_INDIVIDUOS.index(classe_deteccao)
            matriz[linha][coluna] += 1

    por_grupo = {}
    for grupo, classes in GRUPOS.items():
        tp = sum(par["grupo"] == grupo for par in pares)
        fp = sum(objeto.classe in classes for objeto in deteccoes) - tp
        fn = sum(objeto.classe in classes for objeto in anotacoes) - tp
        por_grupo[grupo] = _metricas(tp, fp, fn)
    cobertura = {
        str(classe): _cobertura(
            sum(objeto.classe == classe for objeto in anotacoes),
            sum(par["classe_anotacao"] == classe for par in pares),
        )
        for classe in (0, 2, 1)
    }
    return {
        "criterios": deepcopy(CRITERIOS),
        "por_grupo": por_grupo,
        "pares": pares,
        "anotacoes_sem_par": pareamento["anotacoes_sem_par"],
        "deteccoes_sem_par": pareamento["deteccoes_sem_par"],
        "classificacao_individuos": _classificacao(matriz),
        "cobertura_por_classe": cobertura,
    }


def _contagem(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, Integral):
        raise TypeError(f"{campo} deve ser um inteiro.")
    if valor < 0:
        raise ValueError(f"{campo} não pode ser negativo.")
    return int(valor)


def agregar(resultados: Iterable[dict]) -> dict:
    """Soma avaliações por quadro antes de calcular métricas dos dois grupos.

    Recebe uma avaliação por quadro da mesma configuração. Não concatena pares,
    pois seus índices são locais a cada quadro, nem modifica as entradas. Exige
    os critérios desta versão e contagens coerentes entre grupos, cobertura e
    matriz. Uma sequência vazia é rejeitada; um quadro sem objetos é válido.
    """
    quantidade_quadros = 0
    contagens = {grupo: {nome: 0 for nome in ("tp", "fp", "fn")} for grupo in GRUPOS}
    cobertura = {str(classe): {"anotacoes": 0, "localizadas": 0} for classe in (0, 2, 1)}
    matriz = [[0, 0], [0, 0]]
    for resultado in resultados:
        if resultado["criterios"] != CRITERIOS:
            raise ValueError("Os critérios do quadro diferem da avaliação de indivíduos.")
        grupos_quadro = {
            grupo: {
                nome: _contagem(resultado["por_grupo"][grupo][nome], f"{grupo}.{nome}")
                for nome in ("tp", "fp", "fn")
            }
            for grupo in GRUPOS
        }
        cobertura_quadro = {}
        for classe in cobertura:
            origem = resultado["cobertura_por_classe"][classe]
            contagem = {
                nome: _contagem(origem[nome], f"cobertura.classe_{classe}.{nome}")
                for nome in ("anotacoes", "localizadas", "perdidas")
            }
            if contagem["anotacoes"] != contagem["localizadas"] + contagem["perdidas"]:
                raise ValueError("A cobertura não corresponde ao total de anotações.")
            cobertura_quadro[classe] = contagem
        for grupo, classes in GRUPOS.items():
            localizadas = sum(cobertura_quadro[str(c)]["localizadas"] for c in classes)
            perdidas = sum(cobertura_quadro[str(c)]["perdidas"] for c in classes)
            if localizadas != grupos_quadro[grupo]["tp"] or perdidas != grupos_quadro[grupo]["fn"]:
                raise ValueError("A cobertura não corresponde às contagens dos grupos.")

        classificacao = resultado["classificacao_individuos"]
        if classificacao["ordem_classes"] != list(CLASSES_INDIVIDUOS):
            raise ValueError("A ordem da matriz de classificação deve ser [0, 2].")
        matriz_quadro = classificacao["matriz_confusao"]
        if len(matriz_quadro) != 2 or any(len(linha) != 2 for linha in matriz_quadro):
            raise ValueError("A matriz de classificação deve ter duas linhas e colunas.")
        matriz_quadro = [
            [_contagem(valor, "matriz_confusao") for valor in linha]
            for linha in matriz_quadro
        ]
        esperada = _classificacao(matriz_quadro)
        for nome in ("pares_corretos", "pares_incorretos", "total"):
            if _contagem(classificacao[nome], nome) != esperada[nome]:
                raise ValueError(f"{nome} não corresponde à matriz de classificação.")
        if esperada["total"] != grupos_quadro["individuos"]["tp"]:
            raise ValueError("A matriz não corresponde aos pares de indivíduos.")
        for linha, classe in enumerate(CLASSES_INDIVIDUOS):
            if sum(matriz_quadro[linha]) != cobertura_quadro[str(classe)]["localizadas"]:
                raise ValueError("As linhas da matriz não correspondem à cobertura por classe.")

        for grupo in GRUPOS:
            for nome in ("tp", "fp", "fn"):
                contagens[grupo][nome] += grupos_quadro[grupo][nome]
        for classe in cobertura:
            for nome in ("anotacoes", "localizadas"):
                cobertura[classe][nome] += cobertura_quadro[classe][nome]
        for linha in range(2):
            for coluna in range(2):
                matriz[linha][coluna] += matriz_quadro[linha][coluna]
        quantidade_quadros += 1
    if quantidade_quadros == 0:
        raise ValueError("É necessário fornecer pelo menos uma avaliação de quadro.")
    return {
        "quantidade_quadros": quantidade_quadros,
        "criterios": deepcopy(CRITERIOS),
        "por_grupo": {grupo: _metricas(**valores) for grupo, valores in contagens.items()},
        "classificacao_individuos": _classificacao(matriz),
        "cobertura_por_classe": {
            classe: _cobertura(**valores) for classe, valores in cobertura.items()
        },
    }
