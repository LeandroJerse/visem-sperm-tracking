"""Round0 de watershed: diagnóstico reproduzível, sem seleção de finalistas."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import sys
from time import perf_counter_ns

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import (
    FONTES_CODIGO as FONTES_INSPECAO_BLOBS,
    arquivar_codigo, carregar_json, colunas_metricas, congelar_entradas as congelar_blobs,
    hash_configuracao, objetos, preparar_imagens, caminho_interno,
)
from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, CAMPOS_ORIGEM, agora, desenhar_painel,
    gravar_csv, identificar_origem, sha256,
)

PLANO = RAIZ / "scripts/watershed/inspecao/round0.json"
SAIDA = RAIZ / "resultados/frame-to-frame/watershed/round0"
FONTES = (
    "algoritmos/__init__.py", "algoritmos/classicos/__init__.py", "analise/__init__.py",
    "algoritmos/classicos/watershed.py", "algoritmos/classicos/limiarizacao.py",
    "algoritmos/classicos/comum.py", "algoritmos/classicos/classificacao.py",
    "algoritmos/classicos/requirements.txt", "algoritmos/classicos/requirements-watershed.txt",
    "analise/avaliacao_deteccao.py", "analise/avaliacao_individuos.py",
    "analise/requirements.txt", "analise/requirements-relatorio.txt",
    "analise/relatorio_inspecao_watershed.py", "analise/relatorio_inspecao_blobs.py",
    "scripts/watershed/executar_inspecao.py", "scripts/blobs/executar_inspecao.py",
    "scripts/blobs/arquivos.py", "scripts/limiarizacao/inspecionar_imagem.py",
)
FONTES = tuple(dict.fromkeys((*FONTES, *FONTES_INSPECAO_BLOBS)))


def relativo(p):
    return p.resolve().relative_to(RAIZ.resolve()).as_posix()


def congelar_entradas(caminho=PLANO):
    from algoritmos.classicos.watershed import configuracao_de_dict
    caminho = Path(caminho).resolve(strict=True)
    if not caminho.is_relative_to(RAIZ.resolve()):
        raise ValueError("Plano fora do projeto.")
    blob = caminho.read_bytes()
    plano = carregar_json(blob)
    fixos = {"versao": 1, "algoritmo": "watershed", "rodada": "round0",
             "particao": "desenvolvimento", "seed": 42, "criterios": CRITERIOS}
    if any(plano.get(k) != v or type(plano.get(k)) is not type(v) for k, v in fixos.items()):
        raise ValueError("Plano não corresponde à inspeção acordada.")
    origem = plano["origem_inspecao_blobs"]
    base_path = caminho_interno(origem["arquivo"])
    if sha256(base_path.read_bytes()) != origem["sha256"]:
        raise ValueError("A inspeção de origem foi alterada.")
    base = congelar_blobs(base_path)
    if plano["quadros"] != base["plano"]["quadros"]:
        raise ValueError("Devem ser preservados os seis quadros da inspeção de desenvolvimento.")
    config_origem = plano["origem_parametros"]
    origem_bytes = caminho_interno(config_origem["arquivo"]).read_bytes()
    if sha256(origem_bytes) != config_origem["sha256"]:
        raise ValueError("A referência de parâmetros foi alterada.")
    configs = plano["configuracoes"]
    if [c["id"] for c in configs] != [f"w{i:02}" for i in range(1, 9)]:
        raise ValueError("Round0 deve conter w01 a w08, na ordem acordada.")
    combinacoes = set()
    referencia = carregar_json(origem_bytes)
    parametros_base = next(c["parametros"] for c in referencia["configuracoes"]
                           if c["id"] == config_origem["configuracao_id"])
    for item in configs:
        c = configuracao_de_dict(item["parametros"])
        esperado_base = {**parametros_base, "area_minima": 3, "polaridade": c.segmentacao.polaridade}
        if asdict(c.segmentacao) != esperado_base:
            raise ValueError("Round0 deve manter a base de desenvolvimento e as alterações declaradas.")
        combinacoes.add((c.segmentacao.polaridade, c.fracao_semente, c.politica_aglomerados))
        if asdict(c) != item["parametros"]:
            raise ValueError("Parâmetros não preservados pelo parser.")
    esperadas = {(p, f, g) for p in ("claro", "escuro") for f in (.5, .75)
                 for g in ("separar", "preservar_por_area")}
    if combinacoes != esperadas:
        raise ValueError("A inspeção exige os oito cruzamentos previstos.")
    base["hashes"].update({relativo(caminho): sha256(blob), config_origem["arquivo"]: sha256(origem_bytes)})
    return {"plano": plano, "plano_bytes": blob, "entradas": base["entradas"],
            "hashes": base["hashes"], "origens": {"inspecao_blobs.json": base["plano_bytes"],
            "desenvolvimento.json": base["origem_bytes"], "parametros_desenvolvimento.json": origem_bytes},
            "codigo": {nome: caminho_interno(nome).read_bytes() for nome in FONTES}}


def gravar_png(caminho, imagem, cv2):
    ok, dados = cv2.imencode(".png", imagem)
    if not ok:
        raise ValueError("Falha ao codificar PNG.")
    with caminho.open("xb") as f:
        f.write(dados.tobytes())


def executar_quadro(entrada, item, config, pasta):
    import cv2
    import numpy as np
    from algoritmos.classicos.watershed import inspecionar
    imagem, anotacoes, q = entrada["imagem"], entrada["anotacoes"], entrada["quadro"]
    pasta.mkdir(parents=True, exist_ok=False)
    origem = identificar_origem(Path(q["imagem"]), Path(q["anotacao"]))
    origem.update(imagem=q["imagem"], anotacao=q["anotacao"])
    inicio = perf_counter_ns()
    d = inspecionar(imagem, config)
    tempo = perf_counter_ns() - inicio
    registros = list(d.resultado.registros())
    a = avaliar(objetos(anotacoes, "indice_anotacao"), objetos(registros, "indice_deteccao"))
    gravar_json(pasta / "avaliacao.json", a)
    gravar_json(pasta / "diagnostico.json", {"componentes": d.componentes_info, "candidatos": d.candidatos})
    gravar_csv(pasta / "deteccoes.csv", CAMPOS_ORIGEM + CAMPOS_DETECCAO, ({**origem, **r} for r in registros))
    gravar_csv(pasta / "anotacoes.csv", CAMPOS_ORIGEM + CAMPOS_ANOTACAO, ({**origem, **r} for r in anotacoes))
    campos_pares = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao", "iou", "grupo", "classe_correta"]
    gravar_csv(pasta / "pares.csv", campos_pares, a["pares"])
    pendentes = []
    for tipo, lista, chave, indice in (("FN", anotacoes, "anotacoes_sem_par", "indice_anotacao"),
                                      ("FP", registros, "deteccoes_sem_par", "indice_deteccao")):
        por_id = {r[indice]: r for r in lista}
        for idx in a[chave]:
            r = por_id[idx]
            pendentes.append({"tipo": tipo, "indice": idx, "classe": r["classe"],
                              **{k: r[k] for k in ("caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px")}})
    gravar_csv(pasta / "pendentes.csv", ["tipo", "indice", "classe", "caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"], pendentes)
    (pasta / "predicoes.txt").write_text("".join(x + "\n" for x in d.resultado.linhas_yolo()), encoding="utf-8")
    np.savez_compressed(pasta / "mapas.npz", componentes=d.componentes, marcadores=d.marcadores,
                        regioes=d.regioes, distancia=d.distancia, mascara=d.mascara)
    gravar_png(pasta / "mascara.png", d.mascara, cv2)
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
    painel = np.concatenate((desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}"),
                             desenhar_painel(cv2, np, colorida, registros, f"Watershed {item['id']}: {len(registros)}")), axis=1)
    gravar_png(pasta / "comparacao.png", painel, cv2)
    rotulos = d.regioes.astype(np.int64)
    cores = np.stack([(rotulos * fator % 191 + 64).astype(np.uint8) for fator in (53, 97, 137)], axis=-1)
    cores[rotulos == 0] = 0
    sobreposta = cv2.addWeighted(colorida, .5, cores, .5, 0)
    sobreposta[d.marcadores > 0] = (255, 255, 255)
    gravar_png(pasta / "regioes_sementes.png", sobreposta, cv2)
    linha = {"configuracao_id": item["id"], **origem, "pasta_quadro": relativo(pasta),
             "componentes": len(d.componentes_info), "sementes": sum(i["sementes"] for i in d.componentes_info),
             "componentes_preservados": sum(i["preservado_por_area"] for i in d.componentes_info),
             "regioes_candidatas": len(d.candidatos), "deteccoes": len(registros),
             "rejeitadas_area": len(d.candidatos) - len(registros), "tempo_detector_ns": tempo,
             **colunas_metricas(a)}
    return linha, a


def executar(caminho=PLANO):
    import cv2
    import numpy as np
    import scipy
    import skimage
    import reportlab
    from algoritmos.classicos.watershed import configuracao_de_dict
    dados = congelar_entradas(caminho)
    preparar_imagens(dados["entradas"], cv2, np)
    instante = agora().strftime("%Y%m%dT%H%M%S%fZ")
    pasta = (SAIDA / f"batch__{instante}").resolve()
    if not pasta.is_relative_to(RAIZ.resolve()):
        raise ValueError("Saída fora do projeto.")
    pasta.mkdir(parents=True, exist_ok=False)
    m = {"versao": 1, "algoritmo": "watershed", "rodada": "round0", "situacao": "em_andamento",
         "criterios": CRITERIOS, "seed": dados["plano"]["seed"], "aleatoriedade_utilizada": False,
         "inicio_utc": agora().isoformat(), "configuracoes_previstas": 8, "quadros_por_configuracao": 6,
         "configuracoes_concluidas": 0, "avaliacoes_concluidas": 0, "origens_sha256": dados["hashes"],
         "plano_sha256": sha256(dados["plano_bytes"]), "execucoes": [],
         "dependencias": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                          "scipy": scipy.__version__, "scikit-image": skimage.__version__, "reportlab": reportlab.Version}}
    try:
        gravar_json(pasta / "execucao.json", m)
        (pasta / "plano.json").write_bytes(dados["plano_bytes"])
        (pasta / "origens").mkdir()
        for nome, blob in dados["origens"].items():
            (pasta / "origens" / nome).write_bytes(blob)
        m["codigo"] = arquivar_codigo(pasta, dados["codigo"])
        resumos, linhas = [], []
        for item in dados["plano"]["configuracoes"]:
            config = configuracao_de_dict(item["parametros"])
            nome = (f"{item['id']}__otsu-{config.segmentacao.polaridade}-s{config.fracao_semente:g}"
                    f"-{config.politica_aglomerados}__cfg-{hash_configuracao(item['parametros'])[:12]}__{instante}")
            destino = pasta / nome
            destino.mkdir()
            gravar_json(destino / "configuracao.json", item["parametros"])
            avaliacoes, locais = [], []
            for entrada in dados["entradas"]:
                q = entrada["quadro"]
                linha, a = executar_quadro(entrada, item, config, destino / "quadros" / f"{q['video_id']}_frame_{q['quadro']}")
                linhas.append(linha); locais.append(linha); avaliacoes.append(a)
                m["avaliacoes_concluidas"] += 1
                gravar_json(pasta / "execucao.json", m)
            agregado = agregar(avaliacoes)
            gravar_json(destino / "avaliacao.json", agregado)
            resumo = {"configuracao_id": item["id"], "pasta_origem": relativo(destino), "quantidade_quadros": len(locais),
                      **{k: sum(x[k] for x in locais) for k in ("componentes", "sementes", "componentes_preservados",
                         "regioes_candidatas", "deteccoes", "rejeitadas_area", "tempo_detector_ns")}, **colunas_metricas(agregado)}
            resumos.append(resumo)
            m["configuracoes_concluidas"] += 1
            m["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(destino)})
            print(f"{item['id']}: 6/6 imagens concluídas.", flush=True)
        gravar_csv(pasta / "resumo_por_quadro.csv", list(linhas[0]), linhas)
        gravar_csv(pasta / "resumo_configuracoes.csv", list(resumos[0]), resumos)
        m["saidas_sha256"] = {relativo(f): sha256(f.read_bytes()) for f in sorted(pasta.rglob("*"))
                              if f.is_file() and f != pasta / "execucao.json"}
        m.update(situacao="concluida", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", m)
    except BaseException as erro:
        m.update(situacao="falhou", erro=f"{type(erro).__name__}: {erro}", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", m)
        raise
    from analise.relatorio_inspecao_watershed import gerar_relatorio
    try:
        pdf = gerar_relatorio(pasta)
        print(f"PDF: {pdf}")
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {"situacao": "falhou", "erro": str(erro)})
        print(f"Métricas concluídas; falha no PDF: {erro}", file=sys.stderr)
    return pasta


def main(argv=None):
    parser = argparse.ArgumentParser(description="Watershed round0: 8 configurações, 6 imagens; sem ranking.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--conferir", action="store_true", help="Confere entradas e dependências; não executa detector.")
    grupo.add_argument("--somente-relatorio", type=Path, metavar="BATCH")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio:
            from analise.relatorio_inspecao_watershed import gerar_relatorio
            print(gerar_relatorio(args.somente_relatorio))
        elif args.conferir:
            import reportlab
            dados = congelar_entradas()
            print(f"Conferência concluída: 8 configurações, 6 imagens, {len(dados['hashes'])} origens íntegras. Detector não executado.")
        else:
            print(f"Inspeção concluída: {executar()}")
        return 0
    except KeyboardInterrupt:
        print("Execução interrompida; arquivos parciais preservados.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
