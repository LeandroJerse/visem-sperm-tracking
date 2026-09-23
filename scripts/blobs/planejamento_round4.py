"""Round4: refinamento fatorial com controles de reprodução das três variantes."""

from copy import deepcopy
from pathlib import Path
import sys

from scripts.blobs import planejamento as p
from scripts.blobs.planejamento_round2 import ORIGEM_ROUND1
from scripts.blobs.planejamento_round3 import ORIGEM_ROUND2, validar_origens_round3


ORIGEM_ROUND3 = "scripts/blobs/rodadas/round3.json"
ARQUIVO_GERADOR = "scripts/blobs/planejamento_round4.py"
VERSAO_GERADOR = "4.0"
PROCEDIMENTO = "grades_fatoriais_completas_sem_sorteio"
ORDEM_BLOCOS = ("simpleblob", "dog", "log")
FATORES = {
    "simpleblob": {"area_minima": [48, 64, 80], "margem_pixels": [2, 3]},
    "dog": {"limiar_resposta": [0.12, 0.16, 0.20, 0.24], "margem_pixels": [6, 8]},
    "log": {"limiar_resposta": [0.08, 0.12], "margem_pixels": [5, 6]},
}
REFERENCIAS_BASE = {"simpleblob": "r3c09", "dog": "r3c24", "log": "r3c18"}
CONTROLES = {("simpleblob", 48, 3): "r3c05", ("simpleblob", 64, 3): "r3c09",
             ("dog", 0.12, 6): "r3c24", ("log", 0.08, 6): "r3c16",
             ("log", 0.12, 6): "r3c18"}
IDS_CONTROLES = {"r4c02": "r3c05", "r4c04": "r3c09", "r4c07": "r3c24",
                "r4c16": "r3c16", "r4c18": "r3c18"}
LIMITES = {"configuracoes_distintas_anteriores": 96,
           "configuracoes_distintas_acumuladas": 109,
           "limite_configuracoes_distintas": 122, "limite_execucoes_configuracao": 136,
           "quantidade_prevista_round5": 14, "limite_novas_round5": 13}


def _montar_configuracoes(referencias: dict) -> list[dict]:
    itens = []
    for metodo in ORDEM_BLOCOS:
        base = referencias[REFERENCIAS_BASE[metodo]]
        fator = "area_minima" if metodo == "simpleblob" else "limiar_resposta"
        for valor in FATORES[metodo][fator]:
            for margem in FATORES[metodo]["margem_pixels"]:
                parametros = deepcopy(base["parametros"])
                parametros[fator] = valor
                controle = CONTROLES.get((metodo, valor, margem))
                itens.append({
                    "id": f"r4c{len(itens) + 1:02d}",
                    "bloco": "controle" if controle else "exploracao",
                    "perfil_forma": base["perfil_forma"],
                    "referencia": controle or REFERENCIAS_BASE[metodo],
                    "metodo": base["metodo"],
                    "preprocessamento": deepcopy(base["preprocessamento"]),
                    "parametros": parametros, "caixa": {"modo": "margem", "pixels": margem},
                })
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
                     "procedimento", "aleatoriedade_utilizada", "ordem_blocos",
                     "ordem_fatores", "fatores", "quantidade_controles", "quantidade_exploratorias",
                     "quantidade_simpleblob", "quantidade_dog", "quantidade_log", "quantidade_escala",
                     "referencias_base", "controles_repetidos", "identidades_round1",
                     "identidades_round2", "identidades_round3", *LIMITES}, "geracao round4")
    p._hash_valido(dados["sha256_gerador"])
    p._texto(dados["python"])
    esperados = {
        "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
        "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
        "ordem_blocos": list(ORDEM_BLOCOS),
        "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": FATORES,
        "quantidade_controles": 5, "quantidade_exploratorias": 13,
        "quantidade_simpleblob": 6, "quantidade_dog": 8, "quantidade_log": 4,
        "quantidade_escala": 12,
        "referencias_base": REFERENCIAS_BASE, "controles_repetidos": IDS_CONTROLES, **LIMITES,
    }
    for campo, valor in esperados.items():
        if dados[campo] != valor or type(dados[campo]) is not type(valor):
            raise ValueError(f"Metadado {campo} diverge do desenho aprovado para o round4.")
    conjuntos = [_validar_identidades(dados[f"identidades_round{i}"], f"r{i}", quantidade)
                 for i, quantidade in ((1, 48), (2, 32), (3, 24))]
    if len(conjuntos[0] | conjuntos[1]) != 76 or len(set.union(*conjuntos)) != 96:
        raise ValueError("As origens devem preservar 76 distintas após round2 e 96 após round3.")


