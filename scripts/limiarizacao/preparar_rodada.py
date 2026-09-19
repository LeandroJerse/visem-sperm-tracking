"""Materializa uma rodada exploratória reproduzível, sem executar detectores.

A mesma seed, este gerador e os mesmos arquivos produzem o mesmo plano. Para
repetir um experimento, prefira o plano já salvo: ele fixa as configurações e
os hashes das entradas, sem depender de um novo sorteio.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import re


RAIZ = Path(__file__).resolve().parents[2]
VERSAO_GERADOR = "1.1"
VIDEOS = (11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47, 60)
QUADROS = tuple(range(0, 1401, 100))
AUSENCIAS_CONHECIDAS = {(23, 900), (23, 1100)}
LIMIARES = (60, 90, 120, 150, 180, 210)
AREAS_MINIMAS = (1, 3, 6, 12, 24)
LIMITES_PEQUENO = (20, 40, 80, 120)
LIMITES_AGLOMERADO = (150, 250, 400, 600, 1000)
MORFOLOGIAS = (
    {"forma": "elipse", "tamanho": 3, "iteracoes": 0},
    {"forma": "elipse", "tamanho": 3, "iteracoes": 1},
    {"forma": "elipse", "tamanho": 5, "iteracoes": 1},
)


def sha256(arquivo: Path) -> str:
    resumo = hashlib.sha256()
    with arquivo.open("rb") as entrada:
        for trecho in iter(lambda: entrada.read(1024 * 1024), b""):
            resumo.update(trecho)
    return resumo.hexdigest()


def configuracao_inicial() -> dict:
    """Repete os valores do teste inicial, sem depender de um arquivo mutável."""
    return {
        "metodo": "otsu",
        "polaridade": "claro",
        "limiar_manual": None,
        "abertura": dict(MORFOLOGIAS[0]),
        "fechamento": dict(MORFOLOGIAS[0]),
        "conectividade": 8,
        "area_minima": 1,
        "area_maxima": None,
        "classificacao": {
            "area_maxima_pequeno": 40,
            "area_minima_aglomerado": 150,
        },
    }


def sortear_configuracoes(seed: int) -> list[dict]:
    """Gera 12 configurações por combinação de método e polaridade.

    Nos estratos manuais, cada limiar aparece duas vezes. As demais variáveis
    são sorteadas independentemente, rejeitando duplicatas e combinações que
    eliminariam toda a faixa de área da classe pequena. Operações desativadas
    têm uma única representação para evitar duplicatas equivalentes.
    """
    sorteio = random.Random(seed)
    configuracoes = []
    assinaturas = set()
    for metodo, polaridade in (
        ("otsu", "claro"),
        ("otsu", "escuro"),
        ("manual", "claro"),
        ("manual", "escuro"),
    ):
        limiares = list(LIMIARES) * 2 if metodo == "manual" else [None] * 12
        if metodo == "manual":
            sorteio.shuffle(limiares)
        for posicao, limiar in enumerate(limiares):
            for _ in range(10000):
                if metodo == "otsu" and polaridade == "claro" and posicao == 0:
                    parametros = configuracao_inicial()
                else:
                    parametros = {
                        "metodo": metodo,
                        "polaridade": polaridade,
                        "limiar_manual": limiar,
                        "abertura": dict(sorteio.choice(MORFOLOGIAS)),
                        "fechamento": dict(sorteio.choice(MORFOLOGIAS)),
                        "conectividade": 8,
                        "area_minima": sorteio.choice(AREAS_MINIMAS),
                        "area_maxima": None,
                        "classificacao": {
                            "area_maxima_pequeno": sorteio.choice(LIMITES_PEQUENO),
                            "area_minima_aglomerado": sorteio.choice(LIMITES_AGLOMERADO),
                        },
                    }
                if parametros["area_minima"] > parametros["classificacao"]["area_maxima_pequeno"]:
                    continue
                assinatura = json.dumps(parametros, sort_keys=True, separators=(",", ":"))
                if assinatura in assinaturas:
                    continue
                assinaturas.add(assinatura)
                configuracoes.append({"id": f"c{len(configuracoes) + 1:02d}", "parametros": parametros})
                break
            else:
                raise ValueError("Não foi possível sortear configurações distintas.")
    return configuracoes


def manifesto_entradas() -> tuple[list[dict], list[dict]]:
    """Lê somente os caminhos de desenvolvimento preestabelecidos."""
    quadros = []
    exclusoes = []
    for video in VIDEOS:
        pasta = Path("bases_de_dados/visem_tracking/dataset/Train") / str(video)
        for quadro in QUADROS:
            nome = f"{video}_frame_{quadro}"
            imagem = pasta / "images" / f"{nome}.jpg"
            anotacao = pasta / "labels" / f"{nome}.txt"
            entrada = {
                "video_id": str(video),
                "quadro": quadro,
                "imagem": imagem.as_posix(),
                "anotacao": anotacao.as_posix(),
            }
            if not (RAIZ / imagem).is_file():
                raise ValueError(f"Imagem ausente: {imagem.as_posix()}")
            if not (RAIZ / anotacao).is_file():
                if (video, quadro) not in AUSENCIAS_CONHECIDAS:
                    raise ValueError(f"Anotação ausente não prevista: {anotacao.as_posix()}")
                exclusoes.append({
                    **entrada,
                    "sha256_imagem": sha256(RAIZ / imagem),
                    "motivo": "Arquivo de anotação ausente; não é tratado como anotação vazia.",
                })
                continue
            quadros.append({
                **entrada,
                "sha256_imagem": sha256(RAIZ / imagem),
                "sha256_anotacao": sha256(RAIZ / anotacao),
            })
    return quadros, exclusoes


def gerar_plano(seed: int, rodada: str) -> dict:
    quadros, exclusoes = manifesto_entradas()
    return {
        "versao": 1,
        "algoritmo": "limiarizacao",
        "particao": "desenvolvimento",
        "rodada": rodada,
        "seed": seed,
        "politica_anotacoes_ausentes": "exclusao_explicita",
        "geracao": {
            "versao_gerador": VERSAO_GERADOR,
            "arquivo_gerador": Path(__file__).resolve().relative_to(RAIZ).as_posix(),
            "sha256_gerador": sha256(Path(__file__)),
            "python": platform.python_version(),
            "estrategia": "amostragem_aleatoria_estratificada",
            "quantidade_configuracoes": 48,
            "configuracoes_por_metodo_polaridade": 12,
            "configuracao_inicial_incluida": "c01",
            "limiares_manuais_por_polaridade": "Cada limiar aparece exatamente duas vezes.",
            "restricoes": [
                "Sem configurações duplicadas.",
                "area_minima <= area_maxima_pequeno.",
                "Morfologia desativada: elipse, tamanho 3, zero iterações.",
            ],
            "espaco": {
                "metodo": ["manual", "otsu"],
                "polaridade": ["claro", "escuro"],
                "limiar_manual": list(LIMIARES),
                "abertura": list(MORFOLOGIAS),
                "fechamento": list(MORFOLOGIAS),
                "conectividade": [8],
                "area_minima": list(AREAS_MINIMAS),
                "area_maxima": [None],
                "area_maxima_pequeno": list(LIMITES_PEQUENO),
                "area_minima_aglomerado": list(LIMITES_AGLOMERADO),
            },
            "videos_desenvolvimento": list(VIDEOS),
            "quadros_previstos_por_video": list(QUADROS),
        },
        "configuracoes": sortear_configuracoes(seed),
        "quadros": quadros,
        "exclusoes": exclusoes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", required=True, type=Path, help="Novo JSON dentro de scripts/limiarizacao/rodadas; nunca sobrescreve.")
    parser.add_argument("--seed", type=int, default=42, help="Seed do sorteio (padrão: 42).")
    parser.add_argument("--rodada", default="round1", help="Pasta de destino dos resultados, como round1.")
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed deve ser um inteiro não negativo.")
    if re.fullmatch(r"round[1-9][0-9]*", args.rodada) is None:
        parser.error("--rodada deve seguir o formato round1, round2, etc.")
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    saida = saida.resolve()
    if not saida.is_relative_to((RAIZ / "scripts/limiarizacao/rodadas").resolve()) or saida.suffix.lower() != ".json":
        parser.error("--saida deve apontar para um arquivo .json dentro de scripts/limiarizacao/rodadas.")
    if saida.exists():
        parser.error(f"O arquivo já existe e será preservado: {saida}")
    try:
        plano = gerar_plano(args.seed, args.rodada)
        texto = json.dumps(plano, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        saida.parent.mkdir(parents=True, exist_ok=True)
        with saida.open("x", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(texto)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
    print(f"Plano salvo: {saida}")
    print(f"48 configurações; {len(plano['quadros'])} quadros; {len(plano['exclusoes'])} exclusões explícitas.")
    print("Nenhum detector ou avaliador foi executado. Para repetir, reutilize este JSON.")


if __name__ == "__main__":
    main()
