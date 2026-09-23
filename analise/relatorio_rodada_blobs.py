"""Relatório descritivo de rodadas de blobs, usando somente fontes salvas."""

from __future__ import annotations

from pathlib import Path
import platform
import math
from statistics import mean, median, stdev

from analise.avaliacao_individuos import CRITERIOS
from analise.relatorio_inspecao_blobs import (
    CONTAGENS, _conferir_metricas, _csv, _inteiro, _json, _numero,
)
from scripts.limiarizacao.inspecionar_imagem import agora, sha256
from scripts.blobs.arquivos import gravar_json


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados/frame-to-frame/blobs"
ORCAMENTO = {"round1": 48, "round2": 32, "round3": 24, "round4": 18, "round5": 14}
VIDEOS = ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60")
TEMPOS = ("detector", "adaptacao", "pipeline")


def carregar(pasta: Path) -> dict:
    """Valida plano, hashes e agregações; não abre imagens nem roda detectores."""
    pasta = Path(pasta).expanduser().resolve(strict=True)
    rodada = pasta.parent.name
    if (not SAIDA.resolve().is_relative_to(RAIZ.resolve())
            or rodada not in ORCAMENTO or pasta.parent.parent != SAIDA.resolve()
            or not pasta.name.startswith("batch__") or not pasta.is_dir()):
        raise ValueError("Informe uma pasta batch__... dentro de blobs/round1 a round5.")
    hashes = {}

    def ler(nome):
        caminho = (pasta / nome).resolve(strict=True)
        if not caminho.is_relative_to(pasta) or not caminho.is_file():
            raise ValueError("Fonte do relatório fora da pasta do batch.")
        conteudo = caminho.read_bytes()
        hashes[caminho.relative_to(RAIZ.resolve()).as_posix()] = sha256(conteudo)
        return conteudo

    manifesto_bytes = ler("execucao.json")
    manifesto = _json(manifesto_bytes)
    n = ORCAMENTO[rodada]
    versao = manifesto.get("versao")
    if type(versao) is not int or versao not in (1, 2, 3, 4, 5):
        raise ValueError("Manifesto com versão incompatível.")
    if versao in (3, 4, 5) and rodada != f"round{versao}":
        raise ValueError(f"O esquema v{versao} descreve o desenho experimental do round{versao}.")
    esperados = {"versao": versao, "situacao": "concluida", "tipo": "rodada_blobs",
                 "algoritmo": "blobs", "etapa": "desenvolvimento", "rodada": rodada,
                 "particao": "desenvolvimento", "criterios": CRITERIOS,
                 "configuracoes_previstas": n, "configuracoes_concluidas": n,
                 "quadros_por_configuracao": 178}
    if any(manifesto.get(k) != v or type(manifesto.get(k)) is not type(v)
           for k, v in esperados.items()):
        raise ValueError("Manifesto não descreve uma rodada concluída e compatível.")
    plano_bytes = ler("plano.json")
    if sha256(plano_bytes) != manifesto.get("plano_sha256"):
        raise ValueError("Hash do plano salvo divergente.")
    plano = _json(plano_bytes)
    for campo in ("versao", "algoritmo", "etapa", "rodada", "particao"):
        if plano.get(campo) != esperados[campo] or type(plano.get(campo)) is not type(esperados[campo]):
            raise ValueError("Plano salvo incompatível com a rodada.")
    configuracoes = plano.get("configuracoes", [])
    ids = [x["id"] for x in configuracoes]
    esperados_quadros = {(v, q) for v in VIDEOS for q in range(0, 1401, 100)} - {("23", 900), ("23", 1100)}
    quadros = [(x["video_id"], x["quadro"]) for x in plano.get("quadros", [])]
    if (len(ids) != n or len(set(ids)) != n or len(quadros) != 178
            or set(quadros) != esperados_quadros
            or any(type(x["quadro"]) is not int for x in plano["quadros"])):
        raise ValueError("Composição de configurações/178 quadros incompatível.")
    for item in configuracoes:
        if (item.get("bloco") not in ("controle", "exploracao")
                or item.get("caixa", {}).get("modo") not in ("original", "escala", "margem")
                or not isinstance(item.get("perfil_forma"), str)):
            raise ValueError("Identificação de bloco, caixa ou perfil inválida no plano salvo.")
        metodo = item.get("metodo", "simpleblob")
        pre = item.get("preprocessamento", {"metodo": "nenhum"})
        if (metodo not in ("simpleblob", "log", "dog")
                or not isinstance(pre, dict) or pre.get("metodo") not in ("nenhum", "clahe")
                or item.get("parametros", {}).get("polaridade") not in ("claro", "escuro")):
            raise ValueError("Método, pré-processamento ou polaridade incompatível.")
        if versao == 1 and (metodo != "simpleblob" or pre != {"metodo": "nenhum"}):
            raise ValueError("Plano legado não admite métodos ou pré-processamento novos.")
        if versao >= 2 and ("metodo" not in item or "preprocessamento" not in item):
            raise ValueError("Plano v2 a v5 exige método e pré-processamento explícitos.")
        if pre["metodo"] == "nenhum" and pre != {"metodo": "nenhum"}:
            raise ValueError("Pré-processamento nenhum contém parâmetros extras.")
        if pre["metodo"] == "clahe":
            limite = pre.get("limite_contraste")
            grade = pre.get("grade")
            if (set(pre) != {"metodo", "limite_contraste", "grade"}
                    or type(limite) not in (int, float) or not math.isfinite(limite) or limite <= 0
                    or not isinstance(grade, list) or len(grade) != 2
                    or any(type(x) is not int or x < 1 for x in grade)):
                raise ValueError("Parâmetros de CLAHE inválidos.")

    tabelas = {}
    for nome in ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv"):
        conteudo = ler(nome)
        chave = (pasta / nome).relative_to(RAIZ.resolve()).as_posix()
        if manifesto.get("saidas_sha256", {}).get(chave) != sha256(conteudo):
            raise ValueError(f"Hash divergente em {nome}.")
        tabelas[nome] = _csv(conteudo)
    resumos, linhas, videos = (tabelas[x] for x in
                              ("resumo_configuracoes.csv", "resumo_por_quadro.csv", "resumo_por_video.csv"))
    por_id = {x["configuracao_id"]: x for x in resumos}
    por_video = {(x["configuracao_id"], x["video_id"]): x for x in videos}
    por_quadro = {(x["configuracao_id"], x["video_id"], _inteiro(x["quadro"])): x for x in linhas}
    if len(resumos) != n or set(por_id) != set(ids):
        raise ValueError("Resumo não contém exatamente as configurações do plano.")
    if len(linhas) != n * 178 or set(por_quadro) != {(i, v, q) for i in ids for v, q in quadros}:
        raise ValueError("Resumo por quadro incompleto, repetido ou fora do plano.")
    if len(videos) != n * len(VIDEOS) or set(por_video) != {(i, v) for i in ids for v in VIDEOS}:
        raise ValueError("Resumo por vídeo incompleto, repetido ou fora do plano.")
    for linha in [*resumos, *linhas, *videos]:
        _conferir_metricas(linha)
    quadros_plano = {(x["video_id"], x["quadro"]): x for x in plano["quadros"]}
    for linha in linhas:
        referencia = quadros_plano[linha["video_id"], _inteiro(linha["quadro"])]
        if any(linha[c] != referencia[c] for c in ("imagem", "anotacao")):
            raise ValueError("Origem do quadro divergente do plano salvo.")
        if _inteiro(linha["quantidade_anotacoes"]) != sum(_inteiro(linha[f"anotacoes_classe_{c}"]) for c in (0, 1, 2)):
            raise ValueError("Total de anotações inconsistente.")
        if _inteiro(linha["quantidade_deteccoes"]) != sum(_inteiro(linha[f"{k}_{g}"]) for k in ("tp", "fp") for g in ("individuos", "aglomerados")):
            raise ValueError("Total de detecções inconsistente.")
        for tempo in TEMPOS:
            _inteiro(linha[f"tempo_{tempo}_ns"])
        if versao >= 2:
            pre_ns = _inteiro(linha["tempo_preprocessamento_ns"])
            if _inteiro(linha["tempo_pipeline_ns"]) != pre_ns + sum(
                    _inteiro(linha[f"tempo_{tempo}_ns"]) for tempo in ("detector", "adaptacao")):
                raise ValueError("Tempo de pipeline incompatível com suas etapas.")

    def conferir_agregado(agregado, grupo):
        if _inteiro(agregado["quantidade_quadros"]) != len(grupo):
            raise ValueError("Quantidade de quadros incompatível no agregado.")
        for campo in CONTAGENS:
            if _inteiro(agregado[campo]) != sum(_inteiro(x[campo]) for x in grupo):
                raise ValueError(f"Agregação inconsistente: {campo}.")
        for tempo in (*TEMPOS, "preprocessamento") if versao >= 2 else TEMPOS:
            if _inteiro(agregado[f"tempo_{tempo}_total_ns"]) != sum(_inteiro(x[f"tempo_{tempo}_ns"]) for x in grupo):
                raise ValueError(f"Agregação de tempo inconsistente: {tempo}.")

    for item in configuracoes:
        ident = item["id"]
        linha = por_id[ident]
        if any(linha[c] != item[c] for c in ("bloco", "perfil_forma")) or linha["modo_caixa"] != item["caixa"]["modo"]:
            raise ValueError("Identificação da configuração diverge do plano salvo.")
        grupo = [por_quadro[ident, v, q] for v, q in quadros]
        conferir_agregado(linha, grupo)
        for video in VIDEOS:
            conferir_agregado(por_video[ident, video], [x for x in grupo if x["video_id"] == video])
    for v, q in quadros:
        for classe in (0, 1, 2):
            if len({por_quadro[i, v, q][f"anotacoes_classe_{classe}"] for i in ids}) != 1:
                raise ValueError("Suporte de classe diverge entre configurações no mesmo quadro.")
    dados = {"pasta": pasta, "manifesto": manifesto, "manifesto_bytes": manifesto_bytes,
             "plano": plano, "plano_bytes": plano_bytes, "ids": ids, "quadros": quadros,
             "resumos": por_id, "linhas": linhas, "por_video": por_video, "hashes": hashes}
    if versao in (3, 4):
        _comparacoes_fatoriais(dados)
    elif versao == 5:
        _comparacoes_round5(dados)
    return dados