def validar_desenho_round4(plano: dict) -> None:
    """Confere as 18 células e seu orçamento sem abrir fontes ou executar imagens."""
    if plano["rodada"] != "round4":
        raise ValueError("O desenho v4 está preparado somente para o round4.")
    if plano["seed"] != 42:
        raise ValueError("O round4 fatorial registra seed 42; não realiza sorteios.")
    _validar_geracao(plano["geracao"])
    itens = plano["configuracoes"]
    por_id = {item["id"]: item for item in itens}
    recentes = plano["geracao"]["identidades_round3"]
    for id, referencia in IDS_CONTROLES.items():
        item = por_id[id]
        if item["bloco"] != "controle" or item["referencia"] != referencia:
            raise ValueError("Controle fora da célula fatorial acordada.")
        if p.hash_configuracao(item) != recentes[referencia]:
            raise ValueError("Controle do round4 diverge da identidade do round3.")
    referencias = {"r3c09": por_id["r4c04"], "r3c24": por_id["r4c07"],
                   "r3c18": por_id["r4c18"]}
    esperadas = _montar_configuracoes(referencias)
    for item, esperado in zip(itens, esperadas):
        if any(item[k] != esperado[k] for k in ("id", "bloco", "perfil_forma", "referencia", "metodo")):
            raise ValueError("Identificação ou ordem diverge das grades aprovadas para round4.")
        if p.hash_configuracao(item) != p.hash_configuracao(esperado):
            raise ValueError("Parâmetros divergem das células fatoriais aprovadas para round4.")
    anteriores = set().union(*(set(plano["geracao"][f"identidades_round{i}"].values())
                               for i in (1, 2, 3)))
    atuais = {p.hash_configuracao(item) for item in itens}
    controles = {p.hash_configuracao(item) for item in itens if item["bloco"] == "controle"}
    if len(controles) != 5 or atuais & anteriores != controles:
        raise ValueError("Somente os cinco controles acordados podem repetir configurações anteriores.")
    if len(atuais - anteriores) != 13 or len(atuais | anteriores) != 109:
        raise ValueError("O round4 deve acrescentar 13 configurações, totalizando 109 distintas.")


def validar_origens_round4(plano: dict, conteudo_round1: bytes, conteudo_round2: bytes,
                          conteudo_round3: bytes) -> None:
    """Vincula o round4 à cadeia completa de planos e bytes anteriores."""
    plano = p.carregar_plano(p._serializar(plano))
    if plano["versao"] != 4:
        raise ValueError("A conferência de origens round4 exige plano v4.")
    conteudos = (conteudo_round1, conteudo_round2, conteudo_round3)
    for i, conteudo in enumerate(conteudos, 1):
        if p._sha256(conteudo) != plano[f"origem_round{i}"]["sha256"]:
            raise ValueError(f"Hash incompatível com origem_round{i}.")
    origens = [p.carregar_plano(conteudo) for conteudo in conteudos]
    validar_origens_round3(origens[2], conteudo_round1, conteudo_round2)
    for campo in ("quadros", "origem_desenvolvimento", "origem_inspecao", "origem_round1", "origem_round2"):
        if plano[campo] != origens[2][campo]:
            raise ValueError("Quadros ou fontes do round4 divergem da cadeia de desenvolvimento.")
    for i, origem in enumerate(origens, 1):
        identidades = {item["id"]: p.hash_configuracao(item) for item in origem["configuracoes"]}
        if plano["geracao"][f"identidades_round{i}"] != identidades:
            raise ValueError("Identidades históricas divergem dos planos originais.")


