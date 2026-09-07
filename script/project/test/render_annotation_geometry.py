"""Render the completed training geometry audit from derived CSVs only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria"
RADII = (10, 15, 20)
VIDEO_IDS = (11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args()
    figure_path = AUDIT / "tolerancias_geometria.png"
    manifest_path = AUDIT / "figure_manifest.json"
    if figure_path.exists() or manifest_path.exists():
        parser.error("Figure or manifest already exists; no output overwritten.")
    source_path = AUDIT / "per_video_gates.csv"
    audit_manifest_path = AUDIT / "manifest.json"
    audit_manifest = json.loads(audit_manifest_path.read_text(encoding="utf-8"))
    source_hash = sha256(source_path)
    if source_hash != audit_manifest["outputs"][source_path.name]["sha256"]:
        raise ValueError("Derived CSV differs from its audit manifest.")
    with source_path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["cohort"] == "all"]
    if len(rows) != len(RADII) * len(VIDEO_IDS) or {
        (int(row["video_id"]), int(row["radius_px"])) for row in rows
    } != {(video, radius) for video in VIDEO_IDS for radius in RADII}:
        raise ValueError("Expected one row per authorized training video and radius.")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 6.0), sharey=True)
    definitions = (
        ("neighbor_le_radius_fraction_all", "Outro centro dentro do raio", "distância entre centros ≤ r"),
        ("neighbor_lt_2radius_fraction_all", "Regiões de aceitação sobrepostas", "distância entre centros < 2r"),
    )
    for ax, (field, title, subtitle) in zip(axes, definitions):
        values = np.asarray([[float(next(row[field] for row in rows
                             if int(row["video_id"]) == video and int(row["radius_px"]) == radius))
                              for radius in RADII] for video in VIDEO_IDS]) * 100
        if not np.all(np.isfinite(values)) or not np.all((0 <= values) & (values <= 100)):
            raise ValueError("Invalid fraction in the derived table.")
        for i, series in enumerate(values):
            ax.plot(RADII, series, "o-", color="#a4b4b2", alpha=.7, lw=1, ms=4,
                    label="Cada vídeo de treino" if i == 0 else None, zorder=2)
        means = values.mean(axis=0)
        ax.plot(RADII, means, "o-", color="#006c67", lw=3, ms=8,
                label="Média com peso igual por vídeo", zorder=4)
        for radius, value in zip(RADII, means):
            ax.annotate(f"{value:.1f}%".replace(".", ","), (radius, value),
                        xytext=(0, 10), textcoords="offset points", ha="center",
                        color="#004b48", weight="bold", zorder=5,
                        bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85, "pad": 1})
        ax.set_title(f"{title}\n{subtitle}", fontsize=12, pad=13)
        ax.set_xticks(RADII)
        ax.set_xlim(8.8, 21.2)
        ax.set_ylim(-1, 50)
        ax.set_xlabel("Tolerância espacial r (pixels)")
        ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        ax.grid(axis="y", color="#e2e9e8", zorder=0)
    axes[0].set_ylabel("Anotações com essa condição, por vídeo")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .10),
               ncol=2, frameon=False)
    fig.suptitle("Tolerância maior amplia a possibilidade de ambiguidade", fontsize=17,
                 weight="bold", x=.5, y=.98)
    fig.text(.5, .91, "12 vídeos de treino · 640 × 480 px · classes 0, 1 e 2, incluindo agrupamentos",
             ha="center", fontsize=11)
    fig.text(.5, .025, "Geometria das anotações: estes percentuais não são taxas de erro de um detector.\n"
             "Linhas claras mostram os vídeos; não representam intervalos de confiança.",
             ha="center", fontsize=10, color="#3d514f")
    fig.subplots_adjust(left=.075, right=.98, bottom=.24, top=.78, wspace=.17)
    fig.savefig(figure_path, dpi=160, facecolor="white")
    plt.close(fig)
    manifest = {
        "kind": "render_of_existing_training_annotation_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {str(path.relative_to(ROOT)): sha256(path)
                   for path in (source_path, audit_manifest_path)},
        "generator": {"path": Path(__file__).relative_to(ROOT).as_posix(),
                      "sha256": sha256(Path(__file__))},
        "environment": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                        "numpy": np.__version__},
        "cohort": "all", "video_ids": VIDEO_IDS, "radii_px": RADII,
        "aggregation": "Within-video fractions, then unweighted mean over 12 videos; no confidence interval.",
        "source_data_opened": False,
        "output": {"path": figure_path.relative_to(ROOT).as_posix(), "sha256": sha256(figure_path)},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(figure_path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
