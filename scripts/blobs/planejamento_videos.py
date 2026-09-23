"""Plano das cinco configurações aprovadas nos vídeos completos de seleção."""

from __future__ import annotations

from copy import deepcopy
import csv
from io import StringIO
from pathlib import Path
import sys

from analise.avaliacao_individuos import CRITERIOS
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_selecao as selecao
from scripts.blobs.executar_inspecao import colunas_metricas


ARQUIVO_GERADOR = "scripts/blobs/planejamento_videos.py"
PLANO_VIDEOS_LIMIARIZACAO = "scripts/limiarizacao/videos/plano_selecao.json"
PLANO_SELECAO = "scripts/blobs/selecao/plano.json"
BATCH_SELECAO = "resultados/frame-to-frame/blobs/selecao/batch__20260921T011058635016Z"
IDS_APROVADOS = ("s052", "s082", "s084", "s103", "s051")
IDENTIDADES_APROVADAS = {
    "s052": "9f338a047d2c06957a2c5abd1b40437161293b8f82b0070b4630af5221ff9ae0",
    "s082": "b3fcacbd994287fbc7b6f48c6a97660183253eb298c08faacc2293a66a283f4e",
    "s084": "ce20afa1deccc626f291a14b2e524044968d77a905abff2d1811664921672304",
    "s103": "9de13345e2d641ca5712bc06cb7366a76082867c58f2fac982d6c6ff243bbfcc",
    "s051": "b58290099c7a026468f20bf38f042bb6adfd87d7147dd10cd4918f43c6e99092",
}
FONTES_FIXAS = {
    "origem_videos_limiarizacao": PLANO_VIDEOS_LIMIARIZACAO,
    "origem_selecao": PLANO_SELECAO,
    "execucao_selecao": BATCH_SELECAO + "/execucao.json",
    "ranking_selecao": BATCH_SELECAO + "/ranking.csv",
    "resumo_configuracoes_selecao": BATCH_SELECAO + "/resumo_configuracoes.csv",
    "resumo_por_video_selecao": BATCH_SELECAO + "/resumo_por_video.csv",
    "resumo_por_quadro_selecao": BATCH_SELECAO + "/resumo_por_quadro.csv",
}
HASHES_FONTES_FIXAS = {
    "origem_videos_limiarizacao": "ea797b01681b943e7a1f4c2442fe3cb2215e66d4425d4a23dd0af6bd3c784122",
    "origem_selecao": "b33cdd0b1bb16386230bdf4f55a11bf94b57436ceeabe4c163f4aece885636a4",
    "execucao_selecao": "f6a6a46301f8dd646306ea4ff2ed575d6319ae93f1a7f830e00fae5107a7d9e1",
    "ranking_selecao": "7b94caabc4a886245d73c5fecdc19270e614d1268de81a256808507310ef8507",
    "resumo_configuracoes_selecao": "10ff29d7b55bbfc44695ba22d7090d850fd2da6b92fef31000a687b64df59abf",
    "resumo_por_video_selecao": "3dce8c534e2c9d3ecbedc3e5eaec2a982ed7f6ef3bdf6d10e4d7553ce21966bf",
    "resumo_por_quadro_selecao": "d3571e80794eb0644438bb35cc9b0ca3ddfcd3cdcc7aebc97bca633a5d588d54",
}
VIDEOS = ("13", "29", "52", "54")
QUANTIDADES = {"13": 1470, "29": 1470, "52": 1440, "54": 1470}
ALINHAMENTO_SHA256 = "9d24961e1e6da5262573ff900bd709b821c15505674035b737d9597ea10c5913"
DECISAO = "O pesquisador aprovou explicitamente s052, s082, s084, s103 e s051, nesta ordem, para vídeos completos de seleção. Não há promoção automática pelo ranking."
GERACAO_FIXA = {
    "versao_gerador": "1.0", "arquivo_gerador": ARQUIVO_GERADOR,
    "procedimento": "copiar_configuracoes_aprovadas_e_especificacao_congelada_dos_videos",
    "aleatoriedade_utilizada": False, "quantidade_configuracoes": 5, "quantidade_videos": 4,
    "quadros_por_configuracao": 5850, "avaliacoes_previstas": 29250,
    "quantidade_anotacoes": 5850, "quantidade_referencias_alinhamento": 20,
}


