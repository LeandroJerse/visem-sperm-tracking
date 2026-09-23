"""Compara o catálogo de watershed nas 60 imagens reservadas."""

import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from scripts.watershed import executar_rodada as comum
from scripts.watershed import execucao_round2 as base
from scripts.watershed.execucao_round5 import FONTES as FONTES_ANTERIORES
from scripts.watershed.planejamento_selecao import (
    PLANO, conferir_origens, construir_plano, ler_configuracao, validar_plano,
)
from scripts.watershed.saidas_selecao import executar_quadro

SAIDA = RAIZ / "resultados/frame-to-frame/watershed/selecao"
FONTES = (*FONTES_ANTERIORES, "scripts/watershed/planejamento_selecao.py",
          "scripts/watershed/executar_selecao.py", "scripts/watershed/saidas_selecao.py",
          "analise/relatorio_selecao_watershed.py")


def congelar_entradas():
    return base.congelar_entradas(PLANO, validar=validar_plano, construir=construir_plano,
        conferir=conferir_origens, fontes=FONTES, evoluidas=base.FONTES_EVOLUIDAS, referencia="round5")


def nome_configuracao(item, config, instante):
    w=item["parametros"]["watershed"]; s=w["segmentacao"]; delta=item["parametros"]["deslocamento_otsu"]
    limiar = f"manual{s['limiar_manual']}" if s["metodo"]=="manual" else f"otsu-d{'m' if delta<0 else 'p'}{abs(delta)}"
    politica="separar" if w["politica_aglomerados"]=="separar" else "preservar"
    return (f"{item['id']}__{limiar}-{s['polaridade']}-s{w['fracao_semente']:g}-{politica}"
            f"-amin{s['area_minima']}-fec{s['fechamento']['tamanho']}__cfg-{item['parametros_sha256'][:12]}__{instante}")


def processar(dados):
    from analise.relatorio_selecao_watershed import gerar_relatorio
    return comum.processar(dados, saida=SAIDA, ler_config=ler_configuracao, executar_quadro=executar_quadro,
                          nome_config=nome_configuracao, relatorio=gerar_relatorio)


def main(argv=None):
    parser=argparse.ArgumentParser(description="Seleção de watershed: 114 configurações x 60 imagens.")
    grupo=parser.add_mutually_exclusive_group()
    grupo.add_argument("--conferir",action="store_true",help="Confere entradas sem executar detecção.")
    grupo.add_argument("--somente-relatorio",type=Path,metavar="BATCH",help="Gera outro PDF a partir das métricas salvas.")
    args=parser.parse_args(argv)
    try:
        if args.somente_relatorio:
            from analise.relatorio_selecao_watershed import gerar_relatorio
            print(f"PDF: {gerar_relatorio(args.somente_relatorio)}")
            return 0
        print("Conferindo catálogo, origens, código, dependências e 60 imagens...",flush=True)
        dados=congelar_entradas()
        if args.conferir:
            print(f"Conferência concluída: 114 configurações, 60 imagens, {len(dados['hashes'])} origens íntegras.")
            print("6.840 avaliações previstas. Detector não executado; nenhuma pasta de resultados criada.")
        else:
            print(f"Seleção concluída: {processar(dados)}")
            print("Consulte o ranking e o PDF. As cinco finalistas dependem de revisão conjunta.")
        return 0
    except (ValueError,OSError,RuntimeError,ImportError) as erro:
        print(f"Erro: {erro}",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
