"""Plano dirigido do round2, congelado antes da execução dos detectores.

O round1 define as referências. As novas hipóteses separam geometria, filtros,
contraste e métodos de escala; nenhum resultado é consultado durante a geração.
"""

from copy import deepcopy
from math import pi
from pathlib import Path
import sys

from scripts.blobs import planejamento as p


ORIGEM_ROUND1 = "scripts/blobs/rodadas/round1.json"
ARQUIVO_GERADOR = "scripts/blobs/planejamento_round2.py"
VERSAO_GERADOR = "2.0"
PROCEDIMENTO = "grade_dirigida_sem_sorteio"
REFERENCIAS = ("r1c29", "r1c23", "r1c26", "r1c43")
ORDEM_BLOCOS = ("controles", "refinamentos_simpleblob", "clahe_pareado", "escala")
LIMITES = {"configuracoes_distintas_acumuladas": 76,
           "limite_configuracoes_distintas": 122, "limite_execucoes_configuracao": 136}
REFINAMENTOS = (
    ("r1c29", "caixa", "pixels", 2),
    ("r1c29", "caixa", "pixels", 3),
    ("r1c29", "caixa", "pixels", 5),
    ("r1c29", "caixa", "pixels", 6),
    ("r1c29", "parametros", "area_minima", 8),
    ("r1c29", "parametros", "area_minima", 16),
    ("r1c29", "parametros", "area_minima", 48),
    ("r1c29", "parametros", "inercia_minima", 0.2),
    ("r1c29", "parametros", "inercia_minima", None),
    ("r1c29", "parametros", "distancia_minima", 6),
    ("r1c43", "parametros", "area_minima", 8),
    ("r1c43", "parametros", "inercia_minima", 0.2),
)


def _perfil(parametros: dict) -> str:
    filtros = {chave: parametros[chave] for chave in p.FILTROS}
    for nome, valores in p.PERFIS.items():
        if filtros == valores:
            return nome
    raise ValueError("Filtro de forma fora dos refinamentos aprovados.")


def _montar_configuracoes(referencias: dict) -> list[dict]:
    resultado = []

    def incluir(referencia, *, bloco="exploracao", metodo="simpleblob",
                parametros=None, caixa=None, preprocessamento=None):
        origem = referencias[referencia] if referencia is not None else {}
        parametros = deepcopy(parametros if parametros is not None else origem["parametros"])
        resultado.append({
            "id": f"r2c{len(resultado) + 1:02d}", "bloco": bloco,
            "perfil_forma": _perfil(parametros) if metodo == "simpleblob" else "escala",
            "referencia": referencia, "parametros": parametros,
            "caixa": deepcopy(caixa if caixa is not None else origem["caixa"]),
            "metodo": metodo,
            "preprocessamento": deepcopy(preprocessamento or {"metodo": "nenhum"}),
        })

    for referencia in REFERENCIAS:
        incluir(referencia, bloco="controle")
    for referencia, secao, campo, valor in REFINAMENTOS:
        variante = deepcopy(referencias[referencia])
        variante[secao][campo] = valor
        incluir(referencia, parametros=variante["parametros"], caixa=variante["caixa"])
    for referencia in REFERENCIAS:
        for contraste in (1.0, 2.0):
            incluir(referencia, preprocessamento={
                "metodo": "clahe", "limite_contraste": contraste, "grade": [8, 8],
            })
    for metodo in ("log", "dog"):
        for limiar in (0.02, 0.05):
            for caixa in ({"modo": "original"}, {"modo": "margem", "pixels": 2}):
                parametros = {
                    "polaridade": "claro", "sigma_minimo": 2.0, "sigma_maximo": 12.0,
                    "limiar_resposta": limiar, "sobreposicao": 0.5,
                    "classificacao": {"area_maxima_pequeno": pi * 4 ** 2,
                                      "area_minima_aglomerado": pi * 12 ** 2},
                }
                parametros.update({"numero_escalas": 10} if metodo == "log" else {"razao_sigma": 1.6})
                incluir(None, metodo=metodo, parametros=parametros, caixa=caixa)
    return resultado


