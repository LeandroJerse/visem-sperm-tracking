"""Relatório dos cinco watershed nos vídeos de seleção, sem executar detectores."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import platform

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import CONTAGENS, _conferir_metricas, _csv, _inteiro, _json, _numero
from scripts.watershed.executar_rodada import DIAGNOSTICO, ordenar_por_f1
from scripts.watershed.planejamento_selecao import igual
from scripts.watershed.planejamento_videos import IDS, carregar_plano, conferir_documentos
from scripts.blobs.executar_inspecao import colunas_metricas
from io import BytesIO
from zipfile import ZipFile
from scripts.blobs.arquivos import gravar_json
from scripts.limiarizacao.inspecionar_imagem import agora, sha256


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/videos/watershed/selecao"
QUADROS = {"13": 1470, "29": 1470, "52": 1440, "54": 1470}
FPS = {"13": 49, "29": 49, "52": 48, "54": 49}
FONTES_RELATORIO = (
    "analise/relatorio_videos_watershed.py", "analise/relatorio_inspecao_blobs.py",
    "scripts/watershed/planejamento_videos.py", "scripts/watershed/planejamento_selecao.py",
    "scripts/watershed/executar_rodada.py", "scripts/blobs/executar_inspecao.py",
    "analise/avaliacao_individuos.py", "scripts/blobs/arquivos.py",
    "scripts/limiarizacao/inspecionar_imagem.py",
)


def _valor(valor):
    numero = _numero(valor)
    return "sem casos" if numero is None else f"{numero:.6f}".replace(".", ",")


def _ranking(resumos, ids):
    return [{k: "" if v is None else str(v) for k, v in r.items()}
            for r in ordenar_por_f1([resumos[i] for i in ids])]


def _rotulo_configuracao(item):
    p = item["parametros"]
    return f"{item['id']} | Otsu {p['deslocamento_otsu']:+g}"



def _etapa(particao):
    if particao == "selecao":
        return {"particao": particao, "tipo": "videos_selecao_watershed", "etapa": "selecao_videos",
                "saida": SAIDA, "quadros": QUADROS, "fps": FPS, "titulo": "seleção"}
    raise ValueError("Somente seleção em vídeos está preparada.")


def carregar(pasta: Path) -> dict:
    """Valida todas as métricas por quadro e hashes das mídias; não decodifica MP4."""
    pasta = Path(pasta).expanduser().resolve(strict=True)
    raiz = RAIZ.resolve()
    etapas = [_etapa("selecao")]
    correspondentes = [e for e in etapas if pasta.parent == e["saida"].resolve()
                      and e["saida"].resolve().is_relative_to(raiz)]
    if len(correspondentes) != 1 or not pasta.is_dir() or not pasta.name.startswith("batch__"):
        raise ValueError("Informe um batch diretamente em resultados/videos/watershed/selecao/.")
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
             "particao": etapa["particao"], "algoritmo": "watershed", "situacao": "concluida",
             "criterios": CRITERIOS, "configuracoes_previstas": 5, "configuracoes_concluidas": 5,
             "quadros_por_configuracao": quantidade, "avaliacoes_concluidas": quantidade * 5,
             "videos_concluidos": 20, "alinhamento_conferido": True}
    if any(m.get(k) != v or type(m.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Manifesto não descreve uma etapa de vídeos completa e alinhada na pasta correspondente.")
    plano_bytes = ler("plano.json")
    if sha256(plano_bytes) != m.get("plano_sha256"):
        raise ValueError("Hash do plano salvo divergente.")
    plano = carregar_plano(plano_bytes)
    for campo in ("versao", "tipo", "etapa", "particao", "algoritmo", "criterios"):
        if plano.get(campo) != fixos[campo] or type(plano.get(campo)) is not type(fixos[campo]):
            raise ValueError("Plano incompatível com a etapa de vídeos de watershed.")
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
    campos_soma = [*CONTAGENS, *DIAGNOSTICO]

    def conferir_agregado(total, soma, n):
        if _inteiro(total["quantidade_quadros"]) != n:
            raise ValueError("Quantidade de quadros incompatível no agregado.")
        for campo in CONTAGENS:
            if _inteiro(total[campo]) != soma[campo]:
                raise ValueError(f"Agregação inconsistente: {campo}.")
        for campo in DIAGNOSTICO:
            if _inteiro(total[campo]) != soma[campo]:
                raise ValueError(f"Diagnóstico agregado inconsistente: {campo}.")

    for item in configs:
        ident = item["id"]
        origem = (raiz / mapa_exec[ident]).resolve(strict=True)
        if origem.parent != pasta or not origem.is_dir() or origem.name == "relatorios":
            raise ValueError("Cada configuração deve ocupar uma subpasta direta do batch.")
        total = por_id[ident]
        if (total["pasta_origem"] != mapa_exec[ident]
                or total["bloco"] != item["bloco"]):
            raise ValueError("Metadados do agregado divergem do plano/manifesto.")
        if _json(ler(origem / "configuracao.json")) != item:
            raise ValueError("Configuração salva diverge do plano congelado.")
        e = _json(ler(origem / "execucao.json"))
        if (e.get("situacao") != "concluida" or e.get("configuracao_id") != ident
                or e.get("plano_sha256") != m["plano_sha256"]
                or e.get("batch") != pasta.relative_to(raiz).as_posix()
                or e.get("configuracao_sha256") != item["parametros_sha256"]
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
            if (_inteiro(linha["deteccoes"]) != _inteiro(linha["quantidade_deteccoes"])
                    or _inteiro(linha["regioes_candidatas"]) != _inteiro(linha["deteccoes"]) + _inteiro(linha["rejeitadas_area"])
                    or _inteiro(linha["componentes_preservados"]) > _inteiro(linha["componentes"])):
                raise ValueError("Diagnóstico de regiões inconsistente.")
            pixels, mascara = _inteiro(linha["pixels_imagem"]), _inteiro(linha["pixels_mascara"])
            otsu, efetivo = _numero(linha["limiar_otsu_original"]), _numero(linha["limiar_efetivo"])
            if (pixels != video["largura"] * video["altura"] or mascara > pixels
                    or _numero(linha["fracao_pixels_mascara"]) != mascara / pixels
                    or _numero(linha["deslocamento_otsu"]) != item["parametros"]["deslocamento_otsu"]
                    or otsu is None or not 0 <= otsu <= 255
                    or efetivo != max(0, min(255, otsu + item["parametros"]["deslocamento_otsu"]))):
                raise ValueError("Metadados de segmentação incompatíveis.")
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
        avaliacao = _json(ler(origem / "avaliacao.json"))
        igual(avaliacao["criterios"], CRITERIOS, "critérios da avaliação")
        for agregado, medidas in [(total, avaliacao["total"]), *[
                (por_video[ident, v], avaliacao["por_video"][v]) for v in quadros]]:
            esperado = {k: "" if v is None else str(v) for k, v in colunas_metricas(medidas).items()}
            igual({k: agregado[k] for k in esperado}, esperado, "avaliação JSON e CSV")
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
    if manifesto.get("pasta_origens") != "origens":
        raise ValueError("As fontes devem estar em origens/.")
    documentos = {}
    for nome, f in plano["proveniencia"]["fontes"].items():
        documentos[nome] = ler("origens/" + nome + Path(f["arquivo"]).suffix)
        igual(manifesto["origens_sha256"].get(f["arquivo"]), f["sha256"], "origem registrada")
    conferir_documentos(plano, documentos)
    for video in plano["videos"]:
        for ref in video["referencias_alinhamento"]:
            igual(manifesto["origens_sha256"].get(ref["imagem"]), ref["sha256"], "referência MAE")
    conferencia = _json(ler("conferencia/conferencia.json"))
    igual(conferencia["situacao"], "concluida", "conferência da sequência")
    igual(conferencia["metodo"], "MAE em cinza contra todos os quadros; índice previsto deve ser mínimo único.", "método de alinhamento")
    pixels = ler("conferencia/quadros_decodificados.csv")
    igual(sha256(pixels), conferencia["quadros_decodificados_sha256"], "sequência decodificada")
    esperados = [(v["video_id"], str(q)) for v in plano["videos"] for q in range(v["quantidade_quadros"])]
    igual([(r["video_id"], r["quadro"]) for r in _csv(pixels)], esperados, "todos os quadros conferidos")
    igual(len(conferencia["referencias"]), 20, "referências de alinhamento")
    zip_bytes = ler("codigo.zip")
    igual(sha256(zip_bytes), manifesto["codigo"]["sha256_zip"], "arquivo de código")
    with ZipFile(BytesIO(zip_bytes)) as z:
        igual(sorted(z.namelist()), sorted(manifesto["codigo"]["sha256_arquivos"]), "arquivos de código")
        for nome, digest in manifesto["codigo"]["sha256_arquivos"].items():
            igual(sha256(z.read(nome)), digest, "código " + nome)


def escrever_pdf(caminho: Path, dados: dict) -> int:
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.utils import simpleSplit

    largura, altura = landscape(A4)
    c = Canvas(str(caminho), pagesize=(largura, altura))
    etapa = _etapa(dados["plano"]["particao"])
    final = False
    quadros, fps = etapa["quadros"], etapa["fps"]
    quantidade = sum(quadros.values())
    numero = lambda valor: f"{valor:,}".replace(",", ".")
    ids_videos = ", ".join(list(quadros)[:-1]) + " e " + list(quadros)[-1]
    c.setTitle(f"Watershed - comparação nos vídeos de {etapa['titulo']}")
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
        texto(f"WATERSHED  |  VÍDEOS DE {etapa['titulo'].upper()}", margem, altura - 26, 10, True, azul)
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
            c.setFillColor(HexColor(azul if item["parametros"]["watershed"]["politica_aglomerados"] == "separar" else roxo))
            c.rect(margem + 174, y - 3, 310 * valor, 15, fill=1, stroke=0)
        for campo, dx in (("f1_individuos", 502), ("precisao_individuos", 573), ("recall_individuos", 666)):
            texto(_valor(linha[campo]), margem + dx, y, 11, campo == "f1_individuos")
    texto("Azul: separar regiões; laranja: preservar componentes por área. Delta indica o ajuste do limiar Otsu.", margem, 173, 8)
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
    cols = [("ID", 0), ("Delta Otsu", 70), ("Semente", 175), ("Política", 273),
            ("Área mín.", 462), ("Área máx.", 557), ("Detector ms/quadro", 646)]
    for titulo, dx in cols:
        texto(titulo, margem + dx, 485, 8.5, True)
    for j, linha in enumerate(linhas):
        y = 458 - j * 25
        p = configs[linha["configuracao_id"]]["parametros"]
        w, seg = p["watershed"], p["watershed"]["segmentacao"]
        valores = [linha["configuracao_id"], p["deslocamento_otsu"], w["fracao_semente"],
                   w["politica_aglomerados"], seg["area_minima"], seg["area_maxima"],
                   _valor(_inteiro(linha["tempo_detector_ns"]) / quantidade / 1e6)]
        for valor, (_, dx) in zip(valores, cols):
            texto(valor, margem + dx, y, 9)
    y = paragrafo("Tempo da mesma chamada usada nas imagens: limiarização, morfologia, sementes, watershed e diagnóstico. Exclui decodificação, avaliação, desenho e gravação; não mede a velocidade completa da aplicação.", 317, 8.5)
    texto("Como interpretar esta etapa", margem, y - 3, 12, True); y -= 25
    textos = [
        "As cinco configurações foram aprovadas após a seleção em imagens; permanecem congeladas. Variações próximas de limiar e sementes podem produzir resultados quase redundantes. Analise diferenças por vídeo e exemplos visuais antes de interpretar pequenas mudanças no ranking.",
        "As caixas envolvem as regiões segmentadas, como na seleção em imagens. Uma região menor que a anotação pode não atingir IoU 0,50 mesmo com centro próximo. Não há margem ou escala de caixa nova nesta etapa.",
        "A classificação usa área segmentada: pequeno até 120 pixels, aglomerado a partir de 900. Com filtro mínimo de 120, a classe pequeno fica restrita ao valor 120. Preservar por área não comprova que um componente seja biologicamente um aglomerado.",
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