def _igual(valor, esperado, contexto):
    selecao._igual(valor, esperado, contexto)


def _pasta_configuracao(item: dict) -> str:
    return ("resultados/frame-to-frame/blobs/selecao/" + selecao.nome_configuracao(item)
            + "__" + BATCH_SELECAO.split("batch__", 1)[1])


def _caminhos_esperados(configuracoes: list[dict]) -> dict[str, str]:
    caminhos = dict(FONTES_FIXAS)
    for item in configuracoes:
        pasta = _pasta_configuracao(item)
        for tipo in ("configuracao", "avaliacao", "execucao"):
            caminhos[f"{tipo}_{item['id']}"] = f"{pasta}/{tipo}.json"
    return caminhos


def caminhos_origens(plano: dict) -> dict[str, str]:
    """22 nomes sem extensão; arquivar cada conteúdo com sua extensão original."""
    return {nome: fonte["arquivo"] for nome, fonte in plano["proveniencia"]["fontes"].items()}


def _validar_videos(videos: list) -> None:
    if not isinstance(videos, list) or len(videos) != 4:
        raise ValueError("O plano exige os quatro vídeos completos de seleção.")
    for video, ident in zip(videos, VIDEOS):
        p._chaves(video, {"video_id", "arquivo", "sha256", "fps", "largura", "altura", "quantidade_quadros",
                         "indice_inicial", "duracao_segundos", "codec", "metadados_mp4", "anotacoes",
                         "referencias_alinhamento"}, "vídeo")
        n = QUANTIDADES[ident]
        fps = n / 30
        base = f"bases_de_dados/visem_tracking/dataset/Train/{ident}"
        for campo, valor in {"video_id": ident, "arquivo": f"{base}/{ident}.mp4", "fps": fps,
                             "largura": 640, "altura": 480, "quantidade_quadros": n, "indice_inicial": 0,
                             "duracao_segundos": 30.0, "codec": "avc1"}.items():
            _igual(video[campo], valor, f"vídeo {ident}: {campo}")
        p._hash_valido(video["sha256"])
        metadados = {"timescale": int(fps * 256), "duracao_ticks": n * 256, "handler": "vide", "codec": "avc1",
                     "largura": 640, "altura": 480, "stts": [[n, 256]], "quantidade_quadros": n,
                     "duracao_segundos": 30.0, "fps": fps, "taxa_constante": True}
        _igual(video["metadados_mp4"], metadados, "metadados MP4 congelados")
        anotacoes = video["anotacoes"]
        if not isinstance(anotacoes, list) or len(anotacoes) != n:
            raise ValueError("É necessária uma anotação para cada quadro do vídeo, sem exclusões.")
        for quadro, anotacao in enumerate(anotacoes):
            p._chaves(anotacao, {"quadro", "arquivo", "sha256"}, "anotação de vídeo")
            _igual(anotacao["quadro"], quadro, "índice da anotação")
            _igual(anotacao["arquivo"], f"{base}/labels/{ident}_frame_{quadro}.txt", "arquivo anotado")
            p._hash_valido(anotacao["sha256"])
        referencias = video["referencias_alinhamento"]
        if not isinstance(referencias, list) or len(referencias) != 5:
            raise ValueError("Cada vídeo deve possuir as cinco referências de alinhamento acordadas.")
        for quadro, ref in zip((0, 100, 700, 1400, n - 1), referencias):
            p._chaves(ref, {"quadro", "imagem", "sha256"}, "referência de alinhamento")
            _igual(ref["quadro"], quadro, "índice de referência")
            _igual(ref["imagem"], f"{base}/images/{ident}_frame_{quadro}.jpg", "JPEG de referência")
            p._hash_valido(ref["sha256"])


