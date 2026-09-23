"""Avalia as cinco configurações congeladas nos vídeos completos de seleção."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import csv
import math
from pathlib import Path
import sys
from time import perf_counter_ns

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar
from algoritmos.classicos.variantes_watershed import inspecionar
from scripts.watershed import executar_rodada as rodada
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import CAMPOS_METRICAS, colunas_metricas
from scripts.limiarizacao.inspecionar_imagem import CAMPOS_DETECCAO, CAMPOS_ANOTACAO
from scripts.watershed.planejamento import sha
from scripts.watershed.planejamento_selecao import igual, ler_configuracao
from scripts.watershed.executar_selecao import FONTES as FONTES_SELECAO, nome_configuracao
from scripts.watershed.planejamento_videos import carregar_plano, caminhos_origens, conferir_origens
from scripts.limiarizacao import executar_videos as video_base

SAIDA = RAIZ / "resultados/videos/watershed/selecao"
PLANO_PADRAO = "scripts/watershed/videos/plano_selecao.json"
FONTES_CODIGO = tuple(dict.fromkeys((*FONTES_SELECAO, *video_base.FONTES_CODIGO,
    "scripts/watershed/executar_videos.py", "scripts/watershed/planejamento_videos.py",
    "analise/relatorio_videos_watershed.py",
)))
CAMPOS_ORIGEM = video_base.CAMPOS_ORIGEM
CAMPOS_SEGMENTACAO = ["limiar_otsu_original", "deslocamento_otsu", "limiar_efetivo",
    "pixels_mascara", "pixels_imagem", "fracao_pixels_mascara"]
CAMPOS_QUADRO = ["imagem_largura_px", "imagem_altura_px", "quantidade_anotacoes",
    "quantidade_deteccoes", "tempo_decodificador_segundos",
    *rodada.DIAGNOSTICO, *CAMPOS_SEGMENTACAO, *CAMPOS_METRICAS]


def relativo(caminho: Path) -> str:
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def fonte(nome: str) -> Path:
    return rodada.interno(nome)


def especificacao_etapa(etapa: str) -> dict:
    if etapa == "selecao":
        return {"saida": SAIDA, "plano": RAIZ / PLANO_PADRAO, "tipo": "videos_selecao_watershed",
                "etapa": "selecao_videos", "particao": "selecao",
                "interpretacao": "Vídeos completos de seleção; parâmetros congelados. Não é avaliação final independente."}
    raise ValueError("Apenas os vídeos de seleção estão preparados.")


def conferir_etapa(plano: dict, especificacao: dict) -> None:
    if any(plano.get(c) != especificacao[c] for c in ("tipo", "etapa", "particao")):
        raise ValueError("Plano incompatível com a etapa de vídeos solicitada.")


def congelar_entradas(caminho_plano: Path, etapa: str = "selecao") -> dict:
    """Confere todas as fontes e captura anotações/código antes de criar saídas."""
    caminho = Path(caminho_plano).expanduser().resolve(strict=True)
    if not caminho.is_relative_to(RAIZ.resolve()) or not caminho.is_file():
        raise ValueError("O plano deve ser um arquivo dentro do projeto.")
    especificacao = especificacao_etapa(etapa)
    conteudo = caminho.read_bytes()
    plano = carregar_plano(conteudo)
    conferir_etapa(plano, especificacao)
    origens = conferir_origens(plano, RAIZ)
    caminhos = caminhos_origens(plano)
    hashes = {relativo(caminho): sha(conteudo)}
    hashes.update({caminhos[n]: sha(b) for n, b in origens.items()})
    anotacoes = {}
    for video in plano["videos"]:
        print(f"Conferindo arquivos do vídeo {video['video_id']}...", flush=True)
        for item in [video, *video["referencias_alinhamento"]]:
            nome = item.get("arquivo", item.get("imagem"))
            digest = video_base.hash_arquivo(fonte(nome))
            if digest != item["sha256"]:
                raise ValueError(f"Hash divergente: {nome}.")
            hashes[nome] = digest
        for anotacao in video["anotacoes"]:
            nome = anotacao["arquivo"]
            blob = fonte(nome).read_bytes()
            digest = sha(blob)
            if digest != anotacao["sha256"]:
                raise ValueError(f"Hash divergente: {nome}.")
            hashes[nome] = digest
            anotacoes[(video["video_id"], anotacao["quadro"])] = rodada.ler_anotacoes(blob)
    codigo = {nome: fonte(nome).read_bytes() for nome in FONTES_CODIGO}
    anterior = rodada.carregar_json(origens["execucao_selecao"])
    for nome, digest in anterior["codigo"]["sha256_arquivos"].items():
        if nome not in codigo or sha(codigo[nome]) != digest:
            raise ValueError(f"Código da seleção modificado: {nome}. Rever antes de executar.")
    return {"plano": plano, "plano_bytes": conteudo, "origens": origens,
            "hashes": hashes, "anotacoes": anotacoes, "codigo": codigo}


def conferir_ambiente(dados: dict) -> dict:
    """Valida bibliotecas, parâmetros e metadados sem detectar ou percorrer frames."""
    import cv2
    deps = rodada.dependencias()
    anterior = rodada.carregar_json(dados["origens"]["execucao_selecao"])
    for nome in ("python", "numpy", "opencv", "scipy", "scikit-image"):
        igual(deps[nome], anterior["dependencias"][nome], "dependência " + nome)
    for item in dados["plano"]["configuracoes"]:
        ler_configuracao(item["parametros"])
    ambiente = {"dependencias": deps}
    for video in dados["plano"]["videos"]:
        captura = video_base.abrir_video(video, cv2)
        try:
            for propriedade, valor in ((cv2.CAP_PROP_FRAME_WIDTH, video["largura"]),
                                       (cv2.CAP_PROP_FRAME_HEIGHT, video["altura"]),
                                       (cv2.CAP_PROP_FRAME_COUNT, video["quantidade_quadros"])):
                atual = captura.get(propriedade)
                if not math.isfinite(atual) or not math.isclose(atual, valor, rel_tol=0, abs_tol=1e-6):
                    raise ValueError(f"Metadados incompatíveis no vídeo {video['video_id']}.")
        finally:
            captura.release()
    return ambiente


def processar_quadro(imagem, config):
    """Mesma chamada, caixas e medidas da seleção em imagens."""
    inicio = perf_counter_ns()
    d, metadados = inspecionar(imagem, config)
    tempo = perf_counter_ns() - inicio
    registros = list(d.resultado.registros())
    diagnostico = {
        "componentes": len(d.componentes_info),
        "sementes": sum(x["sementes"] for x in d.componentes_info),
        "componentes_preservados": sum(x["preservado_por_area"] for x in d.componentes_info),
        "regioes_candidatas": len(d.candidatos), "deteccoes": len(registros),
        "rejeitadas_area": len(d.candidatos) - len(registros), "tempo_detector_ns": tempo,
    }
    return registros, {**diagnostico, **metadados}


def abrir_tabelas(pasta: Path, pilha: ExitStack) -> dict:
    campos = {
        "deteccoes": CAMPOS_DETECCAO,
        "anotacoes": CAMPOS_ANOTACAO, "por_quadro": CAMPOS_QUADRO,
        "pares": video_base.CAMPOS_PARES, "pendentes": video_base.CAMPOS_PENDENTES,
    }
    tabelas = {}
    for nome, colunas in campos.items():
        arquivo = pilha.enter_context((pasta / f"{nome}.csv").open("x", encoding="utf-8-sig", newline=""))
        tabelas[nome] = csv.DictWriter(arquivo, fieldnames=[*CAMPOS_ORIGEM, *colunas])
        tabelas[nome].writeheader()
    return tabelas


def salvar_pendentes(tabela, origem, avaliacao, reais, previsoes):
    for tipo, campo, linhas, indice in (("FN", "anotacoes_sem_par", reais, "indice_anotacao"),
                                      ("FP", "deteccoes_sem_par", previsoes, "indice_deteccao")):
        mapa = {r[indice]: r for r in linhas}
        for numero in avaliacao[campo]:
            r = mapa[numero]
            tabela.writerow({**origem, "tipo": tipo, "indice": numero, "classe": r["classe"],
                "grupo": "aglomerados" if r["classe"] == 1 else "individuos",
                **{c: r[c] for c in video_base.CAMPOS_CAIXA}})


def atualizar_relatorio(pasta: Path) -> Path:
    from analise.relatorio_videos_watershed import gerar_relatorio
    pasta = Path(pasta).expanduser().resolve(strict=True)
    if (pasta.parent != SAIDA.resolve()
            or not pasta.is_relative_to(RAIZ.resolve()) or not pasta.name.startswith("batch__")):
        raise ValueError("Informe uma pasta batch dos vídeos de seleção de watershed.")
    try:
        pdf = gerar_relatorio(pasta)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {"situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}"})
        raise
    gravar_json(pasta / "relatorio.json", {"situacao": "concluido", "arquivo": relativo(pdf)})
    return pdf


def executar_configuracao(item: dict, plano: dict, pasta: Path, anotacoes_salvas: dict,
                          metadados: dict, pixels_conferidos: dict, ambiente: dict,
                          cv2, np) -> tuple[dict, list[dict]]:
    config = ler_configuracao(item["parametros"])
    pasta.mkdir(exist_ok=False)
    (pasta / "midia").mkdir()
    identificador = item["id"]
    registro = {**metadados, "situacao": "em_andamento", "configuracao_id": identificador,
                "configuracao_sha256": item["parametros_sha256"],
                "inicio_utc": rodada.agora().isoformat(), "quadros_concluidos": 0, "videos": []}
    linhas, avaliacoes, resumos_video, totais_video = [], [], [], {}
    try:
        gravar_json(pasta / "execucao.json", registro)
        gravar_json(pasta / "configuracao.json", item)
        with ExitStack() as pilha:
            tabelas = abrir_tabelas(pasta, pilha)
            for video in plano["videos"]:
                video_id = video["video_id"]
                captura = video_base.abrir_video(video, cv2)
                caminho_video = pasta / "midia" / f"{identificador}__cfg-{item['parametros_sha256'][:12]}__video-{video_id}.mp4"
                escritor, numero = None, 0
                linhas_video, avaliacoes_video = [], []
                try:
                    escritor = cv2.VideoWriter(str(caminho_video), cv2.VideoWriter_fourcc(*"mp4v"),
                                              video["fps"], (video["largura"] * 2, video["altura"] + 104))
                    if not escritor.isOpened():
                        raise ValueError("Não foi possível iniciar a gravação MP4 (codec mp4v).")
                    while True:
                        sucesso, imagem = captura.read()
                        if not sucesso:
                            break
                        if numero >= video["quantidade_quadros"]:
                            raise ValueError("O vídeo contém quadros extras.")
                        video_base.conferir_quadro(imagem, video)
                        if sha(imagem.tobytes()) != pixels_conferidos[(video_id, numero)]:
                            raise ValueError(f"Pixels decodificados divergentes da conferência: {video_id}/{numero}.")
                        origem = {"video": video["arquivo"], "anotacao": video["anotacoes"][numero]["arquivo"],
                                  "video_id": video_id, "quadro": numero, "tempo_segundos": numero / video["fps"]}
                        reais = video_base.caixas_anotadas(anotacoes_salvas[(video_id, numero)], video["largura"], video["altura"])
                        previsoes, tempos = processar_quadro(imagem, config)
                        resultado = avaliar(video_base.objetos(reais, "indice_anotacao"),
                                            video_base.objetos(previsoes, "indice_deteccao"))
                        avaliacoes_video.append({c: resultado[c] for c in (
                            "criterios", "por_grupo", "cobertura_por_classe", "classificacao_individuos")})
                        linhas_video.append(tempos)
                        tabelas["deteccoes"].writerows({**origem, **r} for r in previsoes)
                        tabelas["anotacoes"].writerows({**origem, **r} for r in reais)
                        tabelas["pares"].writerows({**origem, **r} for r in resultado["pares"])
                        salvar_pendentes(tabelas["pendentes"], origem, resultado, reais, previsoes)
                        tempo_decoder = captura.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        if not math.isfinite(tempo_decoder) or tempo_decoder < 0:
                            tempo_decoder = None
                        tabelas["por_quadro"].writerow({**origem, "imagem_largura_px": video["largura"],
                            "imagem_altura_px": video["altura"], "quantidade_anotacoes": len(reais),
                            "quantidade_deteccoes": len(previsoes), "tempo_decodificador_segundos": tempo_decoder,
                            **tempos, **colunas_metricas(resultado)})
                        escritor.write(video_base.painel_comparativo(imagem, reais, previsoes, video, numero,
                            identificador, "watershed", resultado["por_grupo"]["individuos"], cv2, np))
                        numero += 1
                        registro["quadros_concluidos"] += 1
                        if numero % 250 == 0:
                            gravar_json(pasta / "execucao.json", registro)
                            print(f"{identificador}, vídeo {video_id}: {numero}/{video['quantidade_quadros']} quadros", flush=True)
                finally:
                    captura.release()
                    if escritor is not None:
                        escritor.release()
                if numero != video["quantidade_quadros"]:
                    raise ValueError(f"Vídeo {video_id} terminou antes do quadro previsto.")
                registro["videos"].append({"video_id": video_id,
                    **video_base.conferir_video_gravado(caminho_video, video, cv2)})
                gravar_json(pasta / "execucao.json", registro)
                linhas.extend(linhas_video)
                avaliacoes.extend(avaliacoes_video)
                totais_video[video_id] = agregar(avaliacoes_video)
                resumos_video.append(rodada.resumo(item, linhas_video, avaliacoes_video,
                    pasta_origem=relativo(pasta), video_id=video_id))
        total = rodada.resumo(item, linhas, avaliacoes, pasta_origem=relativo(pasta),
            bloco=item["bloco"])
        gravar_json(pasta / "avaliacao.json", {"criterios": CRITERIOS, "total": agregar(avaliacoes),
                                              "por_video": totais_video})
        rodada.gravar_csv(pasta / "resumo.csv", list(total), [total])
        rodada.gravar_csv(pasta / "resumo_por_video.csv", list(resumos_video[0]), resumos_video)
        registro.update(situacao="concluida", fim_utc=rodada.agora().isoformat())
        gravar_json(pasta / "execucao.json", registro)
    except BaseException as erro:
        registro.update(situacao="falhou", fim_utc=rodada.agora().isoformat(), erro=f"{type(erro).__name__}: {erro}")
        gravar_json(pasta / "execucao.json", registro)
        raise
    return total, resumos_video


def executar(caminho_plano: Path, etapa: str = "selecao") -> Path:
    dados = congelar_entradas(caminho_plano, etapa)
    ambiente = conferir_ambiente(dados)
    return processar(dados, ambiente, etapa)


def processar(dados, ambiente, etapa="selecao"):
    """Executa entradas conferidas; também permite integração com mídia sintética."""
    import cv2
    import numpy as np
    especificacao = especificacao_etapa(etapa)
    conferir_etapa(dados["plano"], especificacao)
    plano = dados["plano"]
    inicio = rodada.agora()
    identificador = inicio.strftime("%Y%m%dT%H%M%S%fZ")
    saida = especificacao["saida"].resolve()
    if not saida.is_relative_to(RAIZ.resolve()):
        raise ValueError("Destino fora do projeto.")
    pasta = saida / f"batch__{identificador}"
    manifesto = {
        "versao": 1, "tipo": especificacao["tipo"], "algoritmo": "watershed", "etapa": especificacao["etapa"],
        "particao": etapa, "situacao": "em_andamento", "inicio_utc": inicio.isoformat(),
        "criterios": CRITERIOS, "plano_sha256": sha(dados["plano_bytes"]),
        "origens_sha256": dados["hashes"], "configuracoes_previstas": len(plano["configuracoes"]),
        "configuracoes_concluidas": 0, "quadros_por_configuracao": sum(v["quantidade_quadros"] for v in plano["videos"]),
        "videos_por_configuracao": len(plano["videos"]),
        "videos_previstos": len(plano["configuracoes"]) * len(plano["videos"]),
        "videos_concluidos": 0, "avaliacoes_concluidas": 0, "alinhamento_conferido": False,
        "execucoes": [], "saidas_sha256": {}, **ambiente, "seed": plano["seed"],
        "aleatoriedade_utilizada": False, "registro_relatorio": "relatorio.json",
        "pasta_origens": "origens",
        "interpretacao": especificacao["interpretacao"],
        "identidade_objetos": "Índices locais por quadro; sem rastreamento, trajetórias ou velocidade.",
        "medidas": "Caixas XYWH/YOLO, área segmentada, centroide, perímetro e forma por região; índices locais.",
        "tempo_segundos": "Índice base zero dividido pelo FPS CFR do MP4; tempo relativo ao clipe.",
        "unidades": {"comprimento": "pixel", "area_segmentada": "pixel quadrado", "tempos": "nanossegundo"},
    }
    pasta.mkdir(parents=True, exist_ok=False)
    try:
        gravar_json(pasta / "execucao.json", manifesto)
        (pasta / "plano.json").write_bytes(dados["plano_bytes"])
        caminhos = caminhos_origens(plano)
        pasta_origens = pasta / "origens"
        pasta_origens.mkdir()
        for nome, blob in dados["origens"].items():
            (pasta_origens / f"{nome}{Path(caminhos[nome]).suffix}").write_bytes(blob)
        manifesto["codigo"] = rodada.arquivar_codigo(pasta, dados["codigo"])
        gravar_json(pasta / "execucao.json", manifesto)
        print("Conferindo alinhamento e integridade da sequência de frames...", flush=True)
        conferencia = video_base.conferir_alinhamento(plano, pasta / "conferencia", cv2, np)
        manifesto["alinhamento_conferido"] = True
        gravar_json(pasta / "execucao.json", manifesto)
        resumos, videos = [], []
        for numero, item in enumerate(plano["configuracoes"], 1):
            nome = nome_configuracao(item, ler_configuracao(item["parametros"]), identificador)
            pasta_config = pasta / nome
            print(f"Vídeos | {etapa} | configuração {numero}/{len(plano['configuracoes'])}: {nome}", flush=True)
            total, por_video = executar_configuracao(item, plano, pasta_config, dados["anotacoes"],
                {"tipo": especificacao["tipo"], "particao": etapa, "criterios": CRITERIOS,
                 "plano_sha256": manifesto["plano_sha256"], "batch": relativo(pasta)},
                conferencia["pixels_sha256"], ambiente, cv2, np)
            resumos.append(total)
            videos.extend(por_video)
            rodada.gravar_csv(pasta / "resumo_configuracoes.csv", list(resumos[0]), resumos)
            rodada.gravar_csv(pasta / "resumo_por_video.csv", list(videos[0]), videos)
            ranking = rodada.ordenar_por_f1(resumos)
            rodada.gravar_csv(pasta / "ranking.csv", list(ranking[0]), ranking)
            manifesto["configuracoes_concluidas"] += 1
            manifesto["avaliacoes_concluidas"] += total["quantidade_quadros"]
            manifesto["videos_concluidos"] += len(plano["videos"])
            manifesto["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(pasta_config)})
            gravar_json(pasta / "execucao.json", manifesto)
        for nome, esperado in dados["hashes"].items():
            if video_base.hash_arquivo(fonte(nome)) != esperado:
                raise ValueError(f"Fonte modificada durante a execução: {nome}.")
        print("Registrando integridade dos vídeos e tabelas...", flush=True)
        manifesto["saidas_sha256"] = {relativo(p): video_base.hash_arquivo(p) for p in sorted(pasta.rglob("*"))
            if p.is_file() and p != pasta / "execucao.json"}
        manifesto.update(situacao="concluida", fim_utc=rodada.agora().isoformat())
        gravar_json(pasta / "execucao.json", manifesto)
    except BaseException as erro:
        manifesto.update(situacao="falhou", fim_utc=rodada.agora().isoformat(), erro=f"{type(erro).__name__}: {erro}")
        gravar_json(pasta / "execucao.json", manifesto)
        print(f"Execução incompleta preservada em: {pasta}", file=sys.stderr)
        raise
    try:
        print(f"Relatório: {atualizar_relatorio(pasta)}", flush=True)
    except Exception as erro:
        print(f"Vídeos e métricas concluídos; falha apenas no PDF: {erro}\n"
              f'Gere novamente com --somente-relatorio "{pasta}".', file=sys.stderr)
    return pasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia as cinco configurações congeladas nos vídeos de seleção de watershed.")
    parser.add_argument("--etapa", choices=("selecao",), default="selecao")
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--plano", type=Path)
    origem.add_argument("--somente-relatorio", type=Path, metavar="BATCH")
    parser.add_argument("--conferir", action="store_true", help="Confere arquivos e metadados sem executar detecção nem criar resultados.")
    args = parser.parse_args(argv)
    if args.conferir and args.somente_relatorio:
        parser.error("--conferir e --somente-relatorio não podem ser combinados.")
    caminho_plano = args.plano or especificacao_etapa(args.etapa)["plano"]
    try:
        if args.somente_relatorio:
            print(f"Relatório: {atualizar_relatorio(args.somente_relatorio)}")
        elif args.conferir:
            dados = congelar_entradas(caminho_plano, args.etapa)
            conferir_ambiente(dados)
            plano = dados["plano"]
            quadros = sum(v["quantidade_quadros"] for v in plano["videos"])
            print(f"Conferência concluída: {len(plano['configuracoes'])} configurações, {len(plano['videos'])} vídeos, "
                  f"{quadros} quadros/configuração, {quadros * len(plano['configuracoes'])} avaliações previstas.")
            print("Alinhamento e decodificação completa serão conferidos na execução. Nenhum resultado criado.")
        else:
            print(f"Execução concluída em: {executar(caminho_plano, args.etapa)}")
    except (ValueError, OSError, RuntimeError, ImportError, KeyError, TypeError, csv.Error) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

