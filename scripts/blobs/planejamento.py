"""Planos reproduzíveis de blobs, sem leitura de imagens ou execução do detector.

O carregamento valida o contrato e a composição do plano. A conferência dos
bytes das entradas contra seus hashes cabe ao executor, antes de criar saídas.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from math import isfinite, pi
from pathlib import Path
import random
import re
import sys

from algoritmos.classicos.blobs import configuracao_de_dict, parametros_opencv
from algoritmos.classicos.caixas_blobs import (
    configuracao_caixa_de_dict, configuracao_canonica,
)


ORIGEM_DESENVOLVIMENTO = "scripts/limiarizacao/rodadas/round1.json"
ORIGEM_INSPECAO = "scripts/blobs/inspecao/round0.json"
ARQUIVO_GERADOR = "scripts/blobs/planejamento.py"
VERSAO_GERADOR = "1.0"
ORCAMENTOS = {"round1": 48, "round2": 32, "round3": 24, "round4": 18, "round5": 14}
VIDEOS = ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60")
CHAVES_QUADROS = {(v, q) for v in VIDEOS for q in range(0, 1401, 100)} - {
    ("23", 900), ("23", 1100),
}
CHAVES_INSPECAO = {("11", 0), ("12", 200), ("19", 0), ("21", 0), ("23", 0), ("36", 1300)}
GRUPOS = tuple((p, m) for p in ("claro", "escuro") for m in ("original", "escala", "margem"))
VALORES = {
    "limiar_minimo": [10, 40, 80], "limiar_maximo": [180, 220, 250],
    "passo_limiar": [5, 10, 20], "repetibilidade_minima": [2, 3, 4],
    "distancia_minima": [3, 6, 12], "area_minima": [3, 8, 16, 32],
    "area_maxima": [500, 1500, 5000],
    "diametro_maximo_pequeno": [4, 6, 8, 10],
    "diametro_minimo_aglomerado": [16, 24, 32],
    "fator_escala": [1.5, 2, 2.5, 3, 4], "margem_pixels": [2, 4, 6, 8],
}
FILTROS = ("circularidade_minima", "inercia_minima", "convexidade_minima")
PERFIS = {
    "sem_filtro": dict.fromkeys(FILTROS),
    "circularidade_04": dict(zip(FILTROS, (0.4, None, None))),
    "circularidade_06": dict(zip(FILTROS, (0.6, None, None))),
    "inercia_02": dict(zip(FILTROS, (None, 0.2, None))),
    "inercia_04": dict(zip(FILTROS, (None, 0.4, None))),
    "convexidade_08": dict(zip(FILTROS, (None, None, 0.8))),
}
CAIXAS_CONTROLE = (
    {"modo": "original"}, {"modo": "escala", "fator": 2},
    {"modo": "escala", "fator": 3}, {"modo": "escala", "fator": 4},
    {"modo": "margem", "pixels": 4}, {"modo": "margem", "pixels": 8},
)
LIMITE_TENTATIVAS = 100
PROCEDIMENTO = "amostragem_balanceada_por_grupo_com_regeneracao_integral"


def _chaves(dados: dict, esperadas: set, contexto: str) -> None:
    if not isinstance(dados, dict) or set(dados) != esperadas:
        raise ValueError(f"Chaves inválidas em {contexto}.")


def _objeto_sem_repeticoes(pares: list) -> dict:
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError(f"Chave JSON repetida: {chave}.")
        resultado[chave] = valor
    return resultado


def _json(conteudo: bytes) -> dict:
    if not isinstance(conteudo, bytes):
        raise TypeError("O conteúdo do plano deve ser bytes UTF-8.")
    def rejeitar_constante(valor):
        raise ValueError(f"Número JSON inválido: {valor}.")
    dados = json.loads(conteudo.decode("utf-8"), object_pairs_hook=_objeto_sem_repeticoes,
                       parse_constant=rejeitar_constante)
    if not isinstance(dados, dict):
        raise ValueError("O plano deve ser um objeto JSON.")
    return dados


def _sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _hash_valido(valor) -> None:
    if not isinstance(valor, str) or re.fullmatch(r"[0-9a-f]{64}", valor) is None:
        raise ValueError("Hash SHA-256 inválido.")


def _inteiro(valor, minimo=0) -> None:
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"Esperado inteiro maior ou igual a {minimo}.")


def _texto(valor) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("Esperado texto não vazio.")


def _serializar(dados) -> bytes:
    return json.dumps(dados, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _origem(dados: dict, caminho: str) -> None:
    _chaves(dados, {"plano", "sha256"}, "origem")
    if dados["plano"] != caminho:
        raise ValueError("Plano de origem diferente do acordado.")
    _hash_valido(dados["sha256"])


def _quadros(dados: list, esperados: set = CHAVES_QUADROS) -> None:
    if not isinstance(dados, list) or len(dados) != len(esperados):
        raise ValueError("Quantidade de quadros diferente da composição acordada.")
    encontrados = set()
    for quadro in dados:
        _chaves(quadro, {"video_id", "quadro", "imagem", "anotacao",
                         "imagem_sha256", "anotacao_sha256"}, "quadro")
        if not isinstance(quadro["video_id"], str):
            raise ValueError("video_id deve ser texto.")
        _inteiro(quadro["quadro"])
        chave = (quadro["video_id"], quadro["quadro"])
        if chave not in esperados or chave in encontrados:
            raise ValueError("Quadro repetido ou fora do desenvolvimento acordado.")
        encontrados.add(chave)
        for tipo, subpasta, ext in (("imagem", "images", "jpg"), ("anotacao", "labels", "txt")):
            caminho = (f"bases_de_dados/visem_tracking/dataset/Train/{chave[0]}/"
                       f"{subpasta}/{chave[0]}_frame_{chave[1]}.{ext}")
            if quadro[tipo] != caminho:
                raise ValueError("Caminho incompatível com o quadro original.")
            _hash_valido(quadro[f"{tipo}_sha256"])


def hash_configuracao(item: dict) -> str:
    """Identidade efetiva: backend float32, classificação e caixa canônica.

    IDs, bloco, perfil e referência não transformam configurações equivalentes
    em distintas. Escala 1 e margem 0 têm a identidade da caixa original.
    """
    caixa = configuracao_canonica(configuracao_caixa_de_dict(item["caixa"]))
    metodo = item.get("metodo", "simpleblob")
    preprocessamento = item.get("preprocessamento", {"metodo": "nenhum"})
    if "metodo" in item or "preprocessamento" in item:
        from algoritmos.classicos.variantes_blobs import validar_preprocessamento
        preprocessamento = validar_preprocessamento(preprocessamento)
    if metodo == "simpleblob":
        config = configuracao_de_dict(item["parametros"])
        identidade = {
            "opencv": parametros_opencv(config),
            "classificacao": {k: float(v) for k, v in item["parametros"]["classificacao"].items()},
            "caixa": caixa,
        }
        # O controle sem pré-processamento mantém exatamente o hash do round1.
        if preprocessamento == {"metodo": "nenhum"}:
            return _sha256(_serializar(identidade))
    elif metodo in ("log", "dog"):
        from algoritmos.classicos.variantes_blobs import configuracao_escala_de_dict
        config = configuracao_escala_de_dict(metodo, item["parametros"])
        identidade = {"parametros": asdict(config), "caixa": caixa}
    else:
        raise ValueError("Método de blobs inválido.")
    identidade.update(metodo=metodo, preprocessamento=preprocessamento)
    return _sha256(_serializar(identidade))


def nome_configuracao(item: dict) -> str:
    """Nome curto para caminhos Windows; o hash identifica todos os parâmetros."""
    if not isinstance(item.get("id"), str) or re.fullmatch(r"r[1-5]c[0-9]{2}", item["id"]) is None:
        raise ValueError("ID de configuração inválido.")
    caixa = configuracao_canonica(configuracao_caixa_de_dict(item["caixa"]))
    modo = caixa["modo"]
    if modo != "original":
        valor = caixa["fator" if modo == "escala" else "pixels"]
        modo += "-" + format(valor, ".6g").replace(".", "p").replace("+", "")
    identificador = "blobs"
    if "metodo" in item:
        from algoritmos.classicos.variantes_blobs import validar_preprocessamento
        pre = validar_preprocessamento(item["preprocessamento"])
        identificador += f"-{item['metodo']}-{pre['metodo']}"
        if pre["metodo"] == "clahe":
            contraste = format(pre["limite_contraste"], ".6g").replace(".", "p")
            identificador += f"{contraste}-g{pre['grade'][0]}x{pre['grade'][1]}"
    return f"{item['id']}__{identificador}-{item['parametros']['polaridade']}-{modo}__cfg-{hash_configuracao(item)[:12]}"


def _parametros_referencia(polaridade: str) -> dict:
    return {
        "polaridade": polaridade, "limiar_minimo": 10, "limiar_maximo": 250,
        "passo_limiar": 10, "repetibilidade_minima": 2, "distancia_minima": 3,
        "area_minima": 3, "area_maxima": 5000, **PERFIS["sem_filtro"],
        "classificacao": {"area_maxima_pequeno": pi * 4 ** 2,
                          "area_minima_aglomerado": pi * 12 ** 2},
    }


def _balanceado(valores: list, candidatos: list) -> None:
    contagens = Counter(valores)
    if any(v not in candidatos for v in valores):
        raise ValueError("Valor fora do espaço aprovado para o round1.")
    piso, resto = divmod(6, len(candidatos))
    esperadas = sorted([piso + 1] * resto + [piso] * (len(candidatos) - resto))
    if sorted(contagens[v] for v in candidatos) != esperadas:
        raise ValueError("Distribuição sem balanceamento em um grupo do round1.")


def _valor_campo(item: dict, campo: str):
    if campo in ("fator_escala", "margem_pixels"):
        return item["caixa"]["fator" if campo == "fator_escala" else "pixels"]
    if campo.startswith("diametro_"):
        chave = "area_maxima_pequeno" if campo == "diametro_maximo_pequeno" else "area_minima_aglomerado"
        area = item["parametros"]["classificacao"][chave]
        for diametro in VALORES[campo]:
            if area == pi * (diametro / 2) ** 2:
                return diametro
        raise ValueError("Limite de classificação fora dos diâmetros acordados.")
    return item["parametros"][campo]


def _campos_grupo(modo: str) -> list[str]:
    return [campo for campo in VALORES
            if campo not in ("fator_escala", "margem_pixels")
            or (campo == "fator_escala" and modo == "escala")
            or (campo == "margem_pixels" and modo == "margem")]


def _desenho_round1(plano: dict) -> None:
    controles = plano["configuracoes"][:12]
    for indice, item in enumerate(controles):
        polaridade = ("claro", "escuro")[indice // 6]
        esperado = {"parametros": _parametros_referencia(polaridade),
                    "caixa": CAIXAS_CONTROLE[indice % 6]}
        if (item["bloco"] != "controle" or item["perfil_forma"] != "sem_filtro"
                or item["referencia"] != ("b01" if polaridade == "claro" else "b02")
                or hash_configuracao(item) != hash_configuracao(esperado)):
            raise ValueError("Os 12 controles devem preservar as referências do round0.")
    exploracao = plano["configuracoes"][12:]
    for indice, (polaridade, modo) in enumerate(GRUPOS):
        grupo = exploracao[indice * 6:(indice + 1) * 6]
        if (len(grupo) != 6 or {x["perfil_forma"] for x in grupo} != set(PERFIS)
                or any(x["bloco"] != "exploracao" or x["referencia"] is not None
                       or x["parametros"]["polaridade"] != polaridade or x["caixa"]["modo"] != modo
                       for x in grupo)):
            raise ValueError("Cada grupo exploratório deve preservar seus seis perfis e sua ordem de grupo.")
        for item in grupo:
            if {k: item["parametros"][k] for k in FILTROS} != PERFIS[item["perfil_forma"]]:
                raise ValueError("Perfil de forma diverge dos parâmetros.")
        for campo in _campos_grupo(modo):
            _balanceado([_valor_campo(x, campo) for x in grupo], VALORES[campo])


def _geracao(dados: dict, rodada: str) -> None:
    _chaves(dados, {"versao_gerador", "arquivo_gerador", "sha256_gerador", "python",
                    "procedimento", "ordem_grupos", "ordem_campos", "valores_candidatos",
                    "perfis_forma", "tentativas_por_grupo", "limite_tentativas_por_grupo",
                    "quantidade_controles", "quantidade_exploratorias"}, "geracao")
    for campo in ("versao_gerador", "arquivo_gerador", "python", "procedimento"):
        _texto(dados[campo])
    if dados["arquivo_gerador"] != ARQUIVO_GERADOR:
        raise ValueError("Arquivo de geração incompatível.")
    _hash_valido(dados["sha256_gerador"])
    for campo in ("quantidade_controles", "quantidade_exploratorias"):
        _inteiro(dados[campo])
    if dados["quantidade_controles"] + dados["quantidade_exploratorias"] != ORCAMENTOS[rodada]:
        raise ValueError("Contagens da geração divergem do orçamento.")
    _inteiro(dados["limite_tentativas_por_grupo"], 1)
    if not isinstance(dados["ordem_grupos"], list) or not isinstance(dados["ordem_campos"], list):
        raise ValueError("Ordens da geração devem ser listas.")
    for valores in (dados["ordem_grupos"], dados["ordem_campos"]):
        for valor in valores:
            _texto(valor)
        if len(valores) != len(set(valores)):
            raise ValueError("Ordem da geração contém repetições.")
    _chaves(dados["tentativas_por_grupo"], set(dados["ordem_grupos"]), "tentativas")
    for tentativas in dados["tentativas_por_grupo"].values():
        _inteiro(tentativas, 1)
        if tentativas > dados["limite_tentativas_por_grupo"]:
            raise ValueError("Limite de tentativas excedido.")
    if not isinstance(dados["valores_candidatos"], dict) or not isinstance(dados["perfis_forma"], dict):
        raise ValueError("Espaço e perfis da geração devem ser objetos.")
    for valores in dados["valores_candidatos"].values():
        if (not isinstance(valores, list) or not valores
                or any(type(v) not in (int, float) or not isfinite(v) or v <= 0 for v in valores)
                or len(set(valores)) != len(valores)):
            raise ValueError("Lista de valores candidatos inválida.")
    if rodada == "round1":
        if (dados["versao_gerador"] != VERSAO_GERADOR or dados["procedimento"] != PROCEDIMENTO
                or dados["ordem_grupos"] != [f"{p}/{m}" for p, m in GRUPOS]
                or dados["ordem_campos"] != list(VALORES)
                or dados["valores_candidatos"] != VALORES or dados["perfis_forma"] != PERFIS
                or dados["limite_tentativas_por_grupo"] != LIMITE_TENTATIVAS
                or dados["quantidade_controles"] != 12 or dados["quantidade_exploratorias"] != 36):
            raise ValueError("Metadados divergem do desenho aprovado para o round1.")


def carregar_plano(conteudo: bytes) -> dict:
    """Valida um plano completo; não abre arquivos de origem ou imagens."""
    plano = _json(conteudo)
    if type(plano.get("versao")) is not int or plano["versao"] not in (1, 2, 3, 4, 5):
        raise ValueError("Versão do plano incompatível.")
    chaves = {"versao", "algoritmo", "etapa", "rodada", "particao", "seed",
                    "origem_desenvolvimento", "origem_inspecao", "geracao", "quadros",
                    "configuracoes", "observacoes"}
    if plano["versao"] >= 2:
        chaves.add("origem_round1")
    if plano["versao"] >= 3:
        chaves.add("origem_round2")
    if plano["versao"] >= 4:
        chaves.add("origem_round3")
    if plano["versao"] == 5:
        chaves.add("origem_round4")
    _chaves(plano, chaves, "plano")
    if (plano["algoritmo"] != "blobs" or plano["etapa"] != "desenvolvimento"
            or plano["particao"] != "desenvolvimento"
            or not isinstance(plano["rodada"], str) or plano["rodada"] not in ORCAMENTOS):
        raise ValueError("O plano deve pertencer às rodadas de desenvolvimento de blobs.")
    _inteiro(plano["seed"])
    _origem(plano["origem_desenvolvimento"], ORIGEM_DESENVOLVIMENTO)
    _origem(plano["origem_inspecao"], ORIGEM_INSPECAO)
    if plano["versao"] >= 2:
        from scripts.blobs.planejamento_round2 import ORIGEM_ROUND1
        _origem(plano["origem_round1"], ORIGEM_ROUND1)
    if plano["versao"] >= 3:
        from scripts.blobs.planejamento_round3 import ORIGEM_ROUND2
        _origem(plano["origem_round2"], ORIGEM_ROUND2)
    if plano["versao"] >= 4:
        from scripts.blobs.planejamento_round4 import ORIGEM_ROUND3
        _origem(plano["origem_round3"], ORIGEM_ROUND3)
    if plano["versao"] == 5:
        from scripts.blobs.planejamento_round5 import ORIGEM_ROUND4
        _origem(plano["origem_round4"], ORIGEM_ROUND4)
    _quadros(plano["quadros"])
    if not isinstance(plano["observacoes"], list):
        raise ValueError("Observações devem ser uma lista de textos.")
    for observacao in plano["observacoes"]:
        _texto(observacao)
    quantidade = ORCAMENTOS[plano["rodada"]]
    if not isinstance(plano["configuracoes"], list) or len(plano["configuracoes"]) != quantidade:
        raise ValueError("Quantidade de configurações diverge do orçamento da rodada.")
    hashes = set()
    for indice, item in enumerate(plano["configuracoes"], 1):
        chaves_item = {"id", "bloco", "perfil_forma", "referencia", "parametros", "caixa"}
        if plano["versao"] >= 2:
            chaves_item.update(("metodo", "preprocessamento"))
        _chaves(item, chaves_item, "configuracao")
        if item["id"] != f"r{plano['rodada'][-1]}c{indice:02d}":
            raise ValueError("IDs devem ser únicos, sequenciais e identificar a rodada.")
        if plano["versao"] == 1:
            referencia_valida = item["referencia"] in (None, "b01", "b02")
        else:
            padrao = {
                2: r"r1c(?:0[1-9]|[1-3][0-9]|4[0-8])",
                3: r"r2c(?:0[1-9]|[12][0-9]|3[0-2])",
                4: r"r3c(?:0[1-9]|1[0-9]|2[0-4])",
                5: r"r4c(?:0[1-9]|1[0-8])",
            }[plano["versao"]]
            referencia_valida = (item["referencia"] is None or isinstance(item["referencia"], str)
                                 and re.fullmatch(padrao, item["referencia"]) is not None)
        if item["bloco"] not in ("controle", "exploracao") or not referencia_valida:
            raise ValueError("Bloco ou referência inválidos.")
        _texto(item["perfil_forma"])
        digest = hash_configuracao(item)
        if digest in hashes:
            raise ValueError("Configurações semanticamente repetidas.")
        hashes.add(digest)
    if plano["versao"] == 1:
        _geracao(plano["geracao"], plano["rodada"])
    elif plano["versao"] == 2:
        from scripts.blobs.planejamento_round2 import validar_desenho_round2
        validar_desenho_round2(plano)
    elif plano["versao"] == 3:
        from scripts.blobs.planejamento_round3 import validar_desenho_round3
        validar_desenho_round3(plano)
    elif plano["versao"] == 4:
        from scripts.blobs.planejamento_round4 import validar_desenho_round4
        validar_desenho_round4(plano)
    else:
        from scripts.blobs.planejamento_round5 import validar_desenho_round5
        validar_desenho_round5(plano)
    if Counter(x["bloco"] for x in plano["configuracoes"]) != {
            "controle": plano["geracao"]["quantidade_controles"],
            "exploracao": plano["geracao"]["quantidade_exploratorias"]}:
        raise ValueError("Blocos divergem das contagens declaradas na geração.")
    if plano["versao"] == 1 and plano["rodada"] == "round1":
        _desenho_round1(plano)
    return plano


def _ler_fontes(conteudo_desenvolvimento: bytes, conteudo_inspecao: bytes) -> tuple[list, dict]:
    desenvolvimento, inspecao = _json(conteudo_desenvolvimento), _json(conteudo_inspecao)
    for dados, algoritmo, rodada in ((desenvolvimento, "limiarizacao", "round1"),
                                     (inspecao, "blobs", "round0")):
        if (type(dados.get("versao")) is not int or dados["versao"] != 1
                or dados.get("algoritmo") != algoritmo or dados.get("rodada") != rodada
                or dados.get("particao") != "desenvolvimento"):
            raise ValueError("Origem não corresponde ao desenvolvimento acordado.")
    if inspecao.get("etapa") != "inspecao":
        raise ValueError("A origem dos controles deve ser a inspeção round0.")
    _origem(inspecao.get("origem_desenvolvimento"), ORIGEM_DESENVOLVIMENTO)
    if inspecao["origem_desenvolvimento"]["sha256"] != _sha256(conteudo_desenvolvimento):
        raise ValueError("Hash da origem de desenvolvimento diverge da inspeção.")
    quadros = []
    if not isinstance(desenvolvimento.get("quadros"), list):
        raise ValueError("Origem de desenvolvimento sem quadros.")
    for q in desenvolvimento["quadros"]:
        _chaves(q, {"video_id", "quadro", "imagem", "anotacao", "sha256_imagem", "sha256_anotacao"}, "quadro de origem")
        quadros.append({k: q[k] for k in ("video_id", "quadro", "imagem", "anotacao")} | {
            "imagem_sha256": q["sha256_imagem"], "anotacao_sha256": q["sha256_anotacao"]})
    _quadros(quadros)
    por_chave = {(q["video_id"], q["quadro"]): q for q in quadros}
    quadros_inspecao = []
    if not isinstance(inspecao.get("quadros"), list):
        raise ValueError("Inspeção sem quadros.")
    for quadro in inspecao["quadros"]:
        _chaves(quadro, set(quadros[0]) | {"objetivo"}, "quadro da inspeção")
        _texto(quadro["objetivo"])
        quadros_inspecao.append({k: v for k, v in quadro.items() if k != "objetivo"})
    _quadros(quadros_inspecao, CHAVES_INSPECAO)
    if any(q != por_chave[(q["video_id"], q["quadro"])] for q in quadros_inspecao):
        raise ValueError("Quadros da inspeção divergem da origem de desenvolvimento.")
    referencias = {}
    if not isinstance(inspecao.get("configuracoes"), list) or len(inspecao["configuracoes"]) != 2:
        raise ValueError("A origem deve conter os dois controles da inspeção.")
    for item in inspecao["configuracoes"]:
        _chaves(item, {"id", "parametros"}, "referência")
        if item["id"] not in ("b01", "b02") or item["id"] in referencias:
            raise ValueError("Referências b01/b02 inválidas ou repetidas.")
        polaridade = "claro" if item["id"] == "b01" else "escuro"
        comparacao = {"parametros": item["parametros"], "caixa": {"modo": "original"}}
        esperado = {"parametros": _parametros_referencia(polaridade), "caixa": {"modo": "original"}}
        if hash_configuracao(comparacao) != hash_configuracao(esperado):
            raise ValueError("Parâmetros do round0 foram alterados.")
        referencias[item["id"]] = deepcopy(item["parametros"])
    return quadros, referencias


def _sortear_coluna(rng: random.Random, candidatos: list) -> list:
    vezes, extras = divmod(6, len(candidatos))
    coluna = candidatos * vezes + rng.sample(candidatos, extras)
    rng.shuffle(coluna)
    return coluna


def gerar_round1(conteudo_desenvolvimento: bytes, conteudo_inspecao: bytes, seed: int = 42) -> dict:
    """Monta 12 controles e seis grupos balanceados de seis configurações.

    Toda tentativa rejeitada descarta o grupo inteiro. A nova tentativa refaz
    todas as colunas balanceadas, sem reduzir quantidades ou relaxar regras.
    Não grava o plano e não consulta o sistema global de números aleatórios.
    """
    _inteiro(seed)
    quadros, referencias = _ler_fontes(conteudo_desenvolvimento, conteudo_inspecao)
    rng, configuracoes, hashes = random.Random(seed), [], set()
    for referencia in ("b01", "b02"):
        for caixa in CAIXAS_CONTROLE:
            item = {"id": f"r1c{len(configuracoes) + 1:02d}", "bloco": "controle",
                    "perfil_forma": "sem_filtro", "referencia": referencia,
                    "parametros": deepcopy(referencias[referencia]), "caixa": deepcopy(caixa)}
            configuracoes.append(item)
            hashes.add(hash_configuracao(item))
    tentativas = {}
    for polaridade, modo in GRUPOS:
        for tentativa in range(1, LIMITE_TENTATIVAS + 1):
            colunas = {campo: _sortear_coluna(rng, VALORES[campo]) for campo in _campos_grupo(modo)}
            grupo, hashes_grupo = [], set()
            for indice, perfil in enumerate(PERFIS):
                parametros = {campo: colunas[campo][indice] for campo in list(VALORES)[:7]}
                parametros.update(polaridade=polaridade, **PERFIS[perfil])
                parametros["classificacao"] = {
                    "area_maxima_pequeno": pi * (colunas["diametro_maximo_pequeno"][indice] / 2) ** 2,
                    "area_minima_aglomerado": pi * (colunas["diametro_minimo_aglomerado"][indice] / 2) ** 2,
                }
                caixa = {"modo": modo}
                if modo == "escala":
                    caixa["fator"] = colunas["fator_escala"][indice]
                elif modo == "margem":
                    caixa["pixels"] = colunas["margem_pixels"][indice]
                item = {"id": f"r1c{len(configuracoes) + indice + 1:02d}", "bloco": "exploracao",
                        "perfil_forma": perfil, "referencia": None, "parametros": parametros, "caixa": caixa}
                try:
                    digest = hash_configuracao(item)
                except (TypeError, ValueError):
                    break
                if digest in hashes or digest in hashes_grupo:
                    break
                grupo.append(item)
                hashes_grupo.add(digest)
            if len(grupo) == 6:
                configuracoes.extend(grupo)
                hashes.update(hashes_grupo)
                tentativas[f"{polaridade}/{modo}"] = tentativa
                break
        else:
            raise ValueError(f"Não foi possível gerar o grupo {polaridade}/{modo} sem relaxar as regras.")
    plano = {
        "versao": 1, "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": "round1",
        "particao": "desenvolvimento", "seed": seed,
        "origem_desenvolvimento": {"plano": ORIGEM_DESENVOLVIMENTO, "sha256": _sha256(conteudo_desenvolvimento)},
        "origem_inspecao": {"plano": ORIGEM_INSPECAO, "sha256": _sha256(conteudo_inspecao)},
        "geracao": {
            "versao_gerador": VERSAO_GERADOR, "arquivo_gerador": ARQUIVO_GERADOR,
            "sha256_gerador": _sha256(Path(__file__).read_bytes()), "python": sys.version.split()[0],
            "procedimento": PROCEDIMENTO, "ordem_grupos": [f"{p}/{m}" for p, m in GRUPOS],
            "ordem_campos": list(VALORES), "valores_candidatos": deepcopy(VALORES),
            "perfis_forma": deepcopy(PERFIS), "tentativas_por_grupo": tentativas,
            "limite_tentativas_por_grupo": LIMITE_TENTATIVAS,
            "quantidade_controles": 12, "quantidade_exploratorias": 36,
        },
        "quadros": quadros, "configuracoes": configuracoes,
        "observacoes": [
            "Desenvolvimento: os mesmos 178 quadros anotados, sem os quadros 900 e 1100 do vídeo 23.",
            "Os 12 controles mantêm o detector e a classificação do round0; somente a caixa varia.",
            "As 36 exploratórias variam vários parâmetros; não isolam efeitos causais individuais.",
            "A classificação usa a área circular estimada bruta, independentemente da transformação da caixa.",
            "Seed auxilia a reprodução; a lista explícita, as fontes e as versões são a referência da execução.",
            "Cada rejeição regenera o grupo completo com balanceamento; o limite de tentativas não relaxa regras.",
            "F1 de indivíduos com IoU >= 0,50; aglomerados e classificação avaliados separadamente.",
            "Sem escolha de finalistas ou exigência de F1 mínimo nesta etapa; limites são hipóteses exploratórias.",
        ],
    }
    return carregar_plano(_serializar(plano))
