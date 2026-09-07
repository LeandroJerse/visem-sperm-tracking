"""Train / fine-tune a YOLO detector on VISEM-Tracking.

The VISEM-Tracking dataset ships labels already in native YOLO format
(``class cx cy w h``, normalized) under ``Train/<id>/labels/*.txt`` next to the
frames in ``Train/<id>/images/*.jpg``. This script:

1. Reads the fixed video-level train/validation/test protocol; fitting and early
   stopping use only train/validation.
2. Generates ``train.txt`` / ``val.txt`` / ``test.txt`` and a ``visem.yaml``
   descriptor. The test definition exists for later frozen evaluation, never as
   an input to training or hyperparameter selection.
3. Runs ``YOLO(model).train(...)`` and reports where ``best.pt`` landed.

The resulting ``best.pt`` is the ``--weights`` argument expected by
:class:`src.detection.learned.yolo.YoloDetector` (and by the interactive runner).

Examples
--------
Prepare the dataset files only (no training)::

    python -m script.detection.test.yolo.train --prepare-only

Fine-tune yolov8n for 50 epochs (CPU is slow; prefer a CUDA machine)::

    python -m script.detection.test.yolo.train --model yolov8n.pt --epochs 50 --batch 16

Reproduce the old exploratory random split explicitly (pilot only)::

    python -m script.detection.test.yolo.train --legacy-pilot-split --val-ids 52 60 82

Light CPU sample-training run (subsample each video to 40 frames)::

    python -m script.detection.test.yolo.train --max-frames-per-video 40 --epochs 5 --batch 4

Full GPU run (auto batch + disk cache for fast I/O)::

    python -m script.detection.test.yolo.train --epochs 100 --batch -1 --cache disk

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
import shutil
import time
from pathlib import Path
from typing import Any

from src.core.artifacts import (
    sha256_file as _sha256,
    write_csv_exclusive as _write_csv_new,
    write_json_exclusive as _write_json_new,
)
from src.core.paths import (
    EXPERIMENT_TESTS_ROOT,
    VISEM_TRACKING_TRAIN_ROOT,
    YOLO_DATASET_ROOT,
    YOLO_PRETRAINED_ROOT,
)
from src.experiments.config import ConfigError, resolve_config
from src.experiments.dataset import load_split_spec
from src.experiments.resources import ResourceMonitor
from src.experiments.runs import RunContext

# VISEM-Tracking object classes (order matches the integer class ids in labels/).
CLASS_NAMES = ["sperm", "cluster", "small_or_pinhead"]

TRAIN_ROOT = VISEM_TRACKING_TRAIN_ROOT
DEFAULT_DATASET_DIR = YOLO_DATASET_ROOT
DEFAULT_SPLITS_CONFIG = Path("configs/protocol/splits.yaml")

DEFAULT_CONFIG: dict[str, Any] = {
    "method": "yolo",
    "params": {"imgsz": 640},
    "data": {
        "train_root": str(TRAIN_ROOT),
        "dataset_dir": str(DEFAULT_DATASET_DIR),
        "splits_config": str(DEFAULT_SPLITS_CONFIG),
        "max_frames_per_video": None,
    },
    "training": {
        "model": str(YOLO_PRETRAINED_ROOT / "yolov8n.pt"),
        "epochs": 50,
        "patience": 15,
        "batch": -1,
        "imgsz": None,
        "device": None,
        "workers": 8,
        "cache": None,
        "project": None,
        "name": None,
        "seeds": [42, 123, 2026],
    },
    "run": {
        "stage": "training",
        "split": "train_val",
        "seed": 42,
        "prepare_only": False,
        "resume": False,
    },
    "pilot": {"enabled": False, "val_ids": None, "val_frac": 0.2},
}


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
            raise SystemExit(f"--val-ids inexistentes no dataset descoberto: {missing}")
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


def write_yaml(
    dataset_dir: Path,
    train_txt: Path,
    val_txt: Path,
    test_txt: Path | None = None,
) -> Path:
    """Write the Ultralytics dataset descriptor and return its path."""
    yaml_path = dataset_dir / "visem.yaml"
    names_block = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES))
    test_line = (
        f"test: {test_txt.resolve().as_posix()}\n" if test_txt is not None else ""
    )
    yaml_path.write_text(
        "# VISEM-Tracking dataset for YOLO (auto-generated by train_yolo.py)\n"
        f"path: {dataset_dir.resolve().as_posix()}\n"
        f"train: {train_txt.resolve().as_posix()}\n"
        f"val: {val_txt.resolve().as_posix()}\n"
        f"{test_line}"
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
    *,
    train_ids: list[str] | None = None,
    test_ids: list[str] | None = None,
) -> Path:
    """Generate train.txt / val.txt / visem.yaml; return the yaml path.

    ``train_ids`` selects protocol mode: train and validation IDs are then used
    exactly as supplied.  With ``train_ids=None`` the historical random/explicit
    validation split is retained solely for a flagged pilot run.
    """
    ids = discover_ids(train_root)
    if not ids:
        raise SystemExit(
            f"Nenhum vídeo com images/ e labels/ em {train_root}. "
            f"Confira o VISEM-Tracking em {VISEM_TRACKING_TRAIN_ROOT}."
        )

    if train_ids is None:
        train_ids_final, val_ids_final = split_ids(ids, val_ids, val_frac, seed)
    else:
        train_ids_final = [str(value) for value in train_ids]
        val_ids_final = [str(value) for value in (val_ids or [])]
        test_ids_final = [str(value) for value in (test_ids or [])]
        groups = {
            "train": set(train_ids_final),
            "val": set(val_ids_final),
            "test": set(test_ids_final),
        }
        overlaps = {
            f"{left}/{right}": sorted(groups[left] & groups[right])
            for left, right in (("train", "val"), ("train", "test"), ("val", "test"))
            if groups[left] & groups[right]
        }
        if overlaps:
            raise SystemExit(f"Vazamento no preparo YOLO: {overlaps}")
        missing = sorted(set().union(*groups.values()) - set(ids))
        if missing:
            raise SystemExit(
                f"IDs do protocolo ausentes em {train_root}: {missing}"
            )
        if not train_ids_final or not val_ids_final:
            raise SystemExit("O protocolo YOLO exige train e val não vazios.")

    train_imgs = list_images(train_root, train_ids_final, max_per_video)
    val_imgs = list_images(train_root, val_ids_final, max_per_video)
    test_imgs = (
        list_images(train_root, test_ids_final, max_per_video)
        if train_ids is not None and test_ids_final
        else []
    )

    train_txt = dataset_dir / "train.txt"
    val_txt = dataset_dir / "val.txt"
    test_txt = dataset_dir / "test.txt" if test_imgs else None
    write_list(train_imgs, train_txt)
    write_list(val_imgs, val_txt)
    if test_txt is not None:
        write_list(test_imgs, test_txt)
    yaml_path = write_yaml(dataset_dir, train_txt, val_txt, test_txt)

    print(f"IDs treino ({len(train_ids_final)}): {' '.join(train_ids_final)}")
    print(f"IDs val    ({len(val_ids_final)}): {' '.join(val_ids_final)}")
    if test_imgs:
        print(f"IDs teste  ({len(test_ids_final)}): {' '.join(test_ids_final)} [bloqueado]")
    print(
        f"Frames treino: {len(train_imgs)} | val: {len(val_imgs)}"
        + (f" | teste: {len(test_imgs)}" if test_imgs else "")
    )
    print(f"Dataset YAML: {yaml_path}")
    return yaml_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Treina/fine-tuna um detector YOLO no VISEM-Tracking."
    )
    p.add_argument("--config", default=None, help="YAML de detecção/treino YOLO.")
    p.add_argument(
        "--set", dest="overrides", action="append", default=[], metavar="key=value",
        help="Override repetível; chave simples entra em training.",
    )
    p.add_argument("--train-root", type=Path, default=None,
                   help="Raiz Train/ do VISEM-Tracking.")
    p.add_argument("--dataset-dir", type=Path, default=None,
                   help="Onde gravar train.txt/val.txt/visem.yaml.")
    p.add_argument("--splits-config", type=Path, default=None,
                   help="Split fixo 12/4/4 (default: configs/protocol/splits.yaml).")
    p.add_argument(
        "--legacy-pilot-split", action="store_true",
        help="Habilita explicitamente o split aleatório/--val-ids histórico (não científico).",
    )
    p.add_argument("--val-ids", nargs="*", default=None,
                   help="Piloto legado: IDs de validação (requer --legacy-pilot-split).")
    p.add_argument("--val-frac", type=float, default=None,
                   help="Piloto legado: fração de validação (requer --legacy-pilot-split).")
    p.add_argument(
        "--seed", type=int, default=None,
        help="Uma seed por execução; use 42, 123 e 2026 em três comandos separados.",
    )
    p.add_argument("--stage", default=None, help="Etapa registrada na run imutável.")
    p.add_argument(
        "--out-dir", default=None,
        help="Raiz opcional; por padrão usa data/tests ou data/results conforme a etapa.",
    )
    p.add_argument("--max-frames-per-video", type=int, default=None,
                   help="Subamostra cada vídeo para até N frames (espalhados pelo "
                        "clipe). Útil p/ treino-amostra leve na CPU.")
    p.add_argument("--prepare-only", action="store_true",
                   help="Apenas gera os arquivos do dataset (não treina).")
    # Training hyperparameters (forwarded to Ultralytics).
    p.add_argument("--model", default=None,
                   help="Modelo base/pesos iniciais (default de config: yolov8n.pt).")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--patience", type=int, default=None)
    p.add_argument("--batch", default=None,
                   help="Tamanho do batch. -1 = auto (usa ~60%% da VRAM na GPU). "
                        "Default da config: -1.")
    p.add_argument("--imgsz", type=int, default=None)
    p.add_argument("--device", default=None,
                   help="cpu | 0 | 0,1 ... (default: GPU 0 se houver CUDA, senão cpu).")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--cache", default=None, choices=["ram", "disk"],
                   help="Cacheia imagens (disk recomendado p/ o VISEM completo; "
                        "acelera muito o I/O). Default: sem cache.")
    p.add_argument(
        "--project", default=None,
        help="Referência histórica registrada; não altera a pasta da run científica.",
    )
    p.add_argument(
        "--name", default=None,
        help="Rótulo registrado; a saída científica usa sempre <run>/ultralytics.",
    )
    p.add_argument("--resume", action="store_true",
                   help="Bloqueado por segurança: use --model <last.pt> para uma nova run imutável.")
    return p.parse_args(argv)


def _normalise_overrides(overrides: list[str]) -> list[str]:
    """Map concise training overrides while retaining dotted config access."""
    data_keys = {
        "train_root", "dataset_dir", "splits_config", "max_frames_per_video"
    }
    pilot_keys = {"legacy_pilot_split", "val_ids", "val_frac"}
    normalised: list[str] = []
    for expression in overrides:
        if "=" not in expression:
            raise ConfigError(f"Override deve usar chave=valor: {expression!r}")
        key = expression.split("=", 1)[0].strip()
        if "." in key:
            normalised.append(expression)
        elif key == "seed":
            normalised.append(f"run.seed={expression.split('=', 1)[1]}")
        elif key in data_keys:
            normalised.append(f"data.{expression}")
        elif key in pilot_keys:
            mapped = "enabled" if key == "legacy_pilot_split" else key
            value = expression.split("=", 1)[1]
            normalised.append(f"pilot.{mapped}={value}")
        else:
            normalised.append(f"training.{expression}")
    return normalised


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve YAML, legacy CLI flags and final ``--set`` overrides."""
    config = resolve_config(args.config, defaults=DEFAULT_CONFIG)
    for section in ("params", "data", "training", "run", "pilot"):
        if config.get(section) is None:
            config[section] = {}
        elif not isinstance(config[section], dict):
            raise ConfigError(f"A seção {section!r} deve ser um mapping.")

    data = config["data"]
    training = config["training"]
    run = config["run"]
    pilot = config["pilot"]
    if args.train_root is not None:
        data["train_root"] = str(args.train_root)
    if args.dataset_dir is not None:
        data["dataset_dir"] = str(args.dataset_dir)
    if args.splits_config is not None:
        data["splits_config"] = str(args.splits_config)
    if args.max_frames_per_video is not None:
        data["max_frames_per_video"] = args.max_frames_per_video
    if args.legacy_pilot_split:
        pilot["enabled"] = True
    if args.val_ids is not None:
        pilot["val_ids"] = args.val_ids
    if args.val_frac is not None:
        pilot["val_frac"] = args.val_frac
    if args.seed is not None:
        run["seed"] = args.seed
    # ``configs/detection/yolo/search.yaml`` starts as screening/inference.
    # Training must never inherit that stage accidentally.
    run["stage"] = args.stage if args.stage is not None else "training"
    if args.prepare_only:
        run["prepare_only"] = True
    if args.resume:
        run["resume"] = True
    for key in (
        "model", "epochs", "patience", "batch", "imgsz", "device", "workers",
        "cache", "project", "name",
    ):
        value = getattr(args, key)
        if value is not None:
            training[key] = value

    return resolve_config(
        defaults=config, overrides=_normalise_overrides(args.overrides)
    )