def carregar_plano(conteudo: bytes) -> dict:
    """Validação pura de IDs aprovados, identidades, quadro a quadro e fontes."""
    plano = p._json(conteudo)
    p._chaves(plano, {"versao", "tipo", "algoritmo", "etapa", "particao", "seed", "criterios",
                     "politica_anotacoes_ausentes", "alinhamento", "configuracoes", "videos",
                     "proveniencia", "geracao", "regras"}, "plano dos vídeos")
    for campo, valor in {"versao": 1, "tipo": "videos_selecao_blobs", "algoritmo": "blobs",
                         "etapa": "selecao_videos", "particao": "selecao", "seed": 42,
                         "criterios": CRITERIOS, "politica_anotacoes_ausentes": "erro"}.items():
        _igual(plano[campo], valor, campo)
    if p._sha256(p._serializar(plano["alinhamento"])) != ALINHAMENTO_SHA256:
        raise ValueError("Contrato de alinhamento MAE diverge da especificação acordada.")
    _validar_videos(plano["videos"])
    configs = plano["configuracoes"]
    if not isinstance(configs, list) or len(configs) != 5:
        raise ValueError("São exigidas exatamente as cinco configurações aprovadas.")
    for item, ident in zip(configs, IDS_APROVADOS):
        digest = selecao._validar_configuracao(item, ident)
        _igual(digest, IDENTIDADES_APROVADAS[ident], "identidade aprovada")
    proveniencia = plano["proveniencia"]
    p._chaves(proveniencia, {"decisao", "ids_aprovados", "configuracoes_congeladas",
                            "aleatoriedade_utilizada", "fontes", "configuracoes"}, "proveniência")
    for campo, valor in {"decisao": DECISAO, "ids_aprovados": list(IDS_APROVADOS),
                         "configuracoes_congeladas": True, "aleatoriedade_utilizada": False}.items():
        _igual(proveniencia[campo], valor, campo)
    caminhos = _caminhos_esperados(configs)
    fontes = proveniencia["fontes"]
    p._chaves(fontes, set(caminhos), "fontes da preparação")
    for nome, caminho in caminhos.items():
        p._chaves(fontes[nome], {"arquivo", "sha256"}, "fonte arquivável")
        _igual(fontes[nome]["arquivo"], caminho, "caminho de origem")
        p._hash_valido(fontes[nome]["sha256"])
        if nome in HASHES_FONTES_FIXAS:
            _igual(fontes[nome]["sha256"], HASHES_FONTES_FIXAS[nome], "fonte já congelada e auditada")
    p._chaves(proveniencia["configuracoes"], set(IDS_APROVADOS), "linhagem das cinco configurações")
    for item in configs:
        ident = item["id"]
        origem = proveniencia["configuracoes"][ident]
        p._chaves(origem, {"configuracao_sha256", "pasta_selecao", "desenvolvimento"}, "origem de configuração")
        _igual(origem["configuracao_sha256"], IDENTIDADES_APROVADAS[ident], "identidade na proveniência")
        _igual(origem["pasta_selecao"], _pasta_configuracao(item), "pasta aprovada na seleção")
        desenvolvimento = origem["desenvolvimento"]
        p._chaves(desenvolvimento, {"configuracao_sha256", "primeira_origem", "origens"}, "linhagem de desenvolvimento")
        _igual(desenvolvimento["configuracao_sha256"], IDENTIDADES_APROVADAS[ident], "identidade no desenvolvimento")
        p._chaves(desenvolvimento["primeira_origem"], {"rodada", "configuracao_id"}, "primeira origem")
        if not isinstance(desenvolvimento["origens"], list) or not desenvolvimento["origens"]:
            raise ValueError("Falta a linhagem das configurações no desenvolvimento.")
        for alias in desenvolvimento["origens"]:
            p._chaves(alias, {"rodada", "configuracao_id", "pasta_execucao", "sha256_arquivo_configuracao",
                             "sha256_manifesto_execucao"}, "alias no desenvolvimento")
            if alias["rodada"] not in p.ORCAMENTOS:
                raise ValueError("Rodada de origem incompatível.")
            numero = int(alias["rodada"][-1])
            if alias["configuracao_id"] not in {f"r{numero}c{i:02d}" for i in range(1, p.ORCAMENTOS[alias["rodada"]] + 1)}:
                raise ValueError("ID histórico fora da rodada.")
            selecao._caminho(alias["pasta_execucao"])
            p._hash_valido(alias["sha256_arquivo_configuracao"])
            p._hash_valido(alias["sha256_manifesto_execucao"])
        _igual(desenvolvimento["primeira_origem"],
               {k: desenvolvimento["origens"][0][k] for k in ("rodada", "configuracao_id")}, "primeiro alias")
    g = plano["geracao"]
    p._chaves(g, {*GERACAO_FIXA, "sha256_gerador", "python"}, "geração dos vídeos")
    for campo, valor in GERACAO_FIXA.items():
        _igual(g[campo], valor, campo)
    p._hash_valido(g["sha256_gerador"])
    p._texto(g["python"])
    if not isinstance(plano["regras"], list) or not plano["regras"]:
        raise ValueError("Faltam as regras desta etapa.")
    for texto in plano["regras"]:
        p._texto(texto)
    return plano


