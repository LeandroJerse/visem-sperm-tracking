"""Inspeção de uma imagem anotada; não calcula métricas nem executa lotes."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "resultados" / "frame-to-frame" / "limiarizacao"
CORES = {0: (0, 220, 255), 1: (255, 70, 200), 2: (255, 220, 0)}  # BGR
CAMPOS_ORIGEM = ["imagem", "anotacao", "video_id", "quadro", "tempo_segundos"]
CAMPOS_DETECCAO = [
    "algoritmo", "indice_deteccao", "classe", "imagem_largura_px",
    "imagem_altura_px", "caixa_x_px", "caixa_y_px", "caixa_largura_px",
    "caixa_altura_px", "caixa_centro_x_norm", "caixa_centro_y_norm",
    "caixa_largura_norm", "caixa_altura_norm", "centroide_x_px",
    "centroide_y_px", "area_pixels", "area_caixa_px2", "alongamento_caixa",
    "ocupacao_caixa", "intensidade_media", "limiar_utilizado",
]
CAMPOS_ANOTACAO = [
    "indice_anotacao", "linha_original", "classe", "caixa_centro_x_norm",
    "caixa_centro_y_norm", "caixa_largura_norm", "caixa_altura_norm",
    "caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px",
]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa manual/Otsu em uma imagem e salva a comparação visual.",
        epilog="Não calcula F1, não escolhe parâmetros e não processa vídeos ou lotes.",
    )
    parser.add_argument("--imagem", type=Path, required=True, help="Imagem original.")
    parser.add_argument(
        "--anotacao", type=Path, required=True,
        help="TXT de labels/ com 5 campos por linha e o mesmo nome-base da imagem.",
    )
    parser.add_argument(
        "--config", type=Path, required=True, help="JSON com todos os parâmetros preenchidos.",
    )
    parser.add_argument(
        "--rodada", default="round0", help="Pasta da rodada, como round0 ou round1 (padrão: round0).",
    )
    return parser.parse_args()


def verificar_chaves(objeto: object, esperadas: set[str], nome: str) -> None:
    if not isinstance(objeto, dict):
        raise ValueError(f"{nome} deve ser um objeto JSON.")
    faltantes, extras = esperadas - objeto.keys(), objeto.keys() - esperadas
    if faltantes or extras:
        raise ValueError(
            f"Campos inválidos em {nome}. Faltantes: {sorted(faltantes)}; "
            f"desconhecidos: {sorted(extras)}."
        )


def rejeitar_constante(valor: str) -> None:
    raise ValueError(f"O JSON não aceita {valor}; informe números finitos.")


def objeto_sem_duplicatas(pares: list[tuple[str, object]]) -> dict:
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError(f"Campo repetido no JSON: {chave}.")
        objeto[chave] = valor
    return objeto


def ler_configuracao(conteudo: bytes) -> dict:
    dados = json.loads(
        conteudo.decode("utf-8-sig"), parse_constant=rejeitar_constante,
        object_pairs_hook=objeto_sem_duplicatas,
    )
    verificar_chaves(dados, {
        "metodo", "polaridade", "limiar_manual", "abertura", "fechamento",
        "conectividade", "area_minima", "area_maxima", "classificacao",
    }, "configuração")
    for operacao in ("abertura", "fechamento"):
        verificar_chaves(dados[operacao], {"forma", "tamanho", "iteracoes"}, operacao)
    verificar_chaves(dados["classificacao"], {
        "area_maxima_pequeno", "area_minima_aglomerado",
    }, "classificacao")
    pendentes = [
        campo for campo in ("metodo", "polaridade", "conectividade", "area_minima")
        if dados[campo] is None
    ]
    for grupo in ("abertura", "fechamento", "classificacao"):
        pendentes.extend(f"{grupo}.{campo}" for campo, valor in dados[grupo].items() if valor is None)
    if dados["metodo"] == "manual" and dados["limiar_manual"] is None:
        pendentes.append("limiar_manual")
    if pendentes:
        raise ValueError("Preencha estes campos da configuração: " + ", ".join(pendentes) + ".")
    return dados


def ler_anotacoes(conteudo: bytes) -> list[dict]:
    anotacoes = []
    for numero, linha in enumerate(conteudo.decode("utf-8-sig").splitlines(), start=1):
        if not linha.strip():
            continue
        campos = linha.split()
        if len(campos) != 5:
            raise ValueError(
                f"Anotação, linha {numero}: esperados 5 campos. Use labels/, não labels_ftid/."
            )
        if campos[0] not in ("0", "1", "2"):
            raise ValueError(f"Anotação, linha {numero}: classe deve ser 0, 1 ou 2.")
        try:
            cx, cy, largura, altura = map(float, campos[1:])
        except ValueError as erro:
            raise ValueError(f"Anotação, linha {numero}: coordenadas inválidas.") from erro
        if not all(math.isfinite(valor) for valor in (cx, cy, largura, altura)):
            raise ValueError(f"Anotação, linha {numero}: coordenadas devem ser finitas.")
        if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < largura <= 1 and 0 < altura <= 1):
            raise ValueError(f"Anotação, linha {numero}: caixa normalizada inválida.")
        # Tolerância apenas para arredondamento decimal na borda; dados são preservados.
        tolerancia = 1e-8
        if (cx - largura / 2 < -tolerancia or cy - altura / 2 < -tolerancia
                or cx + largura / 2 > 1 + tolerancia or cy + altura / 2 > 1 + tolerancia):
            raise ValueError(f"Anotação, linha {numero}: caixa ultrapassa a imagem.")
        anotacoes.append({
            "indice_anotacao": len(anotacoes), "linha_original": numero,
            "classe": int(campos[0]), "caixa_centro_x_norm": cx,
            "caixa_centro_y_norm": cy, "caixa_largura_norm": largura,
            "caixa_altura_norm": altura,
        })
    return anotacoes


def identificar_origem(imagem: Path, anotacao: Path) -> dict:
    correspondencia = re.fullmatch(r"(?P<video>\d+)_frame_(?P<quadro>\d+)", imagem.stem)
    return {
        "imagem": str(imagem), "anotacao": str(anotacao),
        "video_id": correspondencia["video"] if correspondencia else None,
        "quadro": int(correspondencia["quadro"]) if correspondencia else None,
        "tempo_segundos": None,
    }


def nome_configuracao(config: dict, identificador: str) -> str:
    metodo = config["metodo"]
    if metodo == "manual":
        metodo += str(config["limiar_manual"])
    formas = {"elipse": "e", "retangulo": "r", "cruz": "c"}
    operacoes = []
    for chave, abreviacao in (("abertura", "ab"), ("fechamento", "fe")):
        item = config[chave]
        operacoes.append(
            f"{abreviacao}{formas[item['forma']]}{item['tamanho']}x{item['iteracoes']}"
        )
    return f"{metodo}-{config['polaridade']}-{'-'.join(operacoes)}-area__cfg-{identificador[:12]}"


def gravar_json(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    temporario.replace(caminho)


def gravar_csv(caminho: Path, campos: list[str], registros) -> None:
    # BOM facilita a leitura de acentos no Excel; os decimais seguem o padrão CSV.
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(registros)


def versao_codigo() -> dict:
    arquivos = [Path(__file__).resolve(), *sorted((RAIZ / "algoritmos").rglob("*.py"))]
    versao = {
        "commit": None, "arvore_modificada": None,
        "sha256_arquivos": {
            arquivo.relative_to(RAIZ).as_posix(): sha256(arquivo.read_bytes())
            for arquivo in arquivos
        },
    }
    try:
        opcoes = {"cwd": RAIZ, "capture_output": True, "text": True, "timeout": 5, "check": True}
        versao["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], **opcoes).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"], **opcoes)
        versao["arvore_modificada"] = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        # Os hashes continuam identificando o código se o Git não estiver disponível.
        pass
    return versao


def versoes_dependencias() -> dict:
    versoes = {"python": platform.python_version()}
    for pacote in (
        "numpy", "opencv-python", "opencv-python-headless", "opencv-contrib-python",
        "opencv-contrib-python-headless",
    ):
        try:
            versoes[pacote] = metadata.version(pacote)
        except metadata.PackageNotFoundError:
            continue
    return versoes


def desenhar_painel(cv2, np, imagem, registros: list[dict], titulo: str):
    altura, largura = imagem.shape[:2]
    margem = 68
    painel = np.full((altura + margem, max(largura, 420), 3), 28, dtype=np.uint8)
    painel[margem:, :largura] = imagem
    cv2.putText(painel, titulo, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    for classe, texto, x in ((0, "0 normal", 10), (1, "1 aglomerado", 130), (2, "2 pequeno", 285)):
        cv2.putText(painel, texto, (x, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.45, CORES[classe], 1, cv2.LINE_AA)
    for registro in registros:
        x, y = registro["caixa_x_px"], registro["caixa_y_px"]
        w, h = registro["caixa_largura_px"], registro["caixa_altura_px"]
        x1, y1 = max(0, math.floor(x)), max(0, math.floor(y))
        x2 = min(largura - 1, math.ceil(x + w) - 1)
        y2 = min(altura - 1, math.ceil(y + h) - 1)
        cor = CORES[registro["classe"]]
        cv2.rectangle(painel, (x1, y1 + margem), (x2, y2 + margem), cor, 1)
        cv2.putText(
            painel, str(registro["classe"]), (x1, max(margem + 11, y1 + margem - 3)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, cor, 1, cv2.LINE_AA,
        )
    return painel


def executar(args: argparse.Namespace) -> Path:
    rodada = getattr(args, "rodada", "round0")
    if not isinstance(rodada, str) or re.fullmatch(r"round(?:0|[1-9][0-9]*)", rodada) is None:
        raise ValueError("A rodada deve ter o formato round0, round1, round2, ...")
    saida_rodada = (SAIDA / rodada).resolve()
    if not saida_rodada.is_relative_to(SAIDA.resolve()):
        raise ValueError("A pasta da rodada precisa permanecer dentro de limiarizacao/.")
    imagem_path, anotacao_path, config_path = (
        caminho.expanduser().resolve(strict=True) for caminho in (args.imagem, args.anotacao, args.config)
    )
    if imagem_path.stem != anotacao_path.stem:
        raise ValueError("Imagem e anotação devem ter o mesmo nome-base, como 11_frame_0.")
    config_bytes, anotacao_bytes = config_path.read_bytes(), anotacao_path.read_bytes()
    dados_config = ler_configuracao(config_bytes)
    anotacoes = ler_anotacoes(anotacao_bytes)
    try:
        import cv2
        import numpy as np
        sys.path.insert(0, str(RAIZ))
        from algoritmos.classicos.classificacao import ConfiguracaoArea
        from algoritmos.classicos.limiarizacao import ConfiguracaoLimiarizacao, ConfiguracaoMorfologia, detectar
    except ModuleNotFoundError as erro:
        raise ValueError(
            "Dependência não encontrada. Instale com: python -m pip install -r "
            "algoritmos/classicos/requirements.txt"
        ) from erro
    config = ConfiguracaoLimiarizacao(**{
        **dados_config,
        "abertura": ConfiguracaoMorfologia(**dados_config["abertura"]),
        "fechamento": ConfiguracaoMorfologia(**dados_config["fechamento"]),
        "classificacao": ConfiguracaoArea(**dados_config["classificacao"]),
    })
    config_completa = asdict(config)
    canonico = json.dumps(config_completa, sort_keys=True, separators=(",", ":"), allow_nan=False)
    config_id = sha256(canonico.encode("utf-8"))
    imagem_bytes = imagem_path.read_bytes()
    # IMREAD_UNCHANGED conserva orientação e profundidade para não deslocar as caixas.
    imagem = cv2.imdecode(np.frombuffer(imagem_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if imagem is None:
        raise ValueError("Não foi possível decodificar a imagem.")
    if imagem.dtype != np.uint8 or imagem.ndim not in (2, 3):
        raise ValueError("A imagem deve ser uint8 em cinza ou BGR.")
    if imagem.ndim == 3 and imagem.shape[2] != 3:
        raise ValueError("A imagem colorida deve ter três canais BGR, sem transparência.")
    altura, largura = imagem.shape[:2]
    for item in anotacoes:
        item.update({
            "caixa_x_px": (item["caixa_centro_x_norm"] - item["caixa_largura_norm"] / 2) * largura,
            "caixa_y_px": (item["caixa_centro_y_norm"] - item["caixa_altura_norm"] / 2) * altura,
            "caixa_largura_px": item["caixa_largura_norm"] * largura,
            "caixa_altura_px": item["caixa_altura_norm"] * altura,
        })
    inicio = agora()
    nome = nome_configuracao(config_completa, config_id)
    pasta = saida_rodada / f"{nome}__{inicio.strftime('%Y%m%dT%H%M%S%fZ')}"
    origem = identificar_origem(imagem_path, anotacao_path)
    manifesto = {
        "situacao": "em_andamento", "etapa": "inspecao_individual", "algoritmo": "limiarizacao",
        "rodada": rodada,
        "inicio_utc": inicio.isoformat(), "fim_utc": None, "configuracao_sha256": config_id,
        "origem": origem, "configuracao_origem": str(config_path),
        "sha256_entradas": {"imagem": sha256(imagem_bytes), "anotacao": sha256(anotacao_bytes),
                            "configuracao_arquivo": sha256(config_bytes)},
        "codigo": versao_codigo(), "dependencias": {
            **versoes_dependencias(), "numpy_importado": np.__version__, "opencv_importado": cv2.__version__,
        },
        "identificacao_quadro": "nome do arquivo" if origem["video_id"] is not None else None,
        "dimensoes": {"largura": largura, "altura": altura},
        "unidades": {"comprimento": "pixel", "area": "pixel quadrado", "intensidade": "0 a 255",
                     "coordenadas_normalizadas": "fração da dimensão da imagem"},
        "metricas_calculadas": False,
    }
    # A criação exclusiva impede sobrescrever uma execução existente.
    pasta.mkdir(parents=True, exist_ok=False)
    try:
        gravar_json(pasta / "execucao.json", manifesto)
        gravar_json(pasta / "configuracao.json", config_completa)
        resultado = detectar(imagem, config)
        predicoes = list(resultado.registros())
        gravar_csv(pasta / "deteccoes.csv", CAMPOS_ORIGEM + CAMPOS_DETECCAO,
                   ({**origem, **registro} for registro in predicoes))
        gravar_csv(pasta / "anotacoes.csv", CAMPOS_ORIGEM + CAMPOS_ANOTACAO,
                   ({**origem, **registro} for registro in anotacoes))
        linhas = resultado.linhas_yolo()
        (pasta / "predicoes.txt").write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
        resumo = {**origem, "quantidade_anotacoes": len(anotacoes), "quantidade_deteccoes": len(predicoes),
                  "limiar_utilizado": resultado.limiar_utilizado}
        for classe in CORES:
            resumo[f"anotacoes_classe_{classe}"] = sum(item["classe"] == classe for item in anotacoes)
            resumo[f"deteccoes_classe_{classe}"] = sum(item["classe"] == classe for item in predicoes)
        gravar_csv(pasta / "por_quadro.csv", list(resumo), [resumo])
        colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
        esquerda = desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}")
        direita = desenhar_painel(cv2, np, colorida, predicoes, f"Deteccoes: {len(predicoes)} | {config.metodo}")
        comparacao = np.concatenate((esquerda, direita), axis=1)
        sucesso, png = cv2.imencode(".png", comparacao)
        if not sucesso:
            raise ValueError("Não foi possível gerar a imagem de comparação.")
        midia = pasta / "midia"
        midia.mkdir()
        nome_midia = f"{imagem_path.stem}__comparacao.png"
        (midia / nome_midia).write_bytes(png.tobytes())
        manifesto.update({
            "situacao": "concluida", "fim_utc": agora().isoformat(),
            "quantidade_anotacoes": len(anotacoes), "quantidade_deteccoes": len(predicoes),
            "limiar_utilizado": resultado.limiar_utilizado,
            "comparacao": f"midia/{nome_midia}",
        })
        gravar_json(pasta / "execucao.json", manifesto)
    except BaseException as erro:
        manifesto.update({"situacao": "falhou", "fim_utc": agora().isoformat(),
                          "erro": f"{type(erro).__name__}: {erro}"})
        try:
            gravar_json(pasta / "execucao.json", manifesto)
        except OSError:
            pass
        print(f"Execução incompleta em: {pasta}", file=sys.stderr)
        raise
    return pasta


def main() -> int:
    args = argumentos()
    try:
        pasta = executar(args)
    except KeyboardInterrupt:
        print("Execução interrompida.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Resultados salvos em: {pasta}")
    print("Abra a imagem em midia/ para comparar anotações e detecções. Não foram calculadas métricas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