def _validar_geracao(dados: dict) -> None:
    p._chaves(dados, {"versao_gerador", "arquivo_gerador", "sha256_gerador", "python",
                     "procedimento", "aleatoriedade_utilizada", "ordem_blocos",
                     "quantidade_controles", "quantidade_exploratorias",
                     "quantidade_refinamentos", "quantidade_clahe", "quantidade_escala",
                     "referencias_controle", "identidades_round1", *LIMITES}, "geracao round2")
    for campo in ("versao_gerador", "arquivo_gerador", "python", "procedimento"):
        p._texto(dados[campo])
    p._hash_valido(dados["sha256_gerador"])
    esperados = {
        "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
        "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
        "ordem_blocos": list(ORDEM_BLOCOS), "referencias_controle": list(REFERENCIAS),
        "quantidade_controles": 4, "quantidade_exploratorias": 28,
        "quantidade_refinamentos": 12, "quantidade_clahe": 8, "quantidade_escala": 8,
        **LIMITES,
    }
    for campo, valor in esperados.items():
        if dados[campo] != valor or type(dados[campo]) is not type(valor):
            raise ValueError(f"Metadado {campo} diverge do desenho aprovado para o round2.")
    identidades = dados["identidades_round1"]
    p._chaves(identidades, {f"r1c{i:02d}" for i in range(1, 49)}, "identidades do round1")
    for digest in identidades.values():
        p._hash_valido(digest)
    if len(set(identidades.values())) != 48:
        raise ValueError("As 48 configurações de origem devem ser distintas.")


def validar_desenho_round2(plano: dict) -> None:
    """Confere o desenho v2 sem ler a fonte, imagens ou saídas experimentais."""
    if plano["rodada"] != "round2":
        raise ValueError("O desenho v2 está preparado somente para o round2.")
    if plano["seed"] != 42:
        raise ValueError("O round2 dirigido registra seed 42; não realiza sorteios.")
    _validar_geracao(plano["geracao"])
    controles = plano["configuracoes"][:4]
    referencias = dict(zip(REFERENCIAS, controles))
    anteriores = plano["geracao"]["identidades_round1"]
    for referencia, item in referencias.items():
        if p.hash_configuracao(item) != anteriores[referencia]:
            raise ValueError("Controle do round2 difere da identidade registrada no round1.")
    esperadas = _montar_configuracoes(referencias)
    for item, esperado in zip(plano["configuracoes"], esperadas):
        if any(item[campo] != esperado[campo] for campo in (
                "id", "bloco", "perfil_forma", "referencia", "metodo")):
            raise ValueError("Identificação ou ordem diverge dos blocos aprovados para o round2.")
        if p.hash_configuracao(item) != p.hash_configuracao(esperado):
            raise ValueError("Parâmetros divergem dos refinamentos, pares CLAHE ou escalas aprovados.")
    novos = {p.hash_configuracao(x) for x in plano["configuracoes"][4:]}
    if len(novos) != 28 or novos & set(anteriores.values()):
        raise ValueError("O round2 deve incluir 28 configurações novas sem repetir o round1.")
    acumuladas = set(anteriores.values()) | novos
    if len(acumuladas) != LIMITES["configuracoes_distintas_acumuladas"]:
        raise ValueError("Contagem acumulada de configurações incompatível.")


def validar_origem_round1(plano: dict, conteudo_round1: bytes) -> None:
    """Vincula o v2 aos bytes da origem; o executor chama antes de criar saídas."""
    plano = p.carregar_plano(p._serializar(plano))
    if plano["versao"] != 2:
        raise ValueError("A conferência de origem round1 exige plano v2.")
    if p._sha256(conteudo_round1) != plano["origem_round1"]["sha256"]:
        raise ValueError("Hash do plano round1 diverge da origem declarada.")
    origem = p.carregar_plano(conteudo_round1)
    if origem["versao"] != 1 or origem["rodada"] != "round1":
        raise ValueError("A origem deve ser o plano v1 do round1 de blobs.")
    for campo in ("quadros", "origem_desenvolvimento", "origem_inspecao"):
        if plano[campo] != origem[campo]:
            raise ValueError("Quadros ou fontes do round2 divergem do round1.")
    identidades = {item["id"]: p.hash_configuracao(item) for item in origem["configuracoes"]}
    if plano["geracao"]["identidades_round1"] != identidades:
        raise ValueError("Identidades anteriores divergem do conteúdo original do round1.")


