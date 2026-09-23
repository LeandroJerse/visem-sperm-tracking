"""Round3: duas grades fatoriais completas, sem consulta a resultados na geração."""

from copy import deepcopy
from pathlib import Path
import sys

from scripts.blobs import planejamento as p
from scripts.blobs.planejamento_round2 import ORIGEM_ROUND1, validar_origem_round1


ORIGEM_ROUND2 = "scripts/blobs/rodadas/round2.json"
ARQUIVO_GERADOR = "scripts/blobs/planejamento_round3.py"
VERSAO_GERADOR = "3.0"
PROCEDIMENTO = "grades_fatoriais_completas_sem_sorteio"
ORDEM_BLOCOS = ("simpleblob", "escala")
FATORES = {
    "simpleblob": {"area_minima": [32, 48, 64], "distancia_minima": [6, 12],
                   "margem_pixels": [3, 4]},
    "escala": {"metodo": ["log", "dog"], "limiar_resposta": [0.05, 0.08, 0.12],
               "margem_pixels": [4, 6]},
}
REFERENCIAS_BASE = {"simpleblob": "r2c01", "log": "r2c28", "dog": "r2c32"}
CONTROLES = {(32, 6, 4): "r2c14", (32, 12, 3): "r2c06",
             (32, 12, 4): "r2c01", (48, 12, 4): "r2c11"}
IDS_CONTROLES = {"r3c02": "r2c14", "r3c03": "r2c06",
                "r3c04": "r2c01", "r3c08": "r2c11"}
LIMITES = {"configuracoes_distintas_anteriores": 76,
           "configuracoes_distintas_acumuladas": 96,
           "limite_configuracoes_distintas": 122, "limite_execucoes_configuracao": 136}


def _montar_configuracoes(referencias: dict) -> list[dict]:
    itens = []

    def incluir(origem, referencia, bloco, parametros, caixa):
        itens.append({
            "id": f"r3c{len(itens) + 1:02d}", "bloco": bloco,
            "perfil_forma": origem["perfil_forma"], "referencia": referencia,
            "metodo": origem["metodo"], "preprocessamento": deepcopy(origem["preprocessamento"]),
            "parametros": parametros, "caixa": caixa,
        })

    base = referencias[REFERENCIAS_BASE["simpleblob"]]
    for area in FATORES["simpleblob"]["area_minima"]:
        for distancia in FATORES["simpleblob"]["distancia_minima"]:
            for margem in FATORES["simpleblob"]["margem_pixels"]:
                parametros = deepcopy(base["parametros"])
                parametros.update(area_minima=area, distancia_minima=distancia)
                controle = CONTROLES.get((area, distancia, margem))
                incluir(base, controle or REFERENCIAS_BASE["simpleblob"],
                        "controle" if controle else "exploracao", parametros,
                        {"modo": "margem", "pixels": margem})
    for metodo in FATORES["escala"]["metodo"]:
        referencia = REFERENCIAS_BASE[metodo]
        base = referencias[referencia]
        for limiar in FATORES["escala"]["limiar_resposta"]:
            for margem in FATORES["escala"]["margem_pixels"]:
                parametros = deepcopy(base["parametros"])
                parametros["limiar_resposta"] = limiar
                incluir(base, referencia, "exploracao", parametros,
                        {"modo": "margem", "pixels": margem})
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
                     "ordem_fatores", "fatores", "quantidade_controles",
                     "quantidade_exploratorias", "quantidade_simpleblob", "quantidade_escala",
                     "referencias_base", "controles_repetidos", "identidades_round1",
                     "identidades_round2", *LIMITES}, "geracao round3")
    p._hash_valido(dados["sha256_gerador"])
    p._texto(dados["python"])
    esperados = {
        "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
        "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
        "ordem_blocos": list(ORDEM_BLOCOS),
        "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": FATORES,
        "quantidade_controles": 4, "quantidade_exploratorias": 20,
        "quantidade_simpleblob": 12, "quantidade_escala": 12,
        "referencias_base": REFERENCIAS_BASE, "controles_repetidos": IDS_CONTROLES, **LIMITES,
    }
    for campo, valor in esperados.items():
        if dados[campo] != valor or type(dados[campo]) is not type(valor):
            raise ValueError(f"Metadado {campo} diverge do desenho aprovado para o round3.")
    antigas = _validar_identidades(dados["identidades_round1"], "r1", 48)
    recentes = _validar_identidades(dados["identidades_round2"], "r2", 32)
    if len(antigas | recentes) != LIMITES["configuracoes_distintas_anteriores"]:
        raise ValueError("As origens devem reunir 76 configurações distintas.")