def _csv(conteudo: bytes) -> list[dict]:
    return list(csv.DictReader(StringIO(conteudo.decode("utf-8-sig"))))


def _conferir_selecao(plano: dict, documentos: dict, raiz: Path) -> None:
    anterior = selecao.carregar_plano(documentos["origem_selecao"])
    manifesto = p._json(documentos["execucao_selecao"])
    for campo, valor in {"versao": 1, "tipo": "selecao_blobs", "etapa": "selecao_imagens",
                         "algoritmo": "blobs", "rodada": "selecao", "particao": "selecao",
                         "situacao": "concluida", "criterios": CRITERIOS,
                         "configuracoes_previstas": 119, "configuracoes_concluidas": 119,
                         "quadros_por_configuracao": 60, "avaliacoes_concluidas": 7140,
                         "plano_sha256": HASHES_FONTES_FIXAS["origem_selecao"]}.items():
        _igual(manifesto.get(campo), valor, "manifesto da seleção")
    copia = selecao._ler(raiz, BATCH_SELECAO + "/plano.json", HASHES_FONTES_FIXAS["origem_selecao"])
    _igual(copia == documentos["origem_selecao"], True, "plano arquivado da seleção")
    fontes = plano["proveniencia"]["fontes"]
    saidas = manifesto.get("saidas_sha256", {})
    for nome, fonte in fontes.items():
        if nome not in ("origem_videos_limiarizacao", "origem_selecao", "execucao_selecao"):
            _igual(saidas.get(fonte["arquivo"]), fonte["sha256"], "hash no manifesto da seleção")
    resumos = _csv(documentos["resumo_configuracoes_selecao"])
    por_id = {x["configuracao_id"]: x for x in resumos}
    if len(resumos) != 119 or set(por_id) != set(selecao.IDS):
        raise ValueError("Resumo da seleção não descreve suas 119 candidatas.")
    ranking = _csv(documentos["ranking_selecao"])
    if len(ranking) != 119 or {x["configuracao_id"] for x in ranking} != set(selecao.IDS):
        raise ValueError("Ranking de origem incompleto; ele não define as IDs aprovadas.")
    videos = _csv(documentos["resumo_por_video_selecao"])
    if len(videos) != 476 or {(x["configuracao_id"], x["video_id"]) for x in videos} != {
            (i, v) for i in selecao.IDS for v in VIDEOS}:
        raise ValueError("Resumo por vídeo de origem incompleto.")
    quadros = _csv(documentos["resumo_por_quadro_selecao"])
    if len(quadros) != 7140 or {(x["configuracao_id"], x["video_id"], int(x["quadro"])) for x in quadros} != {
            (i, v, q) for i in selecao.IDS for v, q in selecao.ORDEM_QUADROS}:
        raise ValueError("Resumo por quadro de origem incompleto.")
    execucoes = manifesto.get("execucoes", [])
    if len(execucoes) != 119 or [x["configuracao_id"] for x in execucoes] != list(selecao.IDS):
        raise ValueError("Execuções de origem incompletas ou fora da ordem congelada.")
    pastas = {x["configuracao_id"]: x["pasta"] for x in execucoes}
    anteriores = {c["id"]: c for c in anterior["configuracoes"]}
    for item in plano["configuracoes"]:
        ident = item["id"]
        _igual(item, anteriores[ident], "configuração congelada na seleção")
        _igual(p._json(documentos[f"configuracao_{ident}"]), item, "parâmetros efetivamente executados")
        origem = plano["proveniencia"]["configuracoes"][ident]
        _igual(origem["desenvolvimento"], anterior["proveniencia"][ident], "linhagem preservada")
        _igual(pastas[ident], origem["pasta_selecao"], "execução de seleção da configuração")
        estado = p._json(documentos[f"execucao_{ident}"])
        for campo, valor in {"tipo": "selecao_blobs", "situacao": "concluida", "configuracao_id": ident,
                             "batch": BATCH_SELECAO, "plano_sha256": HASHES_FONTES_FIXAS["origem_selecao"],
                             "configuracao_sha256": IDENTIDADES_APROVADAS[ident], "quadros_concluidos": 60}.items():
            _igual(estado.get(campo), valor, "manifesto da configuração selecionada")
        avaliacao = p._json(documentos[f"avaliacao_{ident}"])
        _igual(avaliacao.get("quantidade_quadros"), 60, "avaliação concluída na seleção")
        _igual(avaliacao.get("criterios"), CRITERIOS, "critérios da avaliação de origem")
        for campo, valor in colunas_metricas(avaliacao).items():
            texto = por_id[ident][campo]
            if valor is None:
                _igual(texto, "", "métrica sem casos")
            elif isinstance(valor, (int, float)):
                if float(texto) != float(valor):
                    raise ValueError("Avaliação da configuração diverge do resumo auditado.")
            else:
                _igual(texto, str(valor), "métrica da avaliação")
    por_video = {v["video_id"]: v for v in plano["videos"]}
    for q in anterior["quadros"]:
        video = por_video[q["video_id"]]
        _igual(video["anotacoes"][q["quadro"]]["sha256"], q["anotacao_sha256"], "anotação compartilhada JPEG/MP4")
        for ref in video["referencias_alinhamento"]:
            if ref["quadro"] == q["quadro"]:
                _igual(ref["sha256"], q["imagem_sha256"], "JPEG de referência já congelado")


