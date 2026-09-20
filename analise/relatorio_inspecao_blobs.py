"""PDF descritivo da inspeção round0, a partir de métricas salvas e conferidas."""

from __future__ import annotations

import csv
from io import StringIO
import json
import math
from pathlib import Path
import platform

from analise.avaliacao_individuos import CRITERIOS
from scripts.limiarizacao.inspecionar_imagem import (
    agora, gravar_json, objeto_sem_duplicatas, rejeitar_constante, sha256,
)


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/blobs/round0"
CONTAGENS = [
    *[f"{c}_{g}" for g in ("individuos", "aglomerados") for c in ("tp", "fp", "fn")],
    *[f"{c}_classe_{k}" for k in (0, 2, 1) for c in ("anotacoes", "localizadas", "perdidas")],
    "pares_corretos", "pares_incorretos", "pares_total",
    "matriz_0_0", "matriz_0_2", "matriz_2_0", "matriz_2_2",
]


def _json(conteudo: bytes) -> dict:
    return json.loads(conteudo.decode("utf-8-sig"), parse_constant=rejeitar_constante,
                      object_pairs_hook=objeto_sem_duplicatas)


def _csv(conteudo: bytes) -> list[dict]:
    leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
    if not leitor.fieldnames or len(leitor.fieldnames) != len(set(leitor.fieldnames)):
        raise ValueError("CSV sem cabeçalho válido.")
    linhas = list(leitor)
    if any(None in linha or any(v is None for v in linha.values()) for linha in linhas):
        raise ValueError("CSV com quantidade de colunas divergente.")
    return linhas


def _inteiro(valor: str) -> int:
    if not isinstance(valor, str) or not valor.isascii() or not valor.isdecimal():
        raise ValueError(f"Contagem inteira não negativa esperada: {valor!r}.")
    return int(valor)


def _numero(valor: str) -> float | None:
    if valor == "":
        return None
    convertido = float(valor)
    if not math.isfinite(convertido):
        raise ValueError("Métricas devem ser finitas ou ausentes.")
    return convertido


def _conferir_razao(linha: dict, campo: str, numerador: int, denominador: int) -> None:
    salvo = _numero(linha[campo])
    esperado = numerador / denominador if denominador else None
    if ((salvo is None) != (esperado is None)
            or (salvo is not None and not math.isclose(salvo, esperado, rel_tol=1e-12, abs_tol=1e-15))):
        raise ValueError(f"Métrica inconsistente: {campo}.")


def _conferir_metricas(linha: dict) -> None:
    n = {c: _inteiro(linha[c]) for c in CONTAGENS}
    for grupo, classes in (("individuos", (0, 2)), ("aglomerados", (1,))):
        tp, fp, fn = (n[f"{campo}_{grupo}"] for campo in ("tp", "fp", "fn"))
        _conferir_razao(linha, f"precisao_{grupo}", tp, tp + fp)
        _conferir_razao(linha, f"recall_{grupo}", tp, tp + fn)
        _conferir_razao(linha, f"f1_{grupo}", 2 * tp, 2 * tp + fp + fn)
        estado = "definido" if 2 * tp + fp + fn else "sem_casos"
        if linha[f"situacao_f1_{grupo}"] != estado:
            raise ValueError("Situação do F1 inconsistente.")
        if (sum(n[f"localizadas_classe_{c}"] for c in classes) != tp
                or sum(n[f"perdidas_classe_{c}"] for c in classes) != fn):
            raise ValueError("Cobertura incompatível com as contagens dos grupos.")
    for classe in (0, 2, 1):
        total, localizada, perdida = (n[f"{c}_classe_{classe}"] for c in ("anotacoes", "localizadas", "perdidas"))
        if total != localizada + perdida:
            raise ValueError("Cobertura incompatível com o total anotado.")
        _conferir_razao(linha, f"recall_classe_{classe}", localizada, total)
    if (n["matriz_0_0"] + n["matriz_0_2"] != n["localizadas_classe_0"]
            or n["matriz_2_0"] + n["matriz_2_2"] != n["localizadas_classe_2"]
            or n["matriz_0_0"] + n["matriz_2_2"] != n["pares_corretos"]
            or n["matriz_0_2"] + n["matriz_2_0"] != n["pares_incorretos"]
            or n["pares_corretos"] + n["pares_incorretos"] != n["pares_total"]
            or n["pares_total"] != n["tp_individuos"]):
        raise ValueError("Matriz de classificação inconsistente.")
    _conferir_razao(linha, "acuracia_condicional", n["pares_corretos"], n["pares_total"])