def validar_desenho_round3(plano: dict) -> None:
    """Confere fatores, ordem, controles e orçamento sem abrir fontes ou imagens."""
    if plano["rodada"] != "round3":
        raise ValueError("O desenho v3 está preparado somente para o round3.")
    if plano["seed"] != 42:
        raise ValueError("O round3 fatorial registra seed 42; não realiza sorteios.")
    _validar_geracao(plano["geracao"])
    itens = plano["configuracoes"]
    recentes = plano["geracao"]["identidades_round2"]
    por_id = {item["id"]: item for item in itens}
    for id, referencia in IDS_CONTROLES.items():
        item = por_id[id]
        if item["bloco"] != "controle" or item["referencia"] != referencia:
            raise ValueError("Controle fora da célula fatorial acordada.")
        if p.hash_configuracao(item) != recentes[referencia]:
            raise ValueError("Controle do round3 diverge da identidade do round2.")
    referencias = {"r2c01": por_id["r3c04"]}
    # Nas escalas, a resposta 0,05 preserva o detector da origem. A margem 2
    # é reconstruída somente para validar sua identidade, não para executá-la.
    for id, referencia in (("r3c13", "r2c28"), ("r3c19", "r2c32")):
        origem = deepcopy(por_id[id])
        origem["caixa"] = {"modo": "margem", "pixels": 2}
        if p.hash_configuracao(origem) != recentes[referencia]:
            raise ValueError("Detector de escala diverge da referência histórica do round2.")
        referencias[referencia] = origem
    esperadas = _montar_configuracoes(referencias)
    for item, esperado in zip(itens, esperadas):
        if any(item[k] != esperado[k] for k in ("id", "bloco", "perfil_forma", "referencia", "metodo")):
            raise ValueError("Identificação ou ordem diverge da grade fatorial aprovada.")
        if p.hash_configuracao(item) != p.hash_configuracao(esperado):
            raise ValueError("Parâmetros divergem das células fatoriais aprovadas.")
    anteriores = set(plano["geracao"]["identidades_round1"].values()) | set(recentes.values())
    atuais = {p.hash_configuracao(x) for x in itens}
    controles = {p.hash_configuracao(x) for x in itens if x["bloco"] == "controle"}
    if len(controles) != 4 or atuais & anteriores != controles:
        raise ValueError("Somente os quatro controles acordados podem repetir configurações anteriores.")
    if len(atuais - anteriores) != 20 or len(atuais | anteriores) != 96:
        raise ValueError("O round3 deve acrescentar 20 configurações, totalizando 96 distintas.")


def validar_origens_round3(plano: dict, conteudo_round1: bytes, conteudo_round2: bytes) -> None:
    """Confere a cadeia v1→v2→v3 pelos bytes originais antes de criar saídas."""
    plano = p.carregar_plano(p._serializar(plano))
    if plano["versao"] != 3:
        raise ValueError("A conferência de origens round3 exige plano v3.")
    for campo, conteudo in (("origem_round1", conteudo_round1), ("origem_round2", conteudo_round2)):
        if p._sha256(conteudo) != plano[campo]["sha256"]:
            raise ValueError(f"Hash incompatível com {campo}.")
    round1 = p.carregar_plano(conteudo_round1)
    round2 = p.carregar_plano(conteudo_round2)
    validar_origem_round1(round2, conteudo_round1)
    for campo in ("quadros", "origem_desenvolvimento", "origem_inspecao", "origem_round1"):
        if plano[campo] != round2[campo]:
            raise ValueError("Quadros ou fontes do round3 divergem da cadeia de desenvolvimento.")
    for campo, origem in (("identidades_round1", round1), ("identidades_round2", round2)):
        esperadas = {item["id"]: p.hash_configuracao(item) for item in origem["configuracoes"]}
        if plano["geracao"][campo] != esperadas:
            raise ValueError("Identidades históricas divergem dos planos originais.")