def conferir_origens(plano: dict, raiz: Path) -> dict[str, bytes]:
    """Confere 22 fontes e 4 MP4/5.850 anotações/20 JPEGs; não decodifica mídia."""
    plano = carregar_plano(p._serializar(plano))
    documentos = {nome: selecao._ler(raiz, fonte["arquivo"], fonte["sha256"])
                  for nome, fonte in plano["proveniencia"]["fontes"].items()}
    anterior = p._json(documentos["origem_videos_limiarizacao"])
    for campo, valor in {"versao": 1, "tipo": "videos_selecao", "algoritmo": "limiarizacao",
                         "particao": "selecao", "politica_anotacoes_ausentes": "erro"}.items():
        _igual(anterior.get(campo), valor, "especificação original de vídeos")
    _igual(plano["videos"], anterior.get("videos"), "vídeos e anotações preservados")
    _igual(plano["alinhamento"], anterior.get("alinhamento"), "contrato MAE preservado")
    _conferir_selecao(plano, documentos, raiz)
    for video in plano["videos"]:
        selecao._ler(raiz, video["arquivo"], video["sha256"])
        for anotacao in video["anotacoes"]:
            selecao._ler(raiz, anotacao["arquivo"], anotacao["sha256"])
        for referencia in video["referencias_alinhamento"]:
            selecao._ler(raiz, referencia["imagem"], referencia["sha256"])
    return documentos


