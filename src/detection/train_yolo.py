"""Train / fine-tune a YOLO detector on VISEM-Tracking.

The VISEM-Tracking dataset ships labels already in native YOLO format
(``class cx cy w h``, normalized) under ``Train/<id>/labels/*.txt`` next to the
frames in ``Train/<id>/images/*.jpg``. This script:

1. Splits the videos **by ID** into train/val (frames from the same video are
   near-duplicates, so splitting by frame would leak the val set into train).
2. Generates ``train.txt`` / ``val.txt`` (lists of image paths) and a
   ``visem.yaml`` dataset descriptor that Ultralytics understands.
3. Runs ``YOLO(model).train(...)`` and reports where ``best.pt`` landed.

The resulting ``best.pt`` is the ``--weights`` argument expected by
:class:`src.detection.detect_yolo.YoloDetector` (and by the interactive runner).

Examples
--------
Prepare the dataset files only (no training)::

    python -m src.detection.train_yolo --prepare-only

Fine-tune yolov8n for 50 epochs (CPU is slow; prefer a CUDA machine)::

    python -m src.detection.train_yolo --model yolov8n.pt --epochs 50 --batch 16

Hold out specific videos for validation::

    python -m src.detection.train_yolo --val-ids 52 60 82

Light CPU sample-training run (subsample each video to 40 frames)::

    python -m src.detection.train_yolo --max-frames-per-video 40 --epochs 5 --batch 4

Full GPU run (auto batch + disk cache for fast I/O)::

    python -m src.detection.train_yolo --epochs 100 --batch -1 --cache disk

GPU note
--------
Training is GPU-bound. A CPU-only torch makes it impractical on the full set.
Install a CUDA build matching your driver, e.g. (RTX / CUDA 12.x driver)::

    python -m pip uninstall -y torch torchvision
    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

Then ``torch.cuda.is_available()`` is True and this script auto-selects GPU 0.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

# VISEM-Tracking object classes (order matches the integer class ids in labels/).
CLASS_NAMES = ["sperm", "cluster", "small_or_pinhead"]

TRAIN_ROOT = Path("data/tracked/VISEM_Tracking_Train_v4/Train")
DEFAULT_DATASET_DIR = Path("data/yolo")


def discover_ids(train_root: Path) -> list[str]:
    """Video IDs that have both an images/ and a labels/ folder."""
    if not train_root.exists():
        return []
    ids = [
        d.name
        for d in train_root.iterdir()
        if d.is_dir() and (d / "images").is_dir() and (d / "labels").is_dir()
    ]
    return sorted(ids, key=lambda s: (int(s) if s.isdigit() else 1 << 30, s))


def split_ids(
    ids: list[str],
    val_ids: list[str] | None,
    val_frac: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    """Split video IDs into (train, val).

    Explicit ``val_ids`` win; otherwise a deterministic random fraction is held
    out (at least one video on each side when possible).
    """
    if val_ids:
        val = [v for v in val_ids if v in ids]
        missing = [v for v in val_ids if v not in ids]
        if missing:
            raise SystemExit(f"--val-ids inexistentes em {TRAIN_ROOT}: {missing}")
        train = [v for v in ids if v not in set(val)]
        return train, val

    shuffled = list(ids)
    random.Random(seed).shuffle(shuffled)
    n_val = max(1, round(len(shuffled) * val_frac)) if len(shuffled) > 1 else 0
    val = sorted(shuffled[:n_val], key=lambda s: (int(s) if s.isdigit() else 1 << 30, s))
    train = sorted(shuffled[n_val:], key=lambda s: (int(s) if s.isdigit() else 1 << 30, s))
    return train, val


def _frame_sort_key(img: Path):
    """Sort frames numerically (..._frame_2 before ..._frame_10)."""
    stem = img.stem
    num = stem.rsplit("_", 1)[-1]
    return (int(num) if num.isdigit() else 1 << 30, stem)


def list_images(
    train_root: Path, ids: list[str], max_per_video: int | None = None
) -> list[Path]:
    """Absolute image paths (only frames that have a matching label file).

    ``max_per_video`` evenly subsamples each video to at most that many frames
    (spread across the clip, not just the first N) — useful for a light CPU
    sample-training run.
    """
    paths: list[Path] = []
    for vid in ids:
        img_dir = train_root / vid / "images"
        lbl_dir = train_root / vid / "labels"
        frames = [
            img for img in sorted(img_dir.glob("*.jpg"), key=_frame_sort_key)
            if (lbl_dir / f"{img.stem}.txt").exists()
        ]
        if max_per_video is not None and len(frames) > max_per_video:
            step = len(frames) / max_per_video
            frames = [frames[int(i * step)] for i in range(max_per_video)]
        paths.extend(img.resolve() for img in frames)
    return paths


def write_list(paths: list[Path], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(p.as_posix() for p in paths) + ("\n" if paths else ""),
        encoding="utf-8",
    )


def write_yaml(dataset_dir: Path, train_txt: Path, val_txt: Path) -> Path:
    """Write the Ultralytics dataset descriptor and return its path."""
    yaml_path = dataset_dir / "visem.yaml"
    names_block = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES))
    yaml_path.write_text(
        "# VISEM-Tracking dataset for YOLO (auto-generated by train_yolo.py)\n"
        f"path: {dataset_dir.resolve().as_posix()}\n"
        f"train: {train_txt.resolve().as_posix()}\n"
        f"val: {val_txt.resolve().as_posix()}\n"
        f"nc: {len(CLASS_NAMES)}\n"
        "names:\n"
        f"{names_block}\n",
        encoding="utf-8",
    )
    return yaml_path


def build_dataset(
    train_root: Path,
    dataset_dir: Path,
    val_ids: list[str] | None,
    val_frac: float,
    seed: int,
    max_per_video: int | None = None,
) -> Path:
    """Generate train.txt / val.txt / visem.yaml; return the yaml path."""
    ids = discover_ids(train_root)
    if not ids:
        raise SystemExit(
            f"Nenhum vídeo com images/ e labels/ em {train_root}. "
            "Confira se o VISEM-Tracking está extraído em data/tracked/."
        )

    train_ids, val_ids_final = split_ids(ids, val_ids, val_frac, seed)
    train_imgs = list_images(train_root, train_ids, max_per_video)
    val_imgs = list_images(train_root, val_ids_final, max_per_video)

    train_txt = dataset_dir / "train.txt"
    val_txt = dataset_dir / "val.txt"
    write_list(train_imgs, train_txt)
    write_list(val_imgs, val_txt)
    yaml_path = write_yaml(dataset_dir, train_txt, val_txt)

    print(f"IDs treino ({len(train_ids)}): {' '.join(train_ids)}")
    print(f"IDs val    ({len(val_ids_final)}): {' '.join(val_ids_final)}")
    print(f"Frames treino: {len(train_imgs)} | val: {len(val_imgs)}")
    print(f"Dataset YAML: {yaml_path}")
    return yaml_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Treina/fine-tuna um detector YOLO no VISEM-Tracking."
    )
    p.add_argument("--train-root", type=Path, default=TRAIN_ROOT,
                   help="Raiz Train/ do VISEM-Tracking.")
    p.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR,
                   help="Onde gravar train.txt/val.txt/visem.yaml.")
    p.add_argument("--val-ids", nargs="*", default=None,
                   help="IDs de vídeo para validação (sobrepõe --val-frac).")
    p.add_argument("--val-frac", type=float, default=0.2,
                   help="Fração de vídeos para validação (default: 0.2).")
    p.add_argument("--seed", type=int, default=42, help="Seed do split.")
    p.add_argument("--max-frames-per-video", type=int, default=None,
                   help="Subamostra cada vídeo para até N frames (espalhados pelo "
                        "clipe). Útil p/ treino-amostra leve na CPU.")
    p.add_argument("--prepare-only", action="store_true",
                   help="Apenas gera os arquivos do dataset (não treina).")
    # Training hyperparameters (forwarded to Ultralytics).
    p.add_argument("--model", default="yolov8n.pt",
                   help="Modelo base/pesos iniciais (default: yolov8n.pt).")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch", default="-1",
                   help="Tamanho do batch. -1 = auto (usa ~60%% da VRAM na GPU). "
                        "Default: -1.")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default=None,
                   help="cpu | 0 | 0,1 ... (default: GPU 0 se houver CUDA, senão cpu).")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--cache", default=None, choices=["ram", "disk"],
                   help="Cacheia imagens (disk recomendado p/ o VISEM completo; "
                        "acelera muito o I/O). Default: sem cache.")
    p.add_argument("--project", default="results/yolo",
                   help="Pasta-mãe dos runs do Ultralytics.")
    p.add_argument("--name", default="visem", help="Nome do run.")
    p.add_argument("--resume", action="store_true",
                   help="Retoma de <project>/<name>/weights/last.pt (continua um "
                        "treino interrompido; ignora hiperparâmetros, usa os do checkpoint).")
    return p.parse_args(argv)


def resume_training(project: str, name: str) -> Path | None:
    """Resume an interrupted Ultralytics run from its last.pt checkpoint."""
    try:
        from ultralytics import YOLO
    except ImportError as e:  # pragma: no cover - optional dependency
        raise SystemExit("Treino requer 'ultralytics' (pip install ultralytics).") from e

    last = (Path(project) / name / "weights" / "last.pt").resolve()
    if not last.is_file():
        raise SystemExit(
            f"Nada para retomar: {last} não existe. "
            "Nenhuma época foi concluída? Inicie um treino normal."
        )
    print(f"[resume] Continuando de {last}")
    model = YOLO(str(last))
    results = model.train(resume=True)
    save_dir = Path(getattr(results, "save_dir", Path(project) / name))
    best = save_dir / "weights" / "best.pt"
    print(f"\n--- treino retomado e concluído ---\nMelhores pesos: {best}")
    return best if best.is_file() else None


def main(argv: list[str] | None = None) -> Path | None:
    """Run the dataset prep + training. Returns the best.pt path (or None)."""
    args = parse_args(argv)

    if args.resume:
        return resume_training(args.project, args.name)

    yaml_path = build_dataset(
        train_root=args.train_root,
        dataset_dir=args.dataset_dir,
        val_ids=args.val_ids,
        val_frac=args.val_frac,
        seed=args.seed,
        max_per_video=args.max_frames_per_video,
    )

    if args.prepare_only:
        print("\n--prepare-only: dataset gerado, treino não executado.")
        return None

    try:
        import torch
        from ultralytics import YOLO
    except ImportError as e:  # pragma: no cover - optional dependency
        raise SystemExit(
            "Treino requer 'ultralytics' e 'torch' (pip install ultralytics)."
        ) from e

    # Resolve device: honor --device, else GPU 0 when CUDA is available.
    cuda_ok = torch.cuda.is_available()
    device = args.device if args.device is not None else ("0" if cuda_ok else "cpu")
    if cuda_ok:
        print(f"\n[ok] CUDA disponível — treinando na GPU: {torch.cuda.get_device_name(0)}")
    else:
        print(
            "\n[aviso] CUDA indisponível — o treino rodará na CPU e será LENTO. "
            "Instale torch com CUDA (ver --help) ou use --max-frames-per-video."
        )

    model = YOLO(args.model)
    results = model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        batch=int(args.batch),
        imgsz=args.imgsz,
        device=device,
        workers=args.workers,
        cache=args.cache if args.cache else False,
        # Absolute path so Ultralytics doesn't nest under runs/detect/.
        project=str(Path(args.project).resolve()),
        name=args.name,
    )

    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name))
    best = save_dir / "weights" / "best.pt"
    print("\n--- treino concluído ---")
    print(f"Melhores pesos: {best}")
    print("Use com:")
    print(f'  python -m src.detection.run_detection --method yolo --weights "{best}" '
          '--video <video> --gt-dir <labels>')
    return best if best.is_file() else None


if __name__ == "__main__":
    main()
