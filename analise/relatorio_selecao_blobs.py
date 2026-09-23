"""PDF da seleção em imagens de blobs, gerado exclusivamente de resultados salvos."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
import math
from pathlib import Path
import platform
from statistics import median

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import CONTAGENS, _conferir_metricas, _csv, _inteiro, _json, _numero
from analise.relatorio_rodada_blobs import _rotulo_configuracao, _valor
from scripts.blobs.arquivos import gravar_json
from scripts.limiarizacao.inspecionar_imagem import agora, sha256


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/blobs/selecao"
VIDEOS = ("13", "29", "52", "54")
METODOS = {"simpleblob": 84, "dog": 22, "log": 13}
NOMES = {"simpleblob": "SimpleBlob", "dog": "DoG", "log": "LoG"}
CORES = {"simpleblob": "#167d9a", "dog": "#b8642d", "log": "#7962a9"}
TEMPOS = ("preprocessamento", "detector", "adaptacao", "pipeline")
FONTES_RELATORIO = (
    "analise/relatorio_selecao_blobs.py", "analise/relatorio_inspecao_blobs.py",
    "analise/relatorio_rodada_blobs.py", "analise/avaliacao_individuos.py",
    "scripts/blobs/arquivos.py", "scripts/limiarizacao/inspecionar_imagem.py",
)


def _pontuacao(linha: dict) -> Fraction | None:
    tp, fp, fn = (_inteiro(linha[f"{c}_individuos"]) for c in ("tp", "fp", "fn"))
    return Fraction(2 * tp, 2 * tp + fp + fn) if 2 * tp + fp + fn else None


def _ranking(resumos: dict, ids: list[str]) -> list[dict]:
    """F1 exato; IDs ordenam apenas a apresentação de empates, sem desempatá-los."""
    ordem = sorted(ids, key=lambda i: (_pontuacao(resumos[i]) is None,
                                     -(_pontuacao(resumos[i]) or 0), i))
    anterior, posto = object(), None
    linhas = []
    for numero, ident in enumerate(ordem, 1):
        valor = _pontuacao(resumos[ident])
        if valor is None:
            posto = None
        elif valor != anterior:
            posto = numero
        linhas.append({"posicao": "" if posto is None else str(posto), **resumos[ident]})
        anterior = valor
    return linhas


def _limite_cinco(ranking: list[dict]) -> dict:
    definidos = [x for x in ranking if _pontuacao(x) is not None]
    if len(definidos) < 5:
        return {"situacao": "menos_de_cinco_definidos", "empate": False, "ids_empatados": []}
    quinto = _pontuacao(definidos[4])
    empate = len(definidos) > 5 and quinto == _pontuacao(definidos[5])
    return {"situacao": "empate_no_limite" if empate else "sem_empate_no_limite",
            "empate": empate,
            "ids_empatados": [x["configuracao_id"] for x in definidos if _pontuacao(x) == quinto] if empate else []}


def carregar(pasta: Path) -> dict:
    """Confere fontes, contagens e ranking; não abre imagens nem executa detectores."""
    pasta = Path(pasta).expanduser().resolve(strict=True)
    raiz = RAIZ.resolve()
    if (not SAIDA.resolve().is_relative_to(raiz) or pasta.parent != SAIDA.resolve()
            or not pasta.name.startswith("batch__") or not pasta.is_dir()):
        raise ValueError("Informe uma pasta batch__... diretamente em blobs/selecao.")
    hashes = {}

    def ler(nome: str) -> bytes:
        caminho = (pasta / nome).resolve(strict=True)
        if not caminho.is_relative_to(pasta) or not caminho.is_file():
            raise ValueError("Fonte do relatório fora da pasta do batch.")
        conteudo = caminho.read_bytes()
        hashes[caminho.relative_to(raiz).as_posix()] = sha256(conteudo)
        return conteudo

    manifesto_bytes = ler("execucao.json")
    manifesto = _json(manifesto_bytes)
    esperados = {"versao": 1, "tipo": "selecao_blobs", "situacao": "concluida",
                 "algoritmo": "blobs", "etapa": "selecao_imagens", "rodada": "selecao",
                 "particao": "selecao", "criterios": CRITERIOS,
                 "configuracoes_previstas": 119, "configuracoes_concluidas": 119,
                 "quadros_por_configuracao": 60, "avaliacoes_concluidas": 7140}
    if any(manifesto.get(k) != v or type(manifesto.get(k)) is not type(v) for k, v in esperados.items()):
        raise ValueError("Manifesto não descreve uma seleção completa de 119 x 60 avaliações.")
    plano_bytes = ler("plano.json")
    if sha256(plano_bytes) != manifesto.get("plano_sha256"):
        raise ValueError("Hash do plano salvo divergente.")
    plano = _json(plano_bytes)
    for campo in ("versao", "algoritmo", "etapa", "rodada", "particao", "criterios"):
        if plano.get(campo) != esperados[campo] or type(plano.get(campo)) is not type(esperados[campo]):
            raise ValueError("Plano salvo incompatível com a seleção em imagens.")
    configs = plano.get("configuracoes", [])
    ids = [x.get("id") for x in configs]
    if ids != [f"s{i:03d}" for i in range(1, 120)]:
        raise ValueError("A seleção exige 119 configurações identificadas de s001 a s119.")
    if Counter(x.get("metodo") for x in configs) != METODOS:
        raise ValueError("Composição de métodos incompatível: 84 SimpleBlob, 22 DoG, 13 LoG.")
    for item in configs:
        if (set(item) != {"id", "bloco", "perfil_forma", "referencia", "metodo", "preprocessamento", "parametros", "caixa"}
                or not isinstance(item["perfil_forma"], str)
                or item["bloco"] not in ("controle", "exploracao")
                or item["parametros"].get("polaridade") not in ("claro", "escuro")
                or item["caixa"].get("modo") not in ("original", "escala", "margem")):
            raise ValueError("Identificação ou parâmetros da configuração incompatíveis.")
        pre = item["preprocessamento"]
        if pre == {"metodo": "nenhum"}:
            continue
        if (not isinstance(pre, dict) or set(pre) != {"metodo", "limite_contraste", "grade"}
                or pre["metodo"] != "clahe" or type(pre["limite_contraste"]) not in (int, float)
                or not math.isfinite(pre["limite_contraste"]) or pre["limite_contraste"] <= 0
                or not isinstance(pre["grade"], list) or len(pre["grade"]) != 2
                or any(type(v) is not int or v < 1 for v in pre["grade"])):
            raise ValueError("Pré-processamento inválido.")
    quadros = [(x["video_id"], x["quadro"]) for x in plano.get("quadros", [])]
    if (len(quadros) != 60 or set(quadros) != {(v, q) for v in VIDEOS for q in range(0, 1401, 100)}
            or any(type(x["quadro"]) is not int for x in plano["quadros"])):
        raise ValueError("Composição dos 60 quadros de seleção incompatível.")
    for quadro in plano["quadros"]:
        if Path(quadro["imagem"]).suffix.lower() not in (".jpg", ".jpeg"):
            raise ValueError("A seleção deve usar os JPEGs anotados, sem extração de novos quadros.")
        for tipo in ("imagem", "anotacao"):
            if manifesto.get("origens_sha256", {}).get(quadro[tipo]) != quadro[f"{tipo}_sha256"]:
                raise ValueError("Hash de origem do quadro divergente do plano.")
    _conferir_origens(plano, manifesto, ler)
    tabelas = {}
    for nome in ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv", "ranking.csv"):
        conteudo = ler(nome)
        chave = (pasta / nome).relative_to(raiz).as_posix()
        if manifesto.get("saidas_sha256", {}).get(chave) != sha256(conteudo):
            raise ValueError(f"Hash divergente em {nome}.")
        tabelas[nome] = _csv(conteudo)
    resumos, linhas, videos = (tabelas[x] for x in ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv"))
    por_id = {x["configuracao_id"]: x for x in resumos}
    por_video = {(x["configuracao_id"], x["video_id"]): x for x in videos}
    por_quadro = {(x["configuracao_id"], x["video_id"], _inteiro(x["quadro"])): x for x in linhas}
    if len(resumos) != 119 or set(por_id) != set(ids):
        raise ValueError("Resumo de configurações incompleto ou repetido.")
    if len(linhas) != 7140 or set(por_quadro) != {(i, v, q) for i in ids for v, q in quadros}:
        raise ValueError("Resumo por quadro incompleto, repetido ou fora do plano.")
    if len(videos) != 476 or set(por_video) != {(i, v) for i in ids for v in VIDEOS}:
        raise ValueError("Resumo por vídeo incompleto, repetido ou fora do plano.")
    for linha in [*resumos, *linhas, *videos]:
        _conferir_metricas(linha)
    mapa_quadro = {(x["video_id"], x["quadro"]): x for x in plano["quadros"]}
    for linha in linhas:
        q = mapa_quadro[linha["video_id"], _inteiro(linha["quadro"])]
        if any(linha[c] != q[c] for c in ("imagem", "anotacao")):
            raise ValueError("Origem do quadro divergente do plano salvo.")
        origem = por_id[linha["configuracao_id"]]["pasta_origem"]
        pasta_quadro = f"{origem}/quadros/{q['video_id']}_frame_{q['quadro']}"
        if linha["pasta_quadro"] != pasta_quadro:
            raise ValueError("Pasta de origem divergente entre resumos.")
        if _inteiro(linha["quantidade_anotacoes"]) != sum(_inteiro(linha[f"anotacoes_classe_{c}"]) for c in (0, 1, 2)):
            raise ValueError("Total de anotações inconsistente.")
        if _inteiro(linha["quantidade_deteccoes"]) != sum(_inteiro(linha[f"{c}_{g}"]) for c in ("tp", "fp") for g in ("individuos", "aglomerados")):
            raise ValueError("Total de detecções inconsistente.")
        ns = {t: _inteiro(linha[f"tempo_{t}_ns"]) for t in TEMPOS}
        if ns["pipeline"] != ns["preprocessamento"] + ns["detector"] + ns["adaptacao"]:
            raise ValueError("Tempo de pipeline incompatível com suas etapas.")

    def agregado(total, grupo):
        if _inteiro(total["quantidade_quadros"]) != len(grupo):
            raise ValueError("Quantidade de quadros incompatível no agregado.")
        for campo in CONTAGENS:
            if _inteiro(total[campo]) != sum(_inteiro(x[campo]) for x in grupo):
                raise ValueError(f"Agregação inconsistente: {campo}.")
        for t in TEMPOS:
            if _inteiro(total[f"tempo_{t}_total_ns"]) != sum(_inteiro(x[f"tempo_{t}_ns"]) for x in grupo):
                raise ValueError(f"Agregação de tempo inconsistente: {t}.")

    for item in configs:
        ident = item["id"]
        total = por_id[ident]
        if (any(total[c] != item[c] for c in ("bloco", "perfil_forma"))
                or total["modo_caixa"] != item["caixa"]["modo"]):
            raise ValueError("Metadados da configuração divergem do plano.")
        grupo = [por_quadro[ident, v, q] for v, q in quadros]
        agregado(total, grupo)
        for v in VIDEOS:
            agregado(por_video[ident, v], [x for x in grupo if x["video_id"] == v])
    for v, q in quadros:
        for classe in (0, 1, 2):
            if len({por_quadro[i, v, q][f"anotacoes_classe_{classe}"] for i in ids}) != 1:
                raise ValueError("Anotações diferentes entre configurações no mesmo quadro.")
    ranking = _ranking(por_id, ids)
    if tabelas["ranking.csv"] != ranking:
        raise ValueError("Ranking não corresponde às contagens, posições e empates exatos.")
    return {"pasta": pasta, "manifesto": manifesto, "manifesto_bytes": manifesto_bytes,
            "plano": plano, "plano_bytes": plano_bytes, "ids": ids, "quadros": quadros,
            "resumos": por_id, "linhas": linhas, "por_video": por_video,
            "ranking": ranking, "limite_cinco": _limite_cinco(ranking), "hashes": hashes}


def _conferir_origens(plano, manifesto, ler):
    """Confere cópias dos planos de origem; o executor verifica os JPEGs originais."""
    fontes = plano.get("origens_rodadas", [])
    rodadas = [f"round{i}" for i in range(1, 6)]
    if len(fontes) != 5 or [x.get("rodada") for x in fontes] != rodadas:
        raise ValueError("A seleção exige as cinco rodadas de origem em ordem.")
    origens_hash = manifesto.get("origens_sha256", {})
    saidas_hash = manifesto.get("saidas_sha256", {})
    if manifesto["plano_sha256"] not in origens_hash.values():
        raise ValueError("Hash do plano original ausente das origens do manifesto.")

    def conferir(nome, caminho_original, esperado):
        blob = ler(nome + ".json")
        if (origens_hash.get(caminho_original) != esperado or sha256(blob) != esperado
                or not any(k.endswith("/" + nome + ".json") and v == esperado for k, v in saidas_hash.items())):
            raise ValueError(f"Hash divergente na cópia de origem: {nome}.")
        return _json(blob)

    origem_quadros = plano["origem_quadros"]
    quadros_anteriores = conferir("origem_quadros", origem_quadros["plano"], origem_quadros["sha256"])
    # O plano antigo de limiarização tem hash_nome; a seleção usa nome_sha256.
    anteriores = [{"video_id": str(x["video_id"]), "quadro": x["quadro"],
                   "imagem": x["imagem"], "anotacao": x["anotacao"],
                   "imagem_sha256": x.get("imagem_sha256", x.get("sha256_imagem")),
                   "anotacao_sha256": x.get("anotacao_sha256", x.get("sha256_anotacao"))}
                  for x in quadros_anteriores.get("quadros", [])]
    atuais = [{k: x[k] for k in anteriores[0]} for x in plano["quadros"]] if anteriores else []
    if anteriores != atuais:
        raise ValueError("Os JPEGs ou anotações diferem da origem de seleção acordada.")
    planos, manifestos = {}, {}
    for fonte, n in zip(fontes, (48, 32, 24, 18, 14)):
        rodada = fonte["rodada"]
        anterior = conferir("origem_" + rodada, fonte["plano"], fonte["plano_sha256"])
        execucao = conferir("execucao_" + rodada, fonte["batch"] + "/execucao.json", fonte["manifesto_sha256"])
        if (anterior.get("rodada") != rodada or anterior.get("particao") != "desenvolvimento"
                or len(anterior.get("configuracoes", [])) != n
                or execucao.get("situacao") != "concluida" or execucao.get("rodada") != rodada
                or execucao.get("criterios") != CRITERIOS or execucao.get("plano_sha256") != fonte["plano_sha256"]
                or execucao.get("configuracoes_concluidas") != n
                or execucao.get("quadros_por_configuracao") != 178 or execucao.get("avaliacoes_concluidas") != n * 178):
            raise ValueError("Plano/manifesto da rodada de origem incompatível.")
        planos[rodada], manifestos[rodada] = anterior, execucao
    for campo in ("origem_desenvolvimento", "origem_inspecao"):
        ref = planos["round1"][campo]
        conferir(campo, ref["plano"], ref["sha256"])
    proveniencia = plano.get("proveniencia", {})
    if set(proveniencia) != {x["id"] for x in plano["configuracoes"]}:
        raise ValueError("Proveniência incompleta para as 119 configurações.")
    identidades, aliases = set(), set()
    for item in plano["configuracoes"]:
        origem = proveniencia[item["id"]]
        digest = origem.get("configuracao_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or digest in identidades:
            raise ValueError("Identidades de configuração inválidas ou repetidas.")
        identidades.add(digest)
        lista = origem.get("origens", [])
        if not lista or origem.get("primeira_origem") != {k: lista[0][k] for k in ("rodada", "configuracao_id")}:
            raise ValueError("Primeira origem incompatível com a proveniência.")
        primeira = lista[0]
        candidatos = [x for x in planos[primeira["rodada"]]["configuracoes"] if x["id"] == primeira["configuracao_id"]]
        if len(candidatos) != 1:
            raise ValueError("Configuração original ausente do plano de desenvolvimento.")
        original = {**candidatos[0], "id": item["id"],
                    "metodo": candidatos[0].get("metodo", "simpleblob"),
                    "preprocessamento": candidatos[0].get("preprocessamento", {"metodo": "nenhum"})}
        if original != item:
            raise ValueError("Configuração de seleção alterada em relação à primeira origem.")
        for alias in lista:
            chave = alias["rodada"], alias["configuracao_id"]
            if chave in aliases or chave[0] not in rodadas:
                raise ValueError("Alias de desenvolvimento repetido ou desconhecido.")
            aliases.add(chave)
            m = manifestos[chave[0]]
            registros = [x for x in m.get("execucoes", []) if x["configuracao_id"] == chave[1]]
            if len(registros) != 1 or registros[0]["pasta"] != alias["pasta_execucao"]:
                raise ValueError("Pasta da execução de origem divergente do manifesto.")
            for arquivo, campo in (("configuracao.json", "sha256_arquivo_configuracao"),
                                   ("execucao.json", "sha256_manifesto_execucao")):
                if m.get("saidas_sha256", {}).get(alias["pasta_execucao"] + "/" + arquivo) != alias[campo]:
                    raise ValueError("Hash da configuração/execução original incompatível.")
    esperados = {(f"round{i}", f"r{i}c{j:02d}") for i, n in enumerate((48, 32, 24, 18, 14), 1) for j in range(1, n + 1)}
    if aliases != esperados:
        raise ValueError("A proveniência não cobre exatamente as 136 execuções de desenvolvimento.")


def _aviso_limite(dados):
    limite = dados["limite_cinco"]
    if limite["empate"]:
        return ("EMPATE NO LIMITE DE CINCO: " + ", ".join(limite["ids_empatados"])
                + ". Revisão conjunta necessária; o ID não desempata nem promove finalistas.")
    if limite["situacao"] == "menos_de_cinco_definidos":
        return "MENOS DE CINCO F1 DEFINIDOS: não há cinco resultados classificáveis. Sem casos não recebe posição."
    return "Sem empate exato no limite de cinco. A lista orienta a revisão conjunta; nenhuma configuração foi promovida automaticamente."


def escrever_pdf(caminho: Path, dados: dict) -> int:
    """Sete páginas vetoriais; todas as configurações mantêm espaço legível."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.utils import simpleSplit

    largura, altura = landscape(A4)
    c = Canvas(str(caminho), pagesize=(largura, altura))
    c.setTitle("Blobs - seleção em imagens")
    c.setAuthor("Pesquisa de detecção de espermatozoides")
    margem, util = 32, largura - 64
    configs = {x["id"]: x for x in dados["plano"]["configuracoes"]}
    ranking = dados["ranking"]
    ordem = [x["configuracao_id"] for x in ranking]
    blocos = [ordem[i:i + 40] for i in range(0, 119, 40)]
    postos = {x["configuracao_id"]: x["posicao"] for x in ranking}

    def texto(valor, x, y, tam=9, bold=False, cor="#253b4b"):
        c.setFillColor(HexColor(cor)); c.setFont("Helvetica-Bold" if bold else "Helvetica", tam)
        c.drawString(x, y, str(valor))

    def paragrafo(valor, x, y, w=util, tam=8.5):
        for linha in simpleSplit(valor, "Helvetica", tam, w):
            texto(linha, x, y, tam); y -= tam + 3
        return y - 5

    def cabecalho(titulo, subtitulo, pagina):
        c.setFillColor(HexColor("#f2f6f8")); c.rect(0, altura - 87, largura, 87, fill=1, stroke=0)
        texto("BLOBS  |  SELEÇÃO EM IMAGENS", margem, altura - 26, 10, True, "#167d9a")
        texto(titulo, margem, altura - 50, 20, True)
        texto(subtitulo, margem, altura - 70, 8.5)
        texto(f"Seleção | 119 configurações | 60 quadros | plano {dados['manifesto']['plano_sha256'][:12]}", margem, 21, 7.2)
        texto(f"{pagina}/7", largura - 52, 21, 8)

    def fim():
        c.showPage()

    cabecalho("Comparação para revisão conjunta", "84 SimpleBlob + 22 DoG + 13 LoG | vídeos 13, 29, 52 e 54 | 7.140 avaliações", 1)
    y = paragrafo(_aviso_limite(dados), margem, 490, tam=9)
    texto("Precisão e recall de indivíduos", margem, y - 8, 12, True)
    x0, y0, w, h = margem + 29, 176, 319, 236
    # Mantém o gráfico abaixo do aviso inclusive quando muitos IDs empatam.
    h = min(h, y - 49 - y0)
    c.setStrokeColor(HexColor("#cad8e0")); c.setLineWidth(0.5)
    for k in range(6):
        f = k / 5
        c.line(x0 + f * w, y0, x0 + f * w, y0 + h)
        c.line(x0, y0 + f * h, x0 + w, y0 + f * h)
        texto(f"{f:.1f}".replace(".", ","), x0 + f * w - 6, y0 - 14, 7)
        texto(f"{f:.1f}".replace(".", ","), x0 - 22, y0 + f * h - 2, 7)
    texto("Recall", x0 + w / 2 - 15, y0 - 29, 8)
    texto("Precisão", x0, y0 + h + 9, 8)
    omitidos = 0
    for ident in ordem:
        linha = dados["resumos"][ident]
        p, r = _numero(linha["precisao_individuos"]), _numero(linha["recall_individuos"])
        if p is None or r is None:
            omitidos += 1; continue
        c.setFillColor(HexColor(CORES[configs[ident]["metodo"]]))
        c.circle(x0 + r * w, y0 + p * h, 2.5, fill=1, stroke=0)
    x, yy = 432, y - 8
    texto("F1 por método: descrição da amostra", x, yy, 11, True); yy -= 23
    for metodo in METODOS:
        valores = [float(_pontuacao(dados["resumos"][i])) for i in ordem
                   if configs[i]["metodo"] == metodo and _pontuacao(dados["resumos"][i]) is not None]
        texto(f"{NOMES[metodo]} ({METODOS[metodo]} configurações)", x, yy, 10, True, CORES[metodo]); yy -= 16
        if valores:
            descricao = f"Mediana {_valor(median(valores))} | mínimo {_valor(min(valores))} | máximo {_valor(max(valores))}"
        else:
            descricao = "Todos os F1 estão sem casos."
        yy = paragrafo(descricao, x, yy, 374, 8)
    yy = paragrafo("Amostras desiguais e configurações escolhidas durante o desenvolvimento: os resumos por método não demonstram superioridade estatística. Pontos sobrepostos podem representar mais de uma configuração.", x, yy - 2, 374, 8)
    texto(f"Pontos omitidos por precisão/recall sem casos: {omitidos}.", x, yy - 2, 8)
    y = 119
    for frase in (
        "Métrica principal: F1 de indivíduos (0 e 2 juntos), calculado de TP, FP e FN somados nos 60 quadros. Aglomerados (1) são avaliados separadamente.",
        "Empates usam a fração exata 2TP/(2TP+FP+FN), sem pesos ou desempate pela classe 0. Posição igual indica empate; ID só organiza a apresentação.",
        "Quadros do mesmo vídeo são relacionados. Este PDF é descritivo, sem intervalos de confiança ou testes de hipótese. A seleção em imagens antecede os testes em vídeo.",
    ):
        y = paragrafo(frase, margem, y, tam=8)
    fim()

    for indice_bloco, ids in enumerate(blocos):
        pagina = 2 + indice_bloco
        inicio = indice_bloco * 40 + 1
        cabecalho(f"Ranking completo | linhas {inicio} a {inicio + len(ids) - 1}",
                  "Barra = F1 | P = precisão | R = recall | indivíduos 0/2 | ordem exata, valores impressos com 3 casas", pagina)
        for coluna in range(2):
            x = margem + coluna * 396
            texto("Posto / configuração", x, 485, 8, True)
            texto("F1", x + 273, 485, 8, True); texto("P", x + 315, 485, 8, True); texto("R", x + 352, 485, 8, True)
            for j, ident in enumerate(ids[coluna * 20:(coluna + 1) * 20]):
                y = 463 - j * 18
                linha, item = dados["resumos"][ident], configs[ident]
                if j % 2 == 0:
                    c.setFillColor(HexColor("#f3f6f8")); c.rect(x - 3, y - 5, 380, 17, fill=1, stroke=0)
                texto((postos[ident] or "-") + "  " + _rotulo_configuracao(item), x, y, 7.5)
                valor = _pontuacao(linha)
                if valor is not None:
                    c.setFillColor(HexColor("#dbe5e9")); c.rect(x + 151, y - 1, 109, 6, fill=1, stroke=0)
                    c.setFillColor(HexColor(CORES[item["metodo"]])); c.rect(x + 151, y - 1, 109 * float(valor), 6, fill=1, stroke=0)
                for campo, dx in (("f1_individuos", 270), ("precisao_individuos", 309), ("recall_individuos", 347)):
                    texto(_valor(linha[campo]) if linha[campo] != "" else "s/c", x + dx, y, 7.5)
        y = paragrafo("SB = SimpleBlob; +H = CLAHE; C/E = objetos claros/escuros; O = caixa original; S = fator de escala; M = margem em pixels por lado. Cores distinguem métodos. Parâmetros completos e referências históricas: plano.json.", margem, 87, tam=8)
        paragrafo("s/c = sem casos, nunca zero. Posições repetidas são empates exatos; diferenças aparentes escondidas pelo arredondamento continuam distintas. Todas as 119 configurações constam neste ranking, sem promoção automática.", margem, y, tam=8)
        fim()

    for indice_bloco, ids in enumerate(blocos):
        pagina = 5 + indice_bloco
        inicio = indice_bloco * 40 + 1
        cabecalho(f"Diagnóstico completo | linhas {inicio} a {inicio + len(ids) - 1}",
                  "Cobertura = anotados localizados / anotados | erro 0/2 = classificação errada entre pares localizados | valores em 0 a 1", pagina)
        campos = [("ID / método", 0), ("TP", 89), ("FP", 119), ("FN", 152),
                  ("Cob. 0", 186), ("Cob. 2", 226), ("Cob. 1", 266), ("F1 agl.", 307),
                  ("Erro 0/2 / pares", 353), ("Ac. cond.", 443),
                  ("V13", 507), ("V29", 568), ("V52", 629), ("V54", 690)]
        for titulo, dx in campos:
            texto(titulo, margem + dx, 485, 7.5, True)
        for j, ident in enumerate(ids):
            y = 468 - j * 8.8
            linha, item = dados["resumos"][ident], configs[ident]
            if j % 2 == 0:
                c.setFillColor(HexColor("#f3f6f8")); c.rect(margem - 2, y - 2, util + 2, 8.8, fill=1, stroke=0)
            metodo = {"simpleblob": "SB", "dog": "DoG", "log": "LoG"}[item["metodo"]]
            valores = [f"{ident} {metodo}", *[linha[f"{v}_individuos"] for v in ("tp", "fp", "fn")],
                       *[_valor(linha[f"recall_classe_{v}"]) if linha[f"recall_classe_{v}"] else "s/c" for v in (0, 2, 1)],
                       _valor(linha["f1_aglomerados"]) if linha["f1_aglomerados"] else "s/c",
                       f"{linha['pares_incorretos']} / {linha['pares_total']}",
                       _valor(linha["acuracia_condicional"]) if linha["acuracia_condicional"] else "s/c"]
            for valor, (_, dx) in zip(valores, campos):
                texto(valor, margem + dx, y, 7)
            for k, video in enumerate(VIDEOS):
                v = _numero(dados["por_video"][ident, video]["f1_individuos"])
                x = margem + 500 + k * 61
                if v is not None:
                    c.setFillColor(Color(0.96 - 0.75 * v, 0.98 - 0.32 * v, 0.99 - 0.21 * v))
                    c.rect(x, y - 2, 57, 8.8, fill=1, stroke=0)
                texto("s/c" if v is None else _valor(v), x + 7, y, 7)
        y = 100
        for frase in (
            "V13/V29/V52/V54: F1 de indivíduos em 15 quadros de cada vídeo; cor mais intensa = F1 maior, escala fixa 0 a 1. Consulte o CSV para suportes e tempos.",
            "Ac. cond. mede somente a classe dos indivíduos já localizados. Troca 0/2 não desfaz esse acerto. Mover previsão entre indivíduo e aglomerado pode alterar TP/FP/FN mesmo sem mudar a caixa.",
            "Uma margem maior não muda a medida bruta nem a classe. No DoG, a grade de escalas pode impedir previsões de aglomerados; confira cobertura/F1 da classe 1 e os parâmetros antes de interpretar ausência como acerto.",
            "Fontes conferidas: manifesto, plano e suas origens salvas, três resumos e ranking. Sem releitura de JPEGs, tabelas de caixas ou execução de detectores. Nenhuma anotação foi alterada.",
        ):
            y = paragrafo(frase, margem, y, tam=7.8)
        fim()
    c.save()
    return 7


