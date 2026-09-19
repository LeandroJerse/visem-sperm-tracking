"""Agregação de avaliações por quadro, sem leitura ou gravação de arquivos."""

from collections.abc import Iterable
from copy import deepcopy
from numbers import Integral

from analise.avaliacao_deteccao import CLASSES, _metricas


def _contagem(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, Integral):
        raise TypeError(f"{campo} deve ser um inteiro.")
    if valor < 0:
        raise ValueError(f"{campo} não pode ser negativo.")
    return int(valor)


def agregar(resultados: Iterable[dict]) -> dict:
    """Reúne resultados de ``avaliar`` e recalcula métricas pelas contagens.

    TP, FP e FN são somados por classe antes de calcular precisão, recall e F1.
    Uma classe sem casos em um quadro pode ter F1 definido no conjunto. O
    macro-F1 continua exigindo F1 definido para as três classes.

    O diagnóstico de localização é agregado separadamente, preservando seus
    pareamentos independentes. Índices de pares não são concatenados, pois são
    locais a cada imagem. A função não modifica os resultados recebidos.

    Cabe ao chamador fornecer uma única avaliação por quadro, sempre para a
    mesma configuração. Os critérios de avaliação devem ser iguais em todos
    os resultados. Um conjunto vazio é rejeitado; um quadro vazio é válido.
    """
    quantidade_quadros = 0
    criterios = None
    contagens = {str(classe): {nome: 0 for nome in ("tp", "fp", "fn")}
                 for classe in CLASSES}
    contagens_localizacao = {nome: 0 for nome in ("tp", "fp", "fn")}
    matriz = [[0 for _ in CLASSES] for _ in CLASSES]

    for resultado in resultados:
        if quantidade_quadros == 0:
            criterios = deepcopy(resultado["criterios"])
        elif resultado["criterios"] != criterios:
            raise ValueError("Os critérios de avaliação diferem entre os quadros.")

        for classe in CLASSES:
            origem = resultado["principal"]["por_classe"][str(classe)]
            for nome in ("tp", "fp", "fn"):
                contagens[str(classe)][nome] += _contagem(
                    origem[nome], f"principal.classe_{classe}.{nome}"
                )

        localizacao = resultado["localizacao"]
        metricas_localizacao = {
            nome: _contagem(localizacao["metricas"][nome], f"localizacao.{nome}")
            for nome in ("tp", "fp", "fn")
        }
        matriz_quadro = localizacao["matriz_confusao_pares"]
        if len(matriz_quadro) != len(CLASSES) or any(
            len(linha) != len(CLASSES) for linha in matriz_quadro
        ):
            raise ValueError("A matriz de confusão deve ter três linhas e colunas.")
        matriz_quadro = [
            [_contagem(valor, "matriz_confusao_pares") for valor in linha]
            for linha in matriz_quadro
        ]
        pares = sum(sum(linha) for linha in matriz_quadro)
        corretas = sum(matriz_quadro[classe][classe] for classe in CLASSES)
        if pares != metricas_localizacao["tp"]:
            raise ValueError("A matriz de confusão não corresponde aos pares de localização.")
        for nome, esperado in (
            ("pares_com_classe_correta", corretas),
            ("pares_com_classe_incorreta", pares - corretas),
        ):
            if _contagem(localizacao[nome], nome) != esperado:
                raise ValueError(f"{nome} não corresponde à matriz de confusão.")
        for nome in ("tp", "fp", "fn"):
            contagens_localizacao[nome] += metricas_localizacao[nome]
        for linha in CLASSES:
            for coluna in CLASSES:
                matriz[linha][coluna] += matriz_quadro[linha][coluna]
        quantidade_quadros += 1

    if quantidade_quadros == 0:
        raise ValueError("É necessário fornecer pelo menos uma avaliação de quadro.")

    por_classe = {classe: _metricas(**valores) for classe, valores in contagens.items()}
    f1_classes = [por_classe[str(classe)]["f1"] for classe in CLASSES]
    macro_definido = all(valor is not None for valor in f1_classes)
    classes_corretas = sum(matriz[classe][classe] for classe in CLASSES)
    return {
        "quantidade_quadros": quantidade_quadros,
        "criterios": criterios,
        "principal": {
            "por_classe": por_classe,
            "macro_f1": sum(f1_classes) / len(CLASSES) if macro_definido else None,
            "situacao_macro_f1": "definido" if macro_definido else "classes_sem_casos",
            "totais": {
                nome: sum(valores[nome] for valores in contagens.values())
                for nome in ("tp", "fp", "fn")
            },
        },
        "localizacao": {
            "metricas": _metricas(**contagens_localizacao),
            "matriz_confusao_pares": matriz,
            "pares_com_classe_correta": classes_corretas,
            "pares_com_classe_incorreta": contagens_localizacao["tp"] - classes_corretas,
        },
    }