def gerar_round2(conteudo_round1: bytes, seed: int = 42) -> dict:
    """Gera 4 repetições e 28 novas hipóteses; não lê imagens nem grava arquivos."""
    p._inteiro(seed)
    if seed != 42:
        raise ValueError("O round2 dirigido registra seed 42; não realiza sorteios.")
    origem = p.carregar_plano(conteudo_round1)
    if origem["versao"] != 1 or origem["rodada"] != "round1":
        raise ValueError("A origem deve ser o plano v1 do round1 de blobs.")
    referencias = {item["id"]: item for item in origem["configuracoes"] if item["id"] in REFERENCIAS}
    plano = {
        "versao": 2, "algoritmo": "blobs", "etapa": "desenvolvimento",
        "rodada": "round2", "particao": "desenvolvimento", "seed": seed,
        "origem_desenvolvimento": deepcopy(origem["origem_desenvolvimento"]),
        "origem_inspecao": deepcopy(origem["origem_inspecao"]),
        "origem_round1": {"plano": ORIGEM_ROUND1, "sha256": p._sha256(conteudo_round1)},
        "geracao": {
            "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
            "sha256_gerador": p._sha256(Path(__file__).read_bytes()), "python": sys.version.split()[0],
            "procedimento": PROCEDIMENTO, "aleatoriedade_utilizada": False,
            "ordem_blocos": list(ORDEM_BLOCOS), "quantidade_controles": 4,
            "quantidade_exploratorias": 28, "quantidade_refinamentos": 12,
            "quantidade_clahe": 8, "quantidade_escala": 8,
            "referencias_controle": list(REFERENCIAS),
            "identidades_round1": {x["id"]: p.hash_configuracao(x) for x in origem["configuracoes"]},
            **LIMITES,
        },
        "quadros": deepcopy(origem["quadros"]), "configuracoes": _montar_configuracoes(referencias),
        "observacoes": [
            "Mesmos 178 quadros, ordem, anotações e hashes do round1; nenhuma entrada original alterada.",
            "r2c01-r2c04 repetem r1c29, r1c23, r1c26 e r1c43 para controle de reprodução.",
            "r2c05-r2c08 variam somente a margem de r1c29: 2, 3, 5 e 6 pixels; caixas maiores não são presumidas melhores.",
            "r2c09-r2c11 variam somente a área mínima de r1c29: 8, 16 e 48; medem recuperação de candidatos e falsos positivos.",
            "r2c12-r2c13 variam somente a inércia de r1c29: 0,2 e filtro desligado.",
            "r2c14 varia somente a distância mínima de r1c29 para 6 pixels, investigando candidatos próximos.",
            "r2c15 reduz somente a área mínima de r1c43 para 8, investigando perdas de pequenos na polaridade escura.",
            "r2c16 acrescenta somente inércia mínima 0,2 a r1c43, investigando rejeição de falsos positivos.",
            "r2c17-r2c24 aplicam CLAHE às quatro referências com limites 1 e 2 e grade 8x8; detector, caixa e classificação são pareados.",
            "r2c25-r2c28 usam LoG e r2c29-r2c32 usam DoG, claros, sem CLAHE, sigma 2 a 12, resposta 0,02 ou 0,05 e caixa original ou margem 2.",
            "LoG usa 10 escalas; DoG usa razão sigma 1,6; sobreposição 0,5 para ambos. Limites de classificação equivalem a diâmetros 8 e 24 pixels.",
            "Os limites de resposta dos métodos de escala não são limiares de intensidade do SimpleBlobDetector; comparação é entre configurações completas.",
            "Seed 42 é registrada; geração e execução não sorteiam parâmetros. A lista congelada e as versões preservadas definem a reprodução.",
            "São 32 execuções de configuração: 4 repetições e 28 novas, totalizando 76 distintas; teto do estudo 122 distintas e 136 execuções.",
            "F1 de indivíduos com IoU >= 0,50; cobertura de normais e pequenos, aglomerados e classificação permanecem apresentados separadamente.",
            "Desenvolvimento: não seleciona finalistas nem modifica critérios durante a execução. Resultados não são inéditos nem independentes entre frames do mesmo vídeo.",
        ],
    }
    plano = p.carregar_plano(p._serializar(plano))
    validar_origem_round1(plano, conteudo_round1)
    return plano
