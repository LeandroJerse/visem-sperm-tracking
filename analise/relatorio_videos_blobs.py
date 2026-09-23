"""Relatórios dos candidatos nos vídeos de seleção e finais, sem executar detectores."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import platform

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import CONTAGENS, _conferir_metricas, _csv, _inteiro, _json, _numero
from analise.relatorio_rodada_blobs import _rotulo_configuracao, _valor
from analise.relatorio_selecao_blobs import _ranking
from scripts.blobs.arquivos import gravar_json
from scripts.limiarizacao.inspecionar_imagem import agora, sha256


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/videos/blobs/selecao"
SAIDA_FINAL = RAIZ / "resultados/videos/blobs/final"
IDS = ("s052", "s082", "s084", "s103", "s051")
QUADROS = {"13": 1470, "29": 1470, "52": 1440, "54": 1470}
FPS = {"13": 49, "29": 49, "52": 48, "54": 49}
QUADROS_FINAL = {"14": 1470, "24": 1470, "38": 1470, "82": 1500}
FPS_FINAL = {"14": 49, "24": 49, "38": 49, "82": 50}
TEMPOS = ("preprocessamento", "detector", "adaptacao", "pipeline")
FONTES_RELATORIO = (
    "analise/relatorio_videos_blobs.py", "analise/relatorio_inspecao_blobs.py",
    "analise/relatorio_rodada_blobs.py", "analise/relatorio_selecao_blobs.py",
    "analise/avaliacao_individuos.py", "scripts/blobs/arquivos.py",
    "scripts/limiarizacao/inspecionar_imagem.py",
)


def _etapa(particao):
    if particao == "selecao":
        return {"particao": particao, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos",
                "saida": SAIDA, "quadros": QUADROS, "fps": FPS, "titulo": "seleção"}
    if particao == "final":
        return {"particao": particao, "tipo": "videos_final_blobs", "etapa": "final_videos",
                "saida": SAIDA_FINAL, "quadros": QUADROS_FINAL, "fps": FPS_FINAL, "titulo": "avaliação final"}
    raise ValueError("Etapa precisa ser seleção ou final.")


def carregar(pasta: Path) -> dict:
    """Valida todas as métricas por quadro e hashes das mídias; não decodifica MP4."""
    pasta = Path(pasta).expanduser().resolve(strict=True)
    raiz = RAIZ.resolve()
    etapas = [_etapa(p) for p in ("selecao", "final")]
    correspondentes = [e for e in etapas if pasta.parent == e["saida"].resolve()
                      and e["saida"].resolve().is_relative_to(raiz)]
    if len(correspondentes) != 1 or not pasta.is_dir() or not pasta.name.startswith("batch__"):
        raise ValueError("Informe um batch diretamente em resultados/videos/blobs/selecao ou final.")
    etapa = correspondentes[0]
    quadros, fps = etapa["quadros"], etapa["fps"]
    quantidade = sum(quadros.values())
    hashes = {}

    def interno(nome):
        caminho = Path(nome)
        if not caminho.is_absolute():
            caminho = pasta / caminho
        caminho = caminho.resolve(strict=True)
        if not caminho.is_relative_to(pasta) or not caminho.is_file():
            raise ValueError("Fonte precisa ser um arquivo dentro do batch.")
        return caminho

    def ler(nome, conferir=True):
        caminho = interno(nome)
        blob = caminho.read_bytes()
        chave = caminho.relative_to(raiz).as_posix()
        digest = sha256(blob)
        hashes[chave] = digest
        if conferir and m.get("saidas_sha256", {}).get(chave) != digest:
            raise ValueError(f"Hash divergente ou ausente: {caminho.name}.")
        return blob

    manifesto_bytes = ler("execucao.json", False)
    m = _json(manifesto_bytes)
    fixos = {"versao": 1, "tipo": etapa["tipo"], "etapa": etapa["etapa"],
             "particao": etapa["particao"], "algoritmo": "blobs", "situacao": "concluida",
             "criterios": CRITERIOS, "configuracoes_previstas": 5, "configuracoes_concluidas": 5,
             "quadros_por_configuracao": quantidade, "avaliacoes_concluidas": quantidade * 5,
             "videos_concluidos": 20, "alinhamento_conferido": True}
    if any(m.get(k) != v or type(m.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Manifesto não descreve uma etapa de vídeos completa e alinhada na pasta correspondente.")
    plano_bytes = ler("plano.json")
    if sha256(plano_bytes) != m.get("plano_sha256"):
        raise ValueError("Hash do plano salvo divergente.")
    plano = _json(plano_bytes)
    for campo in ("versao", "tipo", "etapa", "particao", "algoritmo", "criterios"):
        if plano.get(campo) != fixos[campo] or type(plano.get(campo)) is not type(fixos[campo]):
            raise ValueError("Plano incompatível com a etapa de vídeos de blobs.")
    configs = plano.get("configuracoes", [])
    if [x.get("id") for x in configs] != list(IDS):
        raise ValueError("Plano não contém as cinco configurações autorizadas na ordem aprovada.")
    videos = plano.get("videos", [])
    if [x.get("video_id") for x in videos] != list(quadros):
        raise ValueError("Plano não contém os quatro vídeos da etapa.")
    for video in videos:
        v = video["video_id"]
        if (type(video.get("quantidade_quadros")) is not int or video["quantidade_quadros"] != quadros[v]
                or video.get("fps") != fps[v] or video.get("largura") != 640 or video.get("altura") != 480
                or video.get("indice_inicial") != 0
                or [a.get("quadro") for a in video.get("anotacoes", [])] != list(range(quadros[v]))):
            raise ValueError("Metadados/anotações do vídeo incompatíveis com a sequência completa.")
        for origem in [video, *video["anotacoes"]]:
            if m.get("origens_sha256", {}).get(origem["arquivo"]) != origem["sha256"]:
                raise ValueError("Hash original de vídeo/anotação diverge do plano.")
    _conferir_origens(plano, m, ler)
    totais = _csv(ler("resumo_configuracoes.csv"))
    por_video_linhas = _csv(ler("resumo_por_video.csv"))
    ranking_salvo = _csv(ler("ranking.csv"))
    por_id = {x["configuracao_id"]: x for x in totais}
    por_video = {(x["configuracao_id"], x["video_id"]): x for x in por_video_linhas}
    if len(totais) != 5 or set(por_id) != set(IDS):
        raise ValueError("Resumo deve conter as cinco configurações uma única vez.")
    if len(por_video_linhas) != 20 or set(por_video) != {(i, v) for i in IDS for v in quadros}:
        raise ValueError("Resumo por vídeo incompleto ou repetido.")
    for linha in [*totais, *por_video_linhas]:
        _conferir_metricas(linha)
    execucoes = m.get("execucoes", [])
    mapa_exec = {x["configuracao_id"]: x["pasta"] for x in execucoes}
    if len(execucoes) != 5 or set(mapa_exec) != set(IDS) or len(set(mapa_exec.values())) != 5:
        raise ValueError("Pastas das cinco execuções incompletas ou repetidas.")
    planos_video = {x["video_id"]: x for x in videos}
    suportes, midias = {}, []
    campos_soma = [*CONTAGENS, *[f"tempo_{t}_ns" for t in TEMPOS]]

    def conferir_agregado(total, soma, n):
        if _inteiro(total["quantidade_quadros"]) != n:
            raise ValueError("Quantidade de quadros incompatível no agregado.")
        for campo in CONTAGENS:
            if _inteiro(total[campo]) != soma[campo]:
                raise ValueError(f"Agregação inconsistente: {campo}.")
        for t in TEMPOS:
            if _inteiro(total[f"tempo_{t}_total_ns"]) != soma[f"tempo_{t}_ns"]:
                raise ValueError(f"Agregação de tempo inconsistente: {t}.")

    for item in configs:
        ident = item["id"]
        origem = (raiz / mapa_exec[ident]).resolve(strict=True)
        if origem.parent != pasta or not origem.is_dir() or origem.name == "relatorios":
            raise ValueError("Cada configuração deve ocupar uma subpasta direta do batch.")
        total = por_id[ident]
        if (total["pasta_origem"] != mapa_exec[ident]
                or any(total[c] != item[c] for c in ("bloco", "perfil_forma"))
                or total["modo_caixa"] != item["caixa"]["modo"]):
            raise ValueError("Metadados do agregado divergem do plano/manifesto.")
        if _json(ler(origem / "configuracao.json")) != item:
            raise ValueError("Configuração salva diverge do plano congelado.")
        e = _json(ler(origem / "execucao.json"))
        if (e.get("situacao") != "concluida" or e.get("configuracao_id") != ident
                or e.get("plano_sha256") != m["plano_sha256"]
                or e.get("batch") != pasta.relative_to(raiz).as_posix()
                or e.get("configuracao_sha256") != plano["proveniencia"]["configuracoes"][ident]["configuracao_sha256"]
                or type(e.get("quadros_concluidos")) is not int or e["quadros_concluidos"] != quantidade):
            raise ValueError("Execução da configuração incompleta ou incompatível.")
        linhas = _csv(ler(origem / "por_quadro.csv"))
        chaves = [(x["video_id"], _inteiro(x["quadro"])) for x in linhas]
        esperadas = [(v, q) for v in quadros for q in range(quadros[v])]
        if chaves != esperadas:
            raise ValueError("Sequência por quadro incompleta, repetida ou fora de ordem.")
        somas = {v: dict.fromkeys(campos_soma, 0) for v in quadros}
        for linha, (v, q) in zip(linhas, chaves):
            _conferir_metricas(linha)
            video = planos_video[v]
            if linha["video"] != video["arquivo"] or linha["anotacao"] != video["anotacoes"][q]["arquivo"]:
                raise ValueError("Origem de vídeo/anotação do quadro divergente do plano.")
            if (_inteiro(linha["imagem_largura_px"]) != video["largura"]
                    or _inteiro(linha["imagem_altura_px"]) != video["altura"]):
                raise ValueError("Dimensões do quadro divergentes do plano.")
            t, td = _numero(linha["tempo_segundos"]), _numero(linha["tempo_decodificador_segundos"])
            if (t is None or not math.isclose(t, q / video["fps"], rel_tol=1e-12, abs_tol=1e-12)
                    or (td is not None and td < 0)):
                raise ValueError("Tempo do quadro inválido ou incompatível com FPS/índice.")
            if _inteiro(linha["quantidade_anotacoes"]) != sum(_inteiro(linha[f"anotacoes_classe_{cl}"]) for cl in (0, 1, 2)):
                raise ValueError("Total de anotações inconsistente.")
            if _inteiro(linha["quantidade_deteccoes"]) != sum(_inteiro(linha[f"{c}_{g}"]) for c in ("tp", "fp") for g in ("individuos", "aglomerados")):
                raise ValueError("Total de detecções inconsistente.")
            ns = {t: _inteiro(linha[f"tempo_{t}_ns"]) for t in TEMPOS}
            if ns["pipeline"] != ns["preprocessamento"] + ns["detector"] + ns["adaptacao"]:
                raise ValueError("Tempo do pipeline difere da soma de suas etapas.")
            suporte = tuple(_inteiro(linha[f"anotacoes_classe_{cl}"]) for cl in (0, 2, 1))
            if (v, q) in suportes and suportes[v, q] != suporte:
                raise ValueError("Anotações diferentes entre configurações no mesmo quadro.")
            suportes[v, q] = suporte
            for campo in campos_soma:
                somas[v][campo] += _inteiro(linha[campo])
        conferir_agregado(total, {c: sum(somas[v][c] for v in quadros) for c in campos_soma}, quantidade)
        for v in quadros:
            parcial = por_video[ident, v]
            if parcial["pasta_origem"] != mapa_exec[ident]:
                raise ValueError("Pasta de origem divergente no resumo por vídeo.")
            conferir_agregado(parcial, somas[v], quadros[v])
        registros = e.get("videos", [])
        if [x.get("video_id") for x in registros] != list(quadros):
            raise ValueError("Registro das quatro mídias incompleto ou fora de ordem.")
        for registro in registros:
            v = registro["video_id"]
            if (registro.get("quantidade_quadros") != quadros[v] or registro.get("fps") != fps[v]
                    or registro.get("largura") != 1280 or registro.get("altura") != 584
                    or registro.get("codec_solicitado") != "mp4v" or registro.get("decodificacao_conferida") is not True):
                raise ValueError("Mídia sem confirmação de decodificação/metadados compatíveis.")
            arquivo = interno(raiz / registro["arquivo"])
            if not arquivo.is_relative_to(origem) or arquivo.suffix.lower() != ".mp4":
                raise ValueError("Mídia deve permanecer na pasta de sua configuração.")
            resumo = hashlib.sha256()
            with arquivo.open("rb") as f:
                for bloco in iter(lambda: f.read(1024 * 1024), b""):
                    resumo.update(bloco)
            digest = resumo.hexdigest(); chave = arquivo.relative_to(raiz).as_posix()
            if digest != registro.get("sha256") or digest != m.get("saidas_sha256", {}).get(chave):
                raise ValueError("Hash da mídia divergente do manifesto/registro.")
            hashes[chave] = digest
            midias.append(registro)
    if len({x["arquivo"] for x in midias}) != 20:
        raise ValueError("Mídias repetidas entre configurações ou vídeos.")
    ranking = _ranking(por_id, list(IDS))
    if ranking_salvo != ranking:
        raise ValueError("Ranking salvo incompatível com F1 exato/empates das contagens.")
    return {"pasta": pasta, "manifesto": m, "manifesto_bytes": manifesto_bytes,
            "plano": plano, "plano_bytes": plano_bytes, "resumos": por_id,
            "por_video": por_video, "ranking": ranking, "hashes": hashes, "midias": midias}


def _conferir_origens(plano, manifesto, ler):
    """Confere as fontes congeladas e a continuidade dos candidatos aprovados."""
    pasta_origens = manifesto.get("pasta_origens", ".")
    if pasta_origens not in (".", "origens"):
        raise ValueError("Pasta de origens deve ser a raiz histórica ou origens/.")
    prov = plano.get("proveniencia", {})
    nomes = {"origem_videos_limiarizacao", "origem_selecao", "execucao_selecao", "ranking_selecao",
             "resumo_configuracoes_selecao", "resumo_por_video_selecao", "resumo_por_quadro_selecao",
             *[f"{tipo}_{ident}" for ident in IDS for tipo in ("configuracao", "avaliacao", "execucao")]}
    final = plano["particao"] == "final"
    if final:
        nomes.update({"origem_videos_final_limiarizacao", "origem_videos_selecao_blobs",
                      "execucao_videos_selecao_blobs", "ranking_videos_selecao_blobs",
                      "resumo_configuracoes_videos_selecao_blobs", "resumo_por_video_videos_selecao_blobs",
                      *[f"{tipo}_video_{ident}" for ident in IDS for tipo in ("configuracao", "avaliacao", "execucao")]})
    fontes = prov.get("fontes", {})
    if (set(fontes) != nomes or prov.get("ids_aprovados") != list(IDS)
            or prov.get("configuracoes_congeladas") is not True or prov.get("aleatoriedade_utilizada") is not False
            or set(prov.get("configuracoes", {})) != set(IDS)):
        raise ValueError(f"Proveniência deve conter as {len(nomes)} fontes e os cinco candidatos aprovados.")
    documentos = {}
    for nome, fonte in fontes.items():
        extensao = Path(fonte["arquivo"]).suffix.lower()
        if extensao not in (".json", ".csv"):
            raise ValueError("Fonte de proveniência deve ser JSON ou CSV.")
        blob = ler((Path(pasta_origens) / (nome + extensao)).as_posix())
        if (sha256(blob) != fonte["sha256"]
                or manifesto.get("origens_sha256", {}).get(fonte["arquivo"]) != fonte["sha256"]):
            raise ValueError(f"Hash da origem congelada divergente: {nome}.")
        documentos[nome] = _json(blob) if extensao == ".json" else _csv(blob)
    if manifesto["plano_sha256"] not in manifesto.get("origens_sha256", {}).values():
        raise ValueError("Hash do plano original ausente do manifesto.")
    anterior = documentos["origem_videos_final_limiarizacao" if final else "origem_videos_limiarizacao"]
    if plano.get("alinhamento") != anterior.get("alinhamento") or plano["videos"] != anterior.get("videos"):
        raise ValueError("Vídeos/alinhamento diferentes da referência congelada.")
    for video in plano["videos"]:
        for ref in video.get("referencias_alinhamento", []):
            if manifesto.get("origens_sha256", {}).get(ref["imagem"]) != ref["sha256"]:
                raise ValueError("Hash de referência de alinhamento incompatível.")
    selecao = documentos["origem_selecao"]
    exec_selecao = documentos["execucao_selecao"]
    if (selecao.get("etapa") != "selecao_imagens" or selecao.get("criterios") != CRITERIOS
            or exec_selecao.get("situacao") != "concluida" or exec_selecao.get("criterios") != CRITERIOS
            or exec_selecao.get("configuracoes_concluidas") != 119
            or exec_selecao.get("quadros_por_configuracao") != 60
            or exec_selecao.get("plano_sha256") != fontes["origem_selecao"]["sha256"]):
        raise ValueError("A origem deve ser a seleção em imagens concluída com critérios atuais.")
    por_id = {x["id"]: x for x in selecao.get("configuracoes", [])}
    for item in plano["configuracoes"]:
        ident = item["id"]
        origem = prov["configuracoes"][ident]
        e = documentos[f"execucao_{ident}"]
        if (por_id.get(ident) != item or documentos[f"configuracao_{ident}"] != item
                or e.get("configuracao_id") != ident or e.get("situacao") != "concluida"
                or e.get("configuracao_sha256") != origem["configuracao_sha256"]
                or e.get("plano_sha256") != fontes["origem_selecao"]["sha256"]
                or e.get("quadros_concluidos") != 60):
            raise ValueError("Configuração diferente da candidata congelada na seleção em imagens.")
    if final:
        _conferir_selecao_videos(plano, documentos, fontes)


def _conferir_selecao_videos(plano, documentos, fontes):
    """Vincula a avaliação final à seleção em vídeos concluída, sem reclassificar candidatos."""
    anterior = documentos["origem_videos_selecao_blobs"]
    execucao = documentos["execucao_videos_selecao_blobs"]
    fixos = {"versao": 1, "tipo": "videos_selecao_blobs", "etapa": "selecao_videos",
             "particao": "selecao", "algoritmo": "blobs", "criterios": CRITERIOS}
    for campo, valor in fixos.items():
        if any(doc.get(campo) != valor or type(doc.get(campo)) is not type(valor)
               for doc in (anterior, execucao)):
            raise ValueError("Origem deve ser a seleção de vídeos de blobs com os mesmos critérios.")
    estado = {"situacao": "concluida", "configuracoes_previstas": 5, "configuracoes_concluidas": 5,
              "quadros_por_configuracao": 5850, "avaliacoes_concluidas": 29250,
              "videos_concluidos": 20, "alinhamento_conferido": True,
              "plano_sha256": fontes["origem_videos_selecao_blobs"]["sha256"]}
    if any(execucao.get(c) != v or type(execucao.get(c)) is not type(v) for c, v in estado.items()):
        raise ValueError("Seleção de vídeos anterior incompleta ou sem alinhamento conferido.")
    if (anterior.get("configuracoes") != plano["configuracoes"]
            or anterior.get("proveniencia", {}).get("configuracoes") != plano["proveniencia"]["configuracoes"]
            or anterior.get("videos") != documentos["origem_videos_limiarizacao"].get("videos")
            or anterior.get("alinhamento") != documentos["origem_videos_limiarizacao"].get("alinhamento")
            or [v.get("video_id") for v in anterior.get("videos", [])] != list(QUADROS)):
        raise ValueError("Candidatos ou referências diferentes da seleção em vídeos congelada.")
    fontes_anteriores = anterior.get("proveniencia", {}).get("fontes", {})
    nomes_anteriores = {"origem_videos_limiarizacao", "origem_selecao", "execucao_selecao", "ranking_selecao",
                        "resumo_configuracoes_selecao", "resumo_por_video_selecao", "resumo_por_quadro_selecao",
                        *[f"{tipo}_{ident}" for ident in IDS for tipo in ("configuracao", "avaliacao", "execucao")]}
    if set(fontes_anteriores) != nomes_anteriores or any(fontes[n] != fontes_anteriores[n] for n in nomes_anteriores):
        raise ValueError("Origens da seleção em imagens diferentes entre as etapas de vídeo.")
    for item in plano["configuracoes"]:
        ident = item["id"]
        e = documentos[f"execucao_video_{ident}"]
        if (documentos[f"configuracao_video_{ident}"] != item or e.get("configuracao_id") != ident
                or e.get("situacao") != "concluida" or e.get("quadros_concluidos") != 5850
                or e.get("configuracao_sha256") != plano["proveniencia"]["configuracoes"][ident]["configuracao_sha256"]
                or e.get("plano_sha256") != fontes["origem_videos_selecao_blobs"]["sha256"]):
            raise ValueError("Configuração final difere da execução concluída na seleção de vídeos.")


def escrever_pdf(caminho: Path, dados: dict) -> int:
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.utils import simpleSplit

    largura, altura = landscape(A4)
    c = Canvas(str(caminho), pagesize=(largura, altura))
    etapa = _etapa(dados["plano"]["particao"])
    final = etapa["particao"] == "final"
    quadros, fps = etapa["quadros"], etapa["fps"]
    quantidade = sum(quadros.values())
    numero = lambda valor: f"{valor:,}".replace(",", ".")
    ids_videos = ", ".join(list(quadros)[:-1]) + " e " + list(quadros)[-1]
    c.setTitle(f"Blobs - comparação nos vídeos de {etapa['titulo']}")
    c.setAuthor("Pesquisa de detecção de espermatozoides")
    margem, util = 32, largura - 64
    configs = {x["id"]: x for x in dados["plano"]["configuracoes"]}
    linhas = dados["ranking"]
    azul, roxo = "#167d9a", "#b8642d"

    def texto(valor, x, y, tam=9, bold=False, cor="#253b4b"):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", tam); c.setFillColor(HexColor(cor))
        c.drawString(x, y, str(valor))

    def paragrafo(valor, y, tam=9, x=margem, w=util):
        for linha in simpleSplit(valor, "Helvetica", tam, w):
            texto(linha, x, y, tam); y -= tam + 4
        return y - 8

    def faixa(y):
        c.setFillColor(HexColor("#eaf1f5")); c.rect(margem - 3, y - 6, util + 6, 19, fill=1, stroke=0)

    def cabecalho(titulo, pagina):
        c.setFillColor(HexColor("#f2f6f8")); c.rect(0, altura - 87, largura, 87, fill=1, stroke=0)
        texto(f"BLOBS  |  VÍDEOS DE {etapa['titulo'].upper()}", margem, altura - 26, 10, True, azul)
        texto(titulo, margem, altura - 50, 20, True)
        texto(f"5 configurações | vídeos {ids_videos} completos | {numero(quantidade)} quadros por configuração | {numero(quantidade * 5)} avaliações", margem, altura - 70, 8.5)
        contexto = "avaliação final com configurações congeladas" if final else "etapa anterior à avaliação final reservada"
        texto(f"Sem rastreamento | {contexto} | plano {dados['manifesto']['plano_sha256'][:12]}", margem, 21, 7.5)
        texto(f"{pagina}/4", largura - 53, 21, 8)

    cabecalho("Desempenho de localização de indivíduos", 1)
    y = paragrafo("Indivíduos = classes 0 e 2 juntas. F1 usa TP, FP e FN somados em todos os quadros; aglomerados são avaliados separadamente. Nenhuma configuração é escolhida automaticamente por este relatório.", 487)
    for k in range(6):
        x = margem + 174 + k / 5 * 310
        c.setStrokeColor(HexColor("#dbe5e9")); c.line(x, 209, x, 424)
        texto(f"{k / 5:.1f}".replace(".", ","), x - 6, 195, 8)
    texto("Configuração / posto", margem, 440, 9, True)
    for label, dx in (("F1", 502), ("Precisão", 573), ("Recall", 666)):
        texto(label, margem + dx, 440, 9, True)
    for j, linha in enumerate(linhas):
        y = 407 - j * 43
        item = configs[linha["configuracao_id"]]
        texto(_rotulo_configuracao(item), margem, y, 10, True)
        texto("Posto " + (linha["posicao"] or "sem casos"), margem, y - 15, 8)
        valor = _numero(linha["f1_individuos"])
        if valor is not None:
            c.setFillColor(HexColor(azul if item["metodo"] == "simpleblob" else roxo))
            c.rect(margem + 174, y - 3, 310 * valor, 15, fill=1, stroke=0)
        for campo, dx in (("f1_individuos", 502), ("precisao_individuos", 573), ("recall_individuos", 666)):
            texto(_valor(linha[campo]), margem + dx, y, 11, campo == "f1_individuos")
    texto("SB = SimpleBlob; DoG = Difference of Gaussians; C = objetos claros; M = margem em pixels por lado.", margem, 173, 8)
    y = 154
    for frase in (
        "Caixas com IoU >= 0,50 e correspondência exclusiva. F1 exato das contagens ordena a apresentação; empates têm o mesmo posto. Não há peso ou desempate pela classe 0.",
        "No F1, sem casos indica ausência de anotações e previsões no grupo. Somente previsões ou somente anotações dão F1 = 0. Valores impressos são arredondados; o ranking não é.",
        ("Estes quatro vídeos compõem a avaliação final do protocolo, com configurações e critérios congelados. O histórico de exposição aos dados permanece relevante; esta etapa não comprova que os vídeos sejam inéditos."
         if final else "Estes quatro vídeos já forneceram as imagens de seleção. A sequência completa amplia a observação temporal, mas não constitui uma nova avaliação independente ou a avaliação final reservada."),
    ):
        y = paragrafo(frase, y, 8.5)
    c.showPage()

    cabecalho("Cobertura por classe e erros de classificação", 2)
    total = linhas[0]
    y = paragrafo(f"Anotações somadas: normal {total['anotacoes_classe_0']}; pequeno {total['anotacoes_classe_2']}; aglomerado {total['anotacoes_classe_1']}. São ocorrências em quadros: um mesmo espermatozoide pode aparecer repetidamente.", 487)
    colunas = [("ID", 0), ("TP indiv.", 56), ("FP indiv.", 124), ("FN indiv.", 192),
               ("Cobertura 0", 274), ("Cobertura 2", 380), ("Cobertura 1", 488), ("F1 aglom.", 608)]
    faixa(440)
    for titulo, dx in colunas:
        texto(titulo, margem + dx, 440, 9, True)
    for j, linha in enumerate(linhas):
        y = 414 - j * 29
        valores = [linha["configuracao_id"], *[linha[f"{c}_individuos"] for c in ("tp", "fp", "fn")],
                   *[_valor(linha[f"recall_classe_{cl}"]) for cl in (0, 2, 1)], _valor(linha["f1_aglomerados"])]
        for valor, (_, dx) in zip(valores, colunas):
            texto(valor, margem + dx, y, 10)
    faixa(250)
    colunas2 = [("ID", 0), ("Normal -> pequeno", 78), ("Pequeno -> normal", 230),
                ("Erros / localizados", 393), ("Acurácia condicional", 572)]
    for titulo, dx in colunas2:
        texto(titulo, margem + dx, 250, 9, True)
    for j, linha in enumerate(linhas):
        y = 225 - j * 23
        valores = [linha["configuracao_id"], linha["matriz_0_2"], linha["matriz_2_0"],
                   f"{linha['pares_incorretos']} / {linha['pares_total']}", _valor(linha["acuracia_condicional"])]
        for valor, (_, dx) in zip(valores, colunas2):
            texto(valor, margem + dx, y, 10)
    y = 93
    for frase in (
        "Cobertura = anotados localizados / anotados. Trocar 0 por 2, ou 2 por 0, não desfaz o acerto de localização; o erro de classe fica separado.",
        "Acurácia condicional considera somente indivíduos localizados. Um valor alto não garante boa cobertura de pequenos, nem mede os objetos perdidos. Consulte as duas tabelas em conjunto.",
    ):
        y = paragrafo(frase, y, 8.5)
    c.showPage()

    cabecalho("Resultados em cada vídeo", 3)
    colunas = [("ID / vídeo", 0), ("F1 indiv.", 98), ("Precisão", 172), ("Recall", 246),
               ("TP", 314), ("FP", 371), ("FN", 431), ("Cob. 0", 501), ("Cob. 2", 576), ("Cob. 1", 651)]
    faixa(485)
    for titulo, dx in colunas:
        texto(titulo, margem + dx, 485, 9, True)
    for j, linha in enumerate(linhas):
        for k, v in enumerate(quadros):
            y = 459 - j * 75 - k * 15
            l = dados["por_video"][linha["configuracao_id"], v]
            f1 = _numero(l["f1_individuos"])
            if f1 is not None:
                c.setFillColor(Color(.96 - .75 * f1, .98 - .32 * f1, .99 - .21 * f1))
                c.rect(margem + 92, y - 3, 59, 14, fill=1, stroke=0)
            valores = [f"{linha['configuracao_id']} / {v}", *[_valor(l[c]) for c in ("f1_individuos", "precisao_individuos", "recall_individuos")],
                       *[l[f"{c}_individuos"] for c in ("tp", "fp", "fn")], *[_valor(l[f"recall_classe_{cl}"]) for cl in (0, 2, 1)]]
            for valor, (_, dx) in zip(valores, colunas):
                texto(valor, margem + dx, y, 9)
    y = 93
    for frase in (
        ("; ".join(f"Vídeo {v}: {numero(quadros[v])} quadros, {fps[v]} FPS" for v in quadros)
         + ". A cor do F1 usa escala fixa de 0 a 1; mais intensa significa valor maior."),
        "Diferenças entre vídeos revelam limites que o agregado pode esconder. Quadros consecutivos são relacionados; este relatório é descritivo, sem teste de significância ou intervalo de confiança.",
    ):
        y = paragrafo(frase, y, 8.5)
    c.showPage()

    cabecalho("Tempos, configurações e limites da comparação", 4)
    faixa(485)
    cols = [("Configuração", 0), ("Pré-process. ms/quadro", 204), ("Detector ms/quadro", 362),
            ("Caixa ms/quadro", 519), ("Pipeline ms/quadro", 642)]
    for titulo, dx in cols:
        texto(titulo, margem + dx, 485, 8.5, True)
    for j, linha in enumerate(linhas):
        y = 458 - j * 25
        valores = [_rotulo_configuracao(configs[linha["configuracao_id"]]),
                   *[_valor(_inteiro(linha[f"tempo_{t}_total_ns"]) / quantidade / 1e6) for t in TEMPOS]]
        for valor, (_, dx) in zip(valores, cols):
            texto(valor, margem + dx, y, 9)
    y = paragrafo("Pipeline = pré-processamento + detector + adaptação da caixa. Esses tempos não incluem decodificação, avaliação, desenho e gravação do MP4; não representam a velocidade completa da aplicação.", 317, 8.5)
    texto("Como interpretar esta etapa", margem, y - 3, 12, True); y -= 25
    textos = [
        "As cinco configurações foram aprovadas após a seleção em imagens; permanecem congeladas. Variações próximas de parâmetros e caixas podem produzir resultados quase redundantes. Analise diferenças por vídeo e exemplos visuais antes de interpretar pequenas mudanças no ranking.",
        "A adaptação da caixa preserva centro, medida bruta e classe. Uma margem pode melhorar o IoU sem melhorar a detecção do candidato. Mudar o limite de classe entre indivíduo e aglomerado pode alterar o grupo de correspondência, mesmo com a mesma geometria.",
        "No DoG, a grade de escalas pode não alcançar a faixa de aglomerados; ampliar a caixa não corrige essa limitação. Classificação usa área circular estimada, não área segmentada nem confiança calibrada.",
        "O processamento detecta cada quadro de forma independente: não há rastreamento, identidade persistente, contagem de indivíduos únicos, velocidade ou comportamento estimados. Não confunda o total de detecções com o número de espermatozoides do vídeo.",
        ("Esta é a avaliação final nos vídeos 14, 24, 38 e 82, após seleção nos vídeos 13, 29, 52 e 54. Os resultados descrevem o desempenho das cinco configurações congeladas; o relatório não altera parâmetros, critérios, anotações ou finalistas."
         if final else "Esta é a seleção em vídeos 13, 29, 52 e 54. A avaliação final reservada usa outros vídeos após congelar as escolhas. O relatório não altera configurações, critérios, anotações ou finalistas."),
        "Integridade: plano/origens, cinco sequências completas de métricas, 20 agregados por vídeo e ranking conferidos. Os 20 MP4s têm hashes e registro de decodificação conferidos; o gerador do PDF não volta a decodificá-los. Tabelas de caixas e pares permanecem disponíveis nas pastas das configurações.",
    ]
    for frase in textos:
        y = paragrafo(frase, y, 8.5)
    c.showPage(); c.save()
    return 4


def gerar_relatorio(pasta: Path) -> Path:
    """Gera uma versão nova do PDF, sem reexecutar vídeos ou substituir resultados."""
    import reportlab
    dados = carregar(pasta)
    inicio = agora()
    destino = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not destino.is_relative_to(dados["pasta"]):
        raise ValueError("Pasta do relatório fora do batch.")
    destino.mkdir(parents=True, exist_ok=False)
    pdf = destino / "relatorio.pdf"
    registro = {"versao": 1, "tipo": dados["manifesto"]["tipo"], "situacao": "em_andamento", "inicio_utc": inicio.isoformat(),
                "origens_sha256": dados["hashes"], "criterios": CRITERIOS,
                "dependencias": {"python": platform.python_version(), "reportlab": reportlab.Version},
                "codigo_relatorio_sha256": {nome: sha256((Path(__file__).resolve().parents[1] / nome).read_bytes()) for nome in FONTES_RELATORIO},
                "ordem": [x["configuracao_id"] for x in dados["ranking"]], "selecao_automatica": False,
                "ordenacao": "F1 exato de indivíduos decrescente; empates mantêm posição; ID apenas organiza apresentação.",
                "escopo_integridade": f"Plano/origens, resumos, ranking, configurações, manifestos, {dados['manifesto']['avaliacoes_concluidas']} linhas por quadro e hashes dos 20 MP4s. Sem decodificar vídeos ou reler tabelas de caixas e pares."}
    try:
        gravar_json(destino / "relatorio.json", registro)
        (destino / "execucao_origem.json").write_bytes(dados["manifesto_bytes"])
        (destino / "plano_origem.json").write_bytes(dados["plano_bytes"])
        paginas = escrever_pdf(pdf, dados)
        registro.update(situacao="concluida", paginas=paginas, fim_utc=agora().isoformat(),
                        arquivo_pdf=pdf.relative_to(RAIZ.resolve()).as_posix(), pdf_sha256=sha256(pdf.read_bytes()))
        gravar_json(destino / "relatorio.json", registro)
    except BaseException as erro:
        registro.update(situacao="falhou", fim_utc=agora().isoformat(), erro=f"{type(erro).__name__}: {erro}")
        try:
            gravar_json(destino / "relatorio.json", registro)
        except OSError:
            pass
        raise
    return pdf