def carregar(pasta: Path) -> dict:
    """Confere somente as fontes salvas do relatório, sem abrir dados originais."""
    pasta = Path(pasta).expanduser().resolve(strict=True)
    if (not SAIDA.resolve().is_relative_to(RAIZ.resolve())
            or pasta.parent != SAIDA.resolve() or not pasta.name.startswith("inspecao__")):
        raise ValueError("Informe uma pasta inspecao__... diretamente dentro de blobs/round0/.")
    hashes = {}
    def ler(nome: str) -> bytes:
        caminho = (pasta / nome).resolve(strict=True)
        if not caminho.is_relative_to(pasta) or not caminho.is_file():
            raise ValueError("Fonte do relatório fora da pasta de inspeção.")
        conteudo = caminho.read_bytes()
        hashes[caminho.relative_to(RAIZ.resolve()).as_posix()] = sha256(conteudo)
        return conteudo
    manifesto_bytes = ler("execucao.json")
    manifesto = _json(manifesto_bytes)
    if (type(manifesto.get("versao")) is not int or manifesto["versao"] != 1
            or manifesto.get("situacao") != "concluida" or manifesto.get("tipo") != "inspecao_blobs"
            or manifesto.get("algoritmo") != "blobs" or manifesto.get("etapa") != "inspecao"
            or manifesto.get("rodada") != "round0" or manifesto.get("particao") != "desenvolvimento"
            or manifesto.get("criterios") != CRITERIOS
            or manifesto.get("configuracoes_previstas") != 2 or manifesto.get("configuracoes_concluidas") != 2
            or manifesto.get("quadros_por_configuracao") != 6):
        raise ValueError("Manifesto não descreve uma inspeção round0 concluída e compatível.")
    plano_bytes = ler("plano.json")
    if sha256(plano_bytes) != manifesto["plano_sha256"]:
        raise ValueError("Hash do plano salvo divergente.")
    plano = _json(plano_bytes)
    if type(plano.get("versao")) is not int or plano["versao"] != 1:
        raise ValueError("Versão do plano salvo incompatível com a inspeção round0.")
    for campo, esperado in (("versao", 1), ("algoritmo", "blobs"), ("etapa", "inspecao"),
                            ("rodada", "round0"), ("particao", "desenvolvimento")):
        if plano.get(campo) != esperado:
            raise ValueError("Plano salvo não corresponde à inspeção round0.")
    ids = [x["id"] for x in plano["configuracoes"]]
    quadros = [(x["video_id"], x["quadro"]) for x in plano["quadros"]]
    if len(ids) != 2 or len(set(ids)) != 2 or len(quadros) != 6 or len(set(quadros)) != 6:
        raise ValueError("Composição de configurações/quadros inválida.")
    tabelas = {}
    for nome in ("resumo_configuracoes.csv", "resumo_por_quadro.csv"):
        conteudo = ler(nome)
        chave = (pasta / nome).relative_to(RAIZ.resolve()).as_posix()
        if manifesto["saidas_sha256"].get(chave) != sha256(conteudo):
            raise ValueError(f"Hash divergente em {nome}.")
        tabelas[nome] = _csv(conteudo)
    resumos, linhas = tabelas["resumo_configuracoes.csv"], tabelas["resumo_por_quadro.csv"]
    por_id = {x["configuracao_id"]: x for x in resumos}
    if len(resumos) != 2 or set(por_id) != set(ids):
        raise ValueError("Resumo não contém exatamente as duas configurações.")
    chaves = [(x["configuracao_id"], x["video_id"], _inteiro(x["quadro"])) for x in linhas]
    if len(chaves) != 12 or set(chaves) != {(i, v, q) for i in ids for v, q in quadros}:
        raise ValueError("Resumo por quadro incompleto, repetido ou fora do plano.")
    quadros_plano = {(x["video_id"], x["quadro"]): x for x in plano["quadros"]}
    for linha in [*resumos, *linhas]:
        _conferir_metricas(linha)
    for linha in linhas:
        referencia = quadros_plano[linha["video_id"], _inteiro(linha["quadro"])]
        if any(linha[c] != referencia[c] for c in ("imagem", "anotacao", "objetivo")):
            raise ValueError("Origem/objetivo de quadro divergente do plano.")
        if _inteiro(linha["quantidade_anotacoes"]) != sum(_inteiro(linha[f"anotacoes_classe_{c}"]) for c in (0, 1, 2)):
            raise ValueError("Total de anotações inconsistente.")
        if _inteiro(linha["quantidade_deteccoes"]) != sum(_inteiro(linha[f"{k}_{g}"]) for k in ("tp", "fp") for g in ("individuos", "aglomerados")):
            raise ValueError("Total de detecções inconsistente.")
    for ident in ids:
        grupo = [x for x in linhas if x["configuracao_id"] == ident]
        if _inteiro(por_id[ident]["quantidade_quadros"]) != 6:
            raise ValueError("Quantidade de quadros incompatível.")
        for campo in CONTAGENS:
            if sum(_inteiro(x[campo]) for x in grupo) != _inteiro(por_id[ident][campo]):
                raise ValueError(f"Agregação inconsistente: {ident}/{campo}.")
    # As anotações precisam ser as mesmas entre as duas configurações.
    for v, q in quadros:
        grupo = [x for x in linhas if (x["video_id"], _inteiro(x["quadro"])) == (v, q)]
        for c in (0, 1, 2):
            if len({x[f"anotacoes_classe_{c}"] for x in grupo}) != 1:
                raise ValueError("Suporte de classe diverge entre configurações no mesmo quadro.")
    return {"pasta": pasta, "manifesto": manifesto, "manifesto_bytes": manifesto_bytes,
            "plano": plano, "ids": ids, "quadros": quadros, "resumos": por_id,
            "linhas": linhas, "hashes": hashes}


