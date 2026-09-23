"""Rodada de desenvolvimento de watershed com plano congelado e controles."""

from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import argparse
import platform
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS, agregar
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import (
    arquivar_codigo, carregar_json, colunas_metricas, preparar_imagens,
)
from scripts.limiarizacao.inspecionar_imagem import agora, gravar_csv, ler_anotacoes
from scripts.watershed import executar_inspecao as inspecao
from scripts.watershed.planejamento import (
    ARQUIVOS_CONTROLE, DIAGNOSTICO, construir_plano, sha, validar_plano,
)

PLANO = RAIZ / "scripts/watershed/rodadas/round1.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round1"
FONTES = (*inspecao.FONTES, "scripts/watershed/planejamento.py",
          "scripts/watershed/executar_rodada.py", "analise/relatorio_rodada_watershed.py")


def relativo(p):
    return p.resolve().relative_to(RAIZ.resolve()).as_posix()


def interno(nome):
    p = Path(nome)
    if not isinstance(nome, str) or p.is_absolute() or ".." in p.parts or p.as_posix() != nome:
        raise ValueError(f"Caminho relativo inválido: {nome}.")
    alvo = (RAIZ / p).resolve(strict=True)
    if not alvo.is_relative_to(RAIZ.resolve()) or not alvo.is_file():
        raise ValueError(f"Arquivo fora do projeto: {nome}.")
    return alvo


def dependencias():
    import cv2
    import numpy as np
    import scipy
    import skimage
    import reportlab
    return {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
            "scipy": scipy.__version__, "scikit-image": skimage.__version__, "reportlab": reportlab.Version}


def decodificar(entrada):
    import cv2
    import numpy as np
    copia = {**entrada, "anotacoes": deepcopy(entrada["anotacoes"])}
    preparar_imagens([copia], cv2, np)
    return copia


def congelar_entradas(caminho=PLANO):
    """Confere tudo antes de criar saídas; mantém bytes originais em memória."""
    caminho = Path(caminho).resolve(strict=True)
    if not caminho.is_relative_to(RAIZ.resolve()):
        raise ValueError("Plano fora do projeto.")
    blob = caminho.read_bytes()
    p = validar_plano(carregar_json(blob))
    if p != construir_plano(RAIZ):
        raise ValueError("Plano difere da geração ou das origens congeladas. Não foi alterado.")
    hashes = {relativo(caminho): sha(blob)}

    def ler(nome, digest):
        b = interno(nome).read_bytes()
        if sha(b) != digest:
            raise ValueError(f"Arquivo alterado: {nome}.")
        hashes[nome] = digest
        return b

    origens = {nome: ler(o["arquivo"], o["sha256"]) for nome, o in p["origens"].items()}
    m0 = carregar_json(origens["round0_execucao.json"])
    if (m0["situacao"] != "concluida" or m0["avaliacoes_concluidas"] != 48
            or m0["criterios"] != CRITERIOS or sha(origens["round0_codigo.zip"]) != m0["codigo"]["sha256_zip"]):
        raise ValueError("Round0 de referência incompleto ou incompatível.")
    codigo = {nome: interno(nome).read_bytes() for nome in FONTES}
    for nome, digest in m0["codigo"]["sha256_arquivos"].items():
        if nome not in codigo or sha(codigo[nome]) != digest:
            raise ValueError(f"Código de referência mudou: {nome}. Revisar controles antes de executar.")
    deps = dependencias()
    for nome in ("numpy", "opencv", "scipy", "scikit-image"):
        if deps[nome] != m0["dependencias"][nome]:
            raise ValueError(f"Versão de {nome} difere do round0 ({m0['dependencias'][nome]}).")
    for fonte in p["fontes_controles"]:
        origens[fonte["copia"]] = ler(fonte["arquivo"], fonte["sha256"])
    entradas = []
    for q in p["quadros"]:
        imagem = ler(q["imagem"], q["imagem_sha256"])
        anotacao = ler(q["anotacao"], q["anotacao_sha256"])
        entrada = {"quadro": q, "imagem_bytes": imagem, "anotacao_bytes": anotacao,
                   "anotacoes": ler_anotacoes(anotacao)}
        decodificar(entrada)  # Validação de formato; nenhum detector é chamado.
        entradas.append(entrada)
    return {"plano": p, "plano_bytes": blob, "entradas": entradas, "origens": origens,
            "hashes": hashes, "codigo": codigo, "dependencias": deps}