def gerar_round3(conteudo_round1: bytes, conteudo_round2: bytes, seed: int = 42) -> dict:
    """Monta 24 células fatoriais; não grava arquivos nem executa detectores."""
    p._inteiro(seed)
    if seed != 42:
        raise ValueError("O round3 fatorial registra seed 42; não realiza sorteios.")
    round1 = p.carregar_plano(conteudo_round1)
    round2 = p.carregar_plano(conteudo_round2)
    validar_origem_round1(round2, conteudo_round1)
    referencias = {item["id"]: item for item in round2["configuracoes"]}
    plano = {
        "versao": 3, "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": "round3",
        "particao": "desenvolvimento", "seed": seed,
        "origem_desenvolvimento": deepcopy(round2["origem_desenvolvimento"]),
        "origem_inspecao": deepcopy(round2["origem_inspecao"]),
        "origem_round1": {"plano": ORIGEM_ROUND1, "sha256": p._sha256(conteudo_round1)},
        "origem_round2": {"plano": ORIGEM_ROUND2, "sha256": p._sha256(conteudo_round2)},
        "geracao": {
            "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
            "sha256_gerador": p._sha256(Path(__file__).read_bytes()), "python": sys.version.split()[0],
            "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
            "ordem_blocos": list(ORDEM_BLOCOS),
            "ordem_fatores": {k: list(v) for k, v in FATORES.items()}, "fatores": deepcopy(FATORES),
            "quantidade_controles": 4, "quantidade_exploratorias": 20,
            "quantidade_simpleblob": 12, "quantidade_escala": 12,
            "referencias_base": deepcopy(REFERENCIAS_BASE), "controles_repetidos": deepcopy(IDS_CONTROLES),
            "identidades_round1": {x["id"]: p.hash_configuracao(x) for x in round1["configuracoes"]},
            "identidades_round2": {x["id"]: p.hash_configuracao(x) for x in round2["configuracoes"]},
            **LIMITES,
        },
        "quadros": deepcopy(round2["quadros"]), "configuracoes": _montar_configuracoes(referencias),
        "observacoes": [
            "Mesmos 178 quadros, ordem, anotações e hashes das rodadas anteriores; nenhuma entrada original alterada.",
            "r3c01-r3c12 formam a grade SimpleBlobDetector: áreas mínimas 32/48/64, distâncias 6/12 e margens 3/4, nessa ordem de fatores.",
            "Os controles estão nas células r3c02/r3c03/r3c04/r3c08, repetindo respectivamente r2c14/r2c06/r2c01/r2c11; não são as quatro primeiras linhas.",
            "Nos SimpleBlobDetector, somente área mínima, distância e margem variam; demais parâmetros, classificação e ausência de CLAHE preservam r2c01.",
            "Área 64 explora filtragem mais restritiva; a melhora anterior de área e distância separadamente não garante melhora conjunta.",
            "r3c13-r3c18 usam LoG e r3c19-r3c24 usam DoG: respostas 0,05/0,08/0,12 e margens 4/6, nessa ordem, todas novas configurações.",
            "LoG mantém a referência r2c28 e DoG r2c32, alterando somente resposta e margem; essas referências históricas não tornam as variantes controles repetidos.",
            "Margens 4 e 6 investigam insuficiência e excesso da caixa em candidatos já existentes; não alteram centro, sigma, diâmetro, área circular estimada ou classe.",
            "A comparação histórica com resposta 0,05 e margem 2 exige conferir entradas, versões, parâmetros efetivos e candidatos brutos por quadro antes de atribuir diferenças somente à caixa.",
            "Escalas preservadas: sigma mínimo 2 e máximo solicitado 12; LoG com dez escalas lineares, DoG com razão 1,6; sobreposição 0,5, polaridade clara, sem CLAHE.",
            "A grade DoG atual termina em sigma 8,192, abaixo do diâmetro 24 exigido para classe 1; o round3 não amplia essa grade para investigar aglomerados.",
            "Comparações fatoriais mantêm os demais fatores fixos; interações são examinadas por diferenças pareadas, sem tratar os 178 frames como observações independentes.",
            "Seed 42 registrada; não há sorteio. A lista congelada, os planos de origem e as versões preservadas definem a reprodução.",
            "São 24 configurações por 178 quadros: 4272 avaliações, quatro repetições e 20 novas; 96 distintas acumuladas, teto 122 distintas e 136 configurações nas cinco rodadas.",
            "Mantidos F1 de indivíduos por contagens somadas, IoU >= 0,50, classes 0/2 agrupadas, aglomerados e classificação separados; não seleciona finalistas.",
            "Após o round3, analisar resultados antes de definir round4 e round5. O documento explicativo completo permanece previsto após o round5, antes da seleção e dos vídeos.",
        ],
    }
    plano = p.carregar_plano(p._serializar(plano))
    validar_origens_round3(plano, conteudo_round1, conteudo_round2)
    return plano
