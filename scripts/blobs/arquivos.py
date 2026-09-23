"""Gravação de resultados com espera limitada para bloqueios do Windows."""

import json
from pathlib import Path
import sys
from time import sleep


INTERVALOS_REPETICAO = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0, 2.0)


def substituir_arquivo(temporario: Path, destino: Path) -> None:
    """Repete somente a troca, mantendo o destino intacto até ela ter sucesso.

    Acesso negado e violações de compartilhamento/bloqueio podem ser
    temporários no Windows. Permissões persistentes continuam causando erro
    após a espera limitada; o arquivo anterior e o temporário são preservados.
    Não reexecuta detecções, serialização ou acréscimos a tabelas.
    """
    for tentativa in range(len(INTERVALOS_REPETICAO) + 1):
        try:
            temporario.replace(destino)
            return
        except OSError as erro:
            if (getattr(erro, "winerror", None) not in (5, 32, 33)
                    or tentativa == len(INTERVALOS_REPETICAO)):
                raise
            if tentativa == 0:
                print(f"Windows impediu a atualização de {destino.name}; "
                      "aguardando para tentar novamente.", file=sys.stderr, flush=True)
            sleep(INTERVALOS_REPETICAO[tentativa])


def gravar_json(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    substituir_arquivo(temporario, caminho)