def gerar_plano(raiz: Path) -> dict:
    """Prepara a etapa aprovada e verifica bytes; não grava plano ou resultados."""
    originais = {nome: selecao._ler(raiz, caminho, HASHES_FONTES_FIXAS[nome]) for nome, caminho in FONTES_FIXAS.items()}
    selecao_anterior = selecao.carregar_plano(originais["origem_selecao"])
    geometria = p._json(originais["origem_videos_limiarizacao"])
    por_id = {x["id"]: x for x in selecao_anterior["configuracoes"]}
    configs = [deepcopy(por_id[ident]) for ident in IDS_APROVADOS]
    caminhos = _caminhos_esperados(configs)
    fontes = {nome: {"arquivo": caminho, "sha256": p._sha256(originais[nome] if nome in originais
                                                               else selecao._ler(raiz, caminho))}
              for nome, caminho in caminhos.items()}
    plano = {
        "versao": 1, "tipo": "videos_selecao_blobs", "algoritmo": "blobs", "etapa": "selecao_videos",
        "particao": "selecao", "seed": 42, "criterios": deepcopy(CRITERIOS),
        "politica_anotacoes_ausentes": "erro", "alinhamento": deepcopy(geometria["alinhamento"]),
        "configuracoes": configs, "videos": deepcopy(geometria["videos"]),
        "proveniencia": {
            "decisao": DECISAO, "ids_aprovados": list(IDS_APROVADOS),
            "configuracoes_congeladas": True, "aleatoriedade_utilizada": False, "fontes": fontes,
            "configuracoes": {item["id"]: {"configuracao_sha256": IDENTIDADES_APROVADAS[item["id"]],
                                           "pasta_selecao": _pasta_configuracao(item),
                                           "desenvolvimento": deepcopy(selecao_anterior["proveniencia"][item["id"]])}
                              for item in configs},
        },
        "geracao": {**deepcopy(GERACAO_FIXA), "sha256_gerador": p._sha256(Path(__file__).read_bytes()),
                    "python": sys.version.split()[0]},
        "regras": [
            "As cinco IDs aprovadas são fixas e mantêm detector, pré-processamento, classificação e caixa da seleção em JPEGs. Nenhuma busca de parâmetros nesta etapa.",
            "A especificação da limiarização fornece somente vídeos, anotações, metadados e referências MAE; suas configurações e decisões de ranking não são utilizadas.",
            "Processar todos os 5.850 quadros dos quatro MP4 de seleção para cada configuração: 29.250 avaliações. Preservar os mesmos pixels decodificados e anotações entre as cinco.",
            "Antes de detectar, conferir decodificação completa, contagem, FPS, dimensões e alinhamento MAE com as cinco referências de cada vídeo. O estado continua pendente até essa execução.",
            "Anotação ausente interrompe a execução; arquivo existente vazio representa quadro anotado sem objetos. Não há exclusões, deslocamentos temporais ou correções automáticas autorizados.",
            "Somar TP, FP e FN antes de calcular F1; indivíduos 0/2 juntos, aglomerados separados e erros 0/2 registrados à parte, mantendo cobertura por classe e resultados por vídeo.",
            "Tempo do quadro é índice/FPS. Índices das detecções continuam locais ao quadro, sem rastreamento, contagem de indivíduos únicos, velocidade ou comportamento.",
            "Preservar caixas adaptadas e centros, diâmetros e áreas brutos; medidas indisponíveis não se tornam zero. Vídeos anotados serão saídas de inspeção visual.",
            "Seed 42 registrada sem sorteio. As fontes congeladas e o plano completo, não somente a seed, definem a reprodução.",
            "Os vídeos finais 14, 24, 38 e 82 não pertencem a este plano. Revisar os resultados da seleção em conjunto antes de preparar a avaliação final.",
            "O pesquisador executará esta etapa. Cada execução deve criar uma nova pasta e preservar resultados, fontes e falhas anteriores.",
        ],
    }
    plano = carregar_plano(p._serializar(plano))
    conferir_origens(plano, raiz)
    return plano