def _valor(texto: str) -> str:
    return "sem casos" if texto == "" else f"{float(texto):.3f}".replace(".", ",")


def escrever_pdf(caminho: Path, dados: dict) -> int:
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import simpleSplit
    largura, altura = A4
    c = Canvas(str(caminho), pagesize=A4)
    c.setTitle("Blobs — inspeção round0")
    c.setAuthor("Projeto de detecção em microscopia")
    margem, util = 42, largura - 84
    cores = [HexColor("#287b8e"), HexColor("#cf8532")]

    def texto(conteudo, x, y, tamanho=10, negrito=False):
        c.setFillColor(HexColor("#213547"))
        c.setFont("Helvetica-Bold" if negrito else "Helvetica", tamanho)
        c.drawString(x, y, str(conteudo))

    def paragrafo(conteudo, y, tamanho=9):
        linhas = simpleSplit(conteudo, "Helvetica", tamanho, util)
        for linha in linhas:
            texto(linha, margem, y, tamanho)
            y -= tamanho + 4
        return y - 8

    def abrir(numero, subtitulo):
        texto("BLOBS | INSPEÇÃO ROUND0", margem, altura - 48, 19, True)
        texto(subtitulo, margem, altura - 69, 11)
        c.setFillColor(HexColor("#edf3f5"))
        c.rect(margem, altura - 114, util, 29, fill=1, stroke=0)
        texto("Seis imagens de desenvolvimento. Não é round1 nem seleção de finalistas.", margem + 8, altura - 103, 9, True)
        texto(f"{dados['pasta'].name} | página {numero}/2", margem, 27, 8)

    abrir(1, "Localização, cobertura e classificação nas duas sondagens fixas")
    y = altura - 140
    y = paragrafo("F1 é calculado após somar TP, FP e FN das seis imagens. Classes 0 e 2 são indivíduos; a classe 1 é avaliada separadamente. IoU mínimo de 0,50 e correspondência um para um.", y)
    for i, ident in enumerate(dados["ids"]):
        linha = dados["resumos"][ident]
        p = dados["plano"]["configuracoes"][i]["parametros"]
        texto(f"{ident} — {p['polaridade']}", margem, y, 12, True)
        texto(f"F1 indivíduos: {_valor(linha['f1_individuos'])}", margem + 160, y, 11, True)
        y -= 21
        c.setFillColor(HexColor("#e6e9ed")); c.rect(margem, y, util, 10, fill=1, stroke=0)
        valor = _numero(linha["f1_individuos"])
        c.setFillColor(cores[i]); c.rect(margem, y, util * (valor or 0), 10, fill=1, stroke=0)
        y -= 18
        texto(f"TP {linha['tp_individuos']} | FP {linha['fp_individuos']} | FN {linha['fn_individuos']}", margem, y)
        y -= 16
        texto(f"Precisão {_valor(linha['precisao_individuos'])} | Recall {_valor(linha['recall_individuos'])}", margem, y)
        y -= 16
        texto(f"Cobertura: normal {_valor(linha['recall_classe_0'])} | pequeno {_valor(linha['recall_classe_2'])} | aglomerado {_valor(linha['recall_classe_1'])}", margem, y, 9)
        y -= 16
        texto(f"F1 aglomerados {_valor(linha['f1_aglomerados'])} | Trocas 0/2: {linha['pares_incorretos']} de {linha['pares_total']} pares", margem, y, 9)
        y -= 16
        texto(f"Acurácia condicional {_valor(linha['acuracia_condicional'])} (somente indivíduos encontrados)", margem, y, 9)
        y -= 28
    primeiro = dados["resumos"][dados["ids"][0]]
    y = paragrafo("Anotações no conjunto: " + "; ".join(f"classe {k}: {primeiro[f'anotacoes_classe_{k}']}" for k in (0, 1, 2)) + ".", y)
    y = paragrafo("Objetivo: conferir se os centros e caixas são plausíveis, se há perdas, duplicações, falsas detecções e classificações inadequadas. A ordem segue o plano; não há ranking ou escolha automática.", y)
    paragrafo("Centro e diâmetro vêm de keypoints; a área estimada é a de um disco. Esses valores não são centroide nem área segmentada. F1 não representa a porcentagem de objetos encontrados. Os limites de classificação são hipóteses iniciais.", y)
    c.showPage()

    abrir(2, "Variação entre as seis imagens e pontos de revisão visual")
    y = altura - 140
    texto("F1 de indivíduos por quadro (escala fixa de 0 a 1)", margem, y, 11, True)
    y -= 23
    por_chave = {(x["configuracao_id"], x["video_id"], int(x["quadro"])): x for x in dados["linhas"]}
    for video, quadro in dados["quadros"]:
        texto(f"Vídeo {video} | quadro {quadro}", margem, y, 9, True)
        y -= 16
        for i, ident in enumerate(dados["ids"]):
            linha = por_chave[ident, video, quadro]
            texto(ident, margem, y, 9)
            c.setFillColor(HexColor("#e6e9ed")); c.rect(margem + 40, y - 1, 300, 8, fill=1, stroke=0)
            c.setFillColor(cores[i]); c.rect(margem + 40, y - 1, 300 * (_numero(linha["f1_individuos"]) or 0), 8, fill=1, stroke=0)
            texto(_valor(linha["f1_individuos"]), margem + 350, y, 9)
            y -= 15
        y -= 8
    y -= 4
    texto("Objetivos previstos no plano", margem, y, 11, True)
    y -= 18
    for quadro in dados["plano"]["quadros"]:
        y = paragrafo(f"{quadro['video_id']}/{quadro['quadro']}: {quadro['objetivo']}", y, 8)
    paragrafo("Abra comparacao.png nas pastas irmãs de cada configuração. Os CSVs, pares e pendentes permitem rastrear cada acerto e erro. Esta pequena amostra é intencional para inspeção e não estima o desempenho geral do algoritmo.", y, 8)
    c.save()
    return 2


def gerar_relatorio(pasta: Path) -> Path:
    """Cria novo PDF, sem alterar manifestos anteriores nem executar detectores."""
    import reportlab
    dados = carregar(pasta)
    inicio = agora()
    destino = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not destino.is_relative_to(dados["pasta"]):
        raise ValueError("Pasta do relatório fora da inspeção.")
    destino.mkdir(parents=True, exist_ok=False)
    pdf = destino / "relatorio.pdf"
    registro = {"versao": 1, "tipo": "inspecao_blobs", "situacao": "em_andamento",
                "inicio_utc": inicio.isoformat(), "origens_sha256": dados["hashes"],
                "criterios": CRITERIOS, "dependencias": {"python": platform.python_version(), "reportlab": reportlab.Version},
                "codigo_relatorio_sha256": sha256(Path(__file__).read_bytes()),
                "ordem": dados["ids"], "ordenacao": "Ordem do plano, sem ranking.",
                "escopo_integridade": "Manifesto, plano e dois resumos. Sem releitura dos dados originais, PNGs ou tabelas de caixas."}
    try:
        gravar_json(destino / "relatorio.json", registro)
        (destino / "execucao_origem.json").write_bytes(dados["manifesto_bytes"])
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
