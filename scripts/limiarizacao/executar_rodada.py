"""Executa uma rodada congelada de configurações nas mesmas imagens anotadas."""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import csv
from dataclasses import asdict
import json
from pathlib import Path
import platform
import re
import sys
from time import perf_counter_ns
from zipfile import ZIP_DEFLATED, ZipFile


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, CAMPOS_ORIGEM, CORES, SAIDA,
    agora, desenhar_painel, gravar_csv, gravar_json, ler_anotacoes,
    ler_configuracao, nome_configuracao, objeto_sem_duplicatas,
    rejeitar_constante, sha256, versao_codigo, versoes_dependencias,
)


PASTA_RODADAS = Path(__file__).resolve().parent / "rodadas"
VIDEOS_DESENVOLVIMENTO = {"11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60"}
EXCLUSOES_APROVADAS = {("23", 900), ("23", 1100)}
CAMPOS_CAIXA = ["caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"]
CAMPOS_MEDIDAS = ["area_pixels", "area_caixa_px2", "alongamento_caixa", "ocupacao_caixa", "intensidade_media"]
CAMPOS_METRICAS = ["avaliacao", "classe", "tp", "fp", "fn", "precisao", "recall", "f1", "situacao_f1"]
CAMPOS_PARES = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao", "iou"]
CAMPOS_QUADRO = [
    *CAMPOS_ORIGEM, "imagem_largura_px", "imagem_altura_px", "quantidade_anotacoes",
    "quantidade_deteccoes", "limiar_utilizado", "tempo_detector_ns", "macro_f1", "f1_localizacao",
    *[f"{tipo}_classe_{classe}" for classe in CORES for tipo in ("anotacoes", "deteccoes")],
]


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa e avalia todas as configurações de uma rodada de desenvolvimento.",
        epilog="Sem argumentos, executa round1. Repetir uma rodada cria novas saídas no mesmo round.",
    )
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--rodada", help="Nome do plano preparado, como round1. Padrão: round1.")
    origem.add_argument("--plano", type=Path, help="Caminho explícito de um JSON, inclusive a cópia salva em um batch.")
    return parser.parse_args()


def localizar_plano(args: argparse.Namespace) -> tuple[Path, str | None]:
    if args.plano is not None:
        return args.plano.expanduser().resolve(strict=True), None
    rodada = args.rodada if args.rodada is not None else "round1"
    if re.fullmatch(r"round[1-9][0-9]*", rodada) is None:
        raise ValueError("Informe --rodada round1, round2, ...; round0 é a inspeção individual.")
    caminho = PASTA_RODADAS / f"{rodada}.json"
    if not caminho.is_file():
        disponiveis = ", ".join(sorted(
            arquivo.stem for arquivo in PASTA_RODADAS.glob("round*.json")
            if re.fullmatch(r"round[1-9][0-9]*", arquivo.stem)
        ))
        raise ValueError(f"A rodada {rodada} ainda não tem plano preparado. Disponíveis: {disponiveis or 'nenhuma'}.")
    return caminho.resolve(strict=True), rodada