def resume_training(project: str, name: str) -> Path | None:
    """Refuse unsafe in-place resume while retaining the historical API name."""
    last = (Path(project) / name / "weights" / "last.pt").resolve()
    raise SystemExit(
        "Resume in-place foi bloqueado para não alterar runs históricas. "
        f"Inicie uma nova run imutável com --model {last}."
    )


def _file_fingerprint(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _dataset_fingerprints(yaml_path: Path) -> dict[str, dict[str, Any]]:
    """Fingerprint the generated descriptor and immutable split lists."""
    candidates = [yaml_path]
    candidates.extend(
        yaml_path.parent / name for name in ("train.txt", "val.txt", "test.txt")
    )
    return {
        path.name: _file_fingerprint(path)
        for path in candidates
        if path.is_file()
    }


def _video_ids_from_list(path: Path) -> list[str]:
    values = {
        Path(line.strip()).parent.parent.name
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    return sorted(values, key=lambda value: (int(value) if value.isdigit() else 1 << 30, value))


def _snapshot_dataset_definition(
    context: RunContext, fingerprints: dict[str, dict[str, Any]]
) -> dict[str, str]:
    destination = context.path / "dataset_definition"
    destination.mkdir()
    artifacts: dict[str, str] = {}
    for name, fingerprint in fingerprints.items():
        copied = destination / name
        shutil.copy2(fingerprint["path"], copied)
        if _sha256(copied) != fingerprint["sha256"]:
            raise RuntimeError(f"Snapshot do dataset divergiu para {name}.")
        artifacts[f"dataset_{Path(name).stem}"] = str(copied)
    return artifacts


def _training_kwargs(
    config: dict[str, Any], *, yaml_path: Path, seed: int, device: str,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Build the single-seed Ultralytics call without importing ML packages."""
    training = config["training"]
    imgsz_raw = training.get("imgsz")
    if imgsz_raw in (None, ""):
        imgsz_raw = config.get("params", {}).get("imgsz", 640)
    patience = int(training.get("patience", 15))
    if patience < 0:
        raise ValueError("training.patience deve ser não negativo.")
    epochs = int(training.get("epochs", 50))
    if epochs <= 0:
        raise ValueError("training.epochs deve ser positivo.")
    workers = int(training.get("workers", 8))
    if workers < 0:
        raise ValueError("training.workers deve ser não negativo.")
    run_name = "ultralytics" if run_dir is not None else (
        training.get("name") or f"visem_s{seed}"
    )
    cache = training.get("cache")
    return {
        "data": str(yaml_path),
        "epochs": epochs,
        "patience": patience,
        "batch": int(training.get("batch", -1)),
        "imgsz": int(imgsz_raw),
        "seed": seed,
        "device": device,
        "workers": workers,
        "cache": cache if cache else False,
        # Fresh scientific runs are nested under their immutable RunContext.
        "project": str(
            run_dir.resolve()
            if run_dir is not None
            else Path(
                training.get("project")
                or EXPERIMENT_TESTS_ROOT / "detection" / "yolo" / "_adhoc"
            ).resolve()
        ),
        "name": str(run_name),
        **({"exist_ok": False} if run_dir is not None else {}),
    }


def main(argv: list[str] | None = None) -> Path | None:
    """Run the dataset prep + training. Returns the best.pt path (or None)."""
    args = parse_args(argv)
    try:
        config = resolve_cli_config(args)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    if str(config.get("method", "yolo")).lower() != "yolo":
        raise SystemExit("train_yolo aceita somente method: yolo.")

    data = config["data"]
    training = config["training"]
    run = config["run"]
    pilot = config["pilot"]
    seed = int(run.get("seed", 42))
    train_root = Path(data.get("train_root") or TRAIN_ROOT)
    dataset_dir = Path(data.get("dataset_dir") or DEFAULT_DATASET_DIR)
    max_per_raw = data.get("max_frames_per_video")
    max_per_video = None if max_per_raw in (None, "") else int(max_per_raw)
    if max_per_video is not None and max_per_video <= 0:
        raise SystemExit("max_frames_per_video deve ser positivo ou null.")
    legacy_pilot = bool(pilot.get("enabled", False))
    if not legacy_pilot and (args.val_ids is not None or args.val_frac is not None):
        raise SystemExit(
            "--val-ids/--val-frac pertencem ao piloto legado; acrescente "
            "--legacy-pilot-split para usá-los explicitamente."
        )

    if bool(run.get("resume", False)):
        raise SystemExit(
            "--resume in-place foi bloqueado porque pode sobrescrever um run histórico. "
            "Use --model <run-antigo>/weights/last.pt para iniciar uma nova run "
            "imutável com proveniência completa."
        )

    if legacy_pilot:
        print("[PILOTO] split histórico habilitado explicitamente; não é resultado final.")
        yaml_path = build_dataset(
            train_root=train_root,
            dataset_dir=dataset_dir,
            val_ids=pilot.get("val_ids"),
            val_frac=float(pilot.get("val_frac", 0.2)),
            seed=seed,
            max_per_video=max_per_video,
        )
    else:
        try:
            split = load_split_spec(data.get("splits_config") or DEFAULT_SPLITS_CONFIG)
        except (ConfigError, FileNotFoundError) as exc:
            raise SystemExit(str(exc)) from exc
        if split.seeds and seed not in split.seeds:
            raise SystemExit(
                f"Seed {seed} fora do protocolo; use uma de {list(split.seeds)}."
            )
        configured_seeds = tuple(int(value) for value in training.get("seeds", ()))
        if configured_seeds and seed not in configured_seeds:
            raise SystemExit(
                f"Seed {seed} não consta em training.seeds={list(configured_seeds)}."
            )
        print(
            f"[protocolo] seed única desta execução: {seed}. "
            "Repita o comando explicitamente para as demais seeds."
        )
        yaml_path = build_dataset(
            train_root=train_root,
            dataset_dir=dataset_dir,
            train_ids=list(split.train),
            val_ids=list(split.val),
            test_ids=list(split.test),
            val_frac=0.0,
            seed=seed,
            max_per_video=max_per_video,
        )

    if bool(run.get("prepare_only", False)):
        print("\n--prepare-only: dataset gerado, treino não executado.")
        return None

    stage = str(run.get("stage", "training"))
    split_name = "pilot_train_val" if legacy_pilot else "train_val"
    run["stage"] = stage
    run["split"] = split_name
    dataset_files = _dataset_fingerprints(yaml_path)
    data.update(
        {
            "prepared_yaml": str(yaml_path.resolve()),
            "dataset_files": dataset_files,
            "train_ids": _video_ids_from_list(yaml_path.parent / "train.txt"),
            "val_ids": _video_ids_from_list(yaml_path.parent / "val.txt"),
            "test_ids": (
                _video_ids_from_list(yaml_path.parent / "test.txt")
                if (yaml_path.parent / "test.txt").is_file()
                else []
            ),
        }
    )
    model_reference = str(
        training.get("model") or YOLO_PRETRAINED_ROOT / "yolov8n.pt"
    )
    model_candidate = Path(model_reference)
    if not model_candidate.is_file() and model_candidate.parent == Path("."):
        canonical_candidate = YOLO_PRETRAINED_ROOT / model_candidate.name
        if canonical_candidate.is_file():
            model_candidate = canonical_candidate
            model_reference = str(canonical_candidate)
            training["model"] = model_reference
    input_checkpoint = (
        {"reference": model_reference, **_file_fingerprint(model_candidate)}
        if model_candidate.is_file()
        else {
            "reference": model_reference,
            "path": None,
            "sha256": None,
            "bytes": None,
            "status": "ultralytics_reference_not_local_before_run",
        }
    )
    training["input_checkpoint"] = input_checkpoint
    training["output_policy"] = "immutable_run_context/ultralytics"
    training["legacy_project_preserved"] = str(
        training.get("project") or ""
    )
    if training.get("name") or training.get("project") not in (None, ""):
        print(
            "[proveniência] --name/--project foram registrados, mas a saída "
            "científica permanece em <RunContext>/ultralytics."
        )

    create_kwargs: dict[str, Any] = {
        "module": "detection",
        "method": "yolo_train",
        "algorithm": "yolo",
        "stage": stage,
        "seed": seed,
        "config": config,
    }
    if args.out_dir is not None:
        create_kwargs["output_root"] = args.out_dir
    context = RunContext.create(**create_kwargs)

    try:
        definition_artifacts = _snapshot_dataset_definition(context, dataset_files)
        try:
            import torch
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Treino requer 'ultralytics' e 'torch' compatíveis."
            ) from exc

        resources = ResourceMonitor()
        cuda_ok = torch.cuda.is_available()
        configured_device = training.get("device")
        device = (
            str(configured_device)
            if configured_device is not None
            else ("0" if cuda_ok else "cpu")
        )
        if cuda_ok:
            print(
                f"\n[ok] CUDA disponível — treinando na GPU: "
                f"{torch.cuda.get_device_name(0)}"
            )
        else:
            print(
                "\n[aviso] CUDA indisponível — o treino rodará na CPU e será LENTO. "
                "Instale torch com CUDA (ver --help) ou use --max-frames-per-video."
            )

        model = YOLO(model_reference)
        resolved_input_checkpoint = input_checkpoint
        if input_checkpoint.get("sha256") is None and model_candidate.is_file():
            resolved_input_checkpoint = {
                "reference": model_reference,
                **_file_fingerprint(model_candidate),
                "status": "resolved_by_ultralytics_before_training",
            }
        try:
            train_kwargs = _training_kwargs(
                config,
                yaml_path=yaml_path,
                seed=seed,
                device=device,
                run_dir=context.path,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc
        started = time.perf_counter()
        results = model.train(**train_kwargs)
        training_seconds = time.perf_counter() - started
        resources.sample()

        save_dir = Path(
            getattr(
                results,
                "save_dir",
                Path(train_kwargs["project"]) / train_kwargs["name"],
            )
        ).resolve()
        try:
            save_dir.relative_to(context.path.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"Ultralytics gravou fora da run imutável: {save_dir}"
            ) from exc
        best = save_dir / "weights" / "best.pt"
        last = save_dir / "weights" / "last.pt"
        if not best.is_file():
            raise RuntimeError(f"Treino terminou sem checkpoint best.pt: {best}")
        checkpoints: dict[str, dict[str, Any]] = {
            "best": _file_fingerprint(best)
        }
        if last.is_file():
            checkpoints["last"] = _file_fingerprint(last)

        summary: dict[str, Any] = {
            "run_id": context.run_id,
            "stage": stage,
            "split": split_name,
            "seed": seed,
            "pilot": legacy_pilot,
            "train_videos": len(data["train_ids"]),
            "val_videos": len(data["val_ids"]),
            "test_videos_excluded_from_fit": len(data["test_ids"]),
            "epochs_requested": int(training.get("epochs", 50)),
            "patience": int(training.get("patience", 15)),
            "training_seconds": training_seconds,
            "input_checkpoint_sha256": resolved_input_checkpoint.get("sha256"),
            "best_checkpoint": str(best),
            "best_checkpoint_sha256": checkpoints["best"]["sha256"],
        }
        summary.update(resources.summary())
        summary_json = _write_json_new(context.path / "summary.json", summary)
        summary_csv = _write_csv_new(context.path / "summary.csv", summary)
        artifacts: dict[str, str] = {
            **definition_artifacts,
            "ultralytics_dir": str(save_dir),
            "best_checkpoint": str(best),
            "summary_json": str(summary_json),
            "summary_csv": str(summary_csv),
        }
        if last.is_file():
            artifacts["last_checkpoint"] = str(last)
        for name in ("results.csv", "args.yaml"):
            artifact = save_dir / name
            if artifact.is_file():
                artifacts[Path(name).stem] = str(artifact)
        metadata = {
            "summary": summary,
            "dataset": dataset_files,
            "input_checkpoint": resolved_input_checkpoint,
            "output_checkpoints": checkpoints,
            "train_kwargs": train_kwargs,
            "artifacts": artifacts,
        }
        metadata_json = _write_json_new(context.path / "metadata.json", metadata)
        artifacts["metadata_json"] = str(metadata_json)
        context.complete(
            summary=summary,
            dataset=dataset_files,
            input_checkpoint=resolved_input_checkpoint,
            output_checkpoints=checkpoints,
            artifacts=artifacts,
        )
    except BaseException as exc:
        context.fail(exc)
        raise

    print("\n--- treino concluído ---")
    print(f"Melhores pesos: {best}")
    print(f"Run imutável: {context.path}")
    print("Use com:")
    print(f'  python -m script.detection.application.run_detection --method yolo --weights "{best}" '
          '--video <video> --gt-dir <labels>')
    return best


if __name__ == "__main__":
    main()
