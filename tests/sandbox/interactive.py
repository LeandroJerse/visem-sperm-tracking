"""Launcher interativo do sandbox de teste unitário.

Espelha ``src.detection.interactive`` (modo de produção), mas para a bancada de
**um detector em um frame**: pergunta a fonte do vídeo, o frame, o método e os
parâmetros ajustáveis (com defaults — Enter aceita), monta o comando equivalente
a ``python -m tests.sandbox.single_frame ...`` e executa.

Uso:
    python -m tests.sandbox.interactive
"""
from __future__ import annotations

from pathlib import Path

# Reaproveita os helpers de prompt e a descoberta de vídeos da produção.
from src.detection.interactive import (
    ask,
    ask_choice,
    ask_int,
    ask_yes_no,
    discover_ids,
    discover_raw_videos,
)
from src.detection.run_detection import DETECTORS

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
    "blob": {
        "min_threshold": "10", "max_threshold": "200", "dark": "true",
        "min_area": "2", "max_area": "200",
    },
    "bgsub": {
        "method": "MOG2", "history": "200", "var_threshold": "16", "morph_kernel": "3",
        "min_area": "3", "max_area": "400",
    },
    "watershed": {
        "blur": "3", "dist_ratio": "0.4", "morph_kernel": "3",
        "min_area": "3", "max_area": "600",
    },
    "yolo": {},
}


def ask_frame(prompt: str, default: int = 0) -> int:
    """Inteiro >= 0 (o frame 0 é válido; ``ask_int`` de produção o rejeita)."""
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
        ids = discover_ids()
        if not ids:
            print("Nenhum vídeo anotado encontrado em data/tracked/.")
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
        print("Nenhum vídeo bruto encontrado em data/raw/videos/.")
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


def main() -> None:
    print("=== Sandbox de detecção — 1 detector, 1 frame ===")

    source_argv, _ = pick_source()
    if not source_argv:
        return

    method = ask_choice("\nMétodo de detecção:", list(DETECTORS), default="threshold")
    frame = ask_frame("\nQual frame analisar?", default=0)

    extra: list[str] = []
    if method == "bgsub":
        warmup = ask_int(
            "Frames de aquecimento antes do alvo (bgsub adapta o fundo)", default="30"
        )
        if warmup:
            extra += ["--warmup", str(warmup)]
    if method == "threshold":
        thresh_raw = ask("\nValor do threshold (0-255) ou Enter para Otsu automático", default="")
        if thresh_raw.strip():
            extra += ["--set", f"threshold_value={thresh_raw.strip()}"]
    if method in ("threshold", "bgsub", "watershed"):
        iters = ask_int("\nQuantas aberturas morfológicas (morph_open)?", default="1") or 1
        if iters != 1:
            extra += ["--set", f"morph_iterations={iters}"]
        close_iters = ask_int("Quantos fechamentos morfológicos (morph_close)? (0 = desabilitado)", default="1") or 0
        if close_iters != 1:
            extra += ["--set", f"close_iterations={close_iters}"]
    if method == "yolo":
        weights = ask("Caminho dos pesos YOLO (.pt)", default="")
        if not weights:
            print("Cancelado: YOLO requer um arquivo de pesos (.pt).")
            return
        extra += ["--weights", weights]

    draw_mode = ask_choice(
        "\nModo de desenho das caixas:", ["both", "box", "centroid", "circle"], default="both"
    )
    overrides = ask_overrides(method)
    out_dir = ask("\nPasta de saída", default="results/tests")

    argv = (
        ["--method", method, *source_argv, "--frame", str(frame),
         "--draw-mode", draw_mode, "--out-dir", out_dir]
        + extra + overrides
    )

    print("\nComando equivalente:")
    print("  python -m tests.sandbox.single_frame " + " ".join(
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
