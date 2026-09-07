"""Inspect one training frame and its manual annotations, without a detector.

The immutable inspection folder contains the decoded frame, two explanatory
figures, a coordinate table and provenance. See script/README.md for usage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import psutil
import yaml
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

from src.detection.io import load_gt_for_frame


ROOT = Path(__file__).resolve().parents[3]
CLASS_LABELS = {0: "Classe 0 (sperm)", 1: "Classe 1 (cluster)", 2: "Classe 2 (pinhead)"}
COLORS = {0: "#12B8A6", 1: "#F59E0B", 2: "#D946EF"}
BG, INK, MUTED = "#F3F6FA", "#142B40", "#4F6376"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(f"Não foi possível registrar o estado do Git: {result.stderr}")
    return result.stdout.strip()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu")
        / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def read_rows(path: Path, *, identity: bool) -> list[tuple[str | None, int, tuple[float, ...]]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != (6 if identity else 5):
            raise ValueError(f"{path.name}:{line_number}: número incorreto de campos")
        offset = int(identity)
        class_id = int(fields[offset])
        coords = tuple(float(value) for value in fields[offset + 1:])
        if class_id not in CLASS_LABELS:
            raise ValueError(f"{path.name}:{line_number}: classe desconhecida")
        if not all(np.isfinite(value) and 0 <= value <= 1 for value in coords):
            raise ValueError(f"{path.name}:{line_number}: coordenada inválida")
        if min(coords[2:]) <= 0:
            raise ValueError(f"{path.name}:{line_number}: dimensão não positiva")
        rows.append((fields[0] if identity else None, class_id, coords))
    return rows


def render_overview(frame: Image.Image, rows: list[dict], video_id: int, index: int) -> Image.Image:
    scale = 2
    width, height = frame.size
    canvas = Image.new("RGB", (width * scale + 80, height * scale + 278), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 24), f"Nível 1 | Vídeo {video_id} | Quadro {index}", font=font(31, True), fill=INK)
    draw.text((40, 69), "Anotações manuais de referência • nenhuma detecção automática", font=font(24), fill=MUTED)
    canvas.paste(frame.resize((width * scale, height * scale), Image.Resampling.NEAREST), (40, 118))
    boxes = []
    for row in rows:
        x0, y0, x1, y1 = [row[key] for key in ("x_min", "y_min", "x_max", "y_max")]
        points = (40 + x0 * scale, 118 + y0 * scale, 40 + x1 * scale, 118 + y1 * scale)
        boxes.append(points)
        color = COLORS[row["class_id"]]
        draw.rectangle(points, outline=color, width=2)
        cx, cy = 40 + row["cx"] * scale, 118 + row["cy"] * scale
        draw.line((cx - 4, cy, cx + 4, cy), fill=color, width=2)
        draw.line((cx, cy - 4, cx, cy + 4), fill=color, width=2)
    def intersection(a: tuple, b: tuple) -> float:
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))

    placed = []
    for row, points in zip(rows, boxes):
        label = f'{row["visual_number"]:02d}'
        label_width = max(32, draw.textbbox((0, 0), label, font=font(17, True))[2] + 6)
        x0, y0, x1, y1 = points
        candidates = [(x0, y0 - 24), (x1 + 3, y0), (x0, y1 + 3),
                      (x0 - label_width - 3, y0), (x1 - label_width, y0 - 24),
                      (x0, y0 - 49), (x0, y1 + 27), (x1 + 3, y1 + 3)]
        rectangles = []
        for tx, ty in candidates:
            tx = min(max(tx, 40), 40 + width * scale - label_width)
            ty = min(max(ty, 118), 118 + height * scale - 22)
            rectangles.append((tx, ty, tx + label_width, ty + 22))
        def cost(rect: tuple) -> float:
            overlap = sum(intersection(rect, other) for other in placed)
            obscured = sum(intersection(rect, box) for box in boxes)
            distance = abs(rect[0] - x0) + abs(rect[1] - (y0 - 24))
            return overlap * 1000 + obscured * 100 + distance
        selected = min(rectangles, key=cost)
        placed.append(selected)
        draw.rectangle(selected, fill=INK)
        draw.text((selected[0] + 3, selected[1] + 1), label, font=font(17, True), fill="white")
    bottom = height * scale + 142
    counts = Counter(row["class_id"] for row in rows)
    caption = " | ".join(f"Classe {key}: {counts[key]}" for key in CLASS_LABELS)
    draw.text((40, bottom), f"{len(rows)} caixas • {caption}", font=font(23, True), fill=INK)
    draw.text((40, bottom + 36), "Retângulo: caixa manual | Cruz: centro geométrico da caixa", font=font(22), fill=MUTED)
    draw.text((40, bottom + 69), "Números são referências desta figura; IDs originais estão na tabela.", font=font(21), fill=MUTED)
    return canvas


def render_example(frame: Image.Image, row: dict) -> Image.Image:
    scale, radius = 4, 42
    left = max(0, int(row["cx"]) - radius)
    top = max(0, int(row["cy"]) - radius)
    right = min(frame.width, left + 2 * radius)
    bottom = min(frame.height, top + 2 * radius)
    crop = frame.crop((left, top, right, bottom))
    canvas = Image.new("RGB", (1130, 548), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((36, 24), "Como ler uma anotação", font=font(31, True), fill=INK)
    draw.text((36, 69), "Exemplo 01 • mesma imagem, sem realce ou segmentação", font=font(23), fill=MUTED)
    canvas.paste(crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST), (36, 124))
    x0 = 36 + (row["x_min"] - left) * scale
    y0 = 124 + (row["y_min"] - top) * scale
    x1 = 36 + (row["x_max"] - left) * scale
    y1 = 124 + (row["y_max"] - top) * scale
    color = COLORS[row["class_id"]]
    draw.rectangle((x0, y0, x1, y1), outline=color, width=4)
    cx, cy = 36 + (row["cx"] - left) * scale, 124 + (row["cy"] - top) * scale
    draw.line((cx - 9, cy, cx + 9, cy), fill=color, width=3)
    draw.line((cx, cy - 9, cx, cy + 9), fill=color, width=3)
    facts = [
        ("Classe da anotação", str(row["class_id"])),
        ("Centro (x, y)", f'({row["cx"]:g}, {row["cy"]:g}) pixels'),
        ("Largura × altura", f'{row["w"]:g} × {row["h"]:g} pixels'),
        ("Posição de referência", "Centro da caixa; não é o contorno da célula"),
    ]
    for i, (label, value) in enumerate(facts):
        y = 126 + i * 70
        draw.text((413, y), label, font=font(20), fill=MUTED)
        draw.text((413, y + 26), value, font=font(24, True), fill=INK)
    draw.text((413, 421), "ID persistente fornecido pelo dataset", font=font(20), fill=MUTED)
    draw.text((413, 451), row["track_id"], font=font(21), fill=INK)
    draw.text((36, 507), "A classe 0 é um rótulo do dataset; não certifica normalidade clínica.", font=font(22), fill=MUTED)
    return canvas


def main() -> None:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", type=int, required=True)
    parser.add_argument("--frame", type=int, required=True, help="Índice do quadro, começando em zero")
    parser.add_argument("--audit-id", required=True, help="Nome da inspeção, sem barras ou espaços")
    args = parser.parse_args()
    spec_path = ROOT / "configs/protocol/splits.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if args.video_id not in spec["fixed_split"]["train"]:
        parser.error("Esta inspeção aceita exclusivamente vídeos do treino registrado.")
    if args.frame < 0 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", args.audit_id):
        parser.error("Use frame não negativo e audit-id com letras, números, hífen ou sublinhado.")
    out = (ROOT / "data/derived/detection/annotation_audit" / args.audit_id
           / f"video_{args.video_id}" / f"frame_{args.frame:06d}")
    if out.exists():
        parser.error("A pasta desta inspeção já existe. Use outro audit-id; nenhuma saída foi sobrescrita.")
    base = ROOT / "data/sources/visem_tracking/dataset/Train" / str(args.video_id)
    sources = {
        "video": base / f"{args.video_id}.mp4",
        "image": base / "images" / f"{args.video_id}_frame_{args.frame}.jpg",
        "labels": base / "labels" / f"{args.video_id}_frame_{args.frame}.txt",
        "labels_ftid": base / "labels_ftid" / f"{args.video_id}_frame_{args.frame}_with_ftid.txt",
    }
    inputs = {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
              for key, path in sources.items()}
    simple = read_rows(sources["labels"], identity=False)
    tracked = read_rows(sources["labels_ftid"], identity=True)
    plain_boxes = sorted((row[1], *row[2]) for row in simple)
    tracked_boxes = sorted((row[1], *row[2]) for row in tracked)
    if len(simple) != len(tracked) or not np.allclose(plain_boxes, tracked_boxes, atol=1e-12, rtol=0):
        raise ValueError("Os arquivos de detecção e identidade discordam nas caixas/classes.")
    if not tracked or len({row[0] for row in tracked}) != len(tracked):
        raise ValueError("A figura didática exige anotações presentes e IDs únicos neste quadro.")
    capture = cv2.VideoCapture(str(sources["video"]))
    try:
        if not capture.isOpened():
            raise ValueError("Não foi possível abrir o vídeo.")
        fps = capture.get(cv2.CAP_PROP_FPS)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if args.frame >= total_frames:
            raise ValueError("Quadro fora do vídeo.")
        if args.frame:
            capture.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
        success, bgr = capture.read()
        if not success:
            raise ValueError("Não foi possível decodificar o quadro solicitado.")
    finally:
        capture.release()
    height, width = bgr.shape[:2]
    source_jpg = cv2.imread(str(sources["image"]))
    if source_jpg is None or source_jpg.shape != bgr.shape:
        raise ValueError("Dimensões do JPG e do quadro decodificado não correspondem.")
    gt = load_gt_for_frame(base / "labels_ftid", args.frame, width, height,
                           label_index={args.frame: sources["labels_ftid"]})
    if not gt.annotated or len(gt.detections) != len(tracked):
        raise ValueError("O leitor da biblioteca não preservou todas as anotações.")
    rows = []
    for number, (raw, det) in enumerate(zip(tracked, gt.detections), 1):
        identity, class_id, coords = raw
        expected = np.array(coords) * (width, height, width, height)
        if det.object_id != identity or det.class_id != class_id or not np.allclose(
            (det.cx, det.cy, det.w, det.h), expected, atol=1e-9, rtol=0
        ):
            raise ValueError("Conversão da biblioteca difere da referência normalizada.")
        box = (det.x, det.y, det.x + det.w, det.y + det.h)
        if box[0] < -1e-9 or box[1] < -1e-9 or box[2] > width + 1e-9 or box[3] > height + 1e-9:
            raise ValueError("Uma caixa ultrapassa os limites da imagem.")
        rows.append({"video_id": args.video_id, "frame": args.frame, "visual_number": number,
                     "track_id": identity, "class_id": class_id, "cx": det.cx, "cy": det.cy,
                     "w": det.w, "h": det.h, "x_min": box[0], "y_min": box[1],
                     "x_max": box[2], "y_max": box[3], "cx_normalized": coords[0],
                     "cy_normalized": coords[1], "w_normalized": coords[2], "h_normalized": coords[3]})
    frame = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    overview = render_overview(frame, rows, args.video_id, args.frame)
    example = render_example(frame, rows[0])
    out.mkdir(parents=True, exist_ok=False)
    frame.save(out / "00_quadro_original.png")
    overview.save(out / "01_quadro_anotado.png")
    example.save(out / "02_exemplo_anotacao.png")
    with (out / "annotations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if any(sha256(path) != inputs[key]["sha256"] for key, path in sources.items()):
        raise RuntimeError("Um arquivo de origem mudou durante a inspeção.")
    manifest = {
        "schema_version": 1, "kind": "manual_annotation_inspection", "audit_id": args.audit_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "video_id": args.video_id,
        "frame_zero_based": args.frame, "split": "train", "width": width, "height": height,
        "fps": fps, "total_video_frames": total_frames, "annotation_count": len(rows),
        "class_counts": dict(Counter(row["class_id"] for row in rows)), "unique_track_ids": len(rows),
        "checks": {"schema_and_normalized_coordinates": True, "boxes_within_image": True,
                   "label_formats_equivalent": True, "canonical_reader_agrees": True,
                   "input_hashes_unchanged": True, "normalization_atol": 1e-12, "pixel_atol": 1e-9},
        "jpg_vs_decoded_frame_mean_absolute_channel_difference": float(
            np.abs(bgr.astype(np.float64) - source_jpg.astype(np.float64)).mean()),
        "inputs": inputs, "split_config_sha256": sha256(spec_path),
        "git": {"commit": git_output("rev-parse", "HEAD"), "status": git_output("status", "--porcelain")},
        "generator": {"path": Path(__file__).relative_to(ROOT).as_posix(), "sha256": sha256(Path(__file__))},
        "environment": {"python": platform.python_version(), "opencv": cv2.__version__,
                        "numpy": np.__version__, "pillow": pillow_version, "os": platform.platform(),
                        "machine": platform.machine(), "processor": platform.processor()},
        "runtime_seconds": time.perf_counter() - started,
        "process_rss_bytes_at_finish": psutil.Process().memory_info().rss,
        "gpu_used": False, "seed": None,
        "limitations": ["Inspeção de um único quadro de treino; não é avaliação de detector.",
                        "Não certifica completude das anotações nem consistência temporal dos IDs.",
                        "Números visuais são locais a esta figura; IDs originais são preservados na tabela.",
                        "A diferença entre JPG e vídeo é descritiva e não certifica alinhamento temporal.",
                        "Classe 0 é rótulo do dataset, não diagnóstico de normalidade clínica."],
        "outputs": {path.name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
                    for path in sorted(out.iterdir())},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": out.relative_to(ROOT).as_posix(), "annotations": len(rows),
                      "class_counts": manifest["class_counts"], "checks": manifest["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
