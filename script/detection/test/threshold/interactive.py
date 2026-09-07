"""Launcher interativo da triagem histórica de threshold.

Pergunta a fonte, o frame e os parâmetros do threshold, monta o comando
equivalente e executa a mesma implementação de ``src/detection/classical``.
Vídeos do teste bloqueado não aparecem como opção.

Uso:
    python -m script.detection.test.threshold.interactive
"""
from __future__ import annotations

import argparse
from pathlib import Path

# Reaproveita os helpers de prompt do menu exploratório geral.
from script.detection.test.interactive import (
    ask,
    ask_choice,
    ask_yes_no,
)
from src.core.paths import REPOSITORY_ROOT
from src.detection.discovery import discover_raw_videos, discover_tracked_ids
from src.experiments.dataset import load_split_spec

from .single_frame import main as run_single_frame

# Parâmetros ajustáveis por método (nome -> valor padrão como string).
# Servem só para o menu sugerir o que dá para mexer; o cast é feito no
# single_frame. Mantemos alinhado aos construtores em src/detection/.
# Parâmetros secundários expostos no bloco opcional "Ajustar parâmetros?".
# threshold_value e morph_iterations são perguntas diretas no fluxo principal
# e NÃO ficam aqui. min_area/max_area são do filtro de área (CCL), não do limiar.
TUNABLE: dict[str, dict[str, str]] = {
    "threshold": {
        "blur": "1", "invert": "false", "adaptive": "false", "morph_kernel": "3",
        "min_area": "3", "max_area": "300",
    },
}


def ask_frame(prompt: str, default: int = 0) -> int:
    """Lê um inteiro não negativo; o frame/zero iterações são válidos."""
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        if value.isdigit():
            return int(value)
        print("  Digite um número inteiro >= 0 ou Enter.")


def pick_source() -> tuple[list[str], str | None]:
    """Escolhe a fonte e devolve ``(argv_da_fonte, max_frame_index)``.

    ``max_frame_index`` é só informativo (string ou None) para orientar a
    escolha do frame.
    """
    source = ask_choice(
        "\nQual fonte de vídeo?",
        ["anotado (VISEM-Tracking, com gabarito)", "bruto (VISEM original, sem gabarito)"],
        default="anotado (VISEM-Tracking, com gabarito)",
    )
    if source.startswith("anotado"):
        split = load_split_spec(
            REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml"
        )
        allowed = set(split.train) | set(split.val)
        ids = [video_id for video_id in discover_tracked_ids() if video_id in allowed]
        if not ids:
            print("Nenhum vídeo anotado encontrado em data/sources/visem_tracking/.")
            return [], None
        print(f"\nIDs com gabarito disponíveis ({len(ids)}):")
        print("  " + "  ".join(ids))
        while True:
            vid = ask("Digite o ID do vídeo", default=ids[0])
            if vid in ids:
                return ["--id", vid], None
            print(f"  ID inválido. Escolha um da lista: {', '.join(ids)}")

    videos = discover_raw_videos()
    if not videos:
        print("Nenhum vídeo bruto encontrado em data/sources/visem/videos/.")
        return [], None
    ids = list(videos)
    print(f"\nIDs de vídeos brutos disponíveis ({len(ids)}):")
    print("  " + "  ".join(ids))
    print("(VISEM original — sem anotação manual.)")
    while True:
        vid = ask("Digite o ID do vídeo", default=ids[0])
        if vid in videos:
            return ["--video", str(videos[vid])], None
        print(f"  ID inválido. Escolha um da lista: {', '.join(ids)}")


def ask_overrides(method: str) -> list[str]:
    """Pergunta, parâmetro a parâmetro, se quer ajustar (Enter = padrão)."""
    params = TUNABLE.get(method, {})
    if not params:
        return []
    if not ask_yes_no(
        f"\nAjustar parâmetros do '{method}'? (não = usa os padrões)", default=False
    ):
        return []
    print("(Enter mantém o padrão entre colchetes.)")
    argv: list[str] = []
    for name, default in params.items():
        value = ask(f"  {name}", default=default)
        if value != default:
            argv += ["--set", f"{name}={value}"]
    return argv


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Menu de triagem frame a frame da família threshold; "
            "o teste bloqueado não é listado."
        )
    )
    parser.parse_args(argv)
    print("=== Triagem de threshold — 1 configuração, 1 frame ===")

    source_argv, _ = pick_source()
    if not source_argv:
        return

    method = "threshold"
    frame = ask_frame("\nQual frame analisar?", default=0)

    extra: list[str] = []
    thresh_raw = ask(
        "\nValor do threshold (0-255) ou Enter para Otsu automático", default=""
    )
    if thresh_raw.strip():
        extra += ["--set", f"threshold_value={thresh_raw.strip()}"]
    opening = ask_frame("\nQuantas aberturas morfológicas?", default=1)
    closing = ask_frame("Quantos fechamentos morfológicos?", default=1)
    if opening != 1:
        extra += ["--set", f"morph_iterations={opening}"]
    if closing != 1:
        extra += ["--set", f"close_iterations={closing}"]

    draw_mode = ask_choice(
        "\nModo de desenho das caixas:", ["both", "box", "centroid", "circle"], default="both"
    )
    overrides = ask_overrides(method)

    argv = (
        ["--method", method, *source_argv, "--frame", str(frame),
         "--draw-mode", draw_mode]
        + extra + overrides
    )

    print("\nComando equivalente:")
    print("  python -m script.detection.test.threshold.single_frame " + " ".join(
        f'"{a}"' if " " in a or "/" in a or "\\" in a else a for a in argv
    ))
    if not ask_yes_no("\nExecutar agora?", default=True):
        print("Cancelado.")
        return

    print("\n--- executando ---")
    summary = run_single_frame(argv)

    # Atalho para abrir a pasta de resultados no Explorer (Windows).
    out = Path(summary["out_dir"])
    if ask_yes_no(f"\nAbrir a pasta de resultados ({out})?", default=False):
        import os
        os.startfile(out)  # noqa: S606 - conveniência local no Windows


if __name__ == "__main__":
    main()
