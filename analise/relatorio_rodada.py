"""Relatório descritivo de um batch concluído, usando somente resultados salvos.

Não executa detectores, pareamento, agregação de quadros ou seleção de candidatas.
As métricas apresentadas são as dos CSV; as estatísticas descrevem configurações.
"""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import platform
import re
from statistics import mean, median, stdev


RAIZ = Path(__file__).resolve().parents[1]
CLASSES = (0, 1, 2)
COR_MANUAL = "#267c8e"
COR_OTSU = "#4755a7"
COR_SEM_CASOS = "#dddddd"


def verificar_dependencias() -> dict[str, str]:
    """Confere as bibliotecas de apresentação sem importar código experimental."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        import reportlab
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.utils import ImageReader
    except ImportError as erro:
        raise ValueError(
            "Instale as dependências do relatório com: "
            "python -m pip install -r analise/requirements-relatorio.txt"
        ) from erro
    return {
        "python": platform.python_version(),
        "matplotlib": matplotlib.__version__,
        "reportlab": reportlab.Version,
    }


def _sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _objeto_json(pares: list[tuple]) -> dict:
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError(f"Campo JSON repetido: {chave}.")
        resultado[chave] = valor
    return resultado


def _constante_json(valor: str):
    raise ValueError(f"Número JSON não finito: {valor}.")


def _json(conteudo: bytes) -> dict:
    resultado = json.loads(conteudo.decode("utf-8-sig"),
                           object_pairs_hook=_objeto_json, parse_constant=_constante_json)
    if not isinstance(resultado, dict):
        raise ValueError("Esperado um objeto JSON.")
    return resultado


def _inteiro(valor, campo: str) -> int:
    if isinstance(valor, bool) or not re.fullmatch(r"[0-9]+", str(valor)):
        raise ValueError(f"{campo} deve ser um inteiro não negativo.")
    return int(valor)


def _numero(valor, campo: str) -> float | None:
    if valor == "" or valor is None:
        return None
    if isinstance(valor, bool):
        raise ValueError(f"{campo} deve estar entre 0 e 1.")
    resultado = float(valor)
    if not math.isfinite(resultado) or not 0 <= resultado <= 1:
        raise ValueError(f"{campo} deve ser finito e estar entre 0 e 1.")
    return resultado


def _conferir_numero(valor: float | None, esperado: float | None, campo: str) -> None:
    if esperado is None:
        correto = valor is None
    else:
        correto = valor is not None and math.isclose(valor, esperado, rel_tol=1e-10, abs_tol=1e-12)
    if not correto:
        raise ValueError(f"Métrica incoerente com as contagens salvas: {campo}.")


def _ler_resumo(conteudo: bytes, por_video: bool = False) -> list[dict]:
    leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")))
    campos = {
        "configuracao_id", "pasta", "quantidade_quadros", "macro_f1",
        "situacao_macro_f1", "tempo_detector_total_ns", "f1_localizacao",
        *[f"{nome}_classe_{classe}" for classe in CLASSES
          for nome in ("tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1")],
    }
    if por_video:
        campos.add("video_id")
    if not leitor.fieldnames or len(set(leitor.fieldnames)) != len(leitor.fieldnames):
        raise ValueError("CSV sem cabeçalho ou com colunas repetidas.")
    if not campos.issubset(leitor.fieldnames):
        raise ValueError(f"Faltam colunas no resumo: {sorted(campos - set(leitor.fieldnames))}.")
    linhas = []
    for linha in leitor:
        if None in linha or any(valor is None for valor in linha.values()):
            raise ValueError("Linha CSV com quantidade incorreta de colunas.")
        for campo in ("quantidade_quadros", "tempo_detector_total_ns"):
            linha[campo] = _inteiro(linha[campo], campo)
        if linha["quantidade_quadros"] == 0:
            raise ValueError("O resumo precisa representar pelo menos um quadro.")
        for campo in ("macro_f1", "f1_localizacao"):
            linha[campo] = _numero(linha[campo], campo)
        for classe in CLASSES:
            for nome in ("tp", "fp", "fn"):
                campo = f"{nome}_classe_{classe}"
                linha[campo] = _inteiro(linha[campo], campo)
            for nome in ("precisao", "recall", "f1"):
                campo = f"{nome}_classe_{classe}"
                linha[campo] = _numero(linha[campo], campo)
            tp, fp, fn = (linha[f"{nome}_classe_{classe}"] for nome in ("tp", "fp", "fn"))
            esperados = {
                "precisao": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            }
            for nome, esperado in esperados.items():
                _conferir_numero(linha[f"{nome}_classe_{classe}"], esperado, f"{nome}_classe_{classe}")
            situacao = "sem_casos" if esperados["f1"] is None else "definido"
            if linha[f"situacao_f1_classe_{classe}"] != situacao:
                raise ValueError("Situação de F1 incompatível com as contagens.")
        valores = [linha[f"f1_classe_{classe}"] for classe in CLASSES]
        macro = sum(valores) / 3 if all(valor is not None for valor in valores) else None
        _conferir_numero(linha["macro_f1"], macro, "macro_f1")
        situacao = "classes_sem_casos" if macro is None else "definido"
        if linha["situacao_macro_f1"] != situacao:
            raise ValueError("Situação do macro-F1 incompatível com os F1 das classes.")
        linhas.append(linha)
    if not linhas:
        raise ValueError("O resumo está vazio.")
    return linhas


def _carregar(pasta: Path) -> dict:
    pasta = pasta.expanduser().resolve(strict=True)
    permitida = (RAIZ / "resultados" / "frame-to-frame").resolve()
    if not pasta.is_dir() or not pasta.is_relative_to(permitida):
        raise ValueError("Informe uma pasta de batch dentro de resultados/frame-to-frame.")
    origens = {}

    def ler(arquivo: Path) -> bytes:
        caminho = arquivo.resolve(strict=True)
        if not caminho.is_file() or not caminho.is_relative_to(permitida):
            raise ValueError("Um arquivo do relatório está fora da pasta de resultados permitida.")
        conteudo = caminho.read_bytes()
        origens[caminho.relative_to(RAIZ).as_posix()] = _sha256(conteudo)
        return conteudo

    execucao_bytes = ler(pasta / "execucao.json")
    execucao = _json(execucao_bytes)
    if execucao.get("situacao") != "concluida":
        raise ValueError("O relatório exige um batch concluído.")
    plano_bytes = ler(pasta / "rodada.json")
    if _sha256(plano_bytes) != execucao.get("plano_sha256"):
        raise ValueError("O plano salvo não corresponde ao hash registrado na execução.")
    plano = _json(plano_bytes)
    if plano.get("versao") != 1 or plano.get("particao") not in ("desenvolvimento", "selecao"):
        raise ValueError("Formato de plano ou partição não suportados pelo relatório.")
    if plano["particao"] == "selecao" and (
        plano.get("rodada") != "selecao" or execucao.get("etapa") != "selecao_imagens"
    ):
        raise ValueError("Plano de seleção incompatível com a etapa registrada.")
    for chave in ("rodada", "algoritmo", "seed"):
        if plano.get(chave) != execucao.get(chave):
            raise ValueError(f"Plano e execução divergem em {chave}.")
    configs = plano.get("configuracoes")
    quadros = plano.get("quadros")
    if not isinstance(configs, list) or not configs or not isinstance(quadros, list) or not quadros:
        raise ValueError("O plano deve conter configurações e quadros.")
    por_id = {}
    for item in configs:
        identificador = item.get("id")
        if not isinstance(identificador, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identificador):
            raise ValueError("Identificador de configuração inválido.")
        if identificador in por_id or not isinstance(item.get("parametros"), dict):
            raise ValueError("Configuração duplicada ou sem parâmetros.")
        parametros = item["parametros"]
        if parametros.get("metodo") not in ("manual", "otsu") or parametros.get("polaridade") not in ("claro", "escuro"):
            raise ValueError("O relatório suporta as variantes manual/Otsu, claro/escuro.")
        por_id[identificador] = item
    chaves_quadros = [(str(item["video_id"]), _inteiro(item["quadro"], "quadro")) for item in quadros]
    if len(set(chaves_quadros)) != len(quadros):
        raise ValueError("Há quadros repetidos no plano.")
    n_por_video = Counter(video for video, _ in chaves_quadros)
    for campo in ("configuracoes_previstas", "configuracoes_concluidas"):
        if _inteiro(execucao.get(campo), campo) != len(configs):
            raise ValueError("A quantidade de configurações concluídas não corresponde ao plano.")
    if _inteiro(execucao.get("quadros_por_configuracao"), "quadros_por_configuracao") != len(quadros):
        raise ValueError("A quantidade de quadros não corresponde ao plano.")
    totais = _ler_resumo(ler(pasta / "resumo_configuracoes.csv"))
    videos = _ler_resumo(ler(pasta / "resumo_por_video.csv"), por_video=True)
    ids = [item["configuracao_id"] for item in totais]
    if len(set(ids)) != len(ids) or set(ids) != set(por_id):
        raise ValueError("O resumo deve conter uma linha por configuração do plano.")
    registros = execucao.get("execucoes")
    if not isinstance(registros, list) or len(registros) != len(configs):
        raise ValueError("A lista de execuções está incompleta.")
    pastas = {item["configuracao_id"]: item["pasta"] for item in registros}
    if set(pastas) != set(por_id):
        raise ValueError("A lista de execuções diverge do plano.")
    por_video = {}
    for linha in videos:
        chave = (linha["configuracao_id"], linha["video_id"])
        if chave in por_video or chave[0] not in por_id or chave[1] not in n_por_video:
            raise ValueError("Resumo por vídeo com combinação repetida ou não prevista.")
        if linha["quantidade_quadros"] != n_por_video[chave[1]] or linha["pasta"] != pastas[chave[0]]:
            raise ValueError("Resumo por vídeo com origem ou quantidade de quadros divergente.")
        por_video[chave] = linha
    if len(por_video) != len(configs) * len(n_por_video):
        raise ValueError("Faltam combinações de vídeo e configuração no resumo.")
    anotacoes = None
    for linha in totais:
        identificador = linha["configuracao_id"]
        if linha["quantidade_quadros"] != len(quadros) or linha["pasta"] != pastas[identificador]:
            raise ValueError("Resumo total com origem ou quantidade de quadros divergente.")
        caminho_config = (RAIZ / linha["pasta"]).resolve(strict=True)
        if caminho_config.parent != pasta.parent:
            raise ValueError("A configuração precisa estar na mesma pasta de rodada do batch.")
        registro = _json(ler(caminho_config / "execucao.json"))
        if (registro.get("situacao") != "concluida" or registro.get("configuracao_id") != identificador
                or registro.get("batch_id") != execucao.get("batch_id")
                or registro.get("plano_sha256") != execucao.get("plano_sha256")
                or registro.get("quantidade_quadros_concluida") != len(quadros)
                or registro.get("metricas_calculadas") is not True):
            raise ValueError(f"Execução da configuração {identificador} incompleta ou divergente.")
        parciais = [por_video[(identificador, video)] for video in n_por_video]
        for campo in ["tempo_detector_total_ns", *[f"{nome}_classe_{classe}" for classe in CLASSES for nome in ("tp", "fp", "fn")]]:
            if sum(item[campo] for item in parciais) != linha[campo]:
                raise ValueError(f"O resumo total e os vídeos divergem em {identificador}/{campo}.")
        atuais = tuple(linha[f"tp_classe_{classe}"] + linha[f"fn_classe_{classe}"] for classe in CLASSES)
        if anotacoes is not None and atuais != anotacoes:
            raise ValueError("As configurações não foram avaliadas com as mesmas contagens de anotações.")
        anotacoes = atuais
    for video in n_por_video:
        contagens = {tuple(por_video[(identificador, video)][f"tp_classe_{classe}"]
                          + por_video[(identificador, video)][f"fn_classe_{classe}"]
                          for classe in CLASSES) for identificador in por_id}
        if len(contagens) != 1:
            raise ValueError(f"As contagens de anotações do vídeo {video} diferem entre configurações.")
    inicio = datetime.fromisoformat(execucao["inicio_utc"])
    fim = datetime.fromisoformat(execucao["fim_utc"])
    if inicio.tzinfo is None or fim.tzinfo is None or fim < inicio:
        raise ValueError("As datas da execução precisam ter fuso e ordem válidos.")
    return {
        "pasta": pasta, "execucao": execucao, "plano": plano, "configuracoes": por_id,
        "totais": totais, "por_video": por_video, "quadros_por_video": dict(n_por_video),
        "anotacoes_por_classe": dict(zip(map(str, CLASSES), anotacoes)),
        "duracao_segundos": (fim - inicio).total_seconds(), "origens_sha256": origens,
        "execucao_origem_bytes": execucao_bytes,
    }


def _estatisticas(linhas: list[dict]) -> dict:
    resultado = {}
    for campo in ("macro_f1", "f1_classe_0", "f1_classe_1", "f1_classe_2", "f1_localizacao"):
        valores = [linha[campo] for linha in linhas if linha[campo] is not None]
        resultado[campo] = {
            "n_definidos": len(valores), "n_sem_casos": len(linhas) - len(valores),
            "media": mean(valores) if valores else None,
            "mediana": median(valores) if valores else None,
            "desvio_padrao_amostral": stdev(valores) if len(valores) > 1 else None,
            "minimo": min(valores) if valores else None,
            "maximo": max(valores) if valores else None,
        }
    return resultado


def _formato(valor: float | None, casas: int = 3) -> str:
    return "sem casos" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def _rotulo(linha: dict, dados: dict) -> str:
    identificador = linha["configuracao_id"]
    params = dados["configuracoes"][identificador]["parametros"]
    metodo = "Otsu" if params["metodo"] == "otsu" else f"M{params['limiar_manual']}"
    referencia = dados["plano"].get("geracao", {}).get("configuracao_inicial_incluida")
    return f"{identificador}{'*' if identificador == referencia else ''} | {metodo} {params['polaridade']}"


def _figura(largura: float, altura: float):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figura = Figure(figsize=(largura / 72, altura / 72), dpi=300)
    FigureCanvasAgg(figura)
    return figura


def _inserir_figura(pdf, figura, x: float, y: float, largura: float, altura: float) -> None:
    from reportlab.lib.utils import ImageReader
    buffer = BytesIO()
    try:
        figura.savefig(buffer, format="png", dpi=300, facecolor="white")
        buffer.seek(0)
        pdf.drawImage(ImageReader(buffer), x, y, width=largura, height=altura, mask="auto")
    finally:
        figura.clear()
        buffer.close()


def _barras(linhas: list[dict], dados: dict, largura: float, altura: float):
    figura = _figura(largura, altura)
    eixos = figura.subplots(1, 2, squeeze=False)[0]
    figura.subplots_adjust(left=0.135, right=0.985, top=0.98, bottom=0.09, wspace=0.65)
    for eixo, parte in zip(eixos, (linhas[:24], linhas[24:])):
        if not parte:
            eixo.set_axis_off()
            continue
        valores = [linha["macro_f1"] for linha in parte]
        cores = [COR_OTSU if dados["configuracoes"][linha["configuracao_id"]]["parametros"]["metodo"] == "otsu"
                 else COR_MANUAL for linha in parte]
        eixo.barh(range(len(parte)), [valor or 0 for valor in valores], height=0.64, color=cores)
        eixo.set_yticks(range(len(parte)), [_rotulo(linha, dados) for linha in parte], fontsize=8.5)
        eixo.set_ylim(23.8, -0.8)
        eixo.set_xlim(0, 1.18)
        eixo.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "0,25", "0,50", "0,75", "1"], fontsize=8)
        eixo.set_xlabel("Macro-F1 (0 a 1)", fontsize=8)
        eixo.grid(axis="x", alpha=0.18)
        eixo.set_axisbelow(True)
        eixo.tick_params(axis="y", length=0)
        for indice, valor in enumerate(valores):
            eixo.text((valor or 0) + 0.025, indice, _formato(valor), va="center", fontsize=8.5,
                      color="#333333" if valor is not None else "#666666")
        for lado in ("top", "right", "left"):
            eixo.spines[lado].set_visible(False)
    return figura


def _mapa_classes(linhas: list[dict], dados: dict, largura: float, altura: float):
    from matplotlib import colormaps
    from matplotlib.colors import Normalize
    figura = _figura(largura, altura)
    eixos = figura.subplots(1, 2, squeeze=False)[0]
    figura.subplots_adjust(left=0.145, right=0.98, top=0.96, bottom=0.045, wspace=0.78)
    mapa = colormaps["YlGnBu"].copy()
    mapa.set_bad(COR_SEM_CASOS)
    for eixo, parte in zip(eixos, (linhas[:24], linhas[24:])):
        if not parte:
            eixo.set_axis_off()
            continue
        valores = [[linha[f"f1_classe_{classe}"] for classe in CLASSES] for linha in parte]
        matriz = [[math.nan if valor is None else valor for valor in linha] for linha in valores]
        eixo.imshow(matriz, aspect="auto", interpolation="nearest", cmap=mapa, norm=Normalize(0, 1))
        eixo.set_ylim(23.5, -0.5)
        eixo.set_yticks(range(len(parte)), [_rotulo(linha, dados) for linha in parte], fontsize=9)
        eixo.set_xticks(range(3), ["0 normal", "1 aglomerado", "2 pequeno"], fontsize=9)
        eixo.xaxis.tick_top()
        eixo.tick_params(length=0, pad=6)
        for indice, linha in enumerate(valores):
            for coluna, valor in enumerate(linha):
                eixo.text(coluna, indice, "-" if valor is None else _formato(valor), ha="center", va="center",
                          fontsize=9, color="white" if valor is not None and valor > 0.6 else "#17232c")
        for borda in eixo.spines.values():
            borda.set_visible(False)
    return figura


def _mapa_videos(linhas: list[dict], dados: dict, videos: list[str], largura: float, altura: float):
    from matplotlib import colormaps
    from matplotlib.colors import Normalize
    figura = _figura(largura, altura)
    eixos = figura.subplots(2, 1, squeeze=False)[:, 0]
    figura.subplots_adjust(left=0.075, right=0.98, top=0.91, bottom=0.085, hspace=0.43)
    mapa = colormaps["YlGnBu"].copy()
    mapa.set_bad(COR_SEM_CASOS)
    for eixo, parte in zip(eixos, (linhas[:24], linhas[24:])):
        if not parte:
            eixo.set_axis_off()
            continue
        ids = [linha["configuracao_id"] for linha in parte]
        valores = [[dados["por_video"][(identificador, video)]["macro_f1"] for identificador in ids] for video in videos]
        matriz = [[math.nan if valor is None else valor for valor in linha] for linha in valores]
        imagem = eixo.imshow(matriz, aspect="auto", interpolation="nearest", cmap=mapa, norm=Normalize(0, 1))
        eixo.set_xticks(range(len(ids)), ids, fontsize=8)
        eixo.set_yticks(range(len(videos)), [f"Vídeo {video}" for video in videos], fontsize=8)
        eixo.tick_params(length=0)
        barra = figura.colorbar(imagem, ax=eixo, fraction=0.019, pad=0.014)
        barra.ax.tick_params(labelsize=8)
        barra.set_ticks([0, 0.25, 0.5, 0.75, 1])
        barra.set_label("Macro-F1", fontsize=8)
        for borda in eixo.spines.values():
            borda.set_visible(False)
    return figura


def _texto(pdf, texto: str, x: float, y: float, tamanho: float = 9, negrito: bool = False) -> None:
    pdf.setFillColorRGB(0.11, 0.16, 0.21)
    pdf.setFont("Helvetica-Bold" if negrito else "Helvetica", tamanho)
    pdf.drawString(x, y, texto)


def _cabecalho(pdf, dados: dict, titulo: str, subtitulo: str, pagina: int, total: int, criado: str) -> None:
    from reportlab.lib.pagesizes import A4, landscape
    largura, altura = landscape(A4)
    _texto(pdf, f"{dados['plano']['rodada']} | {titulo}", 32, altura - 37, 19, True)
    _texto(pdf, subtitulo, 32, altura - 56, 9)
    pdf.setStrokeColorRGB(0.84, 0.87, 0.9)
    pdf.line(32, 38, largura - 32, 38)
    etapa = "Seleção" if dados["plano"]["particao"] == "selecao" else "Desenvolvimento"
    _texto(pdf, f"{etapa} | seed {dados['plano']['seed']} | plano {dados['execucao']['plano_sha256'][:12]}", 32, 23, 8)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(largura - 32, 23, f"Gerado {criado} | {pagina}/{total}")
    deps = dados["execucao"].get("dependencias", {})
    codigo = dados["execucao"].get("codigo", {})
    commit = str(codigo.get("commit", "não informado"))[:12]
    alteracoes = " | árvore modificada" if codigo.get("arvore_modificada") else ""
    _texto(pdf, f"Código experimental {commit}{alteracoes} | Python {deps.get('python', '?')} | OpenCV {deps.get('opencv_importado', '?')} | SciPy {deps.get('scipy', '?')}", 32, 11, 7)


def _tabela_estatisticas(pdf, estatisticas: dict, y: float, largura: float) -> None:
    titulos = ["Métrica", "N definido", "Média", "Mediana", "DP (n-1)", "Mínimo", "Máximo"]
    posicoes = [32, 230, 327, 424, 521, 618, 715]
    pdf.setFillColorRGB(0.92, 0.94, 0.96)
    pdf.rect(32, y - 4, largura - 64, 15, fill=1, stroke=0)
    for x, titulo in zip(posicoes, titulos):
        _texto(pdf, titulo, x + 5, y, 8, True)
    nomes = {"macro_f1": "Macro-F1", "f1_classe_0": "F1 classe 0", "f1_classe_1": "F1 classe 1",
             "f1_classe_2": "F1 classe 2", "f1_localizacao": "F1 localização (auxiliar)"}
    for indice, (campo, resumo) in enumerate(estatisticas.items(), start=1):
        valores = [nomes[campo], str(resumo["n_definidos"]),
                   *["-" if resumo[nome] is None else _formato(resumo[nome])
                     for nome in ("media", "mediana", "desvio_padrao_amostral", "minimo", "maximo")]]
        for x, valor in zip(posicoes, valores):
            _texto(pdf, valor, x + 5, y - indice * 12, 8)


def _escrever_pdf(caminho: Path, dados: dict, estatisticas: dict, linhas: list[dict], criado: str) -> int:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas
    largura, altura = landscape(A4)
    grupos = [linhas[indice:indice + 48] for indice in range(0, len(linhas), 48)]
    videos = sorted(dados["quadros_por_video"], key=lambda valor: (0, int(valor)) if valor.isdigit() else (1, valor))
    grupos_video = [videos[indice:indice + 12] for indice in range(0, len(videos), 12)]
    total_paginas = len(grupos) * (2 + len(grupos_video))
    pagina = 0
    with caminho.open("xb") as arquivo:
        pdf = Canvas(arquivo, pagesize=landscape(A4), pageCompression=1)
        etapa = "seleção" if dados["plano"]["particao"] == "selecao" else "desenvolvimento"
        pdf.setTitle(f"{dados['plano']['rodada']} - resultados de {etapa}")
        pdf.setAuthor("")
        pdf.setSubject("Relatório descritivo das configurações de detecção em imagens")
        pdf.setCreator("Relatório de rodadas")
        for numero_grupo, grupo in enumerate(grupos, start=1):
            pagina += 1
            sufixo = f" | bloco {numero_grupo}/{len(grupos)}" if len(grupos) > 1 else ""
            _cabecalho(pdf, dados, "Visão geral" + sufixo,
                       "Ordem visual: macro-F1 decrescente; classe 0 somente no empate exato. Não seleciona candidatas.",
                       pagina, total_paginas, criado)
            anotacoes = sum(dados["anotacoes_por_classe"].values())
            cards = [f"{len(linhas)} configurações", f"{len(dados['plano']['quadros'])} quadros / configuração",
                     f"{anotacoes} caixas anotadas", f"{dados['duracao_segundos'] / 60:.1f} min de batch"]
            for indice, texto in enumerate(cards):
                x = 32 + indice * (largura - 64) / 4
                pdf.setFillColorRGB(0.94, 0.96, 0.98)
                pdf.rect(x, altura - 102, (largura - 64) / 4 - 8, 29, fill=1, stroke=0)
                _texto(pdf, texto.replace(".", ","), x + 8, altura - 91, 9, True)
            _texto(pdf, f"{len(videos)} vídeos | {len(dados['plano'].get('exclusoes', []))} quadros excluídos | Caixas anotadas se repetem entre quadros; não representam indivíduos únicos.", 32, altura - 68, 8)
            _inserir_figura(pdf, _barras(grupo, dados, largura - 64, 324), 32, 161, largura - 64, 324)
            _texto(pdf, "Estatísticas de todas as configurações da rodada (valores definidos):", 32, 143, 9, True)
            _tabela_estatisticas(pdf, estatisticas, 126, largura)
            _texto(pdf, "DP descreve dispersão entre configurações; não é incerteza. * referência inicial. Tempo é apenas diagnóstico.", 32, 46, 8)
            pdf.showPage()

            pagina += 1
            _cabecalho(pdf, dados, "F1 por classe" + sufixo,
                       "Mesma ordem da visão geral. F1 calculado após reunir TP, FP e FN dos quadros; escala fixa de 0 a 1.",
                       pagina, total_paginas, criado)
            _inserir_figura(pdf, _mapa_classes(grupo, dados, largura - 64, 440), 32, 79, largura - 64, 440)
            _texto(pdf, "Cinza / -: sem anotações e sem previsões da classe. Zero é um resultado definido, distinto de sem casos.", 32, 63, 9)
            _texto(pdf, "0 normal | 1 aglomerado | 2 pequeno. Os IDs remetem aos parâmetros completos de rodada.json.", 32, 47, 9)
            pdf.showPage()

            for parte_videos in grupos_video:
                pagina += 1
                _cabecalho(pdf, dados, "Variação por vídeo" + sufixo,
                           "Macro-F1 de cada vídeo e configuração. A cor usa sempre a escala de 0 a 1; valores completos no CSV.",
                           pagina, total_paginas, criado)
                _inserir_figura(pdf, _mapa_videos(grupo, dados, parte_videos, largura - 64, 425), 32, 89, largura - 64, 425)
                _texto(pdf, "Cinza: macro-F1 indefinido porque pelo menos uma classe está sem casos. Não equivale a zero.", 32, 74, 9)
                _texto(pdf, "Quadros do mesmo vídeo não são observações independentes; este relatório não estima significância estatística.", 32, 59, 9)
                nota = (
                    "Seleção com parâmetros fixos. A escolha das cinco configurações para vídeos depende da revisão conjunta."
                    if dados["plano"]["particao"] == "selecao" else
                    "Dados de desenvolvimento já explorados. Nenhuma configuração é promovida automaticamente para seleção ou avaliação final."
                )
                _texto(pdf, nota, 32, 44, 8)
                pdf.showPage()
        pdf.save()
    return total_paginas


def _gravar_json(caminho: Path, registro: dict) -> None:
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporario.replace(caminho)


def gerar_relatorio(pasta_batch: Path) -> Path:
    """Cria um PDF e seu registro em ``batch/relatorios/<UTCmicro>/``.

    Recusa batches incompletos ou resumos incoerentes. Nenhum arquivo original
    é alterado; repetir a chamada cria outra pasta. Erros de geração ficam
    registrados em relatorio.json sem mudar a situação do experimento.
    """
    dependencias = verificar_dependencias()
    dados = _carregar(Path(pasta_batch))
    estatisticas = _estatisticas(dados["totais"])
    linhas = sorted(dados["totais"], key=lambda linha: (
        linha["macro_f1"] is None,
        -(linha["macro_f1"] if linha["macro_f1"] is not None else -1),
        -(linha["f1_classe_0"] if linha["f1_classe_0"] is not None else -1),
        linha["configuracao_id"],
    ))
    inicio = datetime.now(timezone.utc)
    pasta = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not pasta.is_relative_to(dados["pasta"]):
        raise ValueError("A pasta do relatório precisa permanecer dentro do batch informado.")
    pasta.mkdir(parents=True, exist_ok=False)
    caminho_pdf = pasta / "relatorio.pdf"
    caminho_json = pasta / "relatorio.json"
    registro = {
        "versao_relatorio": 1, "situacao": "em_andamento", "inicio_utc": inicio.isoformat(), "fim_utc": None,
        "origem_batch": dados["pasta"].relative_to(RAIZ).as_posix(),
        "origens_sha256": dados["origens_sha256"],
        "codigo_relatorio_sha256": _sha256(Path(__file__).read_bytes()),
        "dependencias_relatorio": dependencias, "rodada": dados["plano"]["rodada"],
        "particao": dados["plano"]["particao"],
        "seed": dados["plano"]["seed"], "plano_sha256": dados["execucao"]["plano_sha256"],
        "dependencias_experimento": dados["execucao"].get("dependencias"),
        "codigo_experimento": dados["execucao"].get("codigo"),
        "configuracoes": len(linhas), "quadros_por_configuracao": len(dados["plano"]["quadros"]),
        "quadros_por_video": dados["quadros_por_video"], "anotacoes_por_classe": dados["anotacoes_por_classe"],
        "exclusoes": dados["plano"].get("exclusoes", []), "duracao_batch_segundos": dados["duracao_segundos"],
        "estatisticas_entre_configuracoes": estatisticas,
        "ordem_visual_configuracoes": [linha["configuracao_id"] for linha in linhas],
        "ordem_visual": "Macro-F1 decrescente; F1 da classe 0 somente no empate exato; ID para ordem estável. Não seleciona configurações.",
        "interpretacao": "Estatística descritiva das configurações; DP amostral n-1 não expressa incerteza. Sem casos permanece indefinido. Tempo apenas diagnóstico.",
        "arquivo_pdf": caminho_pdf.relative_to(RAIZ).as_posix(),
    }
    try:
        _gravar_json(caminho_json, registro)
        copia_execucao = pasta / "execucao_origem.json"
        with copia_execucao.open("xb") as arquivo:
            arquivo.write(dados["execucao_origem_bytes"])
        registro["copia_execucao_origem"] = copia_execucao.relative_to(RAIZ).as_posix()
        registro["copia_execucao_origem_sha256"] = _sha256(dados["execucao_origem_bytes"])
        _gravar_json(caminho_json, registro)
        paginas = _escrever_pdf(caminho_pdf, dados, estatisticas, linhas, inicio.strftime("%d/%m/%Y %H:%M UTC"))
        registro.update({"situacao": "concluida", "fim_utc": datetime.now(timezone.utc).isoformat(),
                         "paginas": paginas, "pdf_sha256": _sha256(caminho_pdf.read_bytes())})
        _gravar_json(caminho_json, registro)
    except BaseException as erro:
        registro.update({"situacao": "falhou", "fim_utc": datetime.now(timezone.utc).isoformat(),
                         "erro": f"{type(erro).__name__}: {erro}"})
        try:
            _gravar_json(caminho_json, registro)
        except OSError:
            pass
        raise
    return caminho_pdf