def gerar_round4(conteudo_round1: bytes, conteudo_round2: bytes, conteudo_round3: bytes,
                 seed: int = 42) -> dict:
    """Monta 18 células sem sortear parâmetros, gravar arquivos ou executar detectores."""
    p._inteiro(seed)
    if seed != 42:
        raise ValueError("O round4 fatorial registra seed 42; não realiza sorteios.")
    conteudos = (conteudo_round1, conteudo_round2, conteudo_round3)
    origens = [p.carregar_plano(conteudo) for conteudo in conteudos]
    round3 = origens[2]
    validar_origens_round3(round3, conteudo_round1, conteudo_round2)
    referencias = {item["id"]: item for item in round3["configuracoes"]}
    plano = {
        "versao": 4, "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": "round4",
        "particao": "desenvolvimento", "seed": seed,
        "origem_desenvolvimento": deepcopy(round3["origem_desenvolvimento"]),
        "origem_inspecao": deepcopy(round3["origem_inspecao"]),
        "origem_round1": {"plano": ORIGEM_ROUND1, "sha256": p._sha256(conteudo_round1)},
        "origem_round2": {"plano": ORIGEM_ROUND2, "sha256": p._sha256(conteudo_round2)},
        "origem_round3": {"plano": ORIGEM_ROUND3, "sha256": p._sha256(conteudo_round3)},
        "geracao": {
            "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
            "sha256_gerador": p._sha256(Path(__file__).read_bytes()), "python": sys.version.split()[0],
            "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
            "ordem_blocos": list(ORDEM_BLOCOS),
            "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": deepcopy(FATORES),
            "quantidade_controles": 5, "quantidade_exploratorias": 13,
            "quantidade_simpleblob": 6, "quantidade_dog": 8, "quantidade_log": 4,
            "quantidade_escala": 12,
            "referencias_base": deepcopy(REFERENCIAS_BASE), "controles_repetidos": deepcopy(IDS_CONTROLES),
            **{f"identidades_round{i}": {x["id"]: p.hash_configuracao(x) for x in origem["configuracoes"]}
               for i, origem in enumerate(origens, 1)},
            **LIMITES,
        },
        "quadros": deepcopy(round3["quadros"]), "configuracoes": _montar_configuracoes(referencias),
        "observacoes": [
            "Mesmos 178 quadros, ordem, anotações e hashes das três rodadas anteriores; nenhuma entrada original alterada.",
            "r4c01-r4c06: SimpleBlobDetector a partir de r3c09, áreas mínimas 48/64/80 e margens 2/3, fixando distância 6 e demais parâmetros.",
            "O cruzamento de área e margem investiga a interação observada; área 80 é hipótese de filtragem, não garantia de melhora ou preservação de recall.",
            "r4c07-r4c14: DoG a partir de r3c24, respostas 0,12/0,16/0,20/0,24 e margens 6/8; demais parâmetros e classificação preservados.",
            "A grade DoG verifica respostas mais restritivas e expansão das caixas; ambas podem perder acertos, por isso os fatores são comparados mantendo o outro fixo.",
            "r4c15-r4c18: LoG a partir de r3c18, respostas 0,08/0,12 e margens 5/6; a resposta 0,08 mantém uma frente de cobertura de pequenos.",
            "A margem 5 do LoG investiga excesso geométrico das caixas nos candidatos já disponíveis; não aumenta sigma nem altera medidas brutas.",
            "Controles r4c02/r4c04/r4c07/r4c16/r4c18 repetem respectivamente r3c05/r3c09/r3c24/r3c16/r3c18, preservando também método e pré-processamento.",
            "A classificação mantém as áreas circulares estimadas e limites de cada referência; a adaptação da caixa não altera centro, sigma, diâmetro ou classe.",
            "Sem CLAHE, nova polaridade, fusão ou aprendizado nesta rodada. LoG mantém dez escalas lineares; DoG razão 1,6; sigma mínimo 2, máximo solicitado 12 e sobreposição 0,5.",
            "A limitação de DoG para classe 1 permanece: sua grade termina em sigma 8,192 e não alcança o diâmetro 24 de classificação de aglomerados.",
            "Seed 42 registrada; geração e execução não sorteiam parâmetros. Os planos congelados, a cadeia de fontes e as versões definem a reprodução.",
            "São 18 configurações por 178 quadros: 3204 avaliações, cinco repetições e 13 novas; 109 distintas acumuladas, teto 122 distintas e 136 configurações nas cinco rodadas.",
            "Round5 permanece limitado a 14 configurações, com no máximo 13 novas para respeitar o teto; não é obrigatório atingir 122 distintas.",
            "Mantidos F1 de indivíduos por contagens somadas, IoU >= 0,50, classes 0/2 agrupadas, aglomerados e classificação separados; não seleciona finalistas.",
            "A análise mantém diferenças pareadas por vídeo e bootstrap exploratório, sem tratar os 178 frames como independentes ou decidir por intervalos de confiança isolados.",
            "Analisar o round4 antes de definir round5. O documento explicativo completo permanece previsto após round5, antes da seleção e dos vídeos.",
        ],
    }
    plano = p.carregar_plano(p._serializar(plano))
    validar_origens_round4(plano, *conteudos)
    return plano
