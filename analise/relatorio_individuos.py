"""PDF da reavaliação por grupos, construído somente dos resultados salvos."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from fractions import Fraction
from io import StringIO
import math
from pathlib import Path
from statistics import mean, median, stdev

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_rodada import (
    RAIZ, _figura, _formato, _gravar_json, _inserir_figura, _inteiro,
    _json, _numero, _sha256, _texto, verificar_dependencias,
)


CONTAGENS = (
    "quantidade_quadros", "pares_corretos", "pares_incorretos", "pares_total",
    "matriz_0_0", "matriz_0_2", "matriz_2_0", "matriz_2_2",
    *(f"{campo}_{grupo}" for grupo in ("individuos", "aglomerados")
      for campo in ("tp", "fp", "fn")),
    *(f"{campo}_classe_{classe}" for classe in (0, 2, 1)
      for campo in ("anotacoes", "localizadas", "perdidas")),
)
TAXAS = (
    "acuracia_condicional", "recall_classe_0", "recall_classe_2", "recall_classe_1",
    *(f"{campo}_{grupo}" for grupo in ("individuos", "aglomerados")
      for campo in ("precisao", "recall", "f1")),
)


def _taxa_confere(linha: dict, campo: str, numerador: int, denominador: int) -> None:
    esperado = numerador / denominador if denominador else None
    valor = linha[campo]
    if (valor is None) != (esperado is None) or (
        valor is not None and not math.isclose(valor, esperado, rel_tol=1e-12, abs_tol=1e-12)
    ):
        raise ValueError(f"Taxa incompatível com as contagens: {campo}.")


def _linha(linha: dict) -> dict:
    resultado = dict(linha)
    for campo in CONTAGENS:
        resultado[campo] = _inteiro(linha[campo], campo)
    for campo in TAXAS:
        resultado[campo] = _numero(linha[campo], campo)
    for grupo in ("individuos", "aglomerados"):
        tp, fp, fn = (resultado[f"{campo}_{grupo}"] for campo in ("tp", "fp", "fn"))
        _taxa_confere(resultado, f"precisao_{grupo}", tp, tp + fp)
        _taxa_confere(resultado, f"recall_{grupo}", tp, tp + fn)
        _taxa_confere(resultado, f"f1_{grupo}", 2 * tp, 2 * tp + fp + fn)
        situacao = "sem_casos" if tp + fp + fn == 0 else "definido"
        if resultado[f"situacao_f1_{grupo}"] != situacao:
            raise ValueError(f"Situação do F1 incoerente: {grupo}.")
    for classe in (0, 2, 1):
        anotadas, localizadas, perdidas = (
            resultado[f"{campo}_classe_{classe}"]
            for campo in ("anotacoes", "localizadas", "perdidas")
        )
        if localizadas + perdidas != anotadas:
            raise ValueError("Cobertura incompatível com as contagens.")
        _taxa_confere(resultado, f"recall_classe_{classe}", localizadas, anotadas)
    for grupo, classes in (("individuos", (0, 2)), ("aglomerados", (1,))):
        if sum(resultado[f"localizadas_classe_{c}"] for c in classes) != resultado[f"tp_{grupo}"]:
            raise ValueError("Cobertura incompatível com os acertos do grupo.")
        if sum(resultado[f"perdidas_classe_{c}"] for c in classes) != resultado[f"fn_{grupo}"]:
            raise ValueError("Cobertura incompatível com as perdas do grupo.")
    corretos = resultado["matriz_0_0"] + resultado["matriz_2_2"]
    incorretos = resultado["matriz_0_2"] + resultado["matriz_2_0"]
    if (resultado["pares_corretos"], resultado["pares_incorretos"], resultado["pares_total"]) != (
        corretos, incorretos, corretos + incorretos
    ) or resultado["pares_total"] != resultado["tp_individuos"]:
        raise ValueError("Matriz de classificação incompatível com os pares.")
    for classe in (0, 2):
        if sum(resultado[f"matriz_{classe}_{c}"] for c in (0, 2)) != resultado[f"localizadas_classe_{classe}"]:
            raise ValueError("Matriz de classificação incompatível com a cobertura.")
    _taxa_confere(resultado, "acuracia_condicional", corretos, corretos + incorretos)
    return resultado


def _pontuacao(linha: dict) -> Fraction | None:
    denominador = 2 * linha["tp_individuos"] + linha["fp_individuos"] + linha["fn_individuos"]
    return Fraction(2 * linha["tp_individuos"], denominador) if denominador else None


def _carregar(pasta: Path) -> dict:
    pasta = pasta.resolve()
    limite = (RAIZ / "resultados/frame-to-frame/limiarizacao/selecao").resolve()
    if not pasta.is_relative_to(limite) or pasta.parent.name != "reavaliacoes_individuos":
        raise ValueError("Informe a pasta de uma reavaliação de indivíduos da seleção.")
    hashes = {}

    def ler(caminho: Path) -> bytes:
        caminho = caminho.resolve()
        if not caminho.is_relative_to(limite):
            raise ValueError("A origem do relatório precisa permanecer na seleção.")
        conteudo = caminho.read_bytes()
        hashes[caminho.relative_to(RAIZ).as_posix()] = _sha256(conteudo)
        return conteudo

    execucao_bytes = ler(pasta / "execucao.json")
    execucao = _json(execucao_bytes)
    if execucao.get("tipo") != "reavaliacao_individuos" or execucao.get("situacao") != "concluida":
        raise ValueError("O relatório exige uma reavaliação concluída.")
    if execucao.get("versao") != 1 or execucao.get("criterios") != CRITERIOS:
        raise ValueError("Versão ou critérios de reavaliação incompatíveis com este relatório.")

    def conferir_hash(caminho: Path, conteudo: bytes, campo: str) -> None:
        esperado = execucao.get(campo, {}).get(caminho.resolve().relative_to(RAIZ).as_posix())
        if esperado != _sha256(conteudo):
            raise ValueError(f"Arquivo alterado ou sem hash registrado: {caminho.name}.")

    origem = (RAIZ / execucao["origem_batch"]).resolve()
    if origem != pasta.parent.parent:
        raise ValueError("Batch de origem incompatível com a pasta de reavaliação.")
    plano_bytes = ler(origem / "rodada.json")
    conferir_hash(origem / "rodada.json", plano_bytes, "origens_sha256")
    plano = _json(plano_bytes)
    if plano.get("particao") != "selecao":
        raise ValueError("A origem precisa pertencer à seleção.")
    configuracoes = {item["id"]: item for item in plano["configuracoes"]}

    def csv_linhas(nome: str) -> list[dict]:
        conteudo = ler(pasta / nome)
        conferir_hash(pasta / nome, conteudo, "saidas_sha256")
        leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
        campos = leitor.fieldnames or []
        if len(campos) != len(set(campos)) or not set(CONTAGENS + TAXAS).issubset(campos):
            raise ValueError(f"Cabeçalho inválido: {nome}.")
        linhas = list(leitor)
        if any(None in linha or any(valor is None for valor in linha.values()) for linha in linhas):
            raise ValueError(f"Linha incompleta: {nome}.")
        return [_linha(linha) for linha in linhas]

    totais = csv_linhas("resumo_configuracoes.csv")
    por_video = csv_linhas("resumo_por_video.csv")
    ids = [linha["configuracao_id"] for linha in totais]
    if len(set(ids)) != len(ids) or set(ids) != set(configuracoes):
        raise ValueError("As configurações dos resumos diferem do plano original.")
    for campo in ("configuracoes_previstas", "configuracoes_concluidas"):
        if _inteiro(execucao[campo], campo) != len(totais):
            raise ValueError("Quantidade de configurações incompatível com o manifesto.")
    quantidade_quadros = len(plano["quadros"])
    if _inteiro(execucao["quadros_por_configuracao"], "quadros_por_configuracao") != quantidade_quadros:
        raise ValueError("Quantidade de quadros incompatível com o plano.")
    quadros_por_video = {}
    for quadro in plano["quadros"]:
        video = str(quadro["video_id"])
        quadros_por_video[video] = quadros_por_video.get(video, 0) + 1
    pares = [(linha["configuracao_id"], linha["video_id"]) for linha in por_video]
    esperados = {(identificador, video) for identificador in ids for video in quadros_por_video}
    if len(pares) != len(set(pares)) or set(pares) != esperados:
        raise ValueError("Resumo por vídeo incompleto ou repetido.")
    mapa_video = dict(zip(pares, por_video))
    for total in totais:
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
        suportes = {tuple(mapa_video[(identificador, video)][f"anotacoes_classe_{c}"]
                          for c in (0, 2, 1)) for identificador in ids}
        if len(suportes) != 1:
            raise ValueError("As configurações têm anotações diferentes no mesmo vídeo.")
    linhas = sorted(totais, key=lambda l: (
        _pontuacao(l) is None, -(_pontuacao(l) or Fraction(0)), l["configuracao_id"]
    ))
    return {
        "pasta": pasta, "execucao": execucao, "execucao_bytes": execucao_bytes,
        "plano": plano, "configuracoes": configuracoes, "linhas": linhas,
        "por_video": mapa_video, "quadros_por_video": quadros_por_video,
        "hashes": hashes,
        "empate_corte": len(linhas) > 5 and _pontuacao(linhas[4]) is not None
        and _pontuacao(linhas[4]) == _pontuacao(linhas[5]),
    }


def _estatisticas(linhas: list[dict]) -> dict:
    saida = {}
    for campo in ("f1_individuos", "recall_classe_0", "recall_classe_2", "f1_aglomerados", "acuracia_condicional"):
        valores = [linha[campo] for linha in linhas if linha[campo] is not None]
        saida[campo] = {
            "n": len(valores), "sem_casos": len(linhas) - len(valores),
            "media": mean(valores) if valores else None,
            "mediana": median(valores) if valores else None,
            "desvio_padrao_amostral": stdev(valores) if len(valores) > 1 else None,
            "minimo": min(valores) if valores else None,
            "maximo": max(valores) if valores else None,
        }
    return saida


def _rotulo(linha: dict, dados: dict) -> str:
    metodo = dados["configuracoes"][linha["configuracao_id"]]["parametros"]["metodo"]
    return f"{linha['configuracao_id']} {metodo}"


def _barras(linhas: list[dict], dados: dict, largura: float, altura: float):
    figura = _figura(largura, altura)
    eixos = figura.subplots(1, 2, squeeze=False)[0]
    figura.subplots_adjust(left=0.12, right=0.99, top=0.98, bottom=0.12, wspace=0.55)
    for eixo, parte in zip(eixos, (linhas[:24], linhas[24:])):
        if not parte:
            eixo.set_axis_off()
            continue
        valores = [linha["f1_individuos"] for linha in parte]
        eixo.barh(range(len(parte)), [v or 0 for v in valores], height=0.65, color="#267c8e")
        eixo.set_yticks(range(len(parte)), [_rotulo(l, dados) for l in parte], fontsize=8)
        eixo.set_ylim(23.8, -0.8)
        eixo.set_xlim(0, 1.2)
        eixo.set_xticks([0, .25, .5, .75, 1], ["0", "0,25", "0,50", "0,75", "1"], fontsize=8)
        eixo.set_xlabel("F1 de indivíduos (0 a 1)", fontsize=9)
        eixo.grid(axis="x", alpha=.18)
        eixo.set_axisbelow(True)
        eixo.tick_params(axis="y", length=0)
        for indice, valor in enumerate(valores):
            eixo.text((valor or 0) + .025, indice, _formato(valor), va="center", fontsize=8)
        for lado in ("top", "right", "left"):
            eixo.spines[lado].set_visible(False)
    return figura


def _mapa(linhas: list[dict], dados: dict, colunas: list[tuple[str, str]],
          largura: float, altura: float, por_video: bool = False):
    from matplotlib import colormaps
    import numpy as np
    figura = _figura(largura, altura)
    eixos = figura.subplots(1, 2, squeeze=False)[0]
    figura.subplots_adjust(left=.12, right=.98, top=.94, bottom=.14, wspace=.45)
    cores = colormaps["YlGnBu"].copy()
    cores.set_bad("#dddddd")
    for eixo, parte in zip(eixos, (linhas[:24], linhas[24:])):
        if not parte:
            eixo.set_axis_off()
            continue
        valores = [[dados["por_video"][(l["configuracao_id"], campo)]["f1_individuos"]
                    if por_video else l[campo] for campo, _ in colunas] for l in parte]
        matriz = np.array([[np.nan if v is None else v for v in linha] for linha in valores])
        eixo.imshow(np.ma.masked_invalid(matriz), vmin=0, vmax=1, cmap=cores, aspect="auto")
        eixo.set_yticks(range(len(parte)), [_rotulo(l, dados) for l in parte], fontsize=8)
        eixo.set_xticks(range(len(colunas)), [nome for _, nome in colunas], fontsize=8)
        eixo.set_ylim(23.5, -.5)
        eixo.tick_params(length=0)
        for i, linha in enumerate(valores):
            for j, valor in enumerate(linha):
                eixo.text(j, i, "-" if valor is None else f"{valor:.3f}".replace(".", ","),
                          va="center", ha="center", fontsize=8,
                          color="white" if valor is not None and valor > .55 else "#222222")
        for borda in eixo.spines.values():
            borda.set_visible(False)
    return figura


def _escrever_pdf(caminho: Path, dados: dict, estatisticas: dict) -> int:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas
    largura, altura = landscape(A4)
    linhas = dados["linhas"]
    blocos = [linhas[i:i + 48] for i in range(0, len(linhas), 48)]
    videos = sorted(dados["quadros_por_video"], key=int)
    paginas = len(blocos) * 3
    with caminho.open("xb") as arquivo:
        pdf = Canvas(arquivo, pagesize=landscape(A4), pageCompression=1)
        pdf.setTitle("Seleção - detecção de indivíduos e classificação")
        pdf.setAuthor("")
        pdf.setCreator("Relatório de avaliação de detecções")

        def cabecalho(titulo: str, numero: int, bloco: int) -> None:
            _texto(pdf, titulo, 32, altura - 35, 16, True)
            _texto(pdf, f"Seleção | bloco {bloco}/{len(blocos)} | {len(linhas)} configurações | {len(dados['plano']['quadros'])} quadros por configuração", 32, altura - 54, 9)
            pdf.setStrokeColorRGB(.83, .86, .88)
            pdf.line(32, 32, largura - 32, 32)
            _texto(pdf, "Caixas salvas; rótulos originais preservados. Critério revisado após observar a primeira seleção.", 32, 18, 8)
            _texto(pdf, f"{numero}/{paginas}", largura - 60, 18, 8)

        for numero, bloco in enumerate(blocos, 1):
            cabecalho("F1 de indivíduos - classes 0 e 2 reunidas", 3 * numero - 2, numero)
            _texto(pdf, "Ordem pelo F1 exato; IDs apenas organizam empates. Esta apresentação não escolhe as cinco finalistas.", 32, altura - 72, 9)
            _inserir_figura(pdf, _barras(bloco, dados, largura - 64, 340), 32, 174, largura - 64, 340)
            _texto(pdf, "Distribuição do F1 entre todas as configurações (valores definidos):", 32, 155, 10, True)
            e = estatisticas["f1_individuos"]
            campos = [("N", str(e["n"])), ("Média", _formato(e["media"])), ("Mediana", _formato(e["mediana"])),
                      ("DP amostral", _formato(e["desvio_padrao_amostral"])), ("Mínimo", _formato(e["minimo"])), ("Máximo", _formato(e["maximo"]))]
            for i, (nome, valor) in enumerate(campos):
                x = 32 + i * (largura - 64) / len(campos)
                _texto(pdf, nome, x, 136, 9)
                _texto(pdf, valor, x, 119, 11, True)
            suporte = linhas[0]
            _texto(pdf, f"Anotações: normal {suporte['anotacoes_classe_0']} | pequeno {suporte['anotacoes_classe_2']} | aglomerado {suporte['anotacoes_classe_1']}. Não são indivíduos únicos entre quadros.", 32, 95, 9)
            nota = "Há empate atravessando as posições 5 e 6; a decisão exige revisão conjunta." if dados["empate_corte"] else "Revisar cobertura dos pequenos, aglomerados e diferenças entre vídeos antes de escolher cinco."
            _texto(pdf, nota, 32, 76, 9, True)
            _texto(pdf, "Média e DP descrevem configurações; não são intervalos de confiança ou evidência de superioridade estatística.", 32, 47, 8)
            pdf.showPage()

            cabecalho("Cobertura e classificação - diagnósticos separados", 3 * numero - 1, numero)
            _texto(pdf, "Escala fixa de 0 a 1. '-' indica denominador zero; não equivale a resultado zero.", 32, altura - 72, 9)
            colunas = [("recall_classe_0", "Recall\nnormal"), ("recall_classe_2", "Recall\npequeno"),
                       ("f1_aglomerados", "F1\naglomerado"), ("acuracia_condicional", "Acurácia\ncondicional")]
            _inserir_figura(pdf, _mapa(bloco, dados, colunas, largura - 64, 420), 32, 90, largura - 64, 420)
            _texto(pdf, "Recall por classe anotada: fração localizada dentro do grupo, inclusive trocas 0/2. Não mede acerto do rótulo.", 32, 78, 8)
            _texto(pdf, "Acurácia condicional: rótulo correto apenas entre indivíduos pareados; exclui perdidos e falsas detecções.", 32, 63, 8)
            _texto(pdf, "Matriz 0/2 e contagens de erros estão nas tabelas. Indivíduo e aglomerado não formam par entre si.", 32, 47, 8)
            pdf.showPage()

            cabecalho("F1 de indivíduos por vídeo", 3 * numero, numero)
            _texto(pdf, "Mesma ordem dos gráficos anteriores. Cada valor usa as contagens somadas no vídeo, sem média dos F1 dos quadros.", 32, altura - 72, 9)
            colunas = [(video, f"Vídeo {video}") for video in videos]
            _inserir_figura(pdf, _mapa(bloco, dados, colunas, largura - 64, 420, True), 32, 90, largura - 64, 420)
            _texto(pdf, "Escala fixa de 0 a 1. '-' indica ausência de anotações e previsões do grupo; valores zero permanecem zero.", 32, 78, 8)
            _texto(pdf, "O F1 geral soma contagens: vídeos com mais objetos contribuem mais. Quadros do mesmo vídeo são relacionados.", 32, 63, 8)
            _texto(pdf, "Configurações e dados permanecem fixos; a reavaliação altera apenas o critério de detecção e seus diagnósticos.", 32, 47, 8)
            pdf.showPage()
        pdf.save()
    return paginas


def gerar_relatorio(pasta_reavaliacao: Path) -> Path:
    """Gera outro relatório sem executar pareamento ou modificar os resultados."""
    dependencias = verificar_dependencias()
    dados = _carregar(Path(pasta_reavaliacao))
    estatisticas = _estatisticas(dados["linhas"])
    inicio = datetime.now(timezone.utc)
    pasta = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not pasta.is_relative_to(dados["pasta"]):
        raise ValueError("A pasta do relatório precisa permanecer na reavaliação.")
    pasta.mkdir(parents=True, exist_ok=False)
    caminho_pdf = pasta / "relatorio.pdf"
    caminho_json = pasta / "relatorio.json"
    registro = {
        "versao_relatorio": 1, "situacao": "em_andamento", "inicio_utc": inicio.isoformat(),
        "origem_reavaliacao": dados["pasta"].relative_to(RAIZ).as_posix(),
        "criterios": dados["execucao"]["criterios"], "origens_sha256": dados["hashes"],
        "codigo_relatorio_sha256": {
            nome: _sha256((RAIZ / nome).read_bytes())
            for nome in ("analise/relatorio_individuos.py", "analise/relatorio_rodada.py",
                         "analise/avaliacao_individuos.py", "analise/avaliacao_deteccao.py")
        },
        "dependencias": dependencias, "estatisticas_entre_configuracoes": estatisticas,
        "ordem_visual_configuracoes": [l["configuracao_id"] for l in dados["linhas"]],
        "ordenacao": "F1 de indivíduos pela fração exata; ID somente para apresentação dos empates.",
        "empate_no_corte_5": dados["empate_corte"],
        "interpretacao": "Descrições entre configurações; não estimam incerteza. Sem promoção automática.",
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
