"""Diagnóstico geométrico das saídas salvas do round0; não executa detecção."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO, StringIO
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
SAIDA = RAIZ / "resultados/frame-to-frame/blobs/round0"
FONTES_CODIGO = ("scripts/blobs/diagnosticar_round0.py", "analise/diagnostico_blobs.py")
CAIXA = ("caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px")
MEDIDAS = ("centro_blob_x_px", "centro_blob_y_px", "diametro_blob_px", "area_estimada_blob_px2")
IDENTIDADE = ("configuracao_id", "video_id", "quadro")
AVISO = ("Diagnóstico de geometria, sem novo F1, ranking ou seleção. Centro dentro de caixa "
         "não é pareamento, recall nem acerto; uma detecção sem par por IoU pode estar sobre "
         "o objeto. Zero, um ou vários centros são incidências geométricas, não rótulos de erro.")


def hash_bytes(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def carregar_json(conteudo):
    def objeto(pares):
        resultado = {}
        for k, v in pares:
            if k in resultado:
                raise ValueError(f"Chave JSON repetida: {k}.")
            resultado[k] = v
        return resultado
    def constante(valor):
        raise ValueError(f"Constante JSON não finita: {valor}.")
    return json.loads(conteudo.decode("utf-8-sig"), object_pairs_hook=objeto, parse_constant=constante)


def relativo(caminho):
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def caminho(nome):
    if not isinstance(nome, str) or not nome or "\\" in nome:
        raise ValueError("Caminho relativo inválido.")
    p = Path(nome)
    if p.is_absolute() or ".." in p.parts or p.as_posix() != nome:
        raise ValueError("Caminho relativo inválido.")
    destino = (RAIZ / p).resolve(strict=True)
    if not destino.is_relative_to(RAIZ.resolve()) or not destino.is_file():
        raise ValueError("Arquivo fora do projeto.")
    return destino


def ler_csv(conteudo):
    leitor = csv.DictReader(StringIO(conteudo.decode("utf-8-sig")), strict=True)
    if not leitor.fieldnames or len(set(leitor.fieldnames)) != len(leitor.fieldnames):
        raise ValueError("Cabeçalho CSV inválido.")
    linhas = list(leitor)
    if any(None in x or any(v is None for v in x.values()) for x in linhas):
        raise ValueError("Quantidade de colunas CSV inválida.")
    return leitor.fieldnames, linhas


def inteiro(valor):
    if not isinstance(valor, str) or not valor.isascii() or not valor.isdecimal():
        raise ValueError("Inteiro não negativo esperado no CSV.")
    return int(valor)


def converter_objetos(conteudo, anotacao, quadro):
    indice = "indice_anotacao" if anotacao else "indice_deteccao"
    campos, linhas = ler_csv(conteudo)
    obrigatorios = {indice, "classe", *CAIXA, "video_id", "quadro", "imagem", "anotacao"}
    if not anotacao:
        obrigatorios.update((*MEDIDAS, "algoritmo", "origem_medidas"))
    if not obrigatorios.issubset(campos):
        raise ValueError("Tabela de objetos sem os campos necessários.")
    objetos, indices = [], set()
    for x in linhas:
        if any(x[k] != str(quadro[k]) for k in ("video_id", "quadro", "imagem", "anotacao")):
            raise ValueError("Origem de objeto divergente do plano.")
        novo = {indice: inteiro(x[indice]), "classe": inteiro(x["classe"])}
        if novo[indice] in indices or novo["classe"] not in (0, 1, 2):
            raise ValueError("Índice repetido ou classe inválida.")
        indices.add(novo[indice])
        for k in (*CAIXA, *(() if anotacao else MEDIDAS)):
            novo[k] = float(x[k])
            if not math.isfinite(novo[k]):
                raise ValueError("Coordenadas e medidas precisam ser finitas.")
        if not anotacao:
            if x["algoritmo"] != "blobs" or x["origem_medidas"] != "simpleblob_keypoint":
                raise ValueError("Origem das medidas não corresponde a blobs.")
            novo["origem_medidas"] = x["origem_medidas"]
        objetos.append(novo)
    return objetos


def congelar(origem):
    """Confere e retém bytes de todas as fontes antes de criar a nova pasta."""
    origem = Path(origem).expanduser().resolve(strict=True)
    if (not SAIDA.resolve().is_relative_to(RAIZ.resolve()) or origem.parent != SAIDA.resolve()
            or not origem.name.startswith("inspecao__") or not origem.is_dir()):
        raise ValueError("Informe explicitamente uma inspeção de blobs/round0/.")
    salvos = {}
    def ler(nome):
        if nome not in salvos:
            salvos[nome] = caminho(nome).read_bytes()
        return salvos[nome]
    manifesto = carregar_json(ler(relativo(origem / "execucao.json")))
    if type(manifesto.get("versao")) is not int or manifesto["versao"] != 1:
        raise ValueError("Versão de manifesto incompatível.")
    for k, v in {"tipo": "inspecao_blobs", "situacao": "concluida", "algoritmo": "blobs",
                 "rodada": "round0", "etapa": "inspecao", "particao": "desenvolvimento"}.items():
        if manifesto.get(k) != v:
            raise ValueError(f"Inspeção incompatível: {k}.")
    for k, v in (("configuracoes_previstas", 2), ("configuracoes_concluidas", 2), ("quadros_por_configuracao", 6)):
        if type(manifesto.get(k)) is not int or manifesto[k] != v:
            raise ValueError("A origem deve ter duas configurações e seis quadros completos.")
    plano_bytes = ler(relativo(origem / "plano.json")); plano = carregar_json(plano_bytes)
    if hash_bytes(plano_bytes) != manifesto["plano_sha256"]:
        raise ValueError("Hash do plano divergente.")
    if (type(plano.get("versao")) is not int or plano["versao"] != 1
            or any(plano.get(k) != manifesto[k] for k in ("algoritmo", "etapa", "rodada", "particao"))):
        raise ValueError("Plano incompatível com a inspeção.")
    quadros = plano["quadros"]; configs = plano["configuracoes"]
    chaves = {(q["video_id"], q["quadro"]) for q in quadros}; ids = [c["id"] for c in configs]
    if (len(quadros) != 6 or len(chaves) != 6 or len(ids) != 2 or len(set(ids)) != 2
            or any(not isinstance(i, str) or not re.fullmatch(r"b[0-9]{2}", i) for i in ids)
            or any(not isinstance(v, str) or not v.isdecimal() or type(q) is not int or q < 0 for v, q in chaves)):
        raise ValueError("Composição de quadros/configurações inválida.")
    execucoes = manifesto["execucoes"]
    if len(execucoes) != 2 or {x["configuracao_id"] for x in execucoes} != set(ids):
        raise ValueError("Execuções não correspondem às duas configurações.")
    esperados = {relativo(origem / n) for n in ("plano.json", "origem_desenvolvimento.json", "codigo.zip", "resumo_configuracoes.csv", "resumo_por_quadro.csv")}
    casos, pastas = [], []
    for ex in execucoes:
        ident = ex["configuracao_id"]; pasta = (RAIZ / ex["pasta"]).resolve(strict=True)
        if (pasta.parent != SAIDA.resolve() or not pasta.name.startswith(ident + "__")
                or not pasta.name.endswith(origem.name.removeprefix("inspecao__"))):
            raise ValueError("Pasta de configuração fora da inspeção.")
        pastas.append(pasta)
        esperados.update(relativo(pasta / n) for n in ("execucao.json", "configuracao.json", "configuracao_opencv.json", "avaliacao.json", "resumo_por_quadro.csv"))
        for q in quadros:
            local = pasta / "quadros" / f"{q['video_id']}_frame_{q['quadro']}"
            nomes = {n: relativo(local / n) for n in ("avaliacao.json", "anotacoes.csv", "deteccoes.csv", "pares.csv", "pendentes.csv", "predicoes.txt", "comparacao.png")}
            esperados.update(nomes.values()); casos.append({"configuracao_id": ident, "quadro": q, "arquivos": nomes})
    if set(manifesto["saidas_sha256"]) != esperados or len(esperados) != 99:
        raise ValueError("Manifesto não cobre exatamente as 99 saídas previstas.")
    for nome in esperados:
        if not any(caminho(nome).is_relative_to(p) for p in [origem, *pastas]):
            raise ValueError("Saída declarada fora das pastas da inspeção.")
        if hash_bytes(ler(nome)) != manifesto["saidas_sha256"][nome]:
            raise ValueError(f"Hash de saída divergente: {nome}.")
    for ex, pasta in zip(execucoes, pastas):
        cm = carregar_json(ler(relativo(pasta / "execucao.json")))
        cfg = carregar_json(ler(relativo(pasta / "configuracao.json")))
        canonico = json.dumps(cfg, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if (cm.get("situacao") != "concluida" or cm.get("tipo") != "inspecao_blobs"
                or cm.get("configuracao_id") != ex["configuracao_id"]
                or type(cm.get("quadros_concluidos")) is not int or cm["quadros_concluidos"] != 6
                or cm.get("batch") != relativo(origem) or cm.get("plano_sha256") != manifesto["plano_sha256"]
                or cm.get("configuracao_sha256") != hash_bytes(canonico)
                or cfg != next(c["parametros"] for c in configs if c["id"] == ex["configuracao_id"])
                or carregar_json(ler(relativo(pasta / "configuracao_opencv.json"))) != cm.get("parametros_opencv")
                or cm.get("parametros_opencv") != manifesto["parametros_opencv"][ex["configuracao_id"]]):
            raise ValueError("Manifesto/parâmetros da configuração divergentes.")
    desenvolvimento = carregar_json(ler(relativo(origem / "origem_desenvolvimento.json")))
    if (type(desenvolvimento.get("versao")) is not int or desenvolvimento["versao"] != 1
            or desenvolvimento.get("algoritmo") != "limiarizacao"
            or desenvolvimento.get("rodada") != "round1"
            or desenvolvimento.get("particao") != "desenvolvimento"):
        raise ValueError("Origem não identifica desenvolvimento.")
    indice_dev = {(q["video_id"], q["quadro"]): q for q in desenvolvimento["quadros"]}
    previstas_dev = {(v, q) for v in ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60") for q in range(0, 1401, 100)} - {("23", 900), ("23", 1100)}
    if len(desenvolvimento["quadros"]) != 178 or set(indice_dev) != previstas_dev:
        raise ValueError("A origem deve preservar os 178 quadros de desenvolvimento.")
    fontes_bases = set()
    for q in quadros:
        referencia = indice_dev.get((q["video_id"], q["quadro"]))
        if referencia is None:
            raise ValueError("Quadro fora do desenvolvimento.")
        for k in ("imagem", "anotacao"):
            nome = q[k]
            subpasta, extensao = ("images", "jpg") if k == "imagem" else ("labels", "txt")
            esperado = f"bases_de_dados/visem_tracking/dataset/Train/{q['video_id']}/{subpasta}/{q['video_id']}_frame_{q['quadro']}.{extensao}"
            if (nome != esperado
                    or nome != referencia[k] or q[f"{k}_sha256"] != referencia[f"sha256_{k}"]):
                raise ValueError("Origem do quadro incompatível com desenvolvimento.")
            fontes_bases.add(nome)
            if manifesto["origens_sha256"].get(nome) != q[f"{k}_sha256"] or hash_bytes(ler(nome)) != q[f"{k}_sha256"]:
                raise ValueError("Hash da entrada original divergente.")
    origem_dev = plano["origem_desenvolvimento"]
    if (origem_dev["plano"] != "scripts/limiarizacao/rodadas/round1.json"
            or hash_bytes(ler(relativo(origem / "origem_desenvolvimento.json"))) != origem_dev["sha256"]
            or manifesto["origens_sha256"].get(origem_dev["plano"]) != origem_dev["sha256"]):
        raise ValueError("Plano de desenvolvimento divergente.")
    for nome, digest in manifesto["origens_sha256"].items():
        if nome not in fontes_bases and nome != origem_dev["plano"] and not nome.startswith("scripts/blobs/inspecao/"):
            raise ValueError("Origem fora dos dados e planos de desenvolvimento permitidos.")
        if hash_bytes(ler(nome)) != digest:
            raise ValueError(f"Hash de origem divergente: {nome}.")
    with ZipFile(BytesIO(ler(relativo(origem / "codigo.zip")))) as z:
        codigo = manifesto["codigo"]
        if (hash_bytes(ler(relativo(origem / "codigo.zip"))) != codigo["sha256_zip"]
                or len(z.namelist()) != len(codigo["sha256_arquivos"])
                or set(z.namelist()) != set(codigo["sha256_arquivos"]) or z.testzip() is not None
                or any(hash_bytes(z.read(n)) != h for n, h in codigo["sha256_arquivos"].items())):
            raise ValueError("Arquivo de código divergente ou danificado.")
    _, linhas = ler_csv(ler(relativo(origem / "resumo_por_quadro.csv")))
    por_caso = {(x["configuracao_id"], x["video_id"], inteiro(x["quadro"])): x for x in linhas}
    if len(linhas) != 12 or set(por_caso) != {(i, v, q) for i in ids for v, q in chaves}:
        raise ValueError("Resumo não contém os 12 casos únicos previstos.")
    _, resumos = ler_csv(ler(relativo(origem / "resumo_configuracoes.csv")))
    if len(resumos) != 2 or {x["configuracao_id"] for x in resumos} != set(ids) or any(inteiro(x["quantidade_quadros"]) != 6 for x in resumos):
        raise ValueError("Resumo de configurações incompleto.")
    for caso in casos:
        q, arquivos = caso["quadro"], caso["arquivos"]
        avaliacao = carregar_json(ler(arquivos["avaliacao.json"]))
        if (any(avaliacao["origem"].get(k) != q[k] for k in ("video_id", "quadro", "imagem", "anotacao"))
                or avaliacao.get("criterios") != manifesto["criterios"]):
            raise ValueError("Origem/critérios da avaliação salva divergentes.")
        dimensoes = avaliacao["dimensoes"]
        if any(type(dimensoes.get(k)) is not int or dimensoes[k] <= 0 for k in ("largura", "altura")):
            raise ValueError("Dimensões inválidas.")
        caso.update(dimensoes=dimensoes, anotacoes=converter_objetos(ler(arquivos["anotacoes.csv"]), True, q),
                    deteccoes=converter_objetos(ler(arquivos["deteccoes.csv"]), False, q))
        linha = por_caso[caso["configuracao_id"], q["video_id"], q["quadro"]]
        if (len(caso["anotacoes"]) != inteiro(linha["quantidade_anotacoes"])
                or len(caso["deteccoes"]) != inteiro(linha["quantidade_deteccoes"])
                or dimensoes["largura"] != inteiro(linha["imagem_largura_px"])
                or dimensoes["altura"] != inteiro(linha["imagem_altura_px"])):
            raise ValueError("Contagens dos objetos divergem do resumo.")
    registro_pdf = carregar_json(ler(relativo(origem / "relatorio.json")))
    if registro_pdf.get("situacao") not in ("concluido", "falhou"):
        raise ValueError("Registro do PDF em estado desconhecido.")
    if registro_pdf.get("situacao") == "concluido":
        pdf = caminho(registro_pdf["arquivo"])
        if not pdf.is_relative_to(origem / "relatorios"):
            raise ValueError("PDF fora da inspeção.")
        r = carregar_json(ler(relativo(pdf.parent / "relatorio.json")))
        if r.get("situacao") != "concluida" or hash_bytes(ler(relativo(pdf))) != r["pdf_sha256"]:
            raise ValueError("PDF incompleto ou hash divergente.")
        permitidas_pdf = {relativo(origem / n) for n in ("execucao.json", "plano.json", "resumo_configuracoes.csv", "resumo_por_quadro.csv")}
        if set(r["origens_sha256"]) != permitidas_pdf:
            raise ValueError("Fontes do relatório incompletas.")
        for nome, digest in r["origens_sha256"].items():
            if hash_bytes(ler(nome)) != digest:
                raise ValueError("Fonte do relatório divergente.")
    fontes_codigo = {n: caminho(n).read_bytes() for n in FONTES_CODIGO}
    return {"origem": origem, "manifesto": manifesto, "plano": plano, "salvos": salvos,
            "casos": casos, "codigo": fontes_codigo}


def gravar_json(destino, dados):
    temporario = destino.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporario.replace(destino)


def gravar_csv(destino, campos, linhas):
    with destino.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=campos); writer.writeheader()
        for linha in linhas:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list)) else v for k, v in linha.items()})


def achatar(dados, prefixo=""):
    resultado = {}
    for k, v in dados.items():
        nome = f"{prefixo}_{k}" if prefixo else k
        resultado.update(achatar(v, nome) if isinstance(v, dict) else {nome: v})
    return resultado


def executar(origem):
    dados = congelar(origem)
    from analise.diagnostico_blobs import diagnosticar_quadro
    agora = datetime.now(timezone.utc)
    destino = SAIDA.resolve() / f"diagnostico__{agora.strftime('%Y%m%dT%H%M%S%fZ')}"
    manifesto = {"versao": 1, "tipo": "diagnostico_geometrico_blobs_round0", "situacao": "em_andamento",
                 "origem": relativo(dados["origem"]), "inicio_utc": agora.isoformat(), "interpretacao": AVISO,
                 "python": platform.python_version(), "casos_previstos": 12, "casos_concluidos": 0,
                 "origens_sha256": {n: hash_bytes(v) for n, v in dados["salvos"].items()},
                 "codigo_sha256": {n: hash_bytes(v) for n, v in dados["codigo"].items()}}
    destino.mkdir(parents=True, exist_ok=False)
    try:
        gravar_json(destino / "execucao.json", manifesto)
        for original, copia in (("execucao.json", "execucao_origem.json"), ("plano.json", "plano_origem.json")):
            (destino / copia).write_bytes(dados["salvos"][relativo(dados["origem"] / original)])
        with ZipFile(destino / "codigo.zip", "x", ZIP_DEFLATED) as z:
            for n, v in dados["codigo"].items():
                z.writestr(n, v)
        resumo, anotacoes, deteccoes, revisao, quadros_json = [], [], [], [], []
        guia = ["# Revisão da geometria de blobs — round0", "", AVISO, "",
                "As caixas e imagens de origem permanecem intactas. Este diagnóstico não altera parâmetros nem produz uma nova rodada.", "",
                "Copie modelo_revisao_humana.csv para revisao_humana_preenchida.csv e preencha observacao_humana e hipotese_em_revisao apenas nessa cópia. O modelo faz parte dos hashes do diagnóstico e deve permanecer intacto. As linhas identificam anotações ou detecções pelo tipo_registro e indice_objeto; hipóteses ficam em branco até a inspeção visual.", "",
                "Filtre uma amostra representativa de zero, uma e múltiplas relações em cada configuração e quadro, incluindo detecções fora das caixas anotadas. Não é necessário preencher todas as linhas. Para anotações, a relação é um centro dentro da caixa; para detecções, é uma caixa anotada que contém seu centro. As coordenadas são as caixas originais.", "",
                "Quantidade de centros não decide duplicação, fragmentação, ruído ou objeto perdido. As IoUs e razões de área são descrições geométricas. As cores das comparações são os rótulos salvos do round0.", ""]
        for caso in dados["casos"]:
            q = caso["quadro"]; identidade = {"configuracao_id": caso["configuracao_id"], "video_id": q["video_id"], "quadro": q["quadro"]}
            d = diagnosticar_quadro(caso["anotacoes"], caso["deteccoes"], caso["dimensoes"]["largura"], caso["dimensoes"]["altura"])
            local = destino / "quadros" / identidade["configuracao_id"] / f"{q['video_id']}_frame_{q['quadro']}"
            local.mkdir(parents=True, exist_ok=False); gravar_json(local / "diagnostico.json", {**identidade, **d})
            resumo.append({**identidade, **achatar(d["resumo"])})
            anotacoes.extend({**identidade, **x} for x in d["anotacoes"])
            deteccoes.extend({**identidade, **x} for x in d["deteccoes"])
            comparacao = caso["arquivos"]["comparacao.png"]
            for tipo, lista, indice, quantidade, relacionados in (
                    ("anotacao", d["anotacoes"], "indice_anotacao", "quantidade_centros", "indices_deteccoes"),
                    ("deteccao", d["deteccoes"], "indice_deteccao", "quantidade_anotacoes", "indices_anotacoes")):
                revisao.extend({**identidade, "tipo_registro": tipo, "indice_objeto": x[indice], "classe": x["classe"],
                                "quantidade_relacoes": x[quantidade], "indices_relacionados": x[relacionados],
                                **{k: x[k] for k in CAIXA}, "imagem": q["imagem"], "comparacao_png": comparacao,
                                "observacao_humana": "", "hipotese_em_revisao": ""} for x in lista)
            link = os.path.relpath(RAIZ / comparacao, destino).replace("\\", "/")
            guia.append(f"- {identidade['configuracao_id']} — vídeo {q['video_id']}, quadro {q['quadro']}: [abrir comparação]({link})")
            quadros_json.append({**identidade, "diagnostico": relativo(local / "diagnostico.json"), "resumo": d["resumo"]})
            manifesto["casos_concluidos"] += 1
            gravar_json(destino / "execucao.json", manifesto)
        gravar_json(destino / "diagnostico.json", {"interpretacao": AVISO, "origem": relativo(dados["origem"]), "quadros": quadros_json})
        campos_a = [*IDENTIDADE, "indice_anotacao", "classe", "grupo", *CAIXA, "quantidade_centros", "indices_deteccoes", "incidencias", "melhor_iou_qualquer_classe", "melhor_iou_mesmo_grupo"]
        campos_d = [*IDENTIDADE, "indice_deteccao", "classe", "grupo", *CAIXA, *MEDIDAS, "origem_medidas", "quantidade_anotacoes", "indices_anotacoes", "categoria_incidencia"]
        gravar_csv(destino / "resumo_por_quadro.csv", list(resumo[0]), resumo)
        gravar_csv(destino / "anotacoes.csv", campos_a, anotacoes)
        gravar_csv(destino / "deteccoes.csv", campos_d, deteccoes)
        gravar_csv(destino / "modelo_revisao_humana.csv", [*IDENTIDADE, "tipo_registro", "indice_objeto", "classe", "quantidade_relacoes", "indices_relacionados", *CAIXA, "imagem", "comparacao_png", "observacao_humana", "hipotese_em_revisao"], revisao)
        (destino / "guia_revisao.md").write_text("\n".join(guia) + "\n", encoding="utf-8")
        manifesto.update(situacao="concluida", fim_utc=datetime.now(timezone.utc).isoformat(),
                         saidas_sha256={relativo(p): hash_bytes(p.read_bytes()) for p in sorted(destino.rglob("*")) if p.is_file() and p.name != "execucao.json"})
        gravar_json(destino / "execucao.json", manifesto)
    except BaseException as erro:
        manifesto.update(situacao="falhou", fim_utc=datetime.now(timezone.utc).isoformat(), erro=f"{type(erro).__name__}: {erro}")
        try:
            gravar_json(destino / "execucao.json", manifesto)
        except OSError:
            pass
        raise
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspeciona geometria de caixas salvas, sem executar detector, avaliador ou novos parâmetros.")
    parser.add_argument("--origem", type=Path, required=True, help="Pasta inspecao__... explícita dentro de blobs/round0/.")
    args = parser.parse_args(argv)
    try:
        print(f"Diagnóstico salvo em: {executar(args.origem)}")
        print(AVISO)
        return 0
    except KeyboardInterrupt:
        print("Diagnóstico interrompido; eventual saída parcial foi preservada.", file=sys.stderr); return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