def carregar_plano(conteudo: bytes) -> dict:
    plano = json.loads(conteudo.decode("utf-8-sig"), parse_constant=rejeitar_constante,
                       object_pairs_hook=objeto_sem_duplicatas)
    if not isinstance(plano, dict) or plano.get("versao") != 1:
        raise ValueError("O plano deve ser um objeto JSON com versao=1.")
    if not isinstance(plano.get("rodada"), str) or not re.fullmatch(r"round[1-9][0-9]*", plano["rodada"]):
        raise ValueError("Use uma rodada no formato round1, round2, ...")
    if type(plano.get("seed")) is not int or plano["seed"] < 0:
        raise ValueError("A seed precisa ser um inteiro não negativo.")
    for campo in ("configuracoes", "quadros"):
        if not isinstance(plano.get(campo), list) or not plano[campo]:
            raise ValueError(f"A lista {campo} não pode estar vazia.")
    if not isinstance(plano.get("exclusoes"), list):
        raise ValueError("O plano precisa declarar a lista exclusoes, mesmo que vazia.")
    if plano.get("algoritmo") != "limiarizacao" or plano.get("particao") != "desenvolvimento":
        raise ValueError("O plano deve declarar limiarizacao e a partição desenvolvimento.")
    for item in plano["exclusoes"]:
        if (item.get("video_id"), item.get("quadro")) not in EXCLUSOES_APROVADAS:
            raise ValueError("Só foram acordadas as exclusões dos quadros 900 e 1100 do vídeo 23.")
    vistos = set()
    for item in [*plano["quadros"], *plano["exclusoes"]]:
        video, quadro = item.get("video_id"), item.get("quadro")
        if video not in VIDEOS_DESENVOLVIMENTO or type(quadro) is not int or quadro < 0:
            raise ValueError("O batch aceita somente quadros identificados dos vídeos de desenvolvimento.")
        if (video, quadro) in vistos:
            raise ValueError(f"Quadro repetido ou simultaneamente incluído e excluído: {video}/{quadro}.")
        vistos.add((video, quadro))
        base = f"bases_de_dados/visem_tracking/dataset/Train/{video}"
        for campo, pasta, sufixo in (("imagem", "images", "jpg"), ("anotacao", "labels", "txt")):
            esperado = f"{base}/{pasta}/{video}_frame_{quadro}.{sufixo}"
            if item.get(campo) != esperado:
                raise ValueError(f"Caminho incoerente para {video}/{quadro}: {campo}.")
    esperados = {(video, quadro) for video in VIDEOS_DESENVOLVIMENTO for quadro in range(0, 1401, 100)}
    if vistos != esperados:
        raise ValueError("O plano precisa representar os 180 quadros acordados, incluindo as exclusões explícitas.")
    for item in plano["quadros"]:
        for campo in ("sha256_imagem", "sha256_anotacao"):
            if not isinstance(item.get(campo), str) or not re.fullmatch(r"[0-9a-f]{64}", item[campo]):
                raise ValueError(f"Hash ausente ou inválido: {campo}.")
    ids, configuracoes = set(), set()
    for item in plano["configuracoes"]:
        identificador = item.get("id")
        if not isinstance(identificador, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", identificador):
            raise ValueError("Cada configuração precisa de um id simples, sem espaços ou barras.")
        dados = ler_configuracao(json.dumps(item["parametros"], allow_nan=False).encode("utf-8"))
        # Canonicaliza operações desativadas somente para detectar equivalências.
        equivalente = {**dados}
        for chave in ("abertura", "fechamento"):
            if dados[chave]["iteracoes"] == 0:
                equivalente[chave] = {"forma": "elipse", "tamanho": 3, "iteracoes": 0}
        canonico = json.dumps(equivalente, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if identificador in ids or canonico in configuracoes:
            raise ValueError("O plano contém ids repetidos ou configurações equivalentes.")
        ids.add(identificador)
        configuracoes.add(canonico)
    return plano


def ler_entrada(item: dict, campo: str) -> bytes:
    caminho = (RAIZ / item[campo]).resolve(strict=True)
    permitida = (RAIZ / "bases_de_dados" / "visem_tracking" / "dataset" / "Train").resolve()
    if not caminho.is_relative_to(permitida) or not caminho.is_file():
        raise ValueError(f"Entrada fora da base esperada: {item[campo]}.")
    conteudo = caminho.read_bytes()
    if sha256(conteudo) != item[f"sha256_{campo}"]:
        raise ValueError(f"O arquivo mudou desde a preparação da rodada: {item[campo]}.")
    return conteudo


def ler_quadro(item: dict, cv2, np):
    imagem = cv2.imdecode(np.frombuffer(ler_entrada(item, "imagem"), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if imagem is None or imagem.dtype != np.uint8 or imagem.ndim not in (2, 3):
        raise ValueError(f"Imagem inválida ou diferente de uint8: {item['imagem']}.")
    if imagem.ndim == 3 and imagem.shape[2] != 3:
        raise ValueError(f"Imagem precisa de três canais BGR: {item['imagem']}.")
    altura, largura = imagem.shape[:2]
    anotacoes = ler_anotacoes(ler_entrada(item, "anotacao"))
    for anotacao in anotacoes:
        anotacao.update({
            "caixa_x_px": (anotacao["caixa_centro_x_norm"] - anotacao["caixa_largura_norm"] / 2) * largura,
            "caixa_y_px": (anotacao["caixa_centro_y_norm"] - anotacao["caixa_altura_norm"] / 2) * altura,
            "caixa_largura_px": anotacao["caixa_largura_norm"] * largura,
            "caixa_altura_px": anotacao["caixa_altura_norm"] * altura,
        })
    return imagem, anotacoes


def converter_objetos(registros: list[dict], indice: str):
    from analise.avaliacao_deteccao import Objeto
    return [Objeto(item[indice], item["classe"], *(item[campo] for campo in CAMPOS_CAIXA)) for item in registros]


def metricas_tabulares(resultado: dict, origem: dict):
    for classe, metricas in resultado["principal"]["por_classe"].items():
        yield {**origem, "avaliacao": "principal", "classe": classe, **metricas}
    yield {**origem, "avaliacao": "localizacao", "classe": "todas", **resultado["localizacao"]["metricas"]}


def abrir_tabelas(pasta: Path, pilha: ExitStack) -> dict:
    campos = {
        "deteccoes": CAMPOS_ORIGEM + CAMPOS_DETECCAO,
        "anotacoes": CAMPOS_ORIGEM + CAMPOS_ANOTACAO,
        "por_quadro": CAMPOS_QUADRO,
        "metricas_por_quadro": CAMPOS_ORIGEM + CAMPOS_METRICAS,
        "pares": CAMPOS_ORIGEM + ["avaliacao", *CAMPOS_PARES, "classe_correta", *CAMPOS_MEDIDAS],
        "pendentes": CAMPOS_ORIGEM + ["avaliacao", "tipo", "indice", "classe", *CAMPOS_CAIXA, *CAMPOS_MEDIDAS],
    }
    tabelas = {}
    for nome, colunas in campos.items():
        arquivo = pilha.enter_context((pasta / f"{nome}.csv").open("w", encoding="utf-8-sig", newline=""))
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        tabelas[nome] = escritor
    return tabelas


def registrar_pares(tabelas: dict, resultado: dict, origem: dict, anotacoes: list[dict], deteccoes: list[dict]) -> None:
    referencias = {item["indice_anotacao"]: item for item in anotacoes}
    previsoes = {item["indice_deteccao"]: item for item in deteccoes}
    for modo in ("principal", "localizacao"):
        for par in resultado[modo]["pares"]:
            registro = previsoes[par["indice_deteccao"]]
            tabelas["pares"].writerow({
                **origem, "avaliacao": modo, **par,
                "classe_correta": par["classe_anotacao"] == par["classe_deteccao"],
                **{campo: registro[campo] for campo in CAMPOS_MEDIDAS},
            })
        for tipo, chave, registros in (
            ("falso_positivo", "deteccoes_sem_par", previsoes),
            ("falso_negativo", "anotacoes_sem_par", referencias),
        ):
            for indice in resultado[modo][chave]:
                registro = registros[indice]
                tabelas["pendentes"].writerow({
                    **origem, "avaliacao": modo, "tipo": tipo, "indice": indice, "classe": registro["classe"],
                    **{campo: registro.get(campo) for campo in CAMPOS_CAIXA + CAMPOS_MEDIDAS},
                })


def resumo_configuracao(identificador: str, pasta: Path, resultado: dict, tempo_ns: int) -> dict:
    principal = resultado["principal"]
    registro = {
        "configuracao_id": identificador, "pasta": pasta.relative_to(RAIZ).as_posix(),
        "quantidade_quadros": resultado["quantidade_quadros"], "macro_f1": principal["macro_f1"],
        "situacao_macro_f1": principal["situacao_macro_f1"], "tempo_detector_total_ns": tempo_ns,
        "f1_localizacao": resultado["localizacao"]["metricas"]["f1"],
    }
    for classe, metricas in principal["por_classe"].items():
        registro.update({f"{nome}_classe_{classe}": valor for nome, valor in metricas.items()})
    return registro


def executar_configuracao(item_config: dict, config, plano: dict, pasta: Path, metadados: dict, cv2, np) -> tuple[dict, dict]:
    from algoritmos.classicos.limiarizacao import detectar
    from analise.agregacao_deteccao import agregar
    from analise.avaliacao_deteccao import avaliar

    inicio = agora()
    registro = {
        **metadados, "situacao": "em_andamento", "inicio_utc": inicio.isoformat(), "fim_utc": None,
        "configuracao_id": item_config["id"], "configuracao_sha256": hash_configuracao(asdict(config)),
        "quantidade_quadros_prevista": len(plano["quadros"]), "quantidade_quadros_concluida": 0,
        "metricas_calculadas": False,
    }
    pasta.mkdir(exist_ok=False)
    por_video = defaultdict(list)
    tempos = defaultdict(int)
    try:
        gravar_json(pasta / "execucao.json", registro)
        gravar_json(pasta / "configuracao.json", asdict(config))
        (pasta / "midia").mkdir()
        (pasta / "predicoes").mkdir()
        with ExitStack() as pilha:
            tabelas = abrir_tabelas(pasta, pilha)
            for numero, quadro in enumerate(plano["quadros"], start=1):
                imagem, anotacoes = ler_quadro(quadro, cv2, np)
                origem = {campo: quadro[campo] for campo in ("imagem", "anotacao", "video_id", "quadro")}
                origem["tempo_segundos"] = None
                antes = perf_counter_ns()
                deteccao = detectar(imagem, config)
                duracao_ns = perf_counter_ns() - antes
                predicoes = list(deteccao.registros())
                resultado = avaliar(converter_objetos(anotacoes, "indice_anotacao"),
                                    converter_objetos(predicoes, "indice_deteccao"))
                # Mantém somente as contagens em memória; os pares completos ficam nos CSV.
                por_video[quadro["video_id"]].append(agregar([resultado]))
                tempos[quadro["video_id"]] += duracao_ns
                tabelas["deteccoes"].writerows({**origem, **linha} for linha in predicoes)
                tabelas["anotacoes"].writerows({**origem, **linha} for linha in anotacoes)
                tabelas["metricas_por_quadro"].writerows(metricas_tabulares(resultado, origem))
                registrar_pares(tabelas, resultado, origem, anotacoes, predicoes)
                resumo = {
                    **origem, "imagem_largura_px": deteccao.largura_imagem, "imagem_altura_px": deteccao.altura_imagem,
                    "quantidade_anotacoes": len(anotacoes), "quantidade_deteccoes": len(predicoes),
                    "limiar_utilizado": deteccao.limiar_utilizado, "tempo_detector_ns": duracao_ns,
                    "macro_f1": resultado["principal"]["macro_f1"], "f1_localizacao": resultado["localizacao"]["metricas"]["f1"],
                }
                for classe in CORES:
                    resumo[f"anotacoes_classe_{classe}"] = sum(linha["classe"] == classe for linha in anotacoes)
                    resumo[f"deteccoes_classe_{classe}"] = sum(linha["classe"] == classe for linha in predicoes)
                tabelas["por_quadro"].writerow(resumo)
                nome = Path(quadro["imagem"]).stem
                linhas = deteccao.linhas_yolo()
                (pasta / "predicoes" / f"{nome}.txt").write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
                colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
                esquerda = desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}")
                direita = desenhar_painel(cv2, np, colorida, predicoes, f"Deteccoes: {len(predicoes)} | {config.metodo}")
                sucesso, png = cv2.imencode(".png", np.concatenate((esquerda, direita), axis=1))
                if not sucesso:
                    raise ValueError(f"Falha ao gerar a comparação de {nome}.")
                (pasta / "midia" / f"{nome}__comparacao.png").write_bytes(png.tobytes())
                registro["quantidade_quadros_concluida"] = numero
                if numero % 25 == 0 or numero == len(plano["quadros"]):
                    gravar_json(pasta / "execucao.json", registro)
                    print(f"  {item_config['id']}: {numero}/{len(plano['quadros'])} quadros", flush=True)
        todos = [resultado for resultados in por_video.values() for resultado in resultados]
        total = agregar(todos)
        videos = {video: agregar(resultados) for video, resultados in por_video.items()}
        gravar_json(pasta / "avaliacao.json", {"situacao": "concluida", "total": total, "por_video": videos})
        gravar_csv(pasta / "metricas.csv", CAMPOS_METRICAS, metricas_tabulares(total, {}))
        gravar_csv(pasta / "metricas_por_video.csv", ["video_id", *CAMPOS_METRICAS],
                   (linha for video, resultado in videos.items() for linha in metricas_tabulares(resultado, {"video_id": video})))
        registro.update({"situacao": "concluida", "fim_utc": agora().isoformat(), "metricas_calculadas": True,
                         "tempo_detector_total_ns": sum(tempos.values())})
        gravar_json(pasta / "execucao.json", registro)
    except BaseException as erro:
        registrar_falha(pasta / "execucao.json", registro, erro)
        raise
    resumo_total = resumo_configuracao(item_config["id"], pasta, total, sum(tempos.values()))
    resumos_video = {
        video: {"video_id": video, **resumo_configuracao(item_config["id"], pasta, resultado, tempos[video])}
        for video, resultado in videos.items()
    }
    return resumo_total, resumos_video


def hash_configuracao(config: dict) -> str:
    return sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def registrar_falha(caminho: Path, registro: dict, erro: BaseException) -> None:
    registro.update({"situacao": "falhou", "fim_utc": agora().isoformat(), "erro": f"{type(erro).__name__}: {erro}"})
    try:
        gravar_json(caminho, registro)
    except OSError:
        pass
    print(f"Execução incompleta; arquivos preservados em: {caminho.parent}", file=sys.stderr)


def executar(args: argparse.Namespace) -> Path:
    caminho_plano, rodada_solicitada = localizar_plano(args)
    plano_bytes = caminho_plano.read_bytes()
    plano = carregar_plano(plano_bytes)
    if rodada_solicitada is not None and plano["rodada"] != rodada_solicitada:
        raise ValueError(f"O plano solicitado para {rodada_solicitada} declara {plano['rodada']}. Corrija a identificação antes de executar.")
    try:
        import cv2
        import numpy as np
        import scipy
        from algoritmos.classicos.classificacao import ConfiguracaoArea
        from algoritmos.classicos.limiarizacao import ConfiguracaoLimiarizacao, ConfiguracaoMorfologia
        from analise.agregacao_deteccao import agregar  # Valida a disponibilidade antes da execução.
    except ModuleNotFoundError as erro:
        raise ValueError("Instale as dependências com: python -m pip install -r algoritmos/classicos/requirements.txt -r analise/requirements.txt") from erro
    configuracoes = []
    for item in plano["configuracoes"]:
        dados = item["parametros"]
        configuracoes.append(ConfiguracaoLimiarizacao(**{
            **dados, "abertura": ConfiguracaoMorfologia(**dados["abertura"]),
            "fechamento": ConfiguracaoMorfologia(**dados["fechamento"]),
            "classificacao": ConfiguracaoArea(**dados["classificacao"]),
        }))
    print(f"Conferindo {len(plano['quadros'])} imagens/anotações e {len(configuracoes)} configurações...", flush=True)
    for quadro in plano["quadros"]:
        ler_quadro(quadro, cv2, np)
    # Caminhos, conteúdo e anotações são conferidos antes de qualquer detecção.
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    codigo = versao_codigo()
    fontes = [Path(__file__).resolve(), RAIZ / "scripts" / "limiarizacao" / "inspecionar_imagem.py",
              RAIZ / "scripts" / "limiarizacao" / "preparar_rodada.py",
              *sorted((RAIZ / "algoritmos").rglob("*.py")),
              RAIZ / "analise" / "__init__.py", RAIZ / "analise" / "avaliacao_deteccao.py",
              RAIZ / "analise" / "agregacao_deteccao.py"]
    fontes_bytes = {arquivo.relative_to(RAIZ).as_posix(): arquivo.read_bytes() for arquivo in fontes}
    codigo["sha256_arquivos"] = {nome: sha256(conteudo) for nome, conteudo in fontes_bytes.items()}
    inicio = agora()
    identificador = inicio.strftime("%Y%m%dT%H%M%S%fZ")
    saida_rodada = (SAIDA / plano["rodada"]).resolve()
    if not saida_rodada.is_relative_to(SAIDA.resolve()):
        raise ValueError("A pasta da rodada precisa permanecer dentro de limiarizacao/.")
    pasta_batch = saida_rodada / f"batch__{identificador}"
    metadados = {
        "etapa": "desenvolvimento_imagens", "algoritmo": "limiarizacao", "rodada": plano["rodada"],
        "batch_id": identificador, "seed": plano["seed"], "plano_sha256": sha256(plano_bytes),
        "plano_salvo": (pasta_batch / "rodada.json").relative_to(RAIZ).as_posix(),
        "exclusoes": plano["exclusoes"],
        "codigo": codigo, "dependencias": {**versoes_dependencias(), "scipy": scipy.__version__,
            "numpy_importado": np.__version__, "opencv_importado": cv2.__version__},
        "ambiente": {"sistema": platform.platform(), "arquitetura": platform.machine(),
                     "opencv_threads": cv2.getNumThreads(), "opencv_opencl": cv2.ocl.useOpenCL()},
        "medicao_tempo": "Uma chamada de detectar por imagem, sem cache de detecções; exclui leitura, avaliação e gravação. Diagnóstico, sem desempate automático.",
    }
    registro = {
        **metadados, "situacao": "em_andamento", "inicio_utc": inicio.isoformat(), "fim_utc": None,
        "configuracoes_previstas": len(configuracoes), "configuracoes_concluidas": 0,
        "quadros_por_configuracao": len(plano["quadros"]), "execucoes": [],
    }
    pasta_batch.mkdir(parents=True, exist_ok=False)
    resumos, resumos_video = [], []
    try:
        gravar_json(pasta_batch / "execucao.json", registro)
        (pasta_batch / "rodada.json").write_bytes(plano_bytes)
        with ZipFile(pasta_batch / "codigo.zip", "x", compression=ZIP_DEFLATED) as arquivo:
            for nome, conteudo in fontes_bytes.items():
                arquivo.writestr(nome, conteudo)
        print(f"Rodada {plano['rodada']} | seed {plano['seed']} | {len(configuracoes) * len(plano['quadros'])} avaliações de imagens", flush=True)
        for numero, (item, config) in enumerate(zip(plano["configuracoes"], configuracoes), start=1):
            nome = nome_configuracao(asdict(config), hash_configuracao(asdict(config)))
            pasta = saida_rodada / f"{nome}__{identificador}"
            print(f"Configuração {numero}/{len(configuracoes)}: {item['id']} | {nome}", flush=True)
            resumo, videos = executar_configuracao(item, config, plano, pasta, metadados, cv2, np)
            resumos.append(resumo)
            resumos_video.extend(videos.values())
            gravar_csv(pasta_batch / "resumo_configuracoes.csv", list(resumos[0]), resumos)
            gravar_csv(pasta_batch / "resumo_por_video.csv", list(resumos_video[0]), resumos_video)
            registro["configuracoes_concluidas"] = numero
            registro["execucoes"].append({"configuracao_id": item["id"], "pasta": pasta.relative_to(RAIZ).as_posix()})
            gravar_json(pasta_batch / "execucao.json", registro)
        registro.update({"situacao": "concluida", "fim_utc": agora().isoformat()})
        gravar_json(pasta_batch / "execucao.json", registro)
    except BaseException as erro:
        registrar_falha(pasta_batch / "execucao.json", registro, erro)
        raise
    return pasta_batch


def main() -> int:
    args = argumentos()
    try:
        pasta = executar(args)
    except KeyboardInterrupt:
        print("Rodada interrompida. Repetir o comando inicia uma nova execução.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Rodada concluída. Resumo: {pasta / 'resumo_configuracoes.csv'}")
    print("Resultados em ordem de configuração; a escolha das próximas configurações será conjunta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