def ordenar_por_f1(resumos):
    def fracao(r):
        tp, fp, fn = (int(r[f"{x}_individuos"]) for x in ("tp", "fp", "fn"))
        denominador = 2 * tp + fp + fn
        return Fraction(2 * tp, denominador) if denominador else None

    ordenados = sorted(resumos, key=lambda r: (fracao(r) is None, -(fracao(r) or 0), r["configuracao_id"]))
    anterior, posto = None, None
    ranking = []
    for i, r in enumerate(ordenados, 1):
        valor = fracao(r)
        if valor is not None and (posto is None or valor != anterior):
            posto = i
        ranking.append({"posicao": posto if valor is not None else None, **r})
        anterior = valor
    return ranking


def resumo(item, locais, avaliacoes, **identificacao):
    return {"configuracao_id": item["id"], **identificacao, "quantidade_quadros": len(locais),
            **{k: sum(x[k] for x in locais) for k in DIAGNOSTICO}, **colunas_metricas(agregar(avaliacoes))}


def conferir_controle(item, q, destino, fontes, referencia="round0"):
    esperados = [f for f in fontes if (f["configuracao_id"], f["video_id"], f["quadro"])
                 == (item["id"], q["video_id"], q["quadro"])]
    if not esperados:
        return None
    if {f["nome"] for f in esperados} != set(ARQUIVOS_CONTROLE) or len(esperados) != 4:
        raise ValueError("Referência de controle incompleta.")
    obtidos = {f["nome"]: sha((destino / f["nome"]).read_bytes()) for f in esperados}
    if any(obtidos[f["nome"]] != f["sha256"] for f in esperados):
        raise ValueError(f"Controle {item['id']}/{q['video_id']}/{q['quadro']} diverge do {referencia}. Saídas preservadas.")
    return {"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"],
            "situacao": "identico", "sha256": obtidos}


def nome_configuracao(item, config, instante):
    s = config.segmentacao
    limiar = f"manual{s.limiar_manual}" if s.metodo == "manual" else "otsu"
    politica = "preservar" if config.politica_aglomerados == "preservar_por_area" else "separar"
    return (f"{item['id']}__{limiar}-{s.polaridade}-s{config.fracao_semente:g}-{politica}"
            f"-amin{s.area_minima:g}__cfg-{item['parametros_sha256'][:12]}__{instante}")


