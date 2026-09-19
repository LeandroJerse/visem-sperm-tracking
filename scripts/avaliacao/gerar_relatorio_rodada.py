"""Gera um PDF de uma rodada concluída, sem executar detecção ou avaliação."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from analise.relatorio_rodada import gerar_relatorio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera gráficos e estatísticas descritivas de um batch já concluído.",
        epilog="Use a pasta batch__<execucao>, não a pasta de uma configuração. Não repete o experimento.",
    )
    parser.add_argument("--batch", type=Path, required=True, help="Pasta com execucao.json, rodada.json e os resumos CSV.")
    args = parser.parse_args()
    try:
        pdf = gerar_relatorio(args.batch)
    except KeyboardInterrupt:
        print("Geração do relatório interrompida. Os resultados do experimento foram preservados.", file=sys.stderr)
        return 130
    except Exception as erro:
        print(f"Erro ao gerar o relatório: {erro}", file=sys.stderr)
        return 1
    print(f"PDF salvo em: {pdf}")
    print("O relatório usa os resultados já salvos; nenhuma detecção foi repetida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
