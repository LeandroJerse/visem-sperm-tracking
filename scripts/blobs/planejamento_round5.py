"""Última rodada de desenvolvimento: refinamentos locais e contraste de classificação."""

from copy import deepcopy
from math import pi
from pathlib import Path
import sys

from scripts.blobs import planejamento as p
from scripts.blobs.planejamento_round2 import ORIGEM_ROUND1
from scripts.blobs.planejamento_round3 import ORIGEM_ROUND2
from scripts.blobs.planejamento_round4 import ORIGEM_ROUND3, validar_origens_round4


ORIGEM_ROUND4 = "scripts/blobs/rodadas/round4.json"
ARQUIVO_GERADOR = "scripts/blobs/planejamento_round5.py"
VERSAO_GERADOR = "5.0"
PROCEDIMENTO = "grades_fatoriais_e_contraste_classificacao_sem_sorteio"
ORDEM_BLOCOS = ("simpleblob", "dog", "log")
FATORES = {
    "simpleblob": {"area_minima": [56, 64, 72], "margem_pixels": [2, 3]},
    "dog": {"limiar_resposta": [0.10, 0.12, 0.14], "margem_pixels": [5, 6]},
    "log": {"diametro_minimo_aglomerado": [24, 28]},
}
REFERENCIAS_BASE = {"simpleblob": "r4c04", "dog": "r4c07", "log": "r4c18"}
CONTROLES_GRADE = {("simpleblob", 64, 2): "r4c03", ("simpleblob", 64, 3): "r4c04",
                   ("dog", 0.12, 6): "r4c07"}
IDS_CONTROLES = {"r5c03": "r4c03", "r5c04": "r4c04", "r5c10": "r4c07", "r5c13": "r4c18"}
LIMITES = {"configuracoes_distintas_anteriores": 109,
           "configuracoes_distintas_acumuladas": 119,
           "limite_configuracoes_distintas": 122,
           "limite_execucoes_configuracao": 136,
           "total_configuracoes_nas_cinco_rodadas": 136}


def _montar_configuracoes(referencias: dict) -> list[dict]:
    itens = []

    def incluir(base, referencia, parametros, caixa, controle=False):
        itens.append({
            "id": f"r5c{len(itens) + 1:02d}", "bloco": "controle" if controle else "exploracao",
            "perfil_forma": base["perfil_forma"], "referencia": referencia,
            "metodo": base["metodo"], "preprocessamento": deepcopy(base["preprocessamento"]),
            "parametros": parametros, "caixa": caixa,
        })

    for metodo in ("simpleblob", "dog"):
        base = referencias[REFERENCIAS_BASE[metodo]]
        fator = "area_minima" if metodo == "simpleblob" else "limiar_resposta"
        for valor in FATORES[metodo][fator]:
            for margem in FATORES[metodo]["margem_pixels"]:
                parametros = deepcopy(base["parametros"])
                parametros[fator] = valor
                referencia = CONTROLES_GRADE.get((metodo, valor, margem))
                incluir(base, referencia or REFERENCIAS_BASE[metodo], parametros,
                        {"modo": "margem", "pixels": margem}, controle=referencia is not None)
    base = referencias[REFERENCIAS_BASE["log"]]
    for diametro in FATORES["log"]["diametro_minimo_aglomerado"]:
        parametros = deepcopy(base["parametros"])
        parametros["classificacao"]["area_minima_aglomerado"] = pi * (diametro / 2) ** 2
        incluir(base, REFERENCIAS_BASE["log"], parametros, deepcopy(base["caixa"]), controle=diametro == 24)
    return itens


def _validar_identidades(dados: dict, prefixo: str, quantidade: int) -> set[str]:
    p._chaves(dados, {f"{prefixo}c{i:02d}" for i in range(1, quantidade + 1)},
              f"identidades {prefixo}")
    for digest in dados.values():
        p._hash_valido(digest)
    identidades = set(dados.values())
    if len(identidades) != quantidade:
        raise ValueError("Identidades repetidas dentro de uma rodada de origem.")
    return identidades


def _validar_geracao(dados: dict) -> None:
    p._chaves(dados, {"versao_gerador", "arquivo_gerador", "sha256_gerador", "python",
                     "procedimento", "aleatoriedade_utilizada", "ordem_blocos", "ordem_fatores",
                     "fatores", "quantidade_controles", "quantidade_exploratorias",
                     "quantidade_simpleblob", "quantidade_dog", "quantidade_log", "quantidade_escala",
                     "referencias_base", "controles_repetidos", "identidades_round1",
                     "identidades_round2", "identidades_round3", "identidades_round4", *LIMITES}, "geracao round5")
    p._hash_valido(dados["sha256_gerador"])
    p._texto(dados["python"])
    esperados = {
        "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
        "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
        "ordem_blocos": list(ORDEM_BLOCOS),
        "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": FATORES,
        "quantidade_controles": 4, "quantidade_exploratorias": 10,
        "quantidade_simpleblob": 6, "quantidade_dog": 6, "quantidade_log": 2, "quantidade_escala": 8,
        "referencias_base": REFERENCIAS_BASE, "controles_repetidos": IDS_CONTROLES, **LIMITES,
    }
    for campo, valor in esperados.items():
        if dados[campo] != valor or type(dados[campo]) is not type(valor):
            raise ValueError(f"Metadado {campo} diverge do desenho aprovado para o round5.")
    acumuladas = set()
    for i, quantidade, total in ((1, 48, 48), (2, 32, 76), (3, 24, 96), (4, 18, 109)):
        acumuladas |= _validar_identidades(dados[f"identidades_round{i}"], f"r{i}", quantidade)
        if len(acumuladas) != total:
            raise ValueError("As identidades históricas divergem do orçamento acumulado das rodadas.")