def _valor(texto, casas=3):
    return "sem casos" if texto in (None, "") else f"{float(texto):.{casas}f}".replace(".", ",")


def _caixa(item):
    caixa = item["caixa"]
    if caixa["modo"] == "original":
        return "original"
    campo = "fator" if caixa["modo"] == "escala" else "pixels"
    return f"{caixa['modo']} {caixa[campo]:g}" + (" px/lado" if campo == "pixels" else "x")


def _ordem_visual(dados):
    """F1 decrescente; a estabilidade mantém a ordem do plano nos empates."""
    return sorted(dados["ids"], key=lambda i: (
        _numero(dados["resumos"][i]["f1_individuos"]) is None,
        -(_numero(dados["resumos"][i]["f1_individuos"]) or 0)))


def _paginas(dados):
    ids = _ordem_visual(dados)
    return [("visao", ids), ("metricas", ids), ("videos", ids), ("controles", dados["ids"])]


def _rotulo_configuracao(item):
    metodo = {"simpleblob": "SB", "log": "LoG", "dog": "DoG"}[item.get("metodo", "simpleblob")]
    polaridade = "C" if item["parametros"]["polaridade"] == "claro" else "E"
    pre = "+H" if item.get("preprocessamento", {}).get("metodo") == "clahe" else ""
    caixa = item["caixa"]
    box = {"original": "O", "escala": f"S{caixa.get('fator', 0):g}",
           "margem": f"M{caixa.get('pixels', 0):g}"}[caixa["modo"]]
    return f"{item['id']} {metodo}{pre}/{polaridade}/{box}"