def gerar_relatorio(pasta: Path) -> Path:
    """Gera uma nova versão, preservando métricas, manifesto e PDFs anteriores."""
    import reportlab
    dados = carregar(pasta)
    inicio = agora()
    destino = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not destino.is_relative_to(dados["pasta"]):
        raise ValueError("Pasta do relatório fora do batch.")
    destino.mkdir(parents=True, exist_ok=False)
    pdf = destino / "relatorio.pdf"
    registro = {"versao": 1, "tipo": "selecao_blobs", "rodada": "selecao", "situacao": "em_andamento",
                "inicio_utc": inicio.isoformat(), "origens_sha256": dados["hashes"], "criterios": CRITERIOS,
                "dependencias": {"python": platform.python_version(), "reportlab": reportlab.Version},
                "codigo_relatorio_sha256": {nome: sha256((Path(__file__).resolve().parents[1] / nome).read_bytes())
                                            for nome in FONTES_RELATORIO},
                "ordem": [x["configuracao_id"] for x in dados["ranking"]],
                "limite_cinco": dados["limite_cinco"], "selecao_automatica": False,
                "ordenacao": "F1 exato das contagens decrescente; empates mantêm posição; ID só organiza apresentação; sem desempate pela classe 0.",
                "escopo_integridade": "Manifesto, plano, cópias das origens, três resumos e ranking; contagens e agregações. Não relê base, tabelas de detecções ou PNGs."}
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