def validar_desenho_round5(plano: dict) -> None:
    """Confere refinamentos, contraste isolado, controles e orçamento sem ler imagens."""
    if plano["rodada"] != "round5":
        raise ValueError("O desenho v5 está preparado somente para o round5.")
    if plano["seed"] != 42:
        raise ValueError("O round5 registra seed 42; não realiza sorteios.")
    _validar_geracao(plano["geracao"])
    itens = plano["configuracoes"]
    por_id = {item["id"]: item for item in itens}
    recentes = plano["geracao"]["identidades_round4"]
    for id, referencia in IDS_CONTROLES.items():
        item = por_id[id]
        if item["bloco"] != "controle" or item["referencia"] != referencia:
            raise ValueError("Controle fora da posição acordada para o round5.")
        if p.hash_configuracao(item) != recentes[referencia]:
            raise ValueError("Controle do round5 diverge da identidade do round4.")
    referencias = {"r4c04": por_id["r5c04"], "r4c07": por_id["r5c10"], "r4c18": por_id["r5c13"]}
    esperadas = _montar_configuracoes(referencias)
    for item, esperado in zip(itens, esperadas):
        if any(item[k] != esperado[k] for k in ("id", "bloco", "perfil_forma", "referencia", "metodo")):
            raise ValueError("Identificação ou ordem diverge dos blocos aprovados para round5.")
        if p.hash_configuracao(item) != p.hash_configuracao(esperado):
            raise ValueError("Parâmetros divergem dos refinamentos ou do contraste de classificação aprovados.")
    anteriores = set().union(*(set(plano["geracao"][f"identidades_round{i}"].values()) for i in (1, 2, 3, 4)))
    atuais = {p.hash_configuracao(item) for item in itens}
    controles = {p.hash_configuracao(item) for item in itens if item["bloco"] == "controle"}
    if len(controles) != 4 or atuais & anteriores != controles:
        raise ValueError("Somente os quatro controles acordados podem repetir configurações anteriores.")
    if len(atuais - anteriores) != 10 or len(atuais | anteriores) != 119:
        raise ValueError("O round5 deve acrescentar dez configurações, totalizando 119 distintas.")


def validar_origens_round5(plano: dict, conteudo_round1: bytes, conteudo_round2: bytes,
                          conteudo_round3: bytes, conteudo_round4: bytes) -> None:
    """Confere a cadeia completa de fontes v1→v2→v3→v4→v5 pelos bytes originais."""
    plano = p.carregar_plano(p._serializar(plano))
    if plano["versao"] != 5:
        raise ValueError("A conferência de origens round5 exige plano v5.")
    conteudos = (conteudo_round1, conteudo_round2, conteudo_round3, conteudo_round4)
    for i, conteudo in enumerate(conteudos, 1):
        if p._sha256(conteudo) != plano[f"origem_round{i}"]["sha256"]:
            raise ValueError(f"Hash incompatível com origem_round{i}.")
    origens = [p.carregar_plano(conteudo) for conteudo in conteudos]
    validar_origens_round4(origens[3], conteudo_round1, conteudo_round2, conteudo_round3)
    for campo in ("quadros", "origem_desenvolvimento", "origem_inspecao", "origem_round1", "origem_round2", "origem_round3"):
        if plano[campo] != origens[3][campo]:
            raise ValueError("Quadros ou fontes do round5 divergem da cadeia de desenvolvimento.")
    for i, origem in enumerate(origens, 1):
        identidades = {item["id"]: p.hash_configuracao(item) for item in origem["configuracoes"]}
        if plano["geracao"][f"identidades_round{i}"] != identidades:
            raise ValueError("Identidades históricas divergem dos planos originais.")