def _comparacoes_controle(dados):
    """Somente pares controlados dentro do batch, nunca inferências entre rodadas."""
    configs = dados["plano"]["configuracoes"]
    bases = {}
    for item in configs:
        if item["bloco"] != "controle":
            continue
        if dados["plano"]["versao"] == 1 and item["caixa"]["modo"] != "original":
            continue
        if item.get("preprocessamento", {"metodo": "nenhum"}) == {"metodo": "nenhum"}:
            bases.setdefault(item.get("referencia"), []).append(item)
    linhas = []
    for item in configs:
        candidatas = bases.get(item.get("referencia"), [])
        base = candidatas[0] if item.get("referencia") and len(candidatas) == 1 else None
        if base and (item["parametros"] != base["parametros"]
                     or item.get("metodo", "simpleblob") != base.get("metodo", "simpleblob")
                     or (dados["plano"]["versao"] == 2 and item["caixa"] != base["caixa"])):
            base = None
        if item["bloco"] == "controle" or base:
            valor = _numero(dados["resumos"][item["id"]]["f1_individuos"])
            original = _numero(dados["resumos"][base["id"]]["f1_individuos"]) if base else None
            delta = valor - original if valor is not None and original is not None else None
            linhas.append((item, base, delta))
    return linhas


def _comparacoes_fatoriais(dados):
    """Pares locais de margem; o par de classificação v5 é validado separadamente."""
    versao = dados["plano"]["versao"]
    if versao == 3:
        margens_previstas = {"simpleblob": (3, 4), "log": (4, 6), "dog": (4, 6)}
        fatores_previstos = {"simpleblob": {(a, d) for a in (32, 48, 64) for d in (6, 12)},
                             "log": {0.05, 0.08, 0.12}, "dog": {0.05, 0.08, 0.12}}
    elif versao == 4:
        margens_previstas = {"simpleblob": (2, 3), "log": (5, 6), "dog": (6, 8)}
        fatores_previstos = {"simpleblob": {(a, 6) for a in (48, 64, 80)},
                             "log": {0.08, 0.12}, "dog": {0.12, 0.16, 0.20, 0.24}}
    elif versao == 5:
        margens_previstas = {"simpleblob": (2, 3), "dog": (5, 6)}
        fatores_previstos = {"simpleblob": {(a, 6) for a in (56, 64, 72)},
                             "log": set(), "dog": {0.10, 0.12, 0.14}}
    else:
        raise ValueError("Comparações fatoriais disponíveis apenas para os rounds 3 a 5.")
    grupos = []
    for item in dados["plano"]["configuracoes"]:
        if versao == 5 and item["metodo"] == "log":
            continue
        if (item.get("preprocessamento") != {"metodo": "nenhum"}
                or item.get("caixa", {}).get("modo") != "margem"):
            raise ValueError("Desenho fatorial exige ausência de pré-processamento e caixas por margem.")
        grupo = next((g for g in grupos
                      if g[0]["metodo"] == item["metodo"]
                      and g[0]["parametros"] == item["parametros"]), None)
        if grupo is None:
            grupos.append([item])
        else:
            grupo.append(item)
    pares, fatores = [], {"simpleblob": set(), "log": set(), "dog": set()}
    for grupo in grupos:
        metodo = grupo[0]["metodo"]
        margens = [x["caixa"].get("pixels") for x in grupo]
        esperado = margens_previstas[metodo]
        if len(grupo) != 2 or sorted(margens) != list(esperado):
            raise ValueError("Par fatorial incompleto, repetido ou com outros parâmetros diferentes.")
        base, maior = sorted(grupo, key=lambda x: x["caixa"]["pixels"])
        p = base["parametros"]
        if metodo == "simpleblob":
            if "area_minima" not in p or "distancia_minima" not in p:
                raise ValueError("Fatores de área/distância ausentes no plano.")
            fator = (p["area_minima"], p["distancia_minima"])
            rotulo = f"SB | área mínima {fator[0]:g} | distância {fator[1]:g}"
        else:
            if "limiar_resposta" not in p:
                raise ValueError("Fator de resposta ausente no plano.")
            fator = p["limiar_resposta"]
            rotulo = f"{metodo.title() if metodo == 'log' else 'DoG'} | resposta {_valor(fator, 2)}"
            rotulo = rotulo.replace("Log", "LoG")
        if fator in fatores[metodo]:
            raise ValueError("Fator repetido com parâmetros de fundo diferentes.")
        fatores[metodo].add(fator)
        f1_base = _numero(dados["resumos"][base["id"]]["f1_individuos"])
        f1_maior = _numero(dados["resumos"][maior["id"]]["f1_individuos"])
        pares.append({"base": base, "maior": maior, "fatores": rotulo,
                      "f1_base": f1_base, "f1_maior": f1_maior,
                      "delta": None if f1_base is None or f1_maior is None else f1_maior - f1_base})
    if fatores != fatores_previstos:
        total_pares = sum(len(x) for x in fatores_previstos.values())
        raise ValueError(f"Fatores do round{versao} incompatíveis com os {total_pares} pares previstos.")
    return pares


