"""Congela todas as configurações distintas nos JPEGs de seleção acordados."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZipFile

from analise.avaliacao_individuos import CRITERIOS
from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict, configuracao_canonica
from algoritmos.classicos.variantes_blobs import validar_preprocessamento
from scripts.blobs import planejamento as p
from scripts.blobs.planejamento_round5 import validar_origens_round5


ARQUIVO_GERADOR = "scripts/blobs/planejamento_selecao.py"
ORIGEM_QUADROS = "scripts/limiarizacao/selecao/plano.json"
VIDEOS = ("13", "29", "52", "54")
ORDEM_QUADROS = tuple((v, q) for v in VIDEOS for q in range(0, 1401, 100))
RODADAS = tuple(p.ORCAMENTOS)
BATCHES = {
    "round1": "resultados/frame-to-frame/blobs/round1/batch__20260920T193937586038Z",
    "round2": "resultados/frame-to-frame/blobs/round2/batch__20260920T203403161690Z",
    "round3": "resultados/frame-to-frame/blobs/round3/batch__20260920T225209430564Z",
    "round4": "resultados/frame-to-frame/blobs/round4/batch__20260920T232838676095Z",
    "round5": "resultados/frame-to-frame/blobs/round5/batch__20260921T001209933359Z",
}
IDS = tuple(f"s{i:03d}" for i in range(1, 120))
CAMPOS_CONFIGURACAO = {"id", "bloco", "perfil_forma", "referencia", "metodo",
                       "preprocessamento", "parametros", "caixa"}
GERACAO_FIXA = {
    "versao_gerador": "1.0", "arquivo_gerador": ARQUIVO_GERADOR,
    "procedimento": "deduplicacao_deterministica_de_todas_as_configuracoes_concluidas",
    "ordem_rodadas": list(RODADAS), "ordem_configuracoes": "primeiro_aparecimento",
    "criterio_deduplicacao": "scripts.blobs.planejamento.hash_configuracao",
    "aleatoriedade_utilizada": False, "quantidade_configuracoes": 119,
    "quantidade_origens": 136, "quadros_por_configuracao": 60,
    "avaliacoes_previstas": 7140, "limite_configuracoes_distintas": 122,
}


def _igual(valor, esperado, contexto):
    if p._serializar(valor) != p._serializar(esperado):
        raise ValueError(f"Valor incompatível em {contexto}.")


def _caminho(valor: str) -> None:
    p._texto(valor)
    caminho = PurePosixPath(valor)
    if ("\\" in valor or ":" in valor or caminho.is_absolute()
            or ".." in caminho.parts or caminho.as_posix() != valor):
        raise ValueError("Fonte deve ser um caminho relativo interno ao projeto.")


def _ler(raiz: Path, nome: str, esperado: str | None = None) -> bytes:
    _caminho(nome)
    raiz = Path(raiz).resolve(strict=True)
    arquivo = (raiz / nome).resolve(strict=True)
    if not arquivo.is_relative_to(raiz) or not arquivo.is_file():
        raise ValueError(f"Fonte fora do projeto: {nome}.")
    conteudo = arquivo.read_bytes()
    if esperado is not None and p._sha256(conteudo) != esperado:
        raise ValueError(f"Hash divergente na fonte: {nome}.")
    return conteudo


def _origens_estruturais(origens: list) -> None:
    if not isinstance(origens, list) or len(origens) != 5:
        raise ValueError("A seleção exige as cinco rodadas concluídas.")
    for numero, (origem, rodada) in enumerate(zip(origens, RODADAS), 1):
        p._chaves(origem, {"rodada", "plano", "plano_sha256", "batch", "manifesto_sha256",
                          "codigo_zip_sha256", "configuracoes_concluidas",
                          "quadros_por_configuracao", "avaliacoes_concluidas", "dependencias"},
                  "origem de rodada")
        _igual(origem["rodada"], rodada, "ordem de rodadas")
        _igual(origem["plano"], f"scripts/blobs/rodadas/{rodada}.json", "plano de origem")
        prefixo = f"resultados/frame-to-frame/blobs/{rodada}/batch__"
        if not isinstance(origem["batch"], str) or re.fullmatch(
                re.escape(prefixo) + r"[0-9]{8}T[0-9]{12}Z", origem["batch"]) is None:
            raise ValueError("Batch de desenvolvimento inválido.")
        for campo in ("plano_sha256", "manifesto_sha256", "codigo_zip_sha256"):
            p._hash_valido(origem[campo])
        _igual(origem["configuracoes_concluidas"], p.ORCAMENTOS[rodada], "configurações concluídas")
        _igual(origem["quadros_por_configuracao"], 178, "quadros do desenvolvimento")
        _igual(origem["avaliacoes_concluidas"], p.ORCAMENTOS[rodada] * 178, "avaliações concluídas")
        if not isinstance(origem["dependencias"], dict) or not origem["dependencias"]:
            raise ValueError("Faltam as dependências da execução de origem.")
        for nome, versao in origem["dependencias"].items():
            p._texto(nome)
            p._texto(versao)


def _normalizar_configuracao(item: dict, novo_id: str) -> dict:
    retorno = deepcopy(item)
    retorno.update(id=novo_id, metodo=item.get("metodo", "simpleblob"),
                   preprocessamento=deepcopy(item.get("preprocessamento", {"metodo": "nenhum"})))
    return retorno


def _validar_configuracao(item: dict, ident: str) -> str:
    p._chaves(item, CAMPOS_CONFIGURACAO, "configuração de seleção")
    _igual(item["id"], ident, "ordem s001 a s119")
    if item["bloco"] not in ("controle", "exploracao"):
        raise ValueError("Bloco de origem inválido.")
    p._texto(item["perfil_forma"])
    ref = item["referencia"]
    if ref is not None and (not isinstance(ref, str) or re.fullmatch(r"b0[12]|r[1-4]c[0-9]{2}", ref) is None):
        raise ValueError("Referência de desenvolvimento inválida.")
    return p.hash_configuracao(item)


def carregar_plano(conteudo: bytes) -> dict:
    """Validação pura do contrato, identidade, composição e linhagem; sem I/O."""
    plano = p._json(conteudo)
    p._chaves(plano, {"versao", "algoritmo", "etapa", "rodada", "particao", "seed", "criterios",
                     "politica_anotacoes_ausentes", "exclusoes", "origem_quadros", "origens_rodadas",
                     "geracao", "quadros", "configuracoes", "proveniencia", "observacoes"}, "plano de seleção")
    for campo, valor in {"versao": 1, "algoritmo": "blobs", "etapa": "selecao_imagens",
                         "rodada": "selecao", "particao": "selecao", "seed": 42,
                         "criterios": CRITERIOS, "politica_anotacoes_ausentes": "erro", "exclusoes": []}.items():
        _igual(plano[campo], valor, campo)
    p._origem(plano["origem_quadros"], ORIGEM_QUADROS)
    _origens_estruturais(plano["origens_rodadas"])
    g = plano["geracao"]
    p._chaves(g, {*GERACAO_FIXA, "sha256_gerador", "python"}, "geração da seleção")
    for campo, esperado in GERACAO_FIXA.items():
        _igual(g[campo], esperado, campo)
    p._hash_valido(g["sha256_gerador"])
    p._texto(g["python"])
    p._quadros(plano["quadros"], set(ORDEM_QUADROS))
    if [(x["video_id"], x["quadro"]) for x in plano["quadros"]] != list(ORDEM_QUADROS):
        raise ValueError("Os 60 quadros devem conservar a ordem acordada.")
    if not isinstance(plano["configuracoes"], list) or len(plano["configuracoes"]) != 119:
        raise ValueError("A seleção deve conter as 119 configurações distintas.")
    p._chaves(plano["proveniencia"], set(IDS), "proveniência")
    hashes, aliases, primeiras = set(), {}, []
    origens_por_rodada = {x["rodada"]: x for x in plano["origens_rodadas"]}
    for ident, item in zip(IDS, plano["configuracoes"]):
        digest = _validar_configuracao(item, ident)
        if digest in hashes:
            raise ValueError("Configurações semanticamente equivalentes foram repetidas.")
        hashes.add(digest)
        origem = plano["proveniencia"][ident]
        p._chaves(origem, {"configuracao_sha256", "primeira_origem", "origens"}, "proveniência de configuração")
        _igual(origem["configuracao_sha256"], digest, "identidade da configuração")
        p._chaves(origem["primeira_origem"], {"rodada", "configuracao_id"}, "primeira origem")
        if not isinstance(origem["origens"], list) or not origem["origens"]:
            raise ValueError("Toda candidata precisa de uma execução de origem.")
        ordem = []
        for alias in origem["origens"]:
            p._chaves(alias, {"rodada", "configuracao_id", "pasta_execucao",
                             "sha256_arquivo_configuracao", "sha256_manifesto_execucao"}, "alias de origem")
            rodada, anterior = alias["rodada"], alias["configuracao_id"]
            if rodada not in RODADAS or not isinstance(anterior, str):
                raise ValueError("Origem de configuração fora das cinco rodadas.")
            numero = RODADAS.index(rodada) + 1
            if anterior not in {f"r{numero}c{i:02d}" for i in range(1, p.ORCAMENTOS[rodada] + 1)}:
                raise ValueError("ID de origem fora da rodada.")
            chave = (numero, int(anterior.split("c")[1]))
            if chave in aliases:
                raise ValueError("Uma execução de desenvolvimento aparece em duas origens.")
            aliases[chave] = ident
            ordem.append(chave)
            pasta = alias["pasta_execucao"]
            _caminho(pasta)
            caminho = PurePosixPath(pasta)
            batch = origens_por_rodada[rodada]["batch"]
            if (caminho.parent.as_posix() != f"resultados/frame-to-frame/blobs/{rodada}"
                    or not caminho.name.startswith(anterior + "__")
                    or not caminho.name.endswith("__" + batch.split("batch__", 1)[1])):
                raise ValueError("Pasta da configuração não pertence à execução registrada.")
            for campo in ("sha256_arquivo_configuracao", "sha256_manifesto_execucao"):
                p._hash_valido(alias[campo])
        if ordem != sorted(ordem):
            raise ValueError("Aliases devem seguir sua ordem de desenvolvimento.")
        _igual(origem["primeira_origem"], {k: origem["origens"][0][k] for k in ("rodada", "configuracao_id")},
               "primeira ocorrência")
        primeiras.append(ordem[0])
    esperados = {(n, i) for n, rodada in enumerate(RODADAS, 1)
                 for i in range(1, p.ORCAMENTOS[rodada] + 1)}
    if set(aliases) != esperados or primeiras != sorted(primeiras):
        raise ValueError("A linhagem deve cobrir as 136 execuções em ordem de primeira ocorrência.")
    if not isinstance(plano["observacoes"], list) or not plano["observacoes"]:
        raise ValueError("Faltam observações do protocolo de seleção.")
    for texto in plano["observacoes"]:
        p._texto(texto)
    return plano


def caminhos_origens(plano: dict) -> dict[str, str]:
    """Nomes estáveis dos 13 JSONs que o executor deve arquivar sem transformação."""
    retorno = {"origem_quadros": plano["origem_quadros"]["plano"],
               "origem_desenvolvimento": p.ORIGEM_DESENVOLVIMENTO,
               "origem_inspecao": p.ORIGEM_INSPECAO}
    for fonte in plano["origens_rodadas"]:
        rodada = fonte["rodada"]
        retorno[f"origem_{rodada}"] = fonte["plano"]
        retorno[f"execucao_{rodada}"] = fonte["batch"] + "/execucao.json"
    return retorno


def _quadros_da_referencia(conteudo: bytes) -> list[dict]:
    anterior = p._json(conteudo)
    # A referência fornece apenas os JPEGs. Suas métricas antigas não são herdadas.
    for campo, valor in (("versao", 1), ("seed", 42), ("algoritmo", "limiarizacao"), ("rodada", "selecao"), ("particao", "selecao"),
                         ("politica_anotacoes_ausentes", "erro"), ("exclusoes", [])):
        _igual(anterior.get(campo), valor, "origem dos JPEGs")
    dados = anterior.get("quadros")
    if not isinstance(dados, list) or len(dados) != 60:
        raise ValueError("A origem de seleção não fornece os 60 JPEGs acordados.")
    retorno = []
    for item in dados:
        p._chaves(item, {"video_id", "quadro", "imagem", "anotacao", "sha256_imagem", "sha256_anotacao"},
                  "quadro da seleção de limiarização")
        retorno.append({k: deepcopy(item[k]) for k in ("video_id", "quadro", "imagem", "anotacao")}
                       | {"imagem_sha256": item["sha256_imagem"], "anotacao_sha256": item["sha256_anotacao"]})
    p._quadros(retorno, set(ORDEM_QUADROS))
    if [(x["video_id"], x["quadro"]) for x in retorno] != list(ORDEM_QUADROS):
        raise ValueError("Ordem dos JPEGs de referência incompatível.")
    return retorno


def _verificar_batch(raiz: Path, fonte: dict, anterior: dict, bytes_plano: bytes,
                     bytes_manifesto: bytes) -> tuple[dict, list[dict]]:
    manifesto = p._json(bytes_manifesto)
    rodada, batch = fonte["rodada"], fonte["batch"]
    quantidade = p.ORCAMENTOS[rodada]
    for campo, valor in {"versao": anterior["versao"], "tipo": "rodada_blobs", "algoritmo": "blobs",
                         "situacao": "concluida", "etapa": "desenvolvimento", "particao": "desenvolvimento",
                         "rodada": rodada, "criterios": CRITERIOS, "configuracoes_previstas": quantidade,
                         "configuracoes_concluidas": quantidade, "quadros_por_configuracao": 178,
                         "avaliacoes_concluidas": quantidade * 178, "plano_sha256": p._sha256(bytes_plano)}.items():
        _igual(manifesto.get(campo), valor, f"manifesto {rodada}: {campo}")
    if _ler(raiz, batch + "/plano.json", fonte["plano_sha256"]) != bytes_plano:
        raise ValueError("Plano arquivado difere da origem congelada.")
    saidas = manifesto.get("saidas_sha256", {})
    if not isinstance(saidas, dict):
        raise ValueError("Manifesto sem índice de integridade das saídas.")
    entradas = manifesto.get("origens_sha256", {})
    if not isinstance(entradas, dict):
        raise ValueError("Manifesto sem índice de integridade das entradas.")
    _igual(entradas.get(fonte["plano"]), fonte["plano_sha256"], "plano no índice de entradas")
    _igual(saidas.get(batch + "/plano.json"), fonte["plano_sha256"], "plano no índice de saídas")
    for campo in [k for k in anterior if k.startswith("origem_")]:
        nome = batch + "/" + campo + ".json"
        digest = anterior[campo]["sha256"]
        _igual(saidas.get(nome), digest, "hash de origem arquivada")
        _igual(entradas.get(anterior[campo]["plano"]), digest, "hash da origem no índice de entradas")
        _ler(raiz, nome, digest)
    codigo = manifesto.get("codigo", {})
    if not isinstance(codigo, dict) or not isinstance(codigo.get("sha256_arquivos"), dict):
        raise ValueError("Manifesto sem código arquivado.")
    _igual(codigo.get("sha256_zip"), fonte["codigo_zip_sha256"], "hash do ZIP de código")
    _igual(saidas.get(batch + "/codigo.zip"), fonte["codigo_zip_sha256"], "ZIP no índice de saídas")
    zip_bytes = _ler(raiz, batch + "/codigo.zip", fonte["codigo_zip_sha256"])
    with ZipFile(BytesIO(zip_bytes)) as arquivo:
        nomes = arquivo.namelist()
        if len(nomes) != len(set(nomes)) or set(nomes) != set(codigo["sha256_arquivos"]):
            raise ValueError("Arquivos do ZIP divergem do manifesto.")
        for nome, esperado in codigo["sha256_arquivos"].items():
            _caminho(nome)
            _igual(p._sha256(arquivo.read(nome)), esperado, "código preservado")
    gerador = anterior["geracao"]
    _igual(codigo["sha256_arquivos"].get(gerador["arquivo_gerador"]), gerador["sha256_gerador"],
           "gerador arquivado da rodada")
    _igual(manifesto.get("dependencias"), fonte["dependencias"], "ambiente registrado")
    execucoes = manifesto.get("execucoes")
    if not isinstance(execucoes, list) or len(execucoes) != quantidade:
        raise ValueError("Há configurações sem execução concluída.")
    aliases = []
    for item, execucao in zip(anterior["configuracoes"], execucoes):
        p._chaves(execucao, {"configuracao_id", "pasta"}, "execução de origem")
        _igual(execucao["configuracao_id"], item["id"], "ordem de execuções")
        pasta = execucao["pasta"]
        esperado = f"resultados/frame-to-frame/blobs/{rodada}/{p.nome_configuracao(item)}__{batch.split('batch__')[1]}"
        _igual(pasta, esperado, "pasta de execução")
        hashes = {}
        for nome in ("configuracao.json", "execucao.json"):
            caminho = pasta + "/" + nome
            digest = saidas.get(caminho)
            p._hash_valido(digest)
            hashes[nome] = digest
            conteudo = _ler(raiz, caminho, digest)
            if nome == "configuracao.json":
                _igual(p._json(conteudo), item, "configuração efetivamente executada")
            else:
                estado = p._json(conteudo)
                for campo, valor in {"tipo": "rodada_blobs", "situacao": "concluida", "configuracao_id": item["id"],
                                     "batch": batch, "plano_sha256": fonte["plano_sha256"], "quadros_concluidos": 178,
                                     "configuracao_sha256": p.hash_configuracao(item)}.items():
                    _igual(estado.get(campo), valor, "estado da configuração")
        aliases.append({"rodada": rodada, "configuracao_id": item["id"], "pasta_execucao": pasta,
                        "sha256_arquivo_configuracao": hashes["configuracao.json"],
                        "sha256_manifesto_execucao": hashes["execucao.json"]})
    return manifesto, aliases


def _catalogo(planos: list[dict], aliases_por_rodada: list[list[dict]]) -> tuple[list[dict], dict]:
    configuracoes, proveniencia, por_hash = [], {}, {}
    for anterior, aliases in zip(planos, aliases_por_rodada):
        for item, alias in zip(anterior["configuracoes"], aliases):
            digest = p.hash_configuracao(item)
            if digest not in por_hash:
                ident = f"s{len(configuracoes) + 1:03d}"
                por_hash[digest] = ident
                configuracoes.append(_normalizar_configuracao(item, ident))
                proveniencia[ident] = {"configuracao_sha256": digest,
                                      "primeira_origem": {k: alias[k] for k in ("rodada", "configuracao_id")},
                                      "origens": []}
            proveniencia[por_hash[digest]]["origens"].append(deepcopy(alias))
    if len(configuracoes) != 119 or sum(len(x["origens"]) for x in proveniencia.values()) != 136:
        raise ValueError("As fontes não reproduzem o catálogo de 119 distintas e 136 origens.")
    return configuracoes, proveniencia


def _conferir(raiz: Path, fontes: list[dict], origem_quadros: dict) -> tuple[dict, list[dict], list[dict], dict]:
    _origens_estruturais(fontes)
    documentos = {"origem_quadros": _ler(raiz, origem_quadros["plano"], origem_quadros["sha256"])}
    planos, aliases = [], []
    for fonte in fontes:
        rodada = fonte["rodada"]
        documento = _ler(raiz, fonte["plano"], fonte["plano_sha256"])
        manifesto = _ler(raiz, fonte["batch"] + "/execucao.json", fonte["manifesto_sha256"])
        anterior = p.carregar_plano(documento)
        _igual(anterior["rodada"], rodada, "rodada de origem")
        documentos[f"origem_{rodada}"] = documento
        documentos[f"execucao_{rodada}"] = manifesto
        _, origens_config = _verificar_batch(raiz, fonte, anterior, documento, manifesto)
        planos.append(anterior)
        aliases.append(origens_config)
    validar_origens_round5(planos[4], *(documentos[f"origem_round{i}"] for i in range(1, 5)))
    for campo in ("origem_desenvolvimento", "origem_inspecao"):
        origem = planos[4][campo]
        documentos[campo] = _ler(raiz, origem["plano"], origem["sha256"])
    quadros = _quadros_da_referencia(documentos["origem_quadros"])
    for quadro in quadros:
        for tipo in ("imagem", "anotacao"):
            _ler(raiz, quadro[tipo], quadro[tipo + "_sha256"])
    configuracoes, proveniencia = _catalogo(planos, aliases)
    return documentos, quadros, configuracoes, proveniencia


def conferir_origens(plano: dict, raiz: Path) -> dict[str, bytes]:
    """Confere fontes concluídas, linhagem e todos os 120 arquivos de seleção.

    Retorna 13 JSONs originais para arquivamento. A verificação das rodadas
    lê manifestos, planos, configurações e ZIPs; não repete a auditoria de
    todos os PNGs/CSVs históricos nem executa detectores.
    """
    plano = carregar_plano(p._serializar(plano))
    documentos, quadros, configuracoes, proveniencia = _conferir(
        raiz, plano["origens_rodadas"], plano["origem_quadros"])
    for valor, esperado, contexto in ((plano["quadros"], quadros, "JPEGs de seleção"),
                                      (plano["configuracoes"], configuracoes, "catálogo congelado"),
                                      (plano["proveniencia"], proveniencia, "linhagem completa")):
        _igual(valor, esperado, contexto)
    return documentos


def gerar_plano(raiz: Path) -> dict:
    """Constrói o plano autorizado a partir das cinco fontes explícitas; não grava."""
    fontes = []
    for rodada in RODADAS:
        caminho = f"scripts/blobs/rodadas/{rodada}.json"
        bytes_plano = _ler(raiz, caminho)
        manifesto_bytes = _ler(raiz, BATCHES[rodada] + "/execucao.json")
        manifesto = p._json(manifesto_bytes)
        fontes.append({"rodada": rodada, "plano": caminho, "plano_sha256": p._sha256(bytes_plano),
                       "batch": BATCHES[rodada], "manifesto_sha256": p._sha256(manifesto_bytes),
                       "codigo_zip_sha256": manifesto.get("codigo", {}).get("sha256_zip"),
                       "configuracoes_concluidas": manifesto.get("configuracoes_concluidas"),
                       "quadros_por_configuracao": manifesto.get("quadros_por_configuracao"),
                       "avaliacoes_concluidas": manifesto.get("avaliacoes_concluidas"),
                       "dependencias": deepcopy(manifesto.get("dependencias"))})
    origem = {"plano": ORIGEM_QUADROS, "sha256": p._sha256(_ler(raiz, ORIGEM_QUADROS))}
    _, quadros, configuracoes, proveniencia = _conferir(raiz, fontes, origem)
    return carregar_plano(p._serializar({
        "versao": 1, "algoritmo": "blobs", "etapa": "selecao_imagens", "rodada": "selecao",
        "particao": "selecao", "seed": 42, "criterios": deepcopy(CRITERIOS),
        "politica_anotacoes_ausentes": "erro", "exclusoes": [], "origem_quadros": origem,
        "origens_rodadas": fontes,
        "geracao": {**deepcopy(GERACAO_FIXA), "sha256_gerador": p._sha256(Path(__file__).read_bytes()),
                    "python": sys.version.split()[0]},
        "quadros": quadros, "configuracoes": configuracoes, "proveniencia": proveniencia,
        "observacoes": [
            "Todas as 119 configurações distintas das cinco rodadas concluídas, com 136 aliases preservados; nenhuma escolhida pelo desempenho de desenvolvimento.",
            "IDs s001 a s119 seguem a primeira ocorrência nas ordens round1 a round5 e de cada plano original; IDs organizam arquivos e não decidem empates.",
            "Método, pré-processamento, parâmetros, classificação e caixa preservados. SimpleBlob sem pré-processamento conserva a identidade semântica legada.",
            "Os campos bloco, perfil_forma e referencia descrevem a primeira origem no desenvolvimento; não designam controles novos nesta seleção.",
            "Mesmos 60 JPEGs e anotações originais da seleção de limiarização: vídeos 13, 29, 52 e 54; quadros 0 a 1400, passo 100. Nenhuma exclusão autorizada.",
            "A referência de limiarização fornece apenas os arquivos e seus hashes; suas métricas antigas não são usadas.",
            "F1 de indivíduos 0/2 pelas contagens somadas, IoU >= 0,50 e pareamento exclusivo; aglomerados, cobertura por classe e erros de classificação separados.",
            "Seed 42 registrada sem sorteio. Plano congelado e origens exatas definem a reprodução; 119 vezes 60 totaliza 7.140 avaliações previstas.",
            "Conferência de origens cobre metadados completos, configurações efetivamente concluídas, código arquivado e todos os JPEGs/anotações de seleção. Não repete os hashes de todos os resultados históricos.",
            "Ainda não há cinco finalistas. Empates que atravessem a quinta vaga exigem decisão registrada; sem promoção automática por ID, tempo ou arredondamento.",
            "O pesquisador executará a seleção. Este plano não executa vídeos, não altera parâmetros e não reinicia o desenvolvimento.",
        ],
    }))


def nome_configuracao(item: dict) -> str:
    """Nome identificável e curto para as candidatas s001 a s119."""
    if item.get("id") not in IDS:
        raise ValueError("ID de seleção deve estar entre s001 e s119.")
    digest = _validar_configuracao(item, item["id"])
    caixa = configuracao_canonica(configuracao_caixa_de_dict(item["caixa"]))
    modo = caixa["modo"]
    if modo != "original":
        valor = caixa["fator" if modo == "escala" else "pixels"]
        modo += "-" + format(valor, ".6g").replace(".", "p").replace("+", "")
    pre = validar_preprocessamento(item["preprocessamento"])
    nome_pre = pre["metodo"]
    if nome_pre == "clahe":
        nome_pre += format(pre["limite_contraste"], ".6g").replace(".", "p")
        nome_pre += f"-g{pre['grade'][0]}x{pre['grade'][1]}"
    return f"{item['id']}__blobs-{item['metodo']}-{nome_pre}-{item['parametros']['polaridade']}-{modo}__cfg-{digest[:12]}"
