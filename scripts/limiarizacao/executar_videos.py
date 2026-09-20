"""Executa as cinco configurações congeladas nos vídeos de seleção ou avaliação final."""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter_ns
from zipfile import ZipFile, ZIP_DEFLATED


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.avaliacao_deteccao import Objeto
from analise.avaliacao_individuos import CRITERIOS, avaliar, agregar
from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, agora, desenhar_painel, gravar_csv,
    gravar_json, ler_anotacoes, ler_configuracao, nome_configuracao,
    objeto_sem_duplicatas, rejeitar_constante, versao_codigo, versoes_dependencias,
)
from scripts.limiarizacao.reavaliar_selecao import (
    CAMPOS_METRICAS, CAMPOS_RESUMO, CAMPOS_RANKING, _colunas_metricas,
    construir_ranking,
)


PLANO_PADRAO = Path(__file__).resolve().parent / "videos/plano_selecao.json"
PLANO_FINAL = Path(__file__).resolve().parent / "videos/plano_final.json"
SAIDA = RAIZ / "resultados/videos/limiarizacao/selecao"
SAIDA_FINAL = RAIZ / "resultados/videos/limiarizacao/final"
IDS = ("s068", "s067", "s090", "s099", "s101")
QUADROS = {"13": 1470, "29": 1470, "52": 1440, "54": 1470}
FPS = {"13": 49, "29": 49, "52": 48, "54": 49}
QUADROS_FINAL = {"14": 1470, "24": 1470, "38": 1470, "82": 1500}
FPS_FINAL = {"14": 49, "24": 49, "38": 49, "82": 50}
PLANO_IMAGENS = "scripts/limiarizacao/selecao/plano.json"
HASH_PLANO_IMAGENS = "20bacd6e77cc704db33f9b5525d6a8040b7987854130584ff1c9e7cb65a2980a"
HASH_PLANO_VIDEOS = "ea797b01681b943e7a1f4c2442fe3cb2215e66d4425d4a23dd0af6bd3c784122"
HASH_PLANO_FINAL = "b9e4186f6bad088f3fd676bac150a86cd3359656c5363b09ee393df1d1ba294a"
CAMPOS_ORIGEM = ["video", "anotacao", "video_id", "quadro", "tempo_segundos"]
CAMPOS_CAIXA = ["caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"]
CAMPOS_PARES = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao",
                "iou", "grupo", "classe_correta"]
CAMPOS_PENDENTES = ["tipo", "indice", "classe", "grupo", *CAMPOS_CAIXA]
FONTES_CODIGO = (
    "scripts/limiarizacao/executar_videos.py", "scripts/limiarizacao/inspecionar_imagem.py",
    "scripts/limiarizacao/reavaliar_selecao.py", "scripts/avaliacao/avaliar_imagem.py",
    "algoritmos/__init__.py", "algoritmos/classicos/__init__.py",
    "algoritmos/classicos/limiarizacao.py", "algoritmos/classicos/classificacao.py",
    "algoritmos/classicos/comum.py", "analise/__init__.py", "analise/avaliacao_deteccao.py",
    "analise/avaliacao_individuos.py", "analise/relatorio_rodada.py",
    "analise/relatorio_individuos.py", "analise/relatorio_videos.py",
)


def relativo(caminho: Path) -> str:
    return caminho.resolve().relative_to(RAIZ.resolve()).as_posix()


def hash_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for parte in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(parte)
    return resumo.hexdigest()