def processar(dados, *, saida=None, ler_config=None, executar_quadro=None, nome_config=None,
              relatorio=None, referencia="round0"):
    """Executa entradas já conferidas; separado da leitura para testes sintéticos."""
    from algoritmos.classicos.watershed import configuracao_de_dict
    saida = SAIDA if saida is None else saida
    ler_config = configuracao_de_dict if ler_config is None else ler_config
    executar_quadro = inspecao.executar_quadro if executar_quadro is None else executar_quadro
    nome_config = nome_configuracao if nome_config is None else nome_config
    p = dados["plano"]
    instante = agora().strftime("%Y%m%dT%H%M%S%fZ")
    pasta = (saida / f"batch__{instante}").resolve()
    if not pasta.is_relative_to(RAIZ.resolve()) or pasta.parent != saida.resolve():
        raise ValueError("Saída fora da pasta da rodada.")
    pasta.mkdir(parents=True, exist_ok=False)
    m = {"versao": 1, "algoritmo": "watershed", "rodada": p["rodada"], "etapa": p.get("etapa", "desenvolvimento"),
         "situacao": "em_andamento", "criterios": CRITERIOS, "seed": p["seed"],
         "aleatoriedade": p.get("uso_seed", "seed do desenho experimental; detector determinístico"),
         "inicio_utc": agora().isoformat(), "configuracoes_previstas": len(p["configuracoes"]),
         "quadros_por_configuracao": len(p["quadros"]), "configuracoes_concluidas": 0,
         "avaliacoes_concluidas": 0, "origens_sha256": dados["hashes"], "plano_sha256": sha(dados["plano_bytes"]),
         "execucoes": [], "dependencias": dados["dependencias"]}
    try:
        gravar_json(pasta / "execucao.json", m)
        (pasta / "plano.json").write_bytes(dados["plano_bytes"])
        for nome, blob in dados["origens"].items():
            alvo = (pasta / "origens" / nome).resolve()
            if not alvo.is_relative_to(pasta / "origens"):
                raise ValueError("Cópia de origem fora da pasta permitida.")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with alvo.open("xb") as f:
                f.write(blob)
        m["codigo"] = arquivar_codigo(pasta, dados["codigo"])
        resumos, videos, linhas, controles = [], [], [], []
        for item in p["configuracoes"]:
            config = ler_config(item["parametros"])
            nome = nome_config(item, config, instante)
            destino = pasta / nome
            destino.mkdir()
            gravar_json(destino / "configuracao.json", item["parametros"])
            avaliacoes, locais = [], []
            por_video = defaultdict(list)
            for i, entrada in enumerate(dados["entradas"], 1):
                q = entrada["quadro"]
                m["em_processamento"] = {"configuracao_id": item["id"], "video_id": q["video_id"], "quadro": q["quadro"]}
                quadro = destino / "quadros" / f"{q['video_id']}_frame_{q['quadro']}"
                linha, a = executar_quadro(decodificar(entrada), item, config, quadro)
                verificado = conferir_controle(item, q, quadro, p["fontes_controles"], referencia)
                if verificado:
                    controles.append(verificado)
                linhas.append(linha); locais.append(linha); avaliacoes.append(a)
                por_video[q["video_id"]].append((linha, a))
                m["avaliacoes_concluidas"] += 1
                if i % 20 == 0:
                    gravar_json(pasta / "execucao.json", m)
                    print(f"{item['id']}: {i}/{len(p['quadros'])} quadros.", flush=True)
            gravar_json(destino / "avaliacao.json", agregar(avaliacoes))
            resumos.append(resumo(item, locais, avaliacoes, pasta_origem=relativo(destino)))
            for v, pares in por_video.items():
                videos.append(resumo(item, [x[0] for x in pares], [x[1] for x in pares], video_id=v))
            m["configuracoes_concluidas"] += 1
            m["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(destino)})
            gravar_json(pasta / "controles.json", {"casos_conferidos": len(controles), "casos": controles})
            gravar_json(pasta / "execucao.json", m)
            print(f"{item['id']}: concluída ({m['configuracoes_concluidas']}/{len(p['configuracoes'])}).", flush=True)
        if len(controles) * 4 != len(p["fontes_controles"]):
            raise ValueError("Nem todos os controles foram reproduzidos.")
        for nome, tabela in (("resumo_por_quadro.csv", linhas), ("resumo_configuracoes.csv", resumos),
                             ("resumo_por_video.csv", videos), ("ranking.csv", ordenar_por_f1(resumos))):
            gravar_csv(pasta / nome, list(tabela[0]), tabela)
        print("Conferindo e registrando integridade das saídas...", flush=True)
        m["saidas_sha256"] = {relativo(f): sha(f.read_bytes()) for f in sorted(pasta.rglob("*"))
                              if f.is_file() and f != pasta / "execucao.json"}
        m.pop("em_processamento", None)
        m.update(situacao="concluida", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", m)
    except BaseException as erro:
        m.update(situacao="interrompida" if isinstance(erro, KeyboardInterrupt) else "falhou",
                 erro=f"{type(erro).__name__}: {erro}", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", m)
        raise
    from analise.relatorio_rodada_watershed import gerar_relatorio
    gerar_relatorio = gerar_relatorio if relatorio is None else relatorio
    try:
        print(f"PDF: {gerar_relatorio(pasta)}", flush=True)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {"situacao": "falhou", "erro": str(erro)})
        print(f"Métricas concluídas; falha no PDF: {erro}. Use --somente-relatorio.", file=sys.stderr)
    return pasta


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rodadas reproduzíveis de desenvolvimento de watershed.")
    parser.add_argument("--rodada", choices=["round1", "round2", "round3", "round4", "round5"], default="round1")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--conferir", action="store_true", help="Confere entradas sem executar o detector.")
    grupo.add_argument("--somente-relatorio", type=Path, metavar="BATCH")
    args = parser.parse_args(argv)
    try:
        if args.rodada == "round5":
            from scripts.watershed.execucao_round5 import executar_argumentos
            return executar_argumentos(args)
        if args.rodada == "round4":
            from scripts.watershed.execucao_round4 import executar_argumentos
            return executar_argumentos(args)
        if args.rodada == "round3":
            from scripts.watershed.execucao_round3 import executar_argumentos
            return executar_argumentos(args)
        if args.rodada == "round2":
            from scripts.watershed.execucao_round2 import executar_argumentos
            return executar_argumentos(args)
        if args.somente_relatorio:
            from analise.relatorio_rodada_watershed import gerar_relatorio
            print(gerar_relatorio(args.somente_relatorio))
        else:
            print("Conferindo plano, origens, controles e dependências...", flush=True)
            dados = congelar_entradas()
            if args.conferir:
                print(f"Conferência concluída: 48 configurações, 178 imagens, {len(dados['hashes'])} origens íntegras. Detector não executado.")
            else:
                print(f"Rodada concluída: {processar(dados)}")
        return 0
    except KeyboardInterrupt:
        print("Execução interrompida; arquivos parciais preservados.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
