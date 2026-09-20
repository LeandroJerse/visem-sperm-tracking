"""Executa as candidatas congeladas nos 60 quadros de seleção acordados."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from scripts.limiarizacao import executar_rodada as batch


PLANO_PADRAO = Path(__file__).resolve().parent / "selecao" / "plano.json"
VIDEOS_SELECAO = ("13", "29", "52", "54")
QUADROS_SELECAO = tuple(range(0, 1401, 100))
CONFIGURACOES_POR_RODADA = (48, 32, 24, 18, 14)
TOTAL_CONFIGURACOES = 122
CRITERIOS_AVALIACAO = {
    "iou_minimo": 0.5,
    "principal": "Correspondência um-para-um com a mesma classe; maximiza quantidade de pares válidos e depois soma das IoUs.",
    "localizacao": "Diagnóstico auxiliar com novo pareamento independente, ignorando a classe.",
    "agregacao": "Somar TP, FP e FN antes de calcular F1 e macro-F1; não fazer média dos F1 por quadro.",
    "macro_f1": "Média das três classes 0, 1 e 2, apenas quando todas tiverem F1 definido.",
    "sem_casos": "F1 indefinido somente quando TP=FP=FN=0; manter null. Previsões sem anotação são falsos positivos e resultam em F1 zero.",
    "ordenacao": "Macro-F1 decrescente; somente empate exato usa F1 da classe 0. Se ambos empatam, ID serve apenas para ordem visual determinística e não decide promoção.",
    "tempo": "Tempos são diagnóstico, sem desempate automático.",
    "decisao": "As cinco finalistas serão discutidas após avaliar os resultados da seleção; não são as cinco primeiras do desenvolvimento por definição.",
}


def _json(conteudo: bytes) -> dict:
    dados = json.loads(conteudo.decode("utf-8-sig"),
                       parse_constant=batch.rejeitar_constante,
                       object_pairs_hook=batch.objeto_sem_duplicatas)
    if not isinstance(dados, dict):
        raise ValueError("O documento deve ser um objeto JSON.")
    return dados


def _hash_valido(valor: object) -> bool:
    return isinstance(valor, str) and re.fullmatch(r"[0-9a-f]{64}", valor) is not None


def _parametros_canonicos(parametros: dict) -> dict:
    dados = batch.ler_configuracao(json.dumps(parametros, allow_nan=False).encode("utf-8"))
    canonicos = deepcopy(dados)
    for operacao in ("abertura", "fechamento"):
        if dados[operacao]["iteracoes"] == 0:
            canonicos[operacao] = {"forma": "elipse", "tamanho": 3, "iteracoes": 0}
    return canonicos


def _ler_fonte(caminho: str, hash_esperado: str, pasta_permitida: Path) -> bytes:
    if not isinstance(caminho, str) or not _hash_valido(hash_esperado):
        raise ValueError("A fonte deve informar caminho relativo e SHA-256 válido.")
    relativo = Path(caminho)
    if relativo.is_absolute() or ".." in relativo.parts:
        raise ValueError("O caminho da fonte deve permanecer dentro do projeto.")
    arquivo = (RAIZ / relativo).resolve(strict=True)
    if not arquivo.is_relative_to(pasta_permitida.resolve()) or not arquivo.is_file():
        raise ValueError(f"Fonte fora da pasta permitida: {caminho}.")
    conteudo = arquivo.read_bytes()
    if batch.sha256(conteudo) != hash_esperado:
        raise ValueError(f"A fonte mudou desde o congelamento: {caminho}.")
    return conteudo


def _conferir_fontes(plano: dict) -> list[tuple[dict, dict, dict]]:
    """Lê apenas os registros de desenvolvimento que originaram as candidatas."""
    geracao = plano.get("geracao")
    if not isinstance(geracao, dict):
        raise ValueError("O plano precisa registrar a geração e suas fontes.")
    fontes = geracao.get("fontes_desenvolvimento")
    if not isinstance(fontes, list) or len(fontes) != 5:
        raise ValueError("A seleção exige as cinco fontes de desenvolvimento.")
    registros = []
    for numero, (fonte, quantidade) in enumerate(zip(fontes, CONFIGURACOES_POR_RODADA), start=1):
        rodada = f"round{numero}"
        if not isinstance(fonte, dict) or fonte.get("rodada") != rodada:
            raise ValueError("As fontes devem seguir a ordem round1 a round5.")
        pasta = fonte.get("pasta_batch")
        prefixo = f"resultados/frame-to-frame/limiarizacao/{rodada}/"
        if not isinstance(pasta, str) or re.fullmatch(re.escape(prefixo) + r"batch__[0-9]{8}T[0-9]{12}Z", pasta) is None:
            raise ValueError(f"Pasta de origem inválida para {rodada}.")
        nomes = ("rodada.json", "execucao.json", "resumo_configuracoes.csv", "resumo_por_video.csv")
        hashes = fonte.get("sha256_arquivos")
        if not isinstance(hashes, dict) or set(hashes) != {f"{pasta}/{nome}" for nome in nomes}:
            raise ValueError(f"A fonte {rodada} deve registrar os quatro arquivos e seus hashes.")
        conteudos = {
            nome: _ler_fonte(f"{pasta}/{nome}", hashes[f"{pasta}/{nome}"], RAIZ / prefixo)
            for nome in nomes
        }
        anterior = batch.carregar_plano(conteudos["rodada.json"])
        execucao = _json(conteudos["execucao.json"])
        if anterior["rodada"] != rodada or len(anterior["configuracoes"]) != quantidade:
            raise ValueError(f"Composição de desenvolvimento divergente em {rodada}.")
        if (execucao.get("situacao") != "concluida"
                or execucao.get("etapa") != "desenvolvimento_imagens"
                or execucao.get("rodada") != rodada
                or execucao.get("plano_sha256") != batch.sha256(conteudos["rodada.json"])
                or execucao.get("configuracoes_concluidas") != quantidade
                or execucao.get("quadros_por_configuracao") != 178):
            raise ValueError(f"A fonte {rodada} não corresponde a uma rodada concluída.")
        registros.append((fonte, anterior, execucao))
    resumo = geracao.get("resumo_desenvolvimento")
    if not isinstance(resumo, dict):
        raise ValueError("Falta o registro do resumo de desenvolvimento congelado.")
    _ler_fonte(resumo.get("arquivo"), resumo.get("sha256"), RAIZ / "analise")
    return registros


def _configuracoes_esperadas(fontes: list[tuple[dict, dict, dict]]) -> list[dict]:
    candidatas: dict[str, dict] = {}
    for fonte, anterior, execucao in fontes:
        execucoes = execucao.get("execucoes")
        if not isinstance(execucoes, list) or len(execucoes) != len(anterior["configuracoes"]):
            raise ValueError("As execuções de origem não correspondem às configurações.")
        por_id = {}
        for item in execucoes:
            if not isinstance(item, dict) or not isinstance(item.get("configuracao_id"), str):
                raise ValueError("Execução de origem sem identificação válida.")
            if item["configuracao_id"] in por_id or not isinstance(item.get("pasta"), str):
                raise ValueError("Execução de origem duplicada ou sem pasta.")
            por_id[item["configuracao_id"]] = item["pasta"]
        if set(por_id) != {item["id"] for item in anterior["configuracoes"]}:
            raise ValueError("Há configurações sem execução de origem correspondente.")
        arquivo_plano = f"{fonte['pasta_batch']}/rodada.json"
        for item in anterior["configuracoes"]:
            chave = batch.hash_configuracao(_parametros_canonicos(item["parametros"]))
            origem = {
                "rodada": anterior["rodada"], "configuracao_id": item["id"],
                "arquivo_plano": arquivo_plano,
                "sha256_plano": fonte["sha256_arquivos"][arquivo_plano],
                "pasta_execucao": por_id[item["id"]],
            }
            if chave not in candidatas:
                candidatas[chave] = {
                    "id": f"s{len(candidatas) + 1:03d}", "parametros": item["parametros"],
                    "sha256_parametros_canonicos": chave, "origens": [],
                }
            candidatas[chave]["origens"].append(origem)
    if len(candidatas) != TOTAL_CONFIGURACOES:
        raise ValueError("As fontes não reproduzem as 122 configurações únicas acordadas.")
    return list(candidatas.values())


def carregar_plano_selecao(conteudo: bytes) -> dict:
    plano = _json(conteudo)
    if (type(plano.get("versao")) is not int or plano["versao"] != 1
            or plano.get("algoritmo") != "limiarizacao"
            or plano.get("particao") != "selecao" or plano.get("rodada") != "selecao"):
        raise ValueError("Use o plano de seleção de limiarização, versão 1.")
    if type(plano.get("seed")) is not int or plano["seed"] != 42:
        raise ValueError("A seed do registro de seleção deve permanecer 42.")
    if plano.get("criterios_avaliacao") != CRITERIOS_AVALIACAO:
        raise ValueError(
            "Os critérios devem preservar o contrato acordado: IoU 0,50, mesma classe, "
            "associação única, agregação por contagens, sem casos indefinidos e "
            "macro-F1 com classe 0 somente no empate exato; sem desempate por tempo."
        )
    if plano.get("politica_anotacoes_ausentes") != "erro" or plano.get("exclusoes") != []:
        raise ValueError("Nenhuma exclusão está autorizada nos 60 quadros de seleção.")
    quadros = plano.get("quadros")
    ordem = [(video, quadro) for video in VIDEOS_SELECAO for quadro in QUADROS_SELECAO]
    if not isinstance(quadros, list) or len(quadros) != len(ordem):
        raise ValueError("A seleção deve conter exatamente os 60 quadros acordados.")
    for item, (video, quadro) in zip(quadros, ordem):
        if (not isinstance(item, dict) or item.get("video_id") != video
                or type(item.get("quadro")) is not int or item["quadro"] != quadro):
            raise ValueError("Os quadros devem seguir a ordem dos vídeos 13, 29, 52 e 54, de 0 a 1400, passo 100.")
        base = f"bases_de_dados/visem_tracking/dataset/Train/{video}"
        for campo, pasta, sufixo in (("imagem", "images", "jpg"), ("anotacao", "labels", "txt")):
            if item.get(campo) != f"{base}/{pasta}/{video}_frame_{quadro}.{sufixo}":
                raise ValueError(f"Caminho incoerente para {video}/{quadro}: {campo}.")
            if not _hash_valido(item.get(f"sha256_{campo}")):
                raise ValueError(f"Hash ausente ou inválido: {campo} de {video}/{quadro}.")
    configs = plano.get("configuracoes")
    if not isinstance(configs, list) or len(configs) != TOTAL_CONFIGURACOES:
        raise ValueError("A seleção deve conter todas as 122 configurações únicas.")
    geracao = plano.get("geracao", {})
    if (not isinstance(geracao, dict)
            or geracao.get("aleatoriedade_utilizada") is not False
            or geracao.get("configuracoes_congeladas") is not True
            or geracao.get("quantidade_configuracoes") != TOTAL_CONFIGURACOES
            or geracao.get("quantidade_execucoes_desenvolvimento") != sum(CONFIGURACOES_POR_RODADA)
            or geracao.get("ordem_configuracoes") != "primeiro_aparecimento"):
        raise ValueError("A seleção deve preservar a composição congelada e a ordem de primeiro aparecimento.")
    esperadas = _configuracoes_esperadas(_conferir_fontes(plano))
    vistos = set()
    for item, esperada in zip(configs, esperadas):
        if not isinstance(item, dict) or item.get("id") != esperada["id"]:
            raise ValueError("As configurações devem seguir a ordem s001 a s122.")
        chave = batch.hash_configuracao(_parametros_canonicos(item.get("parametros")))
        if chave in vistos:
            raise ValueError("O plano contém configurações equivalentes duplicadas.")
        vistos.add(chave)
        if (chave != esperada["sha256_parametros_canonicos"]
                or item.get("sha256_parametros_canonicos") != chave
                or item.get("parametros") != esperada["parametros"]
                or item.get("origens") != esperada["origens"]):
            raise ValueError(f"A candidata {item['id']} diverge das fontes de desenvolvimento congeladas.")
    return plano


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa as 122 candidatas congeladas nos 60 quadros de seleção.",
        epilog="Não redefine parâmetros nem escolhe automaticamente as cinco finalistas.",
    )
    parser.add_argument("--plano", type=Path, default=PLANO_PADRAO,
                        help="JSON de seleção; padrão: scripts/limiarizacao/selecao/plano.json.")
    return parser.parse_args()


def executar(args: argparse.Namespace) -> Path:
    return batch.executar_plano(
        args.plano.expanduser().resolve(strict=True), carregar_plano_selecao,
        rodada_solicitada="selecao", fontes_adicionais=(Path(__file__).resolve(),),
    )


def main() -> int:
    try:
        pasta = executar(argumentos())
    except KeyboardInterrupt:
        print("Seleção interrompida. Os arquivos existentes foram preservados.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Avaliação das candidatas concluída. Resumo: {pasta / 'resumo_configuracoes.csv'}")
    print("Compare macro-F1; F1 da classe 0 somente no empate exato. A escolha das cinco será conjunta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
