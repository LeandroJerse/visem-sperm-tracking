"""Relatório dos cinco candidatos nos vídeos de seleção ou avaliação final."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from fractions import Fraction
from io import StringIO
from pathlib import Path

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_individuos import (
    CONTAGENS, TAXAS, _estatisticas, _linha, _pontuacao,
)
from analise.relatorio_rodada import (
    RAIZ, _figura, _formato, _gravar_json, _inserir_figura, _inteiro,
    _json, _sha256, _texto, verificar_dependencias,
)


CONFIGURACOES = frozenset(("s068", "s067", "s090", "s099", "s101"))
VIDEOS = frozenset(("13", "29", "52", "54"))
VIDEOS_FINAIS = frozenset(("14", "24", "38", "82"))
ETAPAS = {
    "selecao": {
        "tipo_execucao": "selecao_videos", "tipo_plano": "videos_selecao", "videos": VIDEOS,
        "rotulo": "Vídeos de seleção",
        "rodape": "Detecção quadro a quadro; sem rastreamento ou contagem de indivíduos únicos. Não é a avaliação final reservada.",
        "decisao": "Nenhuma configuração é escolhida automaticamente. A decisão depende da análise conjunta dos resultados.",
        "encerramento": "Esta etapa precede o congelamento das escolhas e a avaliação final nos vídeos 14, 24, 38 e 82.",
        "interpretacao": "Descrição dos candidatos nos vídeos de seleção; sem escolha automática ou inferência de superioridade.",
    },
    "final": {
        "tipo_execucao": "final_videos", "tipo_plano": "videos_final", "videos": VIDEOS_FINAIS,
        "rotulo": "Avaliação final",
        "rodape": "Avaliação final com escolhas congeladas. Detecção quadro a quadro; sem rastreamento ou indivíduos únicos.",
        "decisao": "Escolhas congeladas antes desta etapa. Estes resultados não orientam novos ajustes ou seleção de configurações.",
        "encerramento": "As cinco configurações são avaliadas nos vídeos 14, 24, 38 e 82; parâmetros e critérios permanecem congelados.",
        "interpretacao": "Avaliação final das cinco configurações congeladas; sem novos ajustes, seleção por estes resultados ou inferência de superioridade.",
    },
}


def _carregar(pasta: Path) -> dict:
    """Confere somente os arquivos consumidos pelo relatório, sem ler vídeos."""
    pasta = pasta.resolve()
    particao = pasta.parent.name
    if particao not in ETAPAS:
        raise ValueError("Informe um batch dos vídeos de seleção ou avaliação final da limiarização.")
    etapa = ETAPAS[particao]
    limite = (RAIZ / "resultados/videos/limiarizacao" / particao).resolve()
    if pasta.parent != limite or not pasta.name.startswith("batch__"):
        raise ValueError("Informe um batch dos vídeos de seleção ou avaliação final da limiarização.")
    hashes = {}

    def ler(caminho: Path) -> bytes:
        caminho = caminho.resolve()
        if not caminho.is_relative_to(pasta):
            raise ValueError("O arquivo do relatório precisa permanecer no batch.")
        conteudo = caminho.read_bytes()
        hashes[caminho.relative_to(RAIZ).as_posix()] = _sha256(conteudo)
        return conteudo

    execucao_bytes = ler(pasta / "execucao.json")
    execucao = _json(execucao_bytes)
    if execucao.get("tipo") != etapa["tipo_execucao"] or execucao.get("situacao") != "concluida":
        raise ValueError("O relatório exige uma execução concluída e compatível com a etapa da pasta.")
    if execucao.get("versao") != 1 or execucao.get("criterios") != CRITERIOS:
        raise ValueError("Versão ou critérios incompatíveis com o relatório de vídeos.")
    for campo in ("configuracoes_previstas", "configuracoes_concluidas"):
        if _inteiro(execucao.get(campo), campo) != len(CONFIGURACOES):
            raise ValueError("Quantidade de configurações incompatível com os cinco candidatos.")
    plano_bytes = ler(pasta / "plano.json")
    if _sha256(plano_bytes) != execucao.get("plano_sha256"):
        raise ValueError("Plano alterado ou sem hash registrado.")
    plano = _json(plano_bytes)
    if (plano.get("versao") != 1 or plano.get("tipo") != etapa["tipo_plano"]
            or plano.get("particao") != particao):
        raise ValueError("Tipo, partição ou versão do plano incompatível com a etapa da pasta.")
    itens = plano.get("configuracoes", [])
    if not isinstance(itens, list) or len(itens) != len(CONFIGURACOES):
        raise ValueError("O plano deve conter os cinco candidatos autorizados.")
    configuracoes = {}
    for item in itens:
        if not isinstance(item, dict) or item.get("id") not in CONFIGURACOES:
            raise ValueError("Configuração inesperada no plano dos vídeos.")
        identificador = item["id"]
        if identificador in configuracoes:
            raise ValueError("Configuração repetida no plano dos vídeos.")
        parametros = item.get("parametros")
        if not isinstance(parametros, dict) or parametros.get("metodo") not in ("manual", "otsu"):
            raise ValueError("Método ausente ou inválido no plano dos vídeos.")
        configuracoes[identificador] = item
    videos = plano.get("videos", [])
    if not isinstance(videos, list) or len(videos) != len(etapa["videos"]):
        raise ValueError("O plano deve conter os quatro vídeos previstos para esta etapa.")
    quadros_por_video = {}
    for item in videos:
        if not isinstance(item, dict):
            raise ValueError("Vídeo inválido no plano.")
        video = str(item.get("video_id"))
        if video not in etapa["videos"] or video in quadros_por_video:
            raise ValueError("Vídeo inesperado ou repetido no plano.")
        quantidade = _inteiro(item.get("quantidade_quadros"), "quantidade_quadros")
        if quantidade == 0:
            raise ValueError("Vídeos completos precisam ter pelo menos um quadro.")
        quadros_por_video[video] = quantidade
    quantidade_quadros = sum(quadros_por_video.values())
    if _inteiro(execucao.get("quadros_por_configuracao"), "quadros_por_configuracao") != quantidade_quadros:
        raise ValueError("Quantidade de quadros incompatível com o plano dos vídeos.")

    def csv_linhas(nome: str, por_video: bool = False) -> list[dict]:
        caminho = pasta / nome
        conteudo = ler(caminho)
        chave = caminho.resolve().relative_to(RAIZ).as_posix()
        if execucao.get("saidas_sha256", {}).get(chave) != _sha256(conteudo):
            raise ValueError(f"Arquivo alterado ou sem hash registrado: {nome}.")
        leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
        campos = leitor.fieldnames or []
        obrigatorios = set(CONTAGENS + TAXAS) | {
            "configuracao_id", "pasta_origem", "situacao_f1_individuos", "situacao_f1_aglomerados",
        }
        if por_video:
            obrigatorios.add("video_id")
        if len(campos) != len(set(campos)) or not obrigatorios.issubset(campos):
            raise ValueError(f"Cabeçalho inválido: {nome}.")
        linhas = list(leitor)
        if any(None in linha or any(v is None for v in linha.values()) for linha in linhas):
            raise ValueError(f"Linha incompleta: {nome}.")
        return [_linha(linha) for linha in linhas]

    totais = csv_linhas("resumo_configuracoes.csv")
    por_video = csv_linhas("resumo_por_video.csv", True)
    ids = [linha["configuracao_id"] for linha in totais]
    if len(ids) != len(CONFIGURACOES) or set(ids) != CONFIGURACOES:
        raise ValueError("Os resumos precisam conter os cinco candidatos uma única vez.")
    chaves = [(linha["configuracao_id"], linha["video_id"]) for linha in por_video]
    esperados = {(identificador, video) for identificador in ids for video in etapa["videos"]}
    if len(chaves) != len(esperados) or set(chaves) != esperados:
        raise ValueError("Resumo por vídeo incompleto, repetido ou inesperado.")
    mapa_video = dict(zip(chaves, por_video))
    pastas_origem = set()
    for total in totais:
        origem = (RAIZ / total["pasta_origem"]).resolve()
        if origem == pasta or not origem.is_relative_to(pasta) or not origem.is_dir():
            raise ValueError("A pasta de cada configuração precisa existir dentro do batch.")
        if origem in pastas_origem or origem.is_relative_to(pasta / "relatorios"):
            raise ValueError("Pasta repetida ou reservada para relatórios.")
        pastas_origem.add(origem)
        partes = [mapa_video[(total["configuracao_id"], video)] for video in quadros_por_video]
        if total["quantidade_quadros"] != quantidade_quadros:
            raise ValueError("Configuração com quantidade inesperada de quadros.")
        for parte in partes:
            if parte["quantidade_quadros"] != quadros_por_video[parte["video_id"]]:
                raise ValueError("Vídeo com quantidade inesperada de quadros.")
            if parte["pasta_origem"] != total["pasta_origem"]:
                raise ValueError("Pastas de origem divergentes entre os resumos.")
        for campo in CONTAGENS:
            if sum(parte[campo] for parte in partes) != total[campo]:
                raise ValueError(f"Soma dos vídeos incompatível: {campo}.")
    for video in quadros_por_video:
        suportes = {
            tuple(mapa_video[(identificador, video)][f"anotacoes_classe_{c}"] for c in (0, 2, 1))
            for identificador in ids
        }
        if len(suportes) != 1:
            raise ValueError("As configurações têm anotações diferentes no mesmo vídeo.")
    linhas = sorted(totais, key=lambda l: (
        _pontuacao(l) is None, -(_pontuacao(l) or Fraction(0)), l["configuracao_id"],
    ))
    return {
        "pasta": pasta, "execucao": execucao, "execucao_bytes": execucao_bytes,
        "plano": plano, "configuracoes": configuracoes, "linhas": linhas,
        "por_video": mapa_video, "quadros_por_video": quadros_por_video,
        "quantidade_quadros": quantidade_quadros, "hashes": hashes, "particao": particao,
    }


def _rotulo(linha: dict, dados: dict) -> str:
    metodo = dados["configuracoes"][linha["configuracao_id"]]["parametros"]["metodo"]
    return f"{linha['configuracao_id']} {metodo}"


def _barras(dados: dict, largura: float, altura: float):
    linhas = dados["linhas"]
    figura = _figura(largura, altura)
    eixo = figura.subplots()
    figura.subplots_adjust(left=.15, right=.97, top=.96, bottom=.17)
    valores = [l["f1_individuos"] for l in linhas]
    eixo.barh(range(len(linhas)), [v or 0 for v in valores], height=.58, color="#267c8e")
    eixo.set_yticks(range(len(linhas)), [_rotulo(l, dados) for l in linhas], fontsize=10)
    eixo.set_ylim(len(linhas) - .4, -.6)
    eixo.set_xlim(0, 1.12)
    eixo.set_xticks([0, .25, .5, .75, 1], ["0", "0,25", "0,50", "0,75", "1"], fontsize=9)
    eixo.set_xlabel("F1 de indivíduos (0 a 1)", fontsize=10)
    eixo.grid(axis="x", alpha=.18)
    eixo.set_axisbelow(True)
    eixo.tick_params(axis="y", length=0)
    for indice, valor in enumerate(valores):
        eixo.text((valor or 0) + .02, indice, _formato(valor), va="center", fontsize=10)
    for lado in ("top", "right", "left"):
        eixo.spines[lado].set_visible(False)
    return figura


def _mapa(dados: dict, colunas: list[tuple[str, str]], largura: float, altura: float,
          por_video: bool = False):
    from matplotlib import colormaps
    import numpy as np
    figura = _figura(largura, altura)
    eixo = figura.subplots()
    figura.subplots_adjust(left=.15, right=.96, top=.97, bottom=.17)
    linhas = dados["linhas"]
    valores = [[dados["por_video"][(l["configuracao_id"], campo)]["f1_individuos"]
                if por_video else l[campo] for campo, _ in colunas] for l in linhas]
    matriz = np.array([[np.nan if v is None else v for v in linha] for linha in valores])
    cores = colormaps["YlGnBu"].copy()
    cores.set_bad("#dddddd")
    eixo.imshow(np.ma.masked_invalid(matriz), vmin=0, vmax=1, cmap=cores, aspect="auto")
    eixo.set_yticks(range(len(linhas)), [_rotulo(l, dados) for l in linhas], fontsize=10)
    eixo.set_xticks(range(len(colunas)), [nome for _, nome in colunas], fontsize=10)
    eixo.tick_params(length=0)
    for i, linha in enumerate(valores):
        for j, valor in enumerate(linha):
            eixo.text(j, i, "-" if valor is None else f"{valor:.3f}".replace(".", ","),
                      va="center", ha="center", fontsize=11,
                      color="white" if valor is not None and valor > .55 else "#222222")
    for borda in eixo.spines.values():
        borda.set_visible(False)
    return figura


def _escrever_pdf(caminho: Path, dados: dict, estatisticas: dict) -> int:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas
    largura, altura = landscape(A4)
    linhas = dados["linhas"]
    etapa = ETAPAS[dados["particao"]]
    with caminho.open("xb") as arquivo:
        pdf = Canvas(arquivo, pagesize=landscape(A4), pageCompression=1)
        pdf.setTitle(f"{etapa['rotulo']} - cinco configurações de limiarização")
        pdf.setAuthor("")
        pdf.setCreator("Relatório de avaliação de detecções")

        def cabecalho(titulo: str, numero: int) -> None:
            _texto(pdf, titulo, 32, altura - 35, 16, True)
            _texto(pdf, f"{etapa['rotulo']} | 5 configurações | 4 vídeos completos | {dados['quantidade_quadros']} quadros por configuração", 32, altura - 54, 9)
            pdf.setStrokeColorRGB(.83, .86, .88)
            pdf.line(32, 32, largura - 32, 32)
            _texto(pdf, etapa["rodape"], 32, 18, 8)
            _texto(pdf, f"{numero}/3", largura - 60, 18, 8)

        cabecalho("F1 de indivíduos nos vídeos completos", 1)
        _texto(pdf, "Classes 0 e 2 reunidas; aglomerados separados. Ordem pelo F1 exato, IDs apenas organizam empates.", 32, altura - 73, 9)
        _inserir_figura(pdf, _barras(dados, largura - 64, 300), 32, 210, largura - 64, 300)
        _texto(pdf, "Distribuição descritiva do F1 entre as cinco configurações:", 32, 190, 10, True)
        e = estatisticas["f1_individuos"]
        campos = [("N definido", str(e["n"])), ("Média", _formato(e["media"])),
                  ("Mediana", _formato(e["mediana"])), ("DP amostral", _formato(e["desvio_padrao_amostral"])),
                  ("Mínimo", _formato(e["minimo"])), ("Máximo", _formato(e["maximo"]))]
        for i, (nome, valor) in enumerate(campos):
            x = 32 + i * (largura - 64) / len(campos)
            _texto(pdf, nome, x, 172, 9)
            _texto(pdf, valor, x, 154, 11, True)
        suporte = linhas[0]
        _texto(pdf, f"Anotações acumuladas: normal {suporte['anotacoes_classe_0']} | pequeno {suporte['anotacoes_classe_2']} | aglomerado {suporte['anotacoes_classe_1']}.", 32, 128, 9)
        _texto(pdf, "O mesmo objeto pode aparecer em vários quadros. As métricas somam TP, FP e FN antes de calcular o F1.", 32, 110, 9)
        _texto(pdf, etapa["decisao"], 32, 79, 9, True)
        _texto(pdf, "As estatísticas descrevem os cinco candidatos; não são intervalos de confiança ou testes de superioridade.", 32, 49, 8)
        pdf.showPage()

        cabecalho("Cobertura e classificação nos vídeos", 2)
        _texto(pdf, "Escala fixa de 0 a 1. '-' indica denominador zero e não equivale a resultado zero.", 32, altura - 73, 9)
        colunas = [("recall_classe_0", "Recall\nnormal"), ("recall_classe_2", "Recall\npequeno"),
                   ("f1_aglomerados", "F1\naglomerado"), ("acuracia_condicional", "Acurácia\ncondicional")]
        _inserir_figura(pdf, _mapa(dados, colunas, largura - 64, 350), 32, 160, largura - 64, 350)
        _texto(pdf, "Recall: fração das anotações da classe que encontrou par no mesmo grupo, incluindo trocas entre 0 e 2.", 32, 132, 9)
        _texto(pdf, "Acurácia condicional: proporção de rótulos corretos somente entre indivíduos pareados; exclui FP e FN.", 32, 111, 9)
        _texto(pdf, "Um rótulo 0/2 trocado mantém o acerto de localização. Indivíduo e aglomerado não formam par entre si.", 32, 90, 9)
        _texto(pdf, "As tabelas preservam os três rótulos e mostram a matriz de classificação, os pares e os objetos sem par.", 32, 69, 9)
        _texto(pdf, "Uma acurácia condicional alta pode coexistir com baixa cobertura: sempre interpretar as duas medidas juntas.", 32, 49, 8)
        pdf.showPage()

        cabecalho("F1 de indivíduos por vídeo", 3)
        _texto(pdf, "Mesma ordem das páginas anteriores. Cada valor utiliza todos os quadros previstos daquele vídeo.", 32, altura - 73, 9)
        videos = sorted(dados["quadros_por_video"], key=int)
        colunas = [(video, f"Vídeo {video}") for video in videos]
        _inserir_figura(pdf, _mapa(dados, colunas, largura - 64, 350, True), 32, 160, largura - 64, 350)
        contagens = " | ".join(f"{v}: {dados['quadros_por_video'][v]} quadros" for v in videos)
        _texto(pdf, contagens, 32, 132, 9, True)
        _texto(pdf, "Escala fixa de 0 a 1. '-' indica ausência de anotações e previsões; zero continua sendo zero.", 32, 111, 9)
        _texto(pdf, "O F1 geral soma contagens: vídeos com mais objetos contribuem mais para a métrica agregada.", 32, 90, 9)
        _texto(pdf, "Quadros próximos são relacionados; os resultados por vídeo ajudam a identificar falhas de generalização.", 32, 69, 9)
        _texto(pdf, etapa["encerramento"], 32, 49, 8)
        pdf.showPage()
        pdf.save()
    return 3


def gerar_relatorio(pasta_batch: Path) -> Path:
    """Cria um relatório novo; não altera o manifesto nem executa os algoritmos."""
    dependencias = verificar_dependencias()
    dados = _carregar(Path(pasta_batch))
    estatisticas = _estatisticas(dados["linhas"])
    inicio = datetime.now(timezone.utc)
    pasta = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not pasta.is_relative_to(dados["pasta"]):
        raise ValueError("A pasta do relatório precisa permanecer no batch.")
    pasta.mkdir(parents=True, exist_ok=False)
    caminho_pdf = pasta / "relatorio.pdf"
    caminho_json = pasta / "relatorio.json"
    etapa = ETAPAS[dados["particao"]]
    registro = {
        "versao_relatorio": 1, "tipo": etapa["tipo_execucao"], "particao": dados["particao"],
        "situacao": "em_andamento",
        "inicio_utc": inicio.isoformat(), "origem_batch": dados["pasta"].relative_to(RAIZ).as_posix(),
        "criterios": dados["execucao"]["criterios"], "origens_sha256": dados["hashes"],
        "escopo_integridade": "Manifesto, plano e duas tabelas consumidas pelo relatório. Vídeos e demais saídas não são relidos.",
        "codigo_relatorio_sha256": {
            nome: _sha256((RAIZ / nome).read_bytes()) for nome in (
                "analise/relatorio_videos.py", "analise/relatorio_individuos.py",
                "analise/relatorio_rodada.py", "analise/avaliacao_individuos.py",
                "analise/avaliacao_deteccao.py",
            )
        },
        "dependencias": dependencias, "estatisticas_entre_configuracoes": estatisticas,
        "ordem_visual_configuracoes": [l["configuracao_id"] for l in dados["linhas"]],
        "ordenacao": "F1 de indivíduos pela fração exata; ID somente para apresentação dos empates.",
        "interpretacao": etapa["interpretacao"],
        "arquivo_pdf": caminho_pdf.relative_to(RAIZ).as_posix(),
    }
    try:
        _gravar_json(caminho_json, registro)
        (pasta / "execucao_origem.json").write_bytes(dados["execucao_bytes"])
        registro["paginas"] = _escrever_pdf(caminho_pdf, dados, estatisticas)
        registro.update(situacao="concluida", fim_utc=datetime.now(timezone.utc).isoformat(),
                        pdf_sha256=_sha256(caminho_pdf.read_bytes()))
        _gravar_json(caminho_json, registro)
    except BaseException as erro:
        registro.update(situacao="falhou", fim_utc=datetime.now(timezone.utc).isoformat(),
                        erro=f"{type(erro).__name__}: {erro}")
        try:
            _gravar_json(caminho_json, registro)
        except OSError:
            pass
        raise
    return caminho_pdf