def gerar_round5(conteudo_round1: bytes, conteudo_round2: bytes, conteudo_round3: bytes,
                 conteudo_round4: bytes, seed: int = 42) -> dict:
    """Monta os 14 testes finais de desenvolvimento sem gravar ou executar detectores."""
    p._inteiro(seed)
    if seed != 42:
        raise ValueError("O round5 registra seed 42; não realiza sorteios.")
    conteudos = (conteudo_round1, conteudo_round2, conteudo_round3, conteudo_round4)
    origens = [p.carregar_plano(conteudo) for conteudo in conteudos]
    round4 = origens[3]
    validar_origens_round4(round4, conteudo_round1, conteudo_round2, conteudo_round3)
    referencias = {item["id"]: item for item in round4["configuracoes"]}
    plano = {
        "versao": 5, "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": "round5",
        "particao": "desenvolvimento", "seed": seed,
        "origem_desenvolvimento": deepcopy(round4["origem_desenvolvimento"]),
        "origem_inspecao": deepcopy(round4["origem_inspecao"]),
        "origem_round1": {"plano": ORIGEM_ROUND1, "sha256": p._sha256(conteudo_round1)},
        "origem_round2": {"plano": ORIGEM_ROUND2, "sha256": p._sha256(conteudo_round2)},
        "origem_round3": {"plano": ORIGEM_ROUND3, "sha256": p._sha256(conteudo_round3)},
        "origem_round4": {"plano": ORIGEM_ROUND4, "sha256": p._sha256(conteudo_round4)},
        "geracao": {
            "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
            "sha256_gerador": p._sha256(Path(__file__).read_bytes()), "python": sys.version.split()[0],
            "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
            "ordem_blocos": list(ORDEM_BLOCOS),
            "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": deepcopy(FATORES),
            "quantidade_controles": 4, "quantidade_exploratorias": 10,
            "quantidade_simpleblob": 6, "quantidade_dog": 6, "quantidade_log": 2, "quantidade_escala": 8,
            "referencias_base": deepcopy(REFERENCIAS_BASE), "controles_repetidos": deepcopy(IDS_CONTROLES),
            **{f"identidades_round{i}": {x["id"]: p.hash_configuracao(x) for x in origem["configuracoes"]}
               for i, origem in enumerate(origens, 1)},
            **LIMITES,
        },
        "quadros": deepcopy(round4["quadros"]), "configuracoes": _montar_configuracoes(referencias),
        "observacoes": [
            "Mesmos 178 quadros, ordem, anotações e hashes das quatro rodadas anteriores; nenhuma entrada original alterada.",
            "r5c01-r5c06: SimpleBlobDetector a partir de r4c04, áreas mínimas 56/64/72 e margens 2/3, fixando distância 6 e todos os demais parâmetros.",
            "As áreas intermediárias investigam a região delimitada e sua interação com a caixa, sem presumir melhora monotônica de precisão ou recall.",
            "r5c07-r5c12: DoG a partir de r4c07, respostas 0,10/0,12/0,14 e margens 5/6; demais parâmetros e classificação preservados.",
            "O DoG refina o interior da faixa de resposta próxima da referência e margens moderadas, depois das perdas nos extremos do round4.",
            "r5c13 repete LoG r4c18: resposta 0,12, margem 6 e limite de aglomerado equivalente ao diâmetro 24.",
            "r5c14 altera somente classificacao.area_minima_aglomerado para pi*14**2, equivalente ao diâmetro 28; detector, resposta, caixa, limite de pequeno e demais parâmetros permanecem iguais.",
            "O contraste LoG investiga a fronteira entre indivíduo e aglomerado. Ganhos de indivíduos e eventuais perdas de aglomerados devem ser apresentados separadamente, sem mudar o critério de ranking.",
            "A alteração de classificação no LoG não deve alterar candidatos brutos, centro, sigma, diâmetro, área estimada ou caixa. Não é uma correção de anotações.",
            "Controles r5c03/r5c04/r5c10/r5c13 repetem respectivamente r4c03/r4c04/r4c07/r4c18, preservando método e pré-processamento.",
            "Sem CLAHE, nova polaridade, fusão ou aprendizado nesta rodada. LoG mantém dez escalas lineares e DoG razão 1,6; sigma mínimo 2, máximo solicitado 12 e sobreposição 0,5.",
            "A limitação do DoG para classe 1 permanece: sua grade termina em sigma 8,192 e não alcança o diâmetro 24 de classificação de aglomerados.",
            "Seed 42 registrada; não há sorteio. Os planos congelados, a cadeia de fontes e as versões preservadas definem a reprodução.",
            "São 14 configurações por 178 quadros: 2492 avaliações, quatro repetições e dez novas; 119 distintas acumuladas, abaixo do teto 122.",
            "As cinco rodadas reúnem 48+32+24+18+14=136 posições de configuração. Essa contagem não representa amostras biológicas independentes nem inclui reexecuções adicionais.",
            "Mantidos F1 de indivíduos por contagens somadas, IoU >= 0,50, classes 0/2 agrupadas, aglomerados e classificação separados; não seleciona finalistas.",
            "Após analisar o round5, produzir o documento explicativo completo de blobs antes de preparar seleção em outras imagens e testes em vídeos; não executar essas etapas automaticamente.",
        ],
    }
    plano = p.carregar_plano(p._serializar(plano))
    validar_origens_round5(plano, *conteudos)
    return plano
