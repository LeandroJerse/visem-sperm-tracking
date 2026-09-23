"""Compara o catálogo congelado de blobs nas imagens de seleção acordadas."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from scripts.blobs import executar_rodada as rodada
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.planejamento_selecao import (
    carregar_plano, caminhos_origens, conferir_origens, nome_configuracao,
)

SAIDA = RAIZ / "resultados/frame-to-frame/blobs/selecao"
PLANO_PADRAO = "scripts/blobs/selecao/plano.json"
FONTES_CODIGO = tuple(dict.fromkeys((*rodada.FONTES_CODIGO,
    "scripts/blobs/executar_selecao.py", "scripts/blobs/planejamento_selecao.py",
    "analise/relatorio_selecao_blobs.py",
)))


def congelar_entradas(caminho_plano: Path) -> dict:
    """Confere procedência e captura as mesmas entradas para todas as candidatas."""
    caminho = Path(caminho_plano).expanduser().resolve(strict=True)
    if not caminho.is_relative_to(RAIZ.resolve()) or not caminho.is_file():
        raise ValueError("O plano deve ser um arquivo dentro do projeto.")
    conteudo = caminho.read_bytes()
    plano = carregar_plano(conteudo)
    origens = conferir_origens(plano, RAIZ)
    caminhos = caminhos_origens(plano)
    hashes = {rodada.relativo(caminho): rodada.sha256(conteudo)}
    hashes.update({caminhos[nome]: rodada.sha256(blob) for nome, blob in origens.items()})
    entradas = []
    for quadro in plano["quadros"]:
        entrada = {"quadro": quadro}
        for tipo in ("imagem", "anotacao"):
            fonte = rodada.caminho_interno(quadro[tipo], RAIZ / "bases_de_dados")
            blob = fonte.read_bytes()
            digest = rodada.sha256(blob)
            if digest != quadro[f"{tipo}_sha256"]:
                raise ValueError(f"Hash divergente: {quadro[tipo]}.")
            hashes[quadro[tipo]] = digest
            entrada[f"{tipo}_bytes"] = blob
        entrada["anotacoes"] = rodada.ler_anotacoes(entrada["anotacao_bytes"])
        entradas.append(entrada)
    codigo = {nome: rodada.caminho_interno(nome).read_bytes() for nome in FONTES_CODIGO}
    return {"plano": plano, "plano_bytes": conteudo, "origens": origens,
            "hashes": hashes, "entradas": entradas, "codigo": codigo}


def atualizar_relatorio(pasta: Path) -> Path:
    """Gera outro PDF a partir dos resumos salvos, preservando relatórios anteriores."""
    from analise.relatorio_selecao_blobs import gerar_relatorio
    pasta = Path(pasta).expanduser().resolve(strict=True)
    if (pasta.parent != SAIDA.resolve() or not pasta.is_relative_to(RAIZ.resolve())
            or not pasta.name.startswith("batch__")):
        raise ValueError("Informe a pasta batch da seleção de imagens de blobs.")
    try:
        pdf = gerar_relatorio(pasta)
    except Exception as erro:
        gravar_json(pasta / "relatorio.json", {
            "situacao": "falhou", "erro": f"{type(erro).__name__}: {erro}"})
        raise
    gravar_json(pasta / "relatorio.json", {"situacao": "concluido", "arquivo": rodada.relativo(pdf)})
    return pdf


def executar(caminho_plano: Path) -> Path:
    print("Conferindo catálogo, origens, dependências e imagens de seleção...", flush=True)
    dados = congelar_entradas(caminho_plano)
    return rodada.executar_dados(
        dados, tipo="selecao_blobs", etapa="selecao_imagens", particao="selecao",
        interpretacao=("Comparação em imagens de seleção. Todas as configurações distintas do "
                       "desenvolvimento são avaliadas sem ajuste de parâmetros. O ranking é descritivo; "
                       "a escolha das cinco finalistas depende de revisão conjunta, incluindo empates."),
        relatorio=atualizar_relatorio, nomear=nome_configuracao,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compara as 119 configurações de blobs nos 60 frames de seleção.")
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--plano", type=Path, help="Plano congelado dentro do projeto; usa o plano de seleção por padrão.")
    origem.add_argument("--somente-relatorio", type=Path, metavar="BATCH", help="Gera outro PDF sem repetir detecções.")
    parser.add_argument("--conferir", action="store_true", help="Confere tudo antes do teste, sem detectar nem criar resultados.")
    args = parser.parse_args(argv)
    try:
        if args.somente_relatorio:
            if args.conferir:
                parser.error("--conferir não se aplica a --somente-relatorio.")
            print(f"Relatório: {atualizar_relatorio(args.somente_relatorio)}")
            return 0
        caminho = args.plano or RAIZ / PLANO_PADRAO
        if args.conferir:
            dados = congelar_entradas(caminho)
            rodada.conferir_ambiente_e_imagens(dados)
            n, q = len(dados["plano"]["configuracoes"]), len(dados["plano"]["quadros"])
            print(f"Conferência concluída: {n} configurações, {q} quadros, {n * q} avaliações previstas.")
            print("Nenhuma detecção executada; nenhuma pasta de resultados criada.")
        else:
            pasta = executar(caminho)
            print(f"Comparação de seleção concluída em: {pasta}")
            print("Consulte ranking.csv e o PDF. As cinco finalistas serão escolhidas após revisão dos resultados.")
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