def _comparacoes_round5(dados):
    """Seis pares de margem e um par que altera somente o limite de aglomerado."""
    pares = []
    for par in _comparacoes_fatoriais(dados):
        base, variante = par["base"], par["maior"]
        pares.append({**par, "tipo": "margem", "variante": variante,
                      "alteracao": f"margem {base['caixa']['pixels']:g} para {variante['caixa']['pixels']:g} px"})
    logs = [x for x in dados["plano"]["configuracoes"] if x["metodo"] == "log"]
    if len(logs) != 2:
        raise ValueError("Round5 exige um par LoG de classificação.")
    for item in logs:
        p = item["parametros"]
        cls = p.get("classificacao", {})
        limite = cls.get("area_minima_aglomerado")
        if (item["preprocessamento"] != {"metodo": "nenhum"}
                or item["caixa"] != {"modo": "margem", "pixels": 6}
                or p.get("limiar_resposta") != 0.12
                or set(cls) != {"area_maxima_pequeno", "area_minima_aglomerado"}
                or type(limite) not in (int, float) or not math.isfinite(limite)):
            raise ValueError("Par LoG de classificação incompatível com o round5.")
    base, variante = sorted(logs, key=lambda x: x["parametros"]["classificacao"]["area_minima_aglomerado"])

    def sem_limite(item):
        p = item["parametros"]
        return {**p, "classificacao": {k: v for k, v in p["classificacao"].items()
                                      if k != "area_minima_aglomerado"}}

    limites = [x["parametros"]["classificacao"]["area_minima_aglomerado"] for x in (base, variante)]
    if sem_limite(base) != sem_limite(variante) or limites != [math.pi * 12 ** 2, math.pi * 14 ** 2]:
        raise ValueError("Par de classificação deve alterar somente o limite de aglomerado de diâmetro 24 para 28.")
    f1_base = _numero(dados["resumos"][base["id"]]["f1_individuos"])
    f1_variante = _numero(dados["resumos"][variante["id"]]["f1_individuos"])
    pares.append({"base": base, "variante": variante, "tipo": "classificacao",
                  "fatores": "LoG | resposta 0,12 | caixa fixa", "alteracao": "diâmetro agl. 24 para 28 px",
                  "f1_base": f1_base, "f1_maior": f1_variante,
                  "delta": None if f1_base is None or f1_variante is None else f1_variante - f1_base})
    return pares


