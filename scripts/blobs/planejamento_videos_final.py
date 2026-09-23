"""Congelamento das cinco configurações aprovadas para os vídeos finais."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

from analise.avaliacao_individuos import CRITERIOS, agregar
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_selecao as selecao
from scripts.blobs import planejamento_videos as anterior
from scripts.blobs.executar_inspecao import colunas_metricas


ARQUIVO_GERADOR = "scripts/blobs/planejamento_videos_final.py"
PLANO_FINAL_LIMIARIZACAO = "scripts/limiarizacao/videos/plano_final.json"
PLANO_VIDEOS_SELECAO = "scripts/blobs/videos/plano_selecao.json"
BATCH_VIDEOS_SELECAO = "resultados/videos/blobs/selecao/batch__20260921T022547636341Z"
IDS_APROVADOS = anterior.IDS_APROVADOS
IDENTIDADES_APROVADAS = anterior.IDENTIDADES_APROVADAS
VIDEOS = ("14", "24", "38", "82")
QUANTIDADES = {"14": 1470, "24": 1470, "38": 1470, "82": 1500}
FONTES_FIXAS = {
    "origem_videos_final_limiarizacao": PLANO_FINAL_LIMIARIZACAO,
    "origem_videos_selecao_blobs": PLANO_VIDEOS_SELECAO,
    "execucao_videos_selecao_blobs": BATCH_VIDEOS_SELECAO + "/execucao.json",
    "ranking_videos_selecao_blobs": BATCH_VIDEOS_SELECAO + "/ranking.csv",
    "resumo_configuracoes_videos_selecao_blobs": BATCH_VIDEOS_SELECAO + "/resumo_configuracoes.csv",
    "resumo_por_video_videos_selecao_blobs": BATCH_VIDEOS_SELECAO + "/resumo_por_video.csv",
}
HASHES_FONTES_FIXAS = {
    "origem_videos_final_limiarizacao": "b9e4186f6bad088f3fd676bac150a86cd3359656c5363b09ee393df1d1ba294a",
    "origem_videos_selecao_blobs": "cc36923b5a846023e8ee538ea25a8e1ce09791a7ee5f798310165749b512b8ed",
    "execucao_videos_selecao_blobs": "28c618a2cfdd012377006fcc5836e5070cce4a3bf02d333b3b228ee60399f565",
    "ranking_videos_selecao_blobs": "254538236aa4bbce5bfad9870162bd04385ad4e68753b91f0c592208dfcf442f",
    "resumo_configuracoes_videos_selecao_blobs": "3a94ca51df80025d77c75d9a2f750b89bd8ca83b0bdeb1cc4b2a5d7bd5895f8d",
    "resumo_por_video_videos_selecao_blobs": "a9eeecbe454c69f5f412c3f544d2c60c7bc9faec95a252f518653f11bbf849a4",
}
DECISAO = (
    "Após revisar a seleção em vídeos, o pesquisador aprovou preparar a avaliação final das mesmas "
    "cinco configurações s052, s082, s084, s103 e s051, nesta ordem, nos vídeos 14, 24, 38 e 82. "
    "Parâmetros e critérios permanecem congelados; os resultados finais não orientarão novos ajustes."
)
GERACAO_FIXA = {
    "versao_gerador": "1.0", "arquivo_gerador": ARQUIVO_GERADOR,
    "procedimento": "preservar_cinco_aprovadas_e_avaliar_videos_finais_congelados",
    "aleatoriedade_utilizada": False, "quantidade_configuracoes": 5, "quantidade_videos": 4,
    "quadros_por_configuracao": 5910, "avaliacoes_previstas": 29550,
    "quantidade_anotacoes": 5910, "quantidade_referencias_alinhamento": 20,
}
_igual = anterior._igual


def _pasta_configuracao(item: dict) -> str:
    return (BATCH_VIDEOS_SELECAO + "/" + selecao.nome_configuracao(item)
            + "__" + BATCH_VIDEOS_SELECAO.split("batch__", 1)[1])


def _caminhos_esperados(configuracoes: list[dict]) -> dict[str, str]:
    caminhos = {**anterior._caminhos_esperados(configuracoes), **FONTES_FIXAS}
    for item in configuracoes:
        for tipo in ("configuracao", "avaliacao", "execucao"):
            caminhos[f"{tipo}_video_{item['id']}"] = f"{_pasta_configuracao(item)}/{tipo}.json"
    return caminhos


def caminhos_origens(plano: dict) -> dict[str, str]:
    """43 nomes sem extensão, preservando a extensão original ao arquivar."""
    return {nome: fonte["arquivo"] for nome, fonte in plano["proveniencia"]["fontes"].items()}


def _validar_videos(videos: list) -> None:
    if not isinstance(videos, list) or len(videos) != 4:
        raise ValueError("A avaliação final exige seus quatro vídeos completos.")
    for video, ident in zip(videos, VIDEOS):
        p._chaves(video, {"video_id", "arquivo", "sha256", "fps", "largura", "altura", "quantidade_quadros",
                         "indice_inicial", "duracao_segundos", "codec", "metadados_mp4", "anotacoes",
                         "referencias_alinhamento"}, "vídeo final")
        n = QUANTIDADES[ident]
        fps = n / 30
        base = f"bases_de_dados/visem_tracking/dataset/Train/{ident}"
        for campo, valor in {"video_id": ident, "arquivo": f"{base}/{ident}.mp4", "fps": fps,
                             "largura": 640, "altura": 480, "quantidade_quadros": n, "indice_inicial": 0,
                             "duracao_segundos": 30.0, "codec": "avc1"}.items():
            _igual(video[campo], valor, f"vídeo {ident}: {campo}")
        p._hash_valido(video["sha256"])
        _igual(video["metadados_mp4"], {
            "timescale": int(fps * 256), "duracao_ticks": n * 256, "handler": "vide", "codec": "avc1",
            "largura": 640, "altura": 480, "stts": [[n, 256]], "quantidade_quadros": n,
            "duracao_segundos": 30.0, "fps": fps, "taxa_constante": True,
        }, "metadados finais congelados")
        anotacoes = video["anotacoes"]
        if not isinstance(anotacoes, list) or len(anotacoes) != n:
            raise ValueError("É necessária uma anotação por quadro final, sem exclusões.")
        for quadro, anotacao in enumerate(anotacoes):
            p._chaves(anotacao, {"quadro", "arquivo", "sha256"}, "anotação final")
            _igual(anotacao["quadro"], quadro, "índice da anotação final")
            _igual(anotacao["arquivo"], f"{base}/labels/{ident}_frame_{quadro}.txt", "arquivo anotado final")
            p._hash_valido(anotacao["sha256"])
        referencias = video["referencias_alinhamento"]
        if not isinstance(referencias, list) or len(referencias) != 5:
            raise ValueError("Cada vídeo final exige cinco referências de alinhamento.")
        for quadro, ref in zip((0, 100, 700, 1400, n - 1), referencias):
            p._chaves(ref, {"quadro", "imagem", "sha256"}, "referência final")
            _igual(ref["quadro"], quadro, "índice de referência final")
            _igual(ref["imagem"], f"{base}/images/{ident}_frame_{quadro}.jpg", "JPEG de referência final")
            p._hash_valido(ref["sha256"])


def carregar_plano(conteudo: bytes) -> dict:
    """Valida o contrato final sem ler arquivos, decodificar ou executar detectores."""
    plano = p._json(conteudo)
    p._chaves(plano, {"versao", "tipo", "algoritmo", "etapa", "particao", "seed", "criterios",
                     "politica_anotacoes_ausentes", "alinhamento", "configuracoes", "videos",
                     "proveniencia", "geracao", "regras"}, "plano final de blobs")
    for campo, valor in {"versao": 1, "tipo": "videos_final_blobs", "algoritmo": "blobs", "etapa": "final_videos",
                         "particao": "final", "seed": 42, "criterios": CRITERIOS,
                         "politica_anotacoes_ausentes": "erro"}.items():
        _igual(plano[campo], valor, campo)
    if p._sha256(p._serializar(plano["alinhamento"])) != anterior.ALINHAMENTO_SHA256:
        raise ValueError("Contrato MAE final diverge do protocolo aprovado.")
    _validar_videos(plano["videos"])
    configs = plano["configuracoes"]
    if not isinstance(configs, list) or len(configs) != 5:
        raise ValueError("São exigidas exatamente as cinco configurações aprovadas.")
    for item, ident in zip(configs, IDS_APROVADOS):
        _igual(selecao._validar_configuracao(item, ident), IDENTIDADES_APROVADAS[ident], "identidade final")
    prov = plano["proveniencia"]
    p._chaves(prov, {"decisao", "ids_aprovados", "configuracoes_congeladas", "aleatoriedade_utilizada",
                    "fontes", "configuracoes"}, "proveniência final")
    for campo, valor in {"decisao": DECISAO, "ids_aprovados": list(IDS_APROVADOS),
                         "configuracoes_congeladas": True, "aleatoriedade_utilizada": False}.items():
        _igual(prov[campo], valor, campo)
    caminhos = _caminhos_esperados(configs)
    p._chaves(prov["fontes"], set(caminhos), "43 fontes finais")
    hashes_fixos = {**anterior.HASHES_FONTES_FIXAS, **HASHES_FONTES_FIXAS}
    for nome, caminho in caminhos.items():
        fonte = prov["fontes"][nome]
        p._chaves(fonte, {"arquivo", "sha256"}, "fonte final")
        _igual(fonte["arquivo"], caminho, "caminho de origem final")
        p._hash_valido(fonte["sha256"])
        if nome in hashes_fixos:
            _igual(fonte["sha256"], hashes_fixos[nome], "fonte congelada e auditada")
    p._chaves(prov["configuracoes"], set(IDS_APROVADOS), "linhagem final")
    for item in configs:
        origem = prov["configuracoes"][item["id"]]
        p._chaves(origem, {"configuracao_sha256", "pasta_selecao", "desenvolvimento"}, "origem final")
        _igual(origem["configuracao_sha256"], IDENTIDADES_APROVADAS[item["id"]], "hash da linhagem")
        _igual(origem["pasta_selecao"], anterior._pasta_configuracao(item), "pasta original em imagens")
        desenvolvimento = origem["desenvolvimento"]
        p._chaves(desenvolvimento, {"configuracao_sha256", "primeira_origem", "origens"}, "desenvolvimento")
        _igual(desenvolvimento["configuracao_sha256"], origem["configuracao_sha256"], "linhagem de parâmetros")
        p._chaves(desenvolvimento["primeira_origem"], {"rodada", "configuracao_id"}, "primeira origem")
        if not isinstance(desenvolvimento["origens"], list) or not desenvolvimento["origens"]:
            raise ValueError("Falta a linhagem de desenvolvimento.")
        for alias in desenvolvimento["origens"]:
            p._chaves(alias, {"rodada", "configuracao_id", "pasta_execucao", "sha256_arquivo_configuracao",
                             "sha256_manifesto_execucao"}, "alias de desenvolvimento")
            if alias["rodada"] not in p.ORCAMENTOS:
                raise ValueError("Rodada histórica incompatível.")
            numero = int(alias["rodada"][-1])
            if alias["configuracao_id"] not in {
                    f"r{numero}c{i:02d}" for i in range(1, p.ORCAMENTOS[alias["rodada"]] + 1)}:
                raise ValueError("ID histórico incompatível com a rodada.")
            selecao._caminho(alias["pasta_execucao"])
            p._hash_valido(alias["sha256_arquivo_configuracao"])
            p._hash_valido(alias["sha256_manifesto_execucao"])
        _igual(desenvolvimento["primeira_origem"],
               {k: desenvolvimento["origens"][0][k] for k in ("rodada", "configuracao_id")}, "primeiro alias")
    p._chaves(plano["geracao"], {*GERACAO_FIXA, "sha256_gerador", "python"}, "geração final")
    for campo, valor in GERACAO_FIXA.items():
        _igual(plano["geracao"][campo], valor, campo)
    p._hash_valido(plano["geracao"]["sha256_gerador"])
    p._texto(plano["geracao"]["python"])
    if not isinstance(plano["regras"], list) or not plano["regras"]:
        raise ValueError("Faltam as regras da avaliação final.")
    for regra in plano["regras"]:
        p._texto(regra)
    return plano


def _metricas_iguais(linha: dict, avaliacao: dict) -> None:
    for campo, valor in colunas_metricas(avaliacao).items():
        texto = linha[campo]
        if valor is None:
            _igual(texto, "", "métrica sem casos")
        elif isinstance(valor, (int, float)):
            _igual(float(texto), float(valor), "métrica da seleção em vídeos")
        else:
            _igual(texto, str(valor), "métrica da seleção em vídeos")


def _conferir_videos_selecao(plano: dict, documentos: dict, raiz: Path) -> None:
    selecao_videos = anterior.carregar_plano(documentos["origem_videos_selecao_blobs"])
    # A seleção permanece vinculada à cadeia completa de imagens e seus arquivos originais.
    origens_anteriores = anterior.conferir_origens(selecao_videos, raiz)
    for nome, conteudo in origens_anteriores.items():
        _igual(conteudo == documentos[nome], True, "origem preservada da seleção")
        _igual(plano["proveniencia"]["fontes"][nome], selecao_videos["proveniencia"]["fontes"][nome],
               "referência preservada da seleção")
    _igual(plano["configuracoes"], selecao_videos["configuracoes"], "cinco configurações sem ajustes")
    _igual(plano["proveniencia"]["configuracoes"], selecao_videos["proveniencia"]["configuracoes"],
           "linhagem intacta")
    _igual(selecao._ler(raiz, BATCH_VIDEOS_SELECAO + "/plano.json",
                       HASHES_FONTES_FIXAS["origem_videos_selecao_blobs"])
           == documentos["origem_videos_selecao_blobs"], True, "plano arquivado em vídeos")
    manifesto = p._json(documentos["execucao_videos_selecao_blobs"])
    for campo, valor in {"versao": 1, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos",
                         "particao": "selecao", "algoritmo": "blobs", "situacao": "concluida",
                         "criterios": CRITERIOS, "configuracoes_previstas": 5, "configuracoes_concluidas": 5,
                         "quadros_por_configuracao": 5850, "avaliacoes_concluidas": 29250,
                         "videos_previstos": 20, "videos_concluidos": 20, "alinhamento_conferido": True,
                         "plano_sha256": HASHES_FONTES_FIXAS["origem_videos_selecao_blobs"]}.items():
        _igual(manifesto.get(campo), valor, "seleção em vídeos concluída")
    execucoes_esperadas = [{"configuracao_id": item["id"], "pasta": _pasta_configuracao(item)}
                          for item in plano["configuracoes"]]
    _igual(manifesto.get("execucoes"), execucoes_esperadas, "execuções de vídeo aprovadas")
    fontes = plano["proveniencia"]["fontes"]
    for nome in set(fontes) - set(selecao_videos["proveniencia"]["fontes"]) - {
            "origem_videos_final_limiarizacao", "origem_videos_selecao_blobs", "execucao_videos_selecao_blobs"}:
        fonte = fontes[nome]
        _igual(manifesto["saidas_sha256"].get(fonte["arquivo"]), fonte["sha256"], "saída de vídeo registrada")
    resumo = anterior._csv(documentos["resumo_configuracoes_videos_selecao_blobs"])
    ranking = anterior._csv(documentos["ranking_videos_selecao_blobs"])
    videos = anterior._csv(documentos["resumo_por_video_videos_selecao_blobs"])
    for linhas in (resumo, ranking):
        if len(linhas) != 5 or {x["configuracao_id"] for x in linhas} != set(IDS_APROVADOS):
            raise ValueError("A seleção em vídeos deve descrever exatamente as cinco configurações aprovadas.")
    if len(videos) != 20 or {(x["configuracao_id"], x["video_id"]) for x in videos} != {
            (i, vid) for i in IDS_APROVADOS for vid in anterior.VIDEOS}:
        raise ValueError("Resumo por vídeo da seleção incompleto ou misturado à partição final.")
    por_id = {x["configuracao_id"]: x for x in resumo}
    por_video = {(x["configuracao_id"], x["video_id"]): x for x in videos}
    for item in plano["configuracoes"]:
        ident = item["id"]
        _igual(p._json(documentos[f"configuracao_video_{ident}"]), item, "configuração usada em vídeos")
        estado = p._json(documentos[f"execucao_video_{ident}"])
        for campo, valor in {"tipo": "videos_selecao_blobs", "particao": "selecao", "situacao": "concluida",
                             "criterios": CRITERIOS, "configuracao_id": ident, "quadros_concluidos": 5850,
                             "batch": BATCH_VIDEOS_SELECAO, "configuracao_sha256": IDENTIDADES_APROVADAS[ident],
                             "plano_sha256": HASHES_FONTES_FIXAS["origem_videos_selecao_blobs"]}.items():
            _igual(estado.get(campo), valor, "execução concluída da configuração em vídeos")
        saidas = estado.get("videos", [])
        if len(saidas) != 4 or [x.get("video_id") for x in saidas] != list(anterior.VIDEOS):
            raise ValueError("Faltam os quatro vídeos conferidos da configuração selecionada.")
        for video in saidas:
            vid = video["video_id"]
            for campo, valor in {"quantidade_quadros": anterior.QUANTIDADES[vid],
                                 "fps": anterior.QUANTIDADES[vid] / 30, "largura": 1280, "altura": 584,
                                 "codec_solicitado": "mp4v", "decodificacao_conferida": True}.items():
                _igual(video.get(campo), valor, "vídeo comparativo selecionado")
            esperado = f"{_pasta_configuracao(item)}/midia/{ident}__cfg-{IDENTIDADES_APROVADAS[ident][:12]}__video-{vid}.mp4"
            _igual(video["arquivo"], esperado, "caminho do comparativo selecionado")
            p._hash_valido(video["sha256"])
            _igual(manifesto["saidas_sha256"].get(esperado), video["sha256"], "hash do comparativo registrado")
        avaliacao = p._json(documentos[f"avaliacao_video_{ident}"])
        _igual(avaliacao.get("criterios"), CRITERIOS, "critérios da avaliação em vídeos")
        _igual(sorted(avaliacao["por_video"]), sorted(anterior.VIDEOS), "partição da avaliação selecionada")
        _igual(avaliacao["total"]["quantidade_quadros"], 5850, "avaliações da configuração")
        _igual(int(por_id[ident]["quantidade_quadros"]), 5850, "quadros no resumo selecionado")
        _igual(por_id[ident]["pasta_origem"], _pasta_configuracao(item), "pasta no resumo selecionado")
        _metricas_iguais(por_id[ident], avaliacao["total"])
        _metricas_iguais(next(x for x in ranking if x["configuracao_id"] == ident), avaliacao["total"])
        for vid in anterior.VIDEOS:
            parcial = avaliacao["por_video"][vid]
            _igual(parcial["quantidade_quadros"], anterior.QUANTIDADES[vid], "quadros na avaliação por vídeo")
            _igual(int(por_video[(ident, vid)]["quantidade_quadros"]), anterior.QUANTIDADES[vid], "quadros por vídeo")
            _metricas_iguais(por_video[(ident, vid)], parcial)
        agregado = agregar(list(avaliacao["por_video"].values()))
        # agregar conta itens recebidos; aqui os quatro itens já agregam vários quadros.
        agregado["quantidade_quadros"] = sum(x["quantidade_quadros"] for x in avaliacao["por_video"].values())
        _igual(agregado, avaliacao["total"], "agregação dos quatro vídeos")


def conferir_origens(plano: dict, raiz: Path) -> dict[str, bytes]:
    """Confere 43 fontes e os bytes dos quatro MP4, 5.910 rótulos e 20 JPEGs finais."""
    plano = carregar_plano(p._serializar(plano))
    documentos = {nome: selecao._ler(raiz, fonte["arquivo"], fonte["sha256"])
                  for nome, fonte in plano["proveniencia"]["fontes"].items()}
    geometria = p._json(documentos["origem_videos_final_limiarizacao"])
    for campo, valor in {"versao": 1, "tipo": "videos_final", "algoritmo": "limiarizacao",
                         "particao": "final", "politica_anotacoes_ausentes": "erro"}.items():
        _igual(geometria.get(campo), valor, "especificação dos vídeos finais")
    _igual(plano["videos"], geometria.get("videos"), "vídeos finais originais")
    _igual(plano["alinhamento"], geometria.get("alinhamento"), "alinhamento final original")
    _conferir_videos_selecao(plano, documentos, raiz)
    for video in plano["videos"]:
        selecao._ler(raiz, video["arquivo"], video["sha256"])
        for anotacao in video["anotacoes"]:
            selecao._ler(raiz, anotacao["arquivo"], anotacao["sha256"])
        for ref in video["referencias_alinhamento"]:
            selecao._ler(raiz, ref["imagem"], ref["sha256"])
    return documentos


def gerar_plano(raiz: Path) -> dict:
    """Monta o plano final reprodutível sem executar detector nem produzir resultados."""
    documentos = {nome: selecao._ler(raiz, caminho, HASHES_FONTES_FIXAS[nome])
                  for nome, caminho in FONTES_FIXAS.items()}
    selecao_videos = anterior.carregar_plano(documentos["origem_videos_selecao_blobs"])
    geometria = p._json(documentos["origem_videos_final_limiarizacao"])
    plano = deepcopy(selecao_videos)
    plano.update(tipo="videos_final_blobs", etapa="final_videos", particao="final",
                 videos=deepcopy(geometria["videos"]), alinhamento=deepcopy(geometria["alinhamento"]))
    plano["proveniencia"]["decisao"] = DECISAO
    plano["proveniencia"]["fontes"] = {
        nome: {"arquivo": caminho, "sha256": p._sha256(documentos[nome] if nome in documentos
                                                       else selecao._ler(raiz, caminho))}
        for nome, caminho in _caminhos_esperados(plano["configuracoes"]).items()
    }
    plano["geracao"] = {**deepcopy(GERACAO_FIXA), "sha256_gerador": p._sha256(Path(__file__).read_bytes()),
                        "python": sys.version.split()[0]}
    plano["regras"] = [
        "As cinco configurações aprovadas permanecem idênticas às seleções em imagens e vídeos, sem novos ajustes ou promoção automática pelo ranking final.",
        "A limiarização fornece somente a especificação dos quatro vídeos finais, anotações, metadados e referências de alinhamento; suas configurações e resultados não são herdados.",
        "Processar todos os 5.910 quadros dos vídeos 14, 24, 38 e 82 para cada configuração, totalizando 29.550 avaliações e 20 vídeos comparativos.",
        "Antes de detectar, conferir sequência completa, FPS, dimensões e alinhamento MAE com cinco JPEGs por vídeo. Manter hashes dos pixels para igualdade entre configurações.",
        "Anotação ausente interrompe a execução; arquivo existente vazio representa quadro anotado sem objetos. Não excluir quadros, deslocar anotações ou corrigir alinhamento automaticamente.",
        "Manter IoU >= 0,5 e pareamento um-para-um por grupo; indivíduos 0/2 juntos, aglomerados separados, erros 0/2 e cobertura por classe registrados separadamente. Agregar contagens antes do F1.",
        "Tempo do quadro é índice/FPS. Centros, diâmetros e medidas brutas permanecem disponíveis; índices são locais ao quadro, sem rastreamento, velocidade ou contagem de indivíduos únicos.",
        "O ranking final descreve o desempenho das cinco configurações congeladas; estes resultados não orientarão novas configurações neste protocolo.",
        "A partição final desta versão não implica dados historicamente inéditos: há exposição em experimentos anteriores, preservados em master e em ../my_tcc_historico_20260914/.",
        "Seed 42 é registrada sem sorteio; plano, configurações e arquivos congelados definem a reprodução. Preservar resultados anteriores e arquivar as 43 origens em subpasta própria.",
        "O pesquisador executará a etapa. O PDF e os vídeos comparativos servem à análise final; a preparação do plano não executa detectores nem valida resultados ainda inexistentes.",
    ]
    plano = carregar_plano(p._serializar(plano))
    conferir_origens(plano, raiz)
    return plano
