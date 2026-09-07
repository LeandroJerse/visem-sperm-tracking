"""Modo interativo de detecção sobre o VISEM-Tracking.

Pergunta apenas o ID do vídeo (mostrando quais são permitidos) e, em seguida, as
demais opções com valores padrão (basta Enter para aceitar). Monta e executa o
comando equivalente a::

    python -m script.detection.test.run_detection --method <m> \
        --video data/sources/visem_tracking/dataset/Train/<id>/<id>.mp4 \
        --gt-dir data/sources/visem_tracking/dataset/Train/<id>/labels_ftid [--max-frames N ...]

Uso exploratório (treino/validação; teste bloqueado oculto):
    python -m script.detection.test.interactive
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.core.paths import REPOSITORY_ROOT
from src.detection.discovery import (
    RAW_VIDEOS_ROOT,
    TRAIN_ROOT,
    discover_raw_videos,
    discover_tracked_ids,
    discover_yolo_weights,
)
from src.experiments.dataset import load_split_spec

from src.detection import yolo_training
from src.detection.pipeline import main as run_main
from src.detection.registry import DETECTORS


# --------------------------------------------------------------------------- #
# Helpers de prompt
# --------------------------------------------------------------------------- #
def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "S/n" if default else "s/N"
    value = input(f"{prompt} [{hint}]: ").strip().lower()
    if not value:
        return default
    return value in ("s", "sim", "y", "yes")


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    print(prompt)
    for i, opt in enumerate(options, 1):
        marca = " (padrão)" if opt == default else ""
        print(f"  {i}) {opt}{marca}")
    value = input(f"Escolha (número ou nome) [{default}]: ").strip().lower()
    if not value:
        return default
    if value.isdigit() and 1 <= int(value) <= len(options):
        return options[int(value) - 1]
    if value in options:
        return value
    print(f"  Opção inválida, usando padrão: {default}")
    return default


def ask_weights_path() -> str | None:
    """Pede um caminho de .pt existente. Enter vazio = cancela (None)."""
    while True:
        value = input(
            "Caminho dos pesos YOLO (.pt) — Enter cancela: "
        ).strip().strip('"')
        if not value:
            return None
        if Path(value).is_file():
            return value
        print(f"  Arquivo não encontrado: {value}. Digite um caminho válido ou Enter para cancelar.")


def train_yolo_interactive() -> str | None:
    """Treina um YOLO no VISEM-Tracking e retorna o best.pt gerado (ou None)."""
    print("\n--- treinar YOLO no VISEM-Tracking ---")
    print("Dica: torch sem CUDA treina na CPU e é LENTO. Use poucos frames/épocas.")
    sample = ask_int(
        "Frames por vídeo (amostra leve p/ CPU; Enter = todos)", default="40"
    )
    epochs = ask_int("Épocas", default="5") or 5
    batch = ask_int("Batch", default="4") or 4

    argv = ["--epochs", str(epochs), "--batch", str(batch)]
    if sample is not None:
        argv += ["--max-frames-per-video", str(sample)]

    print("\nComando equivalente:")
    print("  python -m script.detection.test.yolo.train " + " ".join(argv))
    if not ask_yes_no("\nIniciar treino agora?", default=True):
        return None

    best = yolo_training.main(argv)
    if best is None or not Path(best).is_file():
        print("Treino não produziu best.pt (verifique os logs acima).")
        return None
    return str(best)


def ask_weights() -> str | None:
    """Resolve os pesos YOLO: usar run anterior, informar caminho, ou treinar.

    Retorna o caminho do .pt ou None (cancelar). YOLO não funciona sem pesos
    (modelo treinado/fine-tunado no VISEM-Tracking).
    """
    found = discover_yolo_weights()
    options = [f"usar: {p}" for p in found]
    options += ["informar caminho manualmente", "treinar agora (gera best.pt)"]
    default = options[0]

    choice = ask_choice("\nPesos do YOLO:", options, default=default)
    if choice.startswith("usar: "):
        return choice[len("usar: "):]
    if choice == "informar caminho manualmente":
        return ask_weights_path()
    return train_yolo_interactive()


def ask_int(prompt: str, default: str = "") -> int | None:
    """Inteiro positivo; Enter = sem limite (None)."""
    while True:
        value = input(f"{prompt} (Enter = todos){f' [{default}]' if default else ''}: ").strip()
        if not value:
            value = default
        if not value:
            return None
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("  Digite um número inteiro positivo ou Enter.")


# --------------------------------------------------------------------------- #
# Seleção da fonte de vídeo
# --------------------------------------------------------------------------- #
def pick_tracked() -> tuple[Path, Path | None] | None:
    """Escolhe um vídeo anotado (VISEM-Tracking) e opcionalmente seu gabarito."""
    split = load_split_spec(
        REPOSITORY_ROOT / "configs" / "protocol" / "splits.yaml"
    )
    allowed = set(split.train) | set(split.val)
    ids = [video_id for video_id in discover_tracked_ids() if video_id in allowed]
    if not ids:
        print(f"Nenhum vídeo anotado encontrado em {TRAIN_ROOT}.")
        print("Confira se o VISEM-Tracking está em data/sources/visem_tracking/.")
        return None

    print(f"\nIDs com gabarito disponíveis ({len(ids)}):")
    print("  " + "  ".join(ids))

    while True:
        vid = ask("Digite o ID do vídeo", default=ids[0])
        if vid in ids:
            break
        print(f"  ID inválido. Escolha um da lista: {', '.join(ids)}")

    video = TRAIN_ROOT / vid / f"{vid}.mp4"

    gt_dir = None
    if ask_yes_no("\nComparar com o gabarito manual (labels_ftid)?", default=True):
        cand = TRAIN_ROOT / vid / "labels_ftid"
        if not cand.exists():
            cand = TRAIN_ROOT / vid / "labels"
        gt_dir = cand
    return video, gt_dir


def pick_raw() -> tuple[Path, Path | None] | None:
    """Escolhe um vídeo bruto (VISEM original). Sem gabarito disponível."""
    videos = discover_raw_videos()
    if not videos:
        print(f"Nenhum vídeo bruto encontrado em {RAW_VIDEOS_ROOT}.")
        return None

    ids = list(videos)
    print(f"\nIDs de vídeos brutos disponíveis ({len(ids)}):")
    print("  " + "  ".join(ids))
    print("(VISEM original — sem anotação manual; só detecção.)")

    while True:
        vid = ask("Digite o ID do vídeo", default=ids[0])
        if vid in videos:
            break
        print(f"  ID inválido. Escolha um da lista: {', '.join(ids)}")
    return videos[vid], None


# --------------------------------------------------------------------------- #
# Fluxo principal
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Menu exploratório de detecção; mostra somente vídeos anotados de "
            "treino/validação e grava runs em data/tests."
        )
    )
    parser.parse_args(argv)
    print("=== Detecção de espermatozoides — modo interativo ===")

    source = ask_choice(
        "\nQual fonte de vídeo?",
        ["anotado (VISEM-Tracking, com gabarito)", "bruto (VISEM original, sem gabarito)"],
        default="anotado (VISEM-Tracking, com gabarito)",
    )
    picked = pick_tracked() if source.startswith("anotado") else pick_raw()
    if picked is None:
        return
    video, gt_dir = picked

    # Método
    method = ask_choice("\nMétodo de detecção:", list(DETECTORS), default="threshold")
    weights = None
    if method == "yolo":
        weights = ask_weights()
        if weights is None:
            print("Cancelado: YOLO requer um arquivo de pesos (.pt).")
            return

    # Quantidade de frames
    max_frames = ask_int("\nQuantos frames processar?", default="300")

    make_video = ask_yes_no("Gerar vídeo anotado?", default=True)
    draw_mode = "both"
    if make_video:
        draw_mode = ask_choice(
            "Modo de desenho:", ["both", "box", "centroid", "circle"], default="both"
        )

    # Monta argv para run_detection.main
    argv = ["--method", method, "--video", str(video)]
    if gt_dir is not None:
        argv += ["--gt-dir", str(gt_dir)]
    if max_frames is not None:
        argv += ["--max-frames", str(max_frames)]
    if not make_video:
        argv += ["--no-video"]
    elif draw_mode != "both":
        argv += ["--draw-mode", draw_mode]
    if weights:
        argv += ["--weights", weights]

    # Mostra o comando equivalente e confirma
    print("\nComando equivalente:")
    print("  python -m script.detection.application.run_detection " + " ".join(
        f'"{a}"' if " " in a or "/" in a or "\\" in a else a for a in argv
    ))
    if not ask_yes_no("\nExecutar agora?", default=True):
        print("Cancelado.")
        return

    print("\n--- executando ---")
    run_main(argv)


if __name__ == "__main__":
    main()