def hash_configuracao(parametros: dict) -> str:
    conteudo = json.dumps(parametros, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def carregar_json(conteudo: bytes) -> dict:
    dados = json.loads(conteudo.decode("utf-8-sig"), object_pairs_hook=objeto_sem_duplicatas,
                       parse_constant=rejeitar_constante)
    if not isinstance(dados, dict):
        raise ValueError("Esperado um objeto JSON.")
    return dados


def caminho_fonte(nome: str) -> Path:
    caminho = (RAIZ / nome).resolve(strict=True)
    limite = (RAIZ / "bases_de_dados/visem_tracking/dataset/Train").resolve()
    if not caminho.is_relative_to(limite) or not caminho.is_file():
        raise ValueError(f"Fonte fora do conjunto anotado: {nome}.")
    return caminho


def especificacao_etapa(etapa: str) -> dict:
    if etapa == "selecao":
        return {"quadros": QUADROS, "fps": FPS, "sha256": HASH_PLANO_VIDEOS,
                "plano": PLANO_PADRAO, "saida": SAIDA}
    if etapa == "final":
        return {"quadros": QUADROS_FINAL, "fps": FPS_FINAL, "sha256": HASH_PLANO_FINAL,
                "plano": PLANO_FINAL, "saida": SAIDA_FINAL}
    raise ValueError("Etapa deve ser selecao ou final.")


def carregar_plano(conteudo: bytes, etapa: str = "selecao") -> dict:
    esperado = especificacao_etapa(etapa)
    if hashlib.sha256(conteudo).hexdigest() != esperado["sha256"]:
        raise ValueError("Use o plano congelado dos cinco candidatos, sem modificar seu conteúdo.")
    plano = carregar_json(conteudo)
    if (plano.get("versao") != 1 or plano.get("tipo") != f"videos_{etapa}"
            or plano.get("algoritmo") != "limiarizacao" or plano.get("particao") != etapa
            or plano.get("seed") != 42 or plano.get("politica_anotacoes_ausentes") != "erro"
            or plano.get("criterios_avaliacao") != CRITERIOS):
        raise ValueError(f"Plano incompatível com a etapa de vídeos: {etapa}.")
    fonte = RAIZ / PLANO_IMAGENS
    if hash_arquivo(fonte) != HASH_PLANO_IMAGENS:
        raise ValueError("O plano original das candidatas foi alterado.")
    originais = {item["id"]: item["parametros"]
                 for item in carregar_json(fonte.read_bytes())["configuracoes"]}
    if [item["id"] for item in plano["configuracoes"]] != list(IDS):
        raise ValueError("O plano deve conter exatamente s068, s067, s090, s099 e s101 nessa ordem.")
    for item in plano["configuracoes"]:
        if item["parametros"] != originais[item["id"]]:
            raise ValueError(f"Parâmetros alterados em {item['id']}.")
        ler_configuracao(json.dumps(item["parametros"], allow_nan=False).encode("utf-8"))
    if [v["video_id"] for v in plano["videos"]] != list(esperado["quadros"]):
        raise ValueError(f"Vídeos diferentes dos previstos para a etapa {etapa}.")
    for video in plano["videos"]:
        identificador = video["video_id"]
        n = esperado["quadros"][identificador]
        base = f"bases_de_dados/visem_tracking/dataset/Train/{identificador}"
        if (video["arquivo"] != f"{base}/{identificador}.mp4"
                or type(video["quantidade_quadros"]) is not int or video["quantidade_quadros"] != n
                or video["fps"] != esperado["fps"][identificador] or video["largura"] != 640
                or video["altura"] != 480 or video["indice_inicial"] != 0):
            raise ValueError(f"Vídeo {identificador}: metadados diferentes dos inspecionados.")
        if [a["quadro"] for a in video["anotacoes"]] != list(range(n)):
            raise ValueError(f"Vídeo {identificador}: anotações devem cobrir todos os quadros, sem lacunas.")
        for anotacao in video["anotacoes"]:
            if anotacao["arquivo"] != f"{base}/labels/{identificador}_frame_{anotacao['quadro']}.txt":
                raise ValueError("Caminho de anotação divergente do quadro.")
        referencias = video["referencias_alinhamento"]
        if [r["quadro"] for r in referencias] != [0, 100, 700, 1400, n - 1]:
            raise ValueError("Referências de alinhamento diferentes das previstas.")
        for referencia in referencias:
            if referencia["imagem"] != f"{base}/images/{identificador}_frame_{referencia['quadro']}.jpg":
                raise ValueError("Caminho de referência divergente do quadro.")
        for item in [video, *video["anotacoes"], *referencias]:
            digest = item["sha256"]
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Hash ausente ou inválido no plano de vídeos.")
    return plano


def conferir_fontes(plano: dict) -> tuple[dict, dict]:
    """Confere bytes e todas as anotações antes de abrir os vídeos."""
    hashes = {PLANO_IMAGENS: HASH_PLANO_IMAGENS}
    anotacoes = {}
    origens = [("reavaliacao", "resultados/frame-to-frame/limiarizacao/selecao")]
    if plano.get("particao") == "final":
        origens.append(("selecao_videos", "resultados/videos/limiarizacao/selecao"))
    for chave, limite in origens:
        for nome, esperado in plano["proveniencia"][chave]["arquivos_sha256"].items():
            caminho = (RAIZ / nome).resolve(strict=True)
            if not caminho.is_relative_to((RAIZ / limite).resolve()):
                raise ValueError(f"Proveniência fora da seleção correspondente: {chave}.")
            if hash_arquivo(caminho) != esperado:
                raise ValueError(f"Registro da seleção alterado: {nome}.")
            hashes[nome] = esperado
    for video in plano["videos"]:
        print(f"Conferindo arquivos do vídeo {video['video_id']}...", flush=True)
        for item in [video, *video["anotacoes"], *video["referencias_alinhamento"]]:
            nome = item.get("arquivo", item.get("imagem"))
            caminho = caminho_fonte(nome)
            atual = hash_arquivo(caminho)
            if atual != item["sha256"]:
                raise ValueError(f"Arquivo alterado desde a preparação: {nome}.")
            hashes[nome] = atual
        for item in video["anotacoes"]:
            caminho = caminho_fonte(item["arquivo"])
            conteudo = caminho.read_bytes()
            if hashlib.sha256(conteudo).hexdigest() != item["sha256"]:
                raise ValueError("Anotação alterada durante a conferência.")
            anotacoes[(video["video_id"], item["quadro"])] = ler_anotacoes(conteudo)
    return hashes, anotacoes


def abrir_video(video: dict, cv2):
    captura = cv2.VideoCapture(str(caminho_fonte(video["arquivo"])))
    if not captura.isOpened():
        captura.release()
        raise ValueError(f"Não foi possível abrir o vídeo {video['video_id']}.")
    fps = captura.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or not math.isclose(fps, video["fps"], rel_tol=1e-6, abs_tol=1e-6):
        captura.release()
        raise ValueError(f"FPS do vídeo {video['video_id']} difere do plano.")
    return captura


def conferir_quadro(imagem, video: dict) -> None:
    if imagem is None or imagem.shape != (video["altura"], video["largura"], 3) or str(imagem.dtype) != "uint8":
        raise ValueError(f"Dimensões ou formato inesperados no vídeo {video['video_id']}.")


def atualizar_minimos(estado: dict, indice: int, erro: float) -> None:
    """Retém os dois menores erros sem guardar o vídeo inteiro em memória."""
    candidatos = [*estado["menores"], (erro, indice)]
    estado["menores"] = sorted(candidatos)[:2]
    if indice == estado["quadro"]:
        estado["erro_previsto"] = erro


def alinhamento_valido(estado: dict) -> bool:
    menores = estado["menores"]
    return (len(menores) == 2 and menores[0][1] == estado["quadro"]
            and menores[1][0] - menores[0][0] > 1e-9)


def conferir_alinhamento(plano: dict, pasta: Path, cv2, np) -> dict:
    """Verifica índice temporal nas referências; nunca desloca caixas ou quadros."""
    pasta.mkdir(exist_ok=False)
    registros = []
    pixels = {}
    videos_conferidos = []
    for video in plano["videos"]:
        referencias = []
        for item in video["referencias_alinhamento"]:
            imagem = cv2.imdecode(np.frombuffer(caminho_fonte(item["imagem"]).read_bytes(), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            conferir_quadro(imagem, video)
            referencias.append({**item, "cinza": cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY),
                                "imagem_lida": imagem, "menores": [], "erro_previsto": None})
        captura = abrir_video(video, cv2)
        backend = captura.getBackendName()
        numero = 0
        try:
            while True:
                sucesso, imagem = captura.read()
                if not sucesso:
                    break
                if numero >= video["quantidade_quadros"]:
                    raise ValueError("O vídeo contém mais quadros que o plano.")
                conferir_quadro(imagem, video)
                pixels[(video["video_id"], numero)] = hashlib.sha256(imagem.tobytes()).hexdigest()
                cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
                for referencia in referencias:
                    erro = float(cv2.norm(cinza, referencia["cinza"], cv2.NORM_L1) / cinza.size)
                    atualizar_minimos(referencia, numero, erro)
                    if numero == referencia["quadro"]:
                        esquerda = desenhar_painel(cv2, np, referencia["imagem_lida"], [], "Referencia JPEG da base")
                        direita = desenhar_painel(cv2, np, imagem, [], f"MP4 decodificado | quadro {numero}")
                        sucesso_png, png = cv2.imencode(".png", np.concatenate((esquerda, direita), axis=1))
                        if not sucesso_png:
                            raise ValueError("Falha ao gerar imagem de conferência do alinhamento.")
                        (pasta / f"{video['video_id']}_frame_{numero}__alinhamento.png").write_bytes(png.tobytes())
                numero += 1
        finally:
            captura.release()
        if numero != video["quantidade_quadros"]:
            raise ValueError(f"Vídeo {video['video_id']}: decodificados {numero} de {video['quantidade_quadros']} quadros.")
        for referencia in referencias:
            melhor, segundo = referencia["menores"]
            registros.append({"video_id": video["video_id"], "quadro_previsto": referencia["quadro"],
                              "imagem_referencia": referencia["imagem"], "mae_previsto": referencia["erro_previsto"],
                              "melhor_quadro": melhor[1], "menor_mae": melhor[0],
                              "segundo_quadro": segundo[1], "segundo_mae": segundo[0],
                              "diferenca_mae": segundo[0] - melhor[0], "alinhamento_confirmado": alinhamento_valido(referencia)})
        videos_conferidos.append({"video_id": video["video_id"], "quantidade_quadros": numero,
                                  "fps": video["fps"], "backend": backend})
        gravar_csv(pasta / "alinhamento.csv", list(registros[0]), registros)
        if any(not r["alinhamento_confirmado"] for r in registros):
            raise ValueError("Alinhamento temporal divergente ou ambíguo. Consulte conferencia/alinhamento.csv e as imagens; nenhum detector foi iniciado.")
        print(f"Vídeo {video['video_id']}: {numero} quadros e cinco referências de alinhamento conferidos.", flush=True)
    gravar_csv(pasta / "quadros_decodificados.csv", ["video_id", "quadro", "sha256_bgr"],
               ({"video_id": video, "quadro": quadro, "sha256_bgr": digest}
                for (video, quadro), digest in pixels.items()))
    gravar_json(pasta / "conferencia.json", {
        "situacao": "concluida", "metodo": "MAE em cinza contra todos os quadros; índice previsto deve ser mínimo único.",
        "tolerancia_empate_numerico": 1e-9, "referencias": registros,
        "videos": videos_conferidos, "quadros_decodificados_sha256": hash_arquivo(pasta / "quadros_decodificados.csv"),
        "limite": "Conferência temporal em cinco referências por vídeo; não certifica igualdade de pixels JPEG/MP4.",
    })
    return {"referencias": registros, "pixels_sha256": pixels, "videos": videos_conferidos}


def caixas_anotadas(itens: list[dict], largura: int, altura: int) -> list[dict]:
    return [{**item,
             "caixa_x_px": (item["caixa_centro_x_norm"] - item["caixa_largura_norm"] / 2) * largura,
             "caixa_y_px": (item["caixa_centro_y_norm"] - item["caixa_altura_norm"] / 2) * altura,
             "caixa_largura_px": item["caixa_largura_norm"] * largura,
             "caixa_altura_px": item["caixa_altura_norm"] * altura} for item in itens]


def objetos(registros: list[dict], indice: str) -> list[Objeto]:
    return [Objeto(r[indice], r["classe"], *(r[c] for c in CAMPOS_CAIXA)) for r in registros]


def abrir_tabelas(pasta: Path, pilha: ExitStack) -> dict:
    campos = {
        "deteccoes": CAMPOS_DETECCAO, "anotacoes": CAMPOS_ANOTACAO,
        "por_quadro": ["imagem_largura_px", "imagem_altura_px", "quantidade_anotacoes", "quantidade_deteccoes",
                       "tempo_decodificador_segundos", "limiar_utilizado", "tempo_detector_ns", *CAMPOS_METRICAS],
        "pares": CAMPOS_PARES, "pendentes": CAMPOS_PENDENTES,
    }
    escritores = {}
    for nome, colunas in campos.items():
        arquivo = pilha.enter_context((pasta / f"{nome}.csv").open("x", encoding="utf-8-sig", newline=""))
        escritor = csv.DictWriter(arquivo, fieldnames=[*CAMPOS_ORIGEM, *colunas])
        escritor.writeheader()
        escritores[nome] = escritor
    return escritores


def painel_comparativo(imagem, anotacoes: list[dict], deteccoes: list[dict],
                       video: dict, numero: int, identificador: str, metodo: str, metricas: dict, cv2, np):
    esquerda = desenhar_painel(cv2, np, imagem, anotacoes, f"Anotacoes da base: {len(anotacoes)}")
    direita = desenhar_painel(cv2, np, imagem, deteccoes, f"Deteccoes: {len(deteccoes)} | {identificador} | {metodo}")
    comparacao = np.concatenate((esquerda, direita), axis=1)
    cabecalho = np.full((36, comparacao.shape[1], 3), 28, dtype=np.uint8)
    texto = (f"Video {video['video_id']} | quadro {numero}/{video['quantidade_quadros'] - 1} | "
             f"tempo {numero / video['fps']:.3f}s | Individuos: TP {metricas['tp']} FP {metricas['fp']} FN {metricas['fn']}")
    cv2.putText(cabecalho, texto, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
    return np.concatenate((cabecalho, comparacao), axis=0)


def conferir_video_gravado(caminho: Path, video: dict, cv2) -> dict:
    """Decodifica o arquivo exportado para não aceitar MP4 truncado como concluído."""
    captura = cv2.VideoCapture(str(caminho))
    numero = 0
    try:
        if not captura.isOpened() or not math.isclose(captura.get(cv2.CAP_PROP_FPS), video["fps"], abs_tol=1e-6):
            raise ValueError(f"Vídeo comparativo inválido: {caminho.name}.")
        while True:
            sucesso, imagem = captura.read()
            if not sucesso:
                break
            if imagem.shape != (video["altura"] + 104, video["largura"] * 2, 3):
                raise ValueError("Dimensões incorretas no vídeo comparativo.")
            numero += 1
            if numero > video["quantidade_quadros"]:
                raise ValueError("Vídeo comparativo contém quadros extras.")
    finally:
        captura.release()
    if numero != video["quantidade_quadros"]:
        raise ValueError(f"Vídeo comparativo incompleto: {numero}/{video['quantidade_quadros']} quadros.")
    return {"arquivo": relativo(caminho), "quantidade_quadros": numero, "fps": video["fps"],
            "largura": video["largura"] * 2, "altura": video["altura"] + 104,
            "sha256": hash_arquivo(caminho), "codec_solicitado": "mp4v", "decodificacao_conferida": True}


def executar_configuracao(item: dict, config, plano: dict, pasta: Path, anotacoes_salvas: dict,
                          metadados: dict, pixels_conferidos: dict, cv2, np, detectar) -> tuple[dict, list[dict]]:
    pasta.mkdir(exist_ok=False)
    midia = pasta / "midia"
    midia.mkdir()
    identificador = item["id"]
    registro = {**metadados, "situacao": "em_andamento", "configuracao_id": identificador,
                "inicio_utc": agora().isoformat(), "quadros_concluidos": 0, "videos": []}
    gravar_json(pasta / "configuracao.json", asdict(config))
    gravar_json(pasta / "execucao.json", registro)
    por_video = defaultdict(list)
    hash_config = hash_configuracao(asdict(config))
    try:
        with ExitStack() as pilha:
            tabelas = abrir_tabelas(pasta, pilha)
            for video in plano["videos"]:
                video_id = video["video_id"]
                captura = abrir_video(video, cv2)
                # A pasta já contém o resumo legível; o nome curto evita MAX_PATH no Windows.
                caminho_video = midia / f"{identificador}__cfg-{hash_config[:12]}__video-{video_id}.mp4"
                escritor = None
                numero = 0
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
                        conferir_quadro(imagem, video)
                        if hashlib.sha256(imagem.tobytes()).hexdigest() != pixels_conferidos[(video_id, numero)]:
                            raise ValueError(f"Pixels decodificados divergentes da conferência: {video_id}/{numero}.")
                        anotacao = video["anotacoes"][numero]
                        origem = {"video": video["arquivo"], "anotacao": anotacao["arquivo"],
                                  "video_id": video_id, "quadro": numero, "tempo_segundos": numero / video["fps"]}
                        reais = caixas_anotadas(anotacoes_salvas[(video_id, numero)], video["largura"], video["altura"])
                        antes = perf_counter_ns()
                        saida = detectar(imagem, config)
                        tempo_detector = perf_counter_ns() - antes
                        previsoes = list(saida.registros())
                        resultado = avaliar(objetos(reais, "indice_anotacao"), objetos(previsoes, "indice_deteccao"))
                        por_video[video_id].append({chave: resultado[chave] for chave in (
                            "criterios", "por_grupo", "cobertura_por_classe", "classificacao_individuos")})
                        tabelas["deteccoes"].writerows({**origem, **linha} for linha in previsoes)
                        tabelas["anotacoes"].writerows({**origem, **linha} for linha in reais)
                        tabelas["pares"].writerows({**origem, **par} for par in resultado["pares"])
                        for tipo, campo, linhas, chave in (
                            ("fn", "anotacoes_sem_par", reais, "indice_anotacao"),
                            ("fp", "deteccoes_sem_par", previsoes, "indice_deteccao"),
                        ):
                            mapa = {r[chave]: r for r in linhas}
                            for indice in resultado[campo]:
                                r = mapa[indice]
                                tabelas["pendentes"].writerow({**origem, "tipo": tipo, "indice": indice,
                                    "classe": r["classe"], "grupo": "aglomerados" if r["classe"] == 1 else "individuos",
                                    **{c: r[c] for c in CAMPOS_CAIXA}})
                        tempo_decoder = captura.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        if not math.isfinite(tempo_decoder) or tempo_decoder < 0:
                            tempo_decoder = None
                        tabelas["por_quadro"].writerow({**origem, "imagem_largura_px": video["largura"],
                            "imagem_altura_px": video["altura"], "quantidade_anotacoes": len(reais),
                            "quantidade_deteccoes": len(previsoes), "tempo_decodificador_segundos": tempo_decoder,
                            "limiar_utilizado": saida.limiar_utilizado, "tempo_detector_ns": tempo_detector,
                            **_colunas_metricas(resultado)})
                        comparacao = painel_comparativo(imagem, reais, previsoes, video, numero,
                                                       identificador, config.metodo, resultado["por_grupo"]["individuos"], cv2, np)
                        escritor.write(comparacao)
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
                registro["videos"].append(conferir_video_gravado(caminho_video, video, cv2))
                gravar_json(pasta / "execucao.json", registro)
        todos = [r for resultados in por_video.values() for r in resultados]
        total = agregar(todos)
        totais_video = {video: agregar(resultados) for video, resultados in por_video.items()}
        gravar_json(pasta / "avaliacao.json", {"criterios": CRITERIOS, "total": total, "por_video": totais_video})
        identidade = {"configuracao_id": identificador, "pasta_origem": relativo(pasta)}
        resumo = {**identidade, "quantidade_quadros": total["quantidade_quadros"], **_colunas_metricas(total)}
        resumos_video = [{**identidade, "video_id": video, "quantidade_quadros": total_video["quantidade_quadros"],
                         **_colunas_metricas(total_video)} for video, total_video in totais_video.items()]
        gravar_csv(pasta / "resumo.csv", CAMPOS_RESUMO, [resumo])
        gravar_csv(pasta / "resumo_por_video.csv", ["video_id", *CAMPOS_RESUMO], resumos_video)
        registro.update(situacao="concluida", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", registro)
    except BaseException as erro:
        registro.update(situacao="falhou", fim_utc=agora().isoformat(), erro=f"{type(erro).__name__}: {erro}")
        gravar_json(pasta / "execucao.json", registro)
        raise
    return resumo, resumos_video


def gerar_relatorio(pasta: Path, etapa: str | None = None) -> Path:
    from analise.relatorio_videos import gerar_relatorio as gerar
    pasta = pasta.expanduser().resolve(strict=True)
    etapas = (etapa,) if etapa is not None else ("selecao", "final")
    if (not pasta.name.startswith("batch__")
            or not any(pasta.parent == especificacao_etapa(e)["saida"].resolve() for e in etapas)):
        raise ValueError("Informe um batch de vídeos da etapa correspondente (selecao ou final).")
    try:
        pdf = gerar(pasta)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {"situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}",
                                              "fim_utc": agora().isoformat()})
        raise
    gravar_json(pasta / "relatorio.json", {"situacao": "concluido", "arquivo": relativo(pdf), "fim_utc": agora().isoformat()})
    return pdf


def executar(caminho_plano: Path, etapa: str = "selecao") -> Path:
    especificacao = especificacao_etapa(etapa)
    conteudo = caminho_plano.expanduser().resolve(strict=True).read_bytes()
    plano = carregar_plano(conteudo, etapa)
    try:
        import cv2
        import numpy as np
        import scipy
        from algoritmos.classicos.classificacao import ConfiguracaoArea
        from algoritmos.classicos.limiarizacao import ConfiguracaoLimiarizacao, ConfiguracaoMorfologia, detectar
        from analise.relatorio_rodada import verificar_dependencias
    except ModuleNotFoundError as erro:
        raise ValueError("Instale as dependências no Python utilizado: python -m pip install -r algoritmos/classicos/requirements.txt -r analise/requirements.txt -r analise/requirements-relatorio.txt") from erro
    dependencias_pdf = verificar_dependencias()
    configuracoes = [ConfiguracaoLimiarizacao(**{
        **item["parametros"], "abertura": ConfiguracaoMorfologia(**item["parametros"]["abertura"]),
        "fechamento": ConfiguracaoMorfologia(**item["parametros"]["fechamento"]),
        "classificacao": ConfiguracaoArea(**item["parametros"]["classificacao"]),
    }) for item in plano["configuracoes"]]
    hashes, anotacoes = conferir_fontes(plano)
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    inicio = agora()
    saida = especificacao["saida"].resolve()
    pasta = (saida / f"batch__{inicio.strftime('%Y%m%dT%H%M%S%fZ')}").resolve()
    if pasta.parent != saida:
        raise ValueError(f"Destino fora da pasta de vídeos da etapa {etapa}.")
    pasta.mkdir(parents=True, exist_ok=False)
    (pasta / "plano.json").write_bytes(conteudo)
    registro = {
        "versao": 1, "tipo": f"{etapa}_videos", "particao": etapa,
        "situacao": "em_andamento", "inicio_utc": inicio.isoformat(),
        "criterios": CRITERIOS, "plano_sha256": hashlib.sha256(conteudo).hexdigest(), "origens_sha256": hashes,
        "configuracoes_previstas": len(IDS), "configuracoes_concluidas": 0,
        "quadros_por_configuracao": sum(especificacao["quadros"].values()), "videos_por_configuracao": 4,
        "execucoes": [], "dependencias": {**versoes_dependencias(), "scipy": scipy.__version__, **dependencias_pdf},
        "tempo_segundos": "Índice base zero dividido pelo FPS CFR dos metadados do MP4; tempo relativo ao clipe.",
        "identidade_objetos": "Índices locais por quadro; sem rastreamento, trajetórias ou velocidade.",
        "registro_relatorio": "relatorio.json", "alinhamento_conferido": False,
    }
    gravar_json(pasta / "execucao.json", registro)
    try:
        codigo = versao_codigo()
        codigo["sha256_arquivos"] = {}
        with ZipFile(pasta / "codigo.zip", "x", compression=ZIP_DEFLATED) as arquivo:
            for nome in FONTES_CODIGO:
                bytes_fonte = (RAIZ / nome).read_bytes()
                arquivo.writestr(nome, bytes_fonte)
                codigo["sha256_arquivos"][nome] = hashlib.sha256(bytes_fonte).hexdigest()
        codigo["sha256_zip"] = hash_arquivo(pasta / "codigo.zip")
        registro["codigo"] = codigo
        gravar_json(pasta / "execucao.json", registro)
        conferencia = conferir_alinhamento(plano, pasta / "conferencia", cv2, np)
        registro["alinhamento_conferido"] = True
        gravar_json(pasta / "execucao.json", registro)
        resumos, por_video = [], []
        for item, config in zip(plano["configuracoes"], configuracoes):
            nome = f"{item['id']}__{nome_configuracao(asdict(config), hash_configuracao(asdict(config)))}__{inicio.strftime('%Y%m%dT%H%M%S%fZ')}"
            pasta_config = pasta / nome
            resumo, videos = executar_configuracao(item, config, plano, pasta_config, anotacoes,
                {"tipo": f"{etapa}_videos", "particao": etapa, "criterios": CRITERIOS, "plano_sha256": registro["plano_sha256"],
                 "configuracao_sha256": hash_configuracao(asdict(config)), "batch": relativo(pasta)},
                conferencia["pixels_sha256"], cv2, np, detectar)
            resumos.append(resumo)
            por_video.extend(videos)
            registro["configuracoes_concluidas"] += 1
            registro["execucoes"].append({"configuracao_id": item["id"], "pasta": relativo(pasta_config)})
            gravar_json(pasta / "execucao.json", registro)
        for nome, esperado in hashes.items():
            if hash_arquivo(RAIZ / nome) != esperado:
                raise ValueError(f"Fonte modificada durante a execução: {nome}.")
        gravar_csv(pasta / "resumo_configuracoes.csv", CAMPOS_RESUMO, resumos)
        gravar_csv(pasta / "resumo_por_video.csv", ["video_id", *CAMPOS_RESUMO], por_video)
        gravar_csv(pasta / "ranking.csv", CAMPOS_RANKING, construir_ranking(resumos))
        registro["saidas_sha256"] = {relativo(p): hash_arquivo(p) for p in sorted(pasta.rglob("*"))
                                       if p.is_file() and p != pasta / "execucao.json"}
        registro.update(situacao="concluida", fim_utc=agora().isoformat())
        gravar_json(pasta / "execucao.json", registro)
    except BaseException as erro:
        registro.update(situacao="falhou", fim_utc=agora().isoformat(), erro=f"{type(erro).__name__}: {erro}")
        gravar_json(pasta / "execucao.json", registro)
        print(f"Execução incompleta; arquivos preservados em {pasta}", file=sys.stderr)
        raise
    try:
        print(f"Relatório: {gerar_relatorio(pasta, etapa)}")
    except Exception as erro:
        print(f"Vídeos e métricas concluídos; falha apenas no PDF: {erro}", file=sys.stderr)
        print(f'Gere depois com --somente-relatorio "{pasta}".', file=sys.stderr)
    return pasta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etapa", choices=("selecao", "final"),
                        help="Etapa a executar; padrão selecao. Para somente relatório, a pasta indica a etapa.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--plano", type=Path, help="Cópia exata do plano congelado da etapa; o padrão é videos/plano_<etapa>.json.")
    grupo.add_argument("--somente-relatorio", type=Path, metavar="BATCH", help="Gera outro PDF do batch concluído, sem repetir detecção ou vídeos.")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio is not None:
            print(f"Relatório: {gerar_relatorio(args.somente_relatorio, args.etapa)}")
        else:
            etapa = args.etapa or "selecao"
            plano = args.plano if args.plano is not None else especificacao_etapa(etapa)["plano"]
            print(f"Resultados: {executar(plano, etapa)}")
    except (ValueError, OSError, KeyError, TypeError, ImportError, csv.Error) as erro:
        parser.exit(1, f"Erro: {erro}\n")


if __name__ == "__main__":
    main()