def escrever_pdf(caminho: Path, dados: dict) -> int:
    """Quatro páginas compactas; gráficos vetoriais e métricas atuais de indivíduos."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.utils import simpleSplit

    largura, altura = landscape(A4)
    margem, util, painel = 32, largura - 64, (largura - 84) / 2
    c = Canvas(str(caminho), pagesize=(largura, altura))
    c.setTitle(f"Blobs - {dados['plano']['rodada']} - desenvolvimento")
    c.setAuthor("Projeto de detecção em microscopia")
    c.setCreator("Relatório de rodadas")
    configs = {x["id"]: x for x in dados["plano"]["configuracoes"]}
    paginas = _paginas(dados)
    fatorial = dados["plano"]["versao"] in (3, 4, 5)
    rodada5 = dados["plano"]["versao"] == 5
    por_coluna = len(dados["ids"]) // 2 if fatorial else 24
    passo_barras = 268.4 / (por_coluna - 1) if fatorial else 12.2
    passo_metricas = 286 / (por_coluna - 1) if fatorial else 13
    passo_videos = 308 / (por_coluna - 1) if fatorial else 14
    cor_f1, cor_p, cor_r = "#197a82", "#2d4c88", "#bb7027"

    def texto(conteudo, x, y, tamanho=9, bold=False, cor="#253b4b"):
        c.setFillColor(HexColor(cor)); c.setFont("Helvetica-Bold" if bold else "Helvetica", tamanho)
        c.drawString(x, y, str(conteudo))

    def paragrafo(conteudo, y, tamanho=8.5, x=margem, limite=util):
        for linha in simpleSplit(conteudo, "Helvetica", tamanho, limite):
            texto(linha, x, y, tamanho); y -= tamanho + 4
        return y - 7

    def faixa(x, y, w):
        c.setFillColor(HexColor("#edf2f5")); c.rect(x, y - 5, w, 18, fill=1, stroke=0)

    def celula(valor, x, y, w, h, tamanho=7.2):
        v = _numero(valor)
        cor = HexColor("#e5e7e9") if v is None else Color(.96 - .78 * v, .98 - .51 * v, .98 - .44 * v)
        c.setFillColor(cor); c.rect(x, y - 3, w - 1.5, h, fill=1, stroke=0)
        rotulo = "SC" if v is None else _valor(v, 2)
        c.setFillColor(HexColor("#ffffff" if v is not None and v > .65 else "#253b4b"))
        c.setFont("Helvetica", tamanho); c.drawCentredString(x + (w - 1.5) / 2, y + .6, rotulo)

    def rodape():
        c.setStrokeColor(HexColor("#d5dee4")); c.line(margem, 35, largura - margem, 35)
        texto(f"Desenvolvimento | seed {dados['plano'].get('seed', '?')} | plano {dados['manifesto']['plano_sha256'][:12]}", margem, 22, 7.5)
        c.setFont("Helvetica", 7.5); c.drawRightString(largura - margem, 22, f"{dados['pasta'].name} | {numero}/4")

    titulos = {"visao": "Comparação geral das configurações", "metricas": "Cobertura, erros e classificação",
               "videos": "Variação do F1 de indivíduos por vídeo", "controles": "Controles e critérios de leitura"}
    if fatorial:
        titulos["controles"] = "Efeito da margem no desenho fatorial"
    if rodada5:
        titulos["controles"] = "Comparações de margem e de classificação"
    for numero, (tipo, ids) in enumerate(paginas, 1):
        texto(f"BLOBS | {dados['plano']['rodada'].upper()}", margem, altura - 34, 18, True)
        texto(titulos[tipo], margem, altura - 53, 12)
        subtitulo = (("Pares com os demais parâmetros iguais; comparações dentro da rodada. Nenhuma seleção automática."
                      if fatorial else "Controles em ordem do plano; comparações dentro da rodada. Nenhuma seleção automática.")
                     if tipo == "controles" else
                     "F1 de indivíduos em ordem decrescente; empates mantêm a ordem do plano. Nenhuma seleção automática.")
        texto(subtitulo, margem, altura - 69, 8)
        rodape()
        if tipo == "visao":
            primeira = dados["resumos"][ids[0]]
            cards = [f"{len(ids)} configurações", "178 quadros / configuração",
                     f"{sum(int(primeira[f'anotacoes_classe_{k}']) for k in (0, 2, 1))} caixas anotadas", "12 vídeos de desenvolvimento"]
            for j, rotulo in enumerate(cards):
                x = margem + j * (util + 8) / 4
                faixa(x, 501, (util - 24) / 4); texto(rotulo, x + 7, 501, 8.5, True)
            for coluna in range(2):
                x = margem + coluna * (painel + 20)
                texto("Config. / método / pol. / caixa", x, 476, 7.5, True)
                texto("F1 (barra) | P (ponto) | R (traço)", x + 133, 476, 7, True)
                for nome, dx in (("F1", 282), ("P", 316), ("R", 350)):
                    texto(nome, x + dx, 476, 7.5, True)
                for j, ident in enumerate(ids[coluna * por_coluna:(coluna + 1) * por_coluna]):
                    y = 456 - j * passo_barras; r = dados["resumos"][ident]
                    texto(_rotulo_configuracao(configs[ident]), x, y, 7.3)
                    bx, bw = x + 133, 139
                    c.setFillColor(HexColor("#e9eff2")); c.rect(bx, y - 1, bw, 7, fill=1, stroke=0)
                    valores = [_numero(r[k]) for k in ("f1_individuos", "precisao_individuos", "recall_individuos")]
                    if valores[0] is not None:
                        c.setFillColor(HexColor(cor_f1)); c.rect(bx, y - 1, bw * valores[0], 7, fill=1, stroke=0)
                    if valores[1] is not None:
                        c.setFillColor(HexColor(cor_p)); c.circle(bx + bw * valores[1], y + 2.5, 2.1, fill=1, stroke=0)
                    if valores[2] is not None:
                        c.setStrokeColor(HexColor(cor_r)); c.setLineWidth(1.6)
                        c.line(bx + bw * valores[2], y - 2, bx + bw * valores[2], y + 7)
                    for valor, dx in zip(valores, (282, 316, 350)):
                        texto("SC" if valor is None else _valor(valor), x + dx, y, 7.2)
                texto("0", x + 133, 158, 7); texto("0,5", x + 197, 158, 7); texto("1", x + 268, 158, 7)
            texto("Resumo do F1 entre configurações", margem, 138, 9, True)
            valores = [_numero(dados["resumos"][i]["f1_individuos"]) for i in ids]
            validos = [v for v in valores if v is not None]
            numeros = [len(validos), mean(validos) if validos else None, median(validos) if validos else None,
                       stdev(validos) if len(validos) > 1 else None, min(validos) if validos else None, max(validos) if validos else None]
            for j, (titulo, valor) in enumerate(zip(("N definido", "Média", "Mediana", "DP (n-1)", "Mínimo", "Máximo"), numeros)):
                x = margem + j * util / 6
                texto(titulo, x, 121, 8, True); texto(str(valor) if j == 0 else _valor(valor), x, 107, 9)
            legenda = ("Escala fixa de 0 a 1. SB = SimpleBlobDetector; LoG / DoG = variantes em escala; C = claro; M = margem em px por lado. Sem pré-processamento. Parâmetros completos no plano.json."
                       if fatorial else
                       "Escala fixa de 0 a 1. SB = SimpleBlobDetector; LoG / DoG = variantes em escala; +H = CLAHE. C/E = claro/escuro; O = caixa original; S = escala; M = margem em px por lado. Parâmetros completos no plano.json.")
            paragrafo(legenda, 87, 7.8)
            paragrafo("DP descreve apenas dispersão da busca. Configurações e quadros compartilham dados: não são amostras independentes nem evidência de desempenho em dados novos.", 53, 7.6)
        elif tipo == "metricas":
            paragrafo("Mesma ordem da visão geral. TP/FP/FN pertencem aos indivíduos (0 + 2). Cobertura é a fração de anotações localizadas. SC = sem casos; é diferente de zero.", 503, 8.5)
            colunas = (("ID", 0), ("TP", 39), ("FP", 68), ("FN", 103), ("Cob. 0", 136), ("Cob. 2", 174),
                       ("Cob. 1", 212), ("F1 agl.", 250), ("Trocas/n", 289), ("Ac. cond.", 342))
            for coluna in range(2):
                x = margem + coluna * (painel + 20); faixa(x, 466, painel)
                for titulo, dx in colunas: texto(titulo, x + dx + 2, 466, 6.8, True)
                for j, ident in enumerate(ids[coluna * por_coluna:(coluna + 1) * por_coluna]):
                    y = 445 - j * passo_metricas; r = dados["resumos"][ident]
                    valores = [ident, r['tp_individuos'], r['fp_individuos'], r['fn_individuos'],
                               *[_valor(r[k], 2) if r[k] != "" else "SC" for k in ('recall_classe_0','recall_classe_2','recall_classe_1','f1_aglomerados')],
                               f"{r['pares_incorretos']}/{r['pares_total']}", "SC" if r['acuracia_condicional'] == "" else _valor(r['acuracia_condicional'], 2)]
                    for valor, (_, dx) in zip(valores, colunas): texto(valor, x + dx + 2, y, 6.8)
            y = 117
            y = paragrafo("Trocas/n = erros de classificação 0/2 entre os n indivíduos localizados. Ac. cond. = acurácia somente nesses pares. Uma acurácia alta com cobertura baixa não indica boa detecção. A classificação não apaga o acerto de localização entre 0 e 2.", y, 8.5)
            y = paragrafo("Aglomerados (classe 1) são avaliados separadamente. Trocar indivíduo por aglomerado gera FN no grupo anotado e FP no grupo previsto. Contagens de aglomerados, matriz 0/2 e valores sem arredondamento permanecem nos CSVs.", y, 8.5)
            paragrafo("Localização usa correspondência exclusiva 1:1 com IoU >= 0,50. F1 global é calculado após somar TP, FP e FN dos 178 quadros; não é a média dos F1 por quadro ou vídeo.", y, 8)
        elif tipo == "videos":
            paragrafo("Cada célula usa as contagens somadas dos quadros de um vídeo. Escala fixa de 0 a 1; cinza / SC = sem casos. Cores claras representam F1 menor.", 503, 8.5)
            for coluna in range(2):
                x = margem + coluna * (painel + 20); inicio = x + 39; cw = (painel - 39) / len(VIDEOS)
                texto("ID", x, 466, 8, True)
                for j, video in enumerate(VIDEOS): texto(video, inicio + j * cw + 7, 466, 8, True)
                for j, ident in enumerate(ids[coluna * por_coluna:(coluna + 1) * por_coluna]):
                    y = 444 - j * passo_videos
                    texto(ident, x, y + 1, 7.4)
                    for k, video in enumerate(VIDEOS):
                        celula(dados['por_video'][ident, video]['f1_individuos'], inicio + k * cw, y, cw, 13, 6.8)
            y = paragrafo("São 15 quadros por vídeo, exceto o vídeo 23: 13 quadros, pois 900 e 1100 não têm anotação. As caixas reaparecem entre quadros; o suporte anotado não representa indivíduos únicos.", 91, 8.5)
            paragrafo("Diferenças entre vídeos mostram sensibilidade às condições de imagem. Quadros do mesmo vídeo são dependentes; estes mapas não fornecem significância estatística ou intervalos de confiança.", y, 8.5)
        elif rodada5:
            pares = _comparacoes_round5(dados)
            y = paragrafo("São seis pares que alteram somente a margem da caixa e um par LoG que altera somente o limite de classificação de aglomerados. Delta = F1 da variante menos F1 da base, na mesma rodada; não é teste estatístico nem comparação histórica.", 503, 8.5)
            colunas = (("Método / fatores fixos", 3), ("Base", 221), ("Variante", 279),
                       ("Alteração", 348), ("F1 base", 540), ("F1 variante", 616), ("Delta F1", 699))
            faixa(margem, y, util)
            for titulo, dx in colunas: texto(titulo, margem + dx, y, 8, True)
            y -= 22
            for par in pares:
                delta = par["delta"]
                valores = [par["fatores"], par["base"]["id"], par["variante"]["id"], par["alteracao"],
                           _valor(par["f1_base"]), _valor(par["f1_maior"]),
                           "sem casos" if delta is None else f"{delta:+.3f}".replace(".", ",")]
                for valor, (_, dx) in zip(valores, colunas): texto(valor, margem + dx, y, 8)
                y -= 18
            y -= 12
            texto("O que muda em cada comparação", margem, y, 10, True); y -= 18
            controles = [x for x in dados["plano"]["configuracoes"] if x["bloco"] == "controle"]
            referencias = "; ".join(f"{x['id']} = {x.get('referencia', '?')}" for x in controles)
            textos = [
                "Margem: SimpleBlob com área mínima 56/64/72, distância 6 e margem 2/3; DoG com resposta 0,10/0,12/0,14 e margem 5/6. Dentro de cada par, candidatos, medidas brutas e regras de classificação permanecem iguais; só a caixa muda.",
                "Classificação: LoG com resposta 0,12 e margem 6. A área circular mínima de aglomerado muda de 452,389 para 615,752 px², equivalente a diâmetro 24 para 28 px. Caixa, limites de pequeno e parâmetros de detecção ficam fixos.",
                "Mover uma previsão entre indivíduo e aglomerado muda o grupo de correspondência e pode alterar TP, FP, FN e F1 mesmo com caixas idênticas. Esse ganho deve ser distinguido de melhoria geométrica. Trocas 0/2 continuam apenas erros de classificação entre indivíduos localizados.",
                f"Repetições registradas: {referencias}. A reprodução dos resultados anteriores exige conferência separada de entradas, versões e saídas; o rótulo de controle sozinho não a comprova.",
                "Critérios inalterados: indivíduos 0/2 juntos, aglomerados separados, IoU >= 0,50, pares exclusivos e F1 das contagens somadas. Sem casos não é zero. Leia também cobertura por classe, precisão, recall e classificação condicional.",
                "No DoG, a grade termina em sigma 8,192 e não prevê a faixa de aglomerados. O teste de limite de classificação usa LoG; não modifica essa limitação do DoG. Resposta do filtro não é probabilidade de confiança.",
                "Dados de desenvolvimento já explorados; quadros do mesmo vídeo não são independentes. Relatório descritivo, sem seleção automática ou inferência estatística. Fontes verificadas: plano e três resumos CSV; detalhes e tempos permanecem nos arquivos do batch.",
            ]
            for conteudo in textos: y = paragrafo(conteudo, y, 8)
        elif fatorial:
            pares = _comparacoes_fatoriais(dados)
            y = paragrafo("Cada linha mantém método, pré-processamento e parâmetros iguais, alterando somente a margem da caixa. Delta = F1 da margem maior menos F1 da menor, na mesma rodada. Não é teste de significância nem comparação com métricas históricas.", 503, 8.5)
            colunas = (("Método / fatores fixos", 3), ("Base", 260), ("Maior margem", 323),
                       ("Margens (px/lado)", 419), ("F1 base", 532), ("F1 maior", 605), ("Delta F1", 688))
            faixa(margem, y, util)
            for titulo, dx in colunas: texto(titulo, margem + dx, y, 8, True)
            y -= 22
            for par in pares:
                base, maior, delta = par["base"], par["maior"], par["delta"]
                valores = [par["fatores"], base["id"], maior["id"],
                           f"{maior['caixa']['pixels']:g} versus {base['caixa']['pixels']:g}",
                           _valor(par["f1_base"]), _valor(par["f1_maior"]),
                           "sem casos" if delta is None else f"{delta:+.3f}".replace(".", ",")]
                for valor, (_, dx) in zip(valores, colunas): texto(valor, margem + dx, y, 8)
                y -= 16
            y -= 10
            texto("Critérios preservados e limites de interpretação", margem, y, 10, True); y -= 18
            controles = [item for item in dados["plano"]["configuracoes"] if item["bloco"] == "controle"]
            referencias = "; ".join(f"{item['id']} = {item.get('referencia', '?')}" for item in controles)
            fatores_rodada = ("SimpleBlob: área mínima 32/48/64, distância 6/12 e margem 3/4. LoG e DoG: resposta 0,05/0,08/0,12 e margem 4/6."
                              if dados["plano"]["versao"] == 3 else
                              "SimpleBlob: área mínima 48/64/80, distância 6 e margem 2/3. DoG: resposta 0,12/0,16/0,20/0,24 e margem 6/8. LoG: resposta 0,08/0,12 e margem 5/6.")
            textos = [
                f"Repetições registradas no plano: {referencias}. Esses rótulos não comprovam sozinhos reprodução dos resultados anteriores; a conferência entre rodadas é uma análise separada.",
                "Indivíduos = classes 0 e 2; aglomerados = classe 1 separada. IoU >= 0,50, pares exclusivos e F1 das contagens somadas. Sem casos não é zero. Trocas 0/2 permanecem erros de classificação em pares localizados.",
                fatores_rodada + " Compare o delta entre linhas para explorar interações; leia também cobertura, FP e FN. A resposta não é probabilidade de confiança.",
                "A margem altera somente a caixa; centro, medida bruta e classe permanecem iguais. No DoG, a grade atual termina em sigma 8,192 e não alcança a faixa de aglomerados. Nenhuma margem corrige essa limitação de escala.",
                "Dados de desenvolvimento já explorados; quadros do mesmo vídeo não são independentes. O PDF é descritivo, sem seleção automática, intervalos de confiança ou teste estatístico. Fontes verificadas: plano e três resumos CSV. Parâmetros, tempos e pares completos ficam nos arquivos do batch.",
            ]
            for conteudo in textos: y = paragrafo(conteudo, y, 8)
        else:
            controles = _comparacoes_controle(dados)
            y = paragrafo("Comparações abaixo usam apenas referências da própria rodada e mantêm o detector e seus parâmetros. No round1 varia a caixa; nos pares com CLAHE varia o pré-processamento. Delta é F1 menos F1 da referência; não é um teste estatístico.", 503, 8.5)
            colunas = (("Configuração", 3), ("Referência local", 169), ("Caixa", 268), ("Pré-processamento", 365), ("F1 indiv.", 546), ("Delta F1", 620), ("Bloco", 693))
            faixa(margem, y, util)
            for titulo, dx in colunas: texto(titulo, margem + dx, y, 8, True)
            y -= 21
            for item, base, delta in controles:
                pre = item.get('preprocessamento', {'metodo':'nenhum'})
                nomepre = 'nenhum' if pre['metodo']=='nenhum' else f"CLAHE {pre.get('limite_contraste', '?')} / {pre.get('grade', '?')}"
                valores = [_rotulo_configuracao(item), base['id'] if base else '-', _caixa(item), nomepre,
                           _valor(dados['resumos'][item['id']]['f1_individuos']), '-' if delta is None else f'{delta:+.3f}'.replace('.',','), item['bloco']]
                for valor, (_, dx) in zip(valores,colunas): texto(valor,margem+dx,y,7.7)
                y -= 14
            y -= 13
            texto("Como interpretar e reproduzir", margem, y, 10, True); y -= 18
            textos = [
                "As classes 0 e 2 formam o grupo de indivíduos; a classe 1 permanece separada. Sem anotações nem previsões: F1 sem casos. Somente previsões ou somente anotações: F1 = 0.",
                "As caixas são comparadas com as mesmas anotações, sem alterá-las. Escala e margem preservam centro, medida bruta e classe; a área da caixa não passa a ser área segmentada do objeto.",
                "Na exploração vários parâmetros podem mudar juntos. Seu melhor F1 não identifica sozinho qual parâmetro causou a melhora. Métodos LoG/DoG e CLAHE estão identificados nas legendas e no plano.",
                "O desenvolvimento utiliza dados já explorados. Estes resultados orientam novas configurações; não selecionam automaticamente finalistas nem estimam desempenho em dados inéditos.",
                "Fontes: plano.json e os três resumos CSV do batch. Hashes, contagens e agregações são conferidos antes do PDF. Tempos e parâmetros completos ficam nos CSVs/plano; pares, pendências e imagens comparativas ficam nas pastas dos quadros.",
            ]
            for conteudo in textos: y = paragrafo(conteudo, y, 8.2)
        c.showPage()
    c.save()
    return len(paginas)


def gerar_relatorio(pasta: Path) -> Path:
    """Gera nova versão do PDF, preservando o batch e todos os relatórios anteriores."""
    import reportlab
    dados = carregar(pasta)
    inicio = agora()
    destino = (dados["pasta"] / "relatorios" / inicio.strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not destino.is_relative_to(dados["pasta"]):
        raise ValueError("Pasta do relatório fora do batch.")
    destino.mkdir(parents=True, exist_ok=False)
    pdf = destino / "relatorio.pdf"
    registro = {"versao": 1, "tipo": "rodada_blobs", "situacao": "em_andamento",
                "rodada": dados["plano"]["rodada"], "inicio_utc": inicio.isoformat(),
                "origens_sha256": dados["hashes"], "criterios": CRITERIOS,
                "dependencias": {"python": platform.python_version(), "reportlab": reportlab.Version},
                "codigo_relatorio_sha256": sha256(Path(__file__).read_bytes()),
                "ordem": _ordem_visual(dados),
                "ordenacao": ("F1 de indivíduos decrescente; empates preservam ordem do plano; pares de margem e classificação na quarta página; sem seleção automática."
                              if dados["plano"]["versao"] == 5 else
                              "F1 de indivíduos decrescente; empates preservam ordem do plano; pares de margem na quarta página; sem seleção automática."
                              if dados["plano"]["versao"] in (3, 4) else
                              "F1 de indivíduos decrescente; empates preservam ordem do plano; controles em seção própria; sem seleção automática."),
                "escopo_integridade": "Manifesto, plano e três resumos; métricas e agregações por quadro/vídeo/configuração. Sem releitura da base, PNGs ou tabelas de caixas."}
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
