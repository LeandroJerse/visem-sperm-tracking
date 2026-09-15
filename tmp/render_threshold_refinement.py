"""Render a completed training refinement into a static scientific PNG/SVG.

Consumes only hashed run JSON/CSV artifacts. Never loads videos, source
annotations, cached pixels, detectors or scientific evaluator implementations.
The output directory must be new. No p-values or confidence intervals are
computed for candidates selected on the same training sample.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
CONTRACT_READY = True  # Final contract agreed; a passed verification remains mandatory.
CONFIG_ID = re.compile(r"^t(?P<threshold>\d{3})_o(?P<opening>[012])_c(?P<closing>[012])$")
PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(value not in (None, "") and not isinstance(value, bool), f"Invalid number: {value!r}")
    result = float(value)
    require(math.isfinite(result), f"Nonfinite number: {value!r}")
    return result


def f1(value):
    result = number(value)
    require(0 <= result <= 1, "F1 outside [0, 1]")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Inputs:
    def __init__(self):
        self.files = {}

    def load(self, value, expected_hash=None):
        path = Path(value).resolve()
        require(path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / "data/sources"), "Only repository artifacts may be read")
        require(path.suffix.lower() in {".csv", ".json"}, "Only CSV/JSON inputs are supported")
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"Input changed while reading: {path}")
        digest = hashlib.sha256(content).hexdigest()
        if expected_hash is not None:
            require(digest == expected_hash, f"SHA256 mismatch: {path}")
        previous = self.files.get(str(path))
        require(previous is None or previous["sha256"] == digest, f"Input changed across reads: {path}")
        self.files[str(path)] = {"path": str(path), "sha256": digest, "bytes": len(content),
                                 "expected_hash_verified": expected_hash is not None}
        text = content.decode("utf-8-sig")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        return list(csv.DictReader(io.StringIO(text, newline="")))

    def artifact(self, manifest, manifest_path, filename):
        hashes = manifest.get("artifact_hashes", {})
        declared = manifest.get("artifacts", {})
        matches = []
        for key, digest in hashes.items():
            path = Path(declared.get(key, key))
            if not path.is_absolute():
                path = manifest_path.parent / path
            path = path.resolve()
            if path.name == filename:
                require(path.parent == manifest_path.parent, "Artifact must belong to its manifest directory")
                matches.append((path, digest))
        require(len(matches) == 1, f"Expected one hashed {filename} artifact")
        return self.load(*matches[0])


def read_plot_data(batch_path, verification_path, inputs):
    require(CONTRACT_READY, "Refinement contract is not finalized; no run artifacts were opened")
    batch_path = Path(batch_path).resolve()
    batch = inputs.load(batch_path)
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False
            and batch.get("summary", {}).get("mode") == "refine"
            and batch.get("summary", {}).get("selection_allowed") is True,
            "Only a complete refinement batch with clean recorded Git can be plotted")
    verification = inputs.load(verification_path)
    require(verification.get("status") == "passed" and verification.get("ranking_complete_match") is True
            and verification.get("candidates") == 117 and verification.get("frames_per_video") == 48
            and len(verification.get("matching_checks", [])) == 162,
            "Rendering requires the complete independent refinement verification")
    require(Path(verification["batch_manifest"]).resolve() == batch_path
            and verification["batch_manifest_sha256"] == inputs.files[str(batch_path)]["sha256"],
            "Verification refers to another batch manifest")
    derived_ref = verification["derived_plan"]
    derived = inputs.load(derived_ref["path"], derived_ref["sha256"])
    require(derived["candidate_count"] == 117 and derived["frames_per_video"] == 48
            and derived["sample_hash"] == verification["sample_hash"], "Derived plot universe differs")
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False, "Rendering requires a completed batch with clean recorded Git")
    require(batch["summary"].get("mode") == "refine" and batch["summary"].get("selection_allowed") is True, "Only the completed refinement search can be plotted")
    plan = batch["config"]["plan"]
    require(tuple(map(str, plan["protocol"]["train_ids"])) == TRAIN, "Unexpected training video universe")
    require(plan["sampling"]["master_frames_per_video"] == 48, "Expected 48 refinement frames per video")
    require(plan["evaluation"]["protocol_id"] == PROTOCOL, "Unexpected evaluation protocol")
    require(batch["summary"]["completed_candidates"] == 117 and batch["summary"]["frame_evaluations"] == 67392,
            "Cannot render an incomplete comparison")
    ranking = inputs.artifact(batch, batch_path, "ranking.csv")
    finalists = inputs.artifact(batch, batch_path, "finalists.json")
    require(len(ranking) == 117 and len(finalists) == 2, "Expected 117 ranks and two finalists")
    ids = [row["configuration_id"] for row in ranking]
    require(len(set(ids)) == 117, "Duplicate candidate ID")
    require([int(row["rank"]) for row in ranking] == list(range(1, 118)), "Invalid rank positions")
    require([row["configuration_id"] for row in finalists] == ids[:2], "Finalists differ from ranking")
    require(ids[:2] == verification["independent_top2"]
            and batch["summary"]["plan_hash"] == verification["plan_hash"]
            and batch["summary"]["sample_hash"] == verification["sample_hash"],
            "Plot identities differ from the independent verification")
    curves = []
    for row in ranking:
        config_id = row["configuration_id"]
        match = CONFIG_ID.fullmatch(config_id)
        require(match is not None, f"Unexpected threshold configuration ID: {config_id}")
        require(row["evaluation_protocol_id"] == PROTOCOL and int(row["n_videos"]) == 12
                and int(row["frames_total"]) == 576, "Incomplete or incompatible candidate summary")
        values = {key: int(value) for key, value in match.groupdict().items()}
        curves.append({"configuration_id": config_id, **values, "macro_video_f1": f1(row["macro_video_f1"]),
                       "rank": int(row["rank"]),
                       "macro_metrics": {key: number(value) if value not in (None, "") else None
                                         for key, value in row.items() if key.startswith("macro_video_")}})
    expected = {(int(row["params"]["threshold_value"]), int(row["params"]["morph_iterations"]),
                 int(row["params"]["close_iterations"])) for row in derived["candidates"]}
    require(len(expected) == 117 and len({(o, c) for _, o, c in expected}) == 3,
            "Derived plan must contain 117 candidates and three morphology pairs")
    require({(item["threshold"], item["opening"], item["closing"]) for item in curves} == expected,
            "Curves do not contain exactly the candidates from the validated derived plan")
    top_ids = ids[:2]
    children = batch["candidate_manifests"]
    require(len(children) == 117 and len({row["path"] for row in children}) == 117, "Invalid child-manifest universe")
    top_videos = {}
    # Inspect the immutable child manifest identities, then open only the two
    # video-summary CSVs used in panel B. No GT/object CSV is required here.
    for reference in children:
        child_path = Path(reference["path"]).resolve()
        child = inputs.load(child_path, reference["sha256"])
        config_id = child["config"]["configuration_id"]
        if config_id not in top_ids:
            continue
        require(config_id not in top_videos and child.get("status") == "complete", "Invalid finalist manifest")
        require(child["source_hash"] == batch["source_hash"] and child["git_sha"] == batch["git_sha"], "Mixed run code identities")
        rows = inputs.artifact(child, child_path, "video_summary.csv")
        by_video = {str(row["video_id"]): row for row in rows}
        require(len(rows) == len(by_video) == 12 and set(by_video) == set(TRAIN), "Incomplete video-summary universe")
        for row in rows:
            require(row["configuration_id"] == config_id and row["evaluation_protocol_id"] == PROTOCOL
                    and int(row["frames_total"]) == int(row["frames_annotated"]) == int(row["count_evaluated_frames"]) == 48,
                    "Video summary is incomplete or incompatible")
        scores = [f1(by_video[vid]["f1"]) for vid in TRAIN]
        macro = next(item["macro_video_f1"] for item in curves if item["configuration_id"] == config_id)
        require(math.isclose(statistics.fmean(scores), macro, abs_tol=1e-12, rel_tol=0), "Heatmap video F1 does not reproduce macro F1")
        top_videos[config_id] = [{"video_id": vid, "f1": scores[index],
                                  "precision": number(by_video[vid]["precision"]),
                                  "recall": number(by_video[vid]["recall"]),
                                  "count_mae": number(by_video[vid]["count_mae"]),
                                  "count_bias": number(by_video[vid]["count_bias"])} for index, vid in enumerate(TRAIN)]
    require(set(top_videos) == set(top_ids), "Could not resolve both selected video summaries")
    return {
        "scope": "refinamento no treino; 48 quadros/vídeo; sem promoção",
        "verification_report": str(Path(verification_path).resolve()), "derived_plan": derived_ref,
        "batch_manifest": str(batch_path), "run_id": batch["run_id"], "git_sha": batch["git_sha"],
        "source_hash": batch["source_hash"], "plan_hash": batch["summary"]["plan_hash"],
        "sample_hash": batch["summary"]["sample_hash"], "evaluation_protocol_id": PROTOCOL,
        "training_video_ids": list(TRAIN), "frames_per_video": 48, "candidate_count": 117,
        "curves": sorted(curves, key=lambda item: (item["opening"], item["closing"], item["threshold"])),
        "top2_ids_in_rank_order": top_ids, "top2_video_metrics": top_videos,
        "base_selection": plan["selection"],
        "selection": batch["config"]["refinement_execution"]["selection"],
        "p_values_computed": False, "confidence_intervals_computed": False,
        "rounding": "Full precision in data/curves; heatmap cell labels display three decimal places only.",
        "limits": ["Selected on the same training sample shown here; not a generalization estimate.",
                   "Each video receives equal weight in macro F1; sampled frames are not independent samples.",
                   "Three curves represent separate parameter configurations, never a weighted score."]}


def draw(data, output_dir):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12,
                         "axes.labelsize": 11, "svg.fonttype": "none", "savefig.facecolor": "white"})
    fig = plt.figure(figsize=(17, 8.4), facecolor="white")
    grid = fig.add_gridspec(1, 2, width_ratios=(1.45, 1), left=.06, right=.965, top=.80, bottom=.30, wspace=.22)
    ax_curve = fig.add_subplot(grid[0, 0])
    ax_heat = fig.add_subplot(grid[0, 1])
    colors = ("#0072B2", "#D55E00", "#009E73")
    styles = ("-", "--", ":")
    markers = ("o", "s", "^")
    pairs = sorted({(item["opening"], item["closing"]) for item in data["curves"]})
    require(len(pairs) == 3, "Expected three inherited morphology pairs")
    for index, (opening, closing) in enumerate(pairs):
        points = [item for item in data["curves"] if item["opening"] == opening and item["closing"] == closing]
        points.sort(key=lambda item: item["threshold"])
        require(all(right["threshold"] == left["threshold"] + 1 for left, right in zip(points, points[1:])),
                "Do not connect untested threshold gaps in a curve")
        ax_curve.plot([item["threshold"] for item in points], [item["macro_video_f1"] for item in points],
                      color=colors[index], linestyle=styles[index], marker=markers[index],
                      markersize=3.0, linewidth=1.8, alpha=.9,
                      label=f"Abertura {opening} · fechamento {closing}")
    thresholds = [item["threshold"] for item in data["curves"]]
    ax_curve.set(title="(A) F1 macro por limiar e morfologia", xlabel="Limiar de intensidade (0–255)",
                 ylabel="F1 macro no treino (peso igual por vídeo)", xlim=(min(thresholds)-1, max(thresholds)+1), ylim=(0, 1))
    ax_curve.set_xticks(range(5 * (min(thresholds) // 5), max(thresholds)+1, 10))
    ax_curve.set_yticks(np.linspace(0, 1, 6))
    ax_curve.grid(axis="y", color="#D8DEE5", linewidth=.7)
    ax_curve.spines[["top", "right"]].set_visible(False)
    ax_curve.legend(loc="upper center", bbox_to_anchor=(.5, -.20), ncol=3, frameon=False,
                    fontsize=8.5, columnspacing=1.2, handlelength=2.8)
    selected = data["top2_ids_in_rank_order"]
    matrix = np.asarray([[data["top2_video_metrics"][config_id][index]["f1"] for config_id in selected]
                         for index in range(12)], dtype=float)
    image = ax_heat.imshow(matrix, cmap="viridis", vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    labels = []
    for rank, config_id in enumerate(selected, 1):
        parsed = CONFIG_ID.fullmatch(config_id).groupdict()
        labels.append(f"{rank}º · T{int(parsed['threshold'])}\nA{parsed['opening']} / F{parsed['closing']}")
    ax_heat.set_xticks(range(2), labels)
    ax_heat.set_yticks(range(12), TRAIN)
    ax_heat.set(title="(B) F1 por vídeo · dois finalistas de treino", xlabel="Configuração (A: abertura; F: fechamento)",
                ylabel="Vídeo de treino")
    ax_heat.tick_params(axis="x", labelsize=9)
    ax_heat.set_xticks(np.arange(-.5, 2, 1), minor=True)
    ax_heat.set_yticks(np.arange(-.5, 12, 1), minor=True)
    ax_heat.grid(which="minor", color="white", linewidth=1.1)
    ax_heat.tick_params(which="minor", bottom=False, left=False)
    for i in range(12):
        for j in range(2):
            value = matrix[i, j]
            ax_heat.text(j, i, f"{value:.3f}".replace(".", ","), ha="center", va="center",
                         color="black" if value > .56 else "white", fontsize=9.3)
    colorbar = fig.colorbar(image, ax=ax_heat, fraction=.042, pad=.03)
    colorbar.set_label("F1 por vídeo")
    colorbar.set_ticks(np.linspace(0, 1, 6))
    fig.suptitle("Refinamento registrado do threshold fixo", x=.5, y=.96, fontsize=19, fontweight="bold")
    fig.text(.5, .91, "Refinamento no treino; 48 quadros/vídeo; sem promoção", ha="center", fontsize=12.5)
    fig.text(.5, .865, "12 vídeos de treino · 117 configurações · F1 dos indivíduos a 10 px", ha="center", fontsize=10.5, color="#344454")
    fig.text(.06, .072,
             "Indivíduos: classes 0/2; matching Húngaro a 10 px; regiões de agrupamento conforme o protocolo v3.\n"
             "Seleção na própria amostra de treino: esta figura não estima generalização. Sem intervalos de confiança ou testes de hipótese.",
             fontsize=9.2, color="#344454", va="bottom")
    png = output_dir / "refinamento_threshold_treino.png"
    svg = output_dir / "refinamento_threshold_treino.svg"
    require(not png.exists() and not svg.exists(), "Figure output already exists")
    fig.savefig(png, dpi=300, metadata={"Title": "Refinamento no treino; 48 quadros/vídeo; sem promoção"})
    fig.savefig(svg, metadata={"Title": "Refinamento no treino; 48 quadros/vídeo; sem promoção", "Date": None})
    plt.close(fig)
    return [png, svg]


def write_json(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--verification-report", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    require(output_dir.is_relative_to(ROOT) and not output_dir.is_relative_to(ROOT / "data/sources"),
            "Output must be a new directory inside the repository, outside immutable sources")
    require(output_dir.parent.is_dir(), "Output parent must already exist")
    output_dir.mkdir(exist_ok=False)
    inputs = Inputs()
    files = []
    try:
        data = read_plot_data(args.batch_manifest, args.verification_report, inputs)
        data_path = output_dir / "figure_data.json"
        write_json(data_path, data)
        files.append(data_path)
        files.extend(draw(data, output_dir))
        report = {"status": "complete", "scope": data["scope"], "batch_manifest": data["batch_manifest"],
                  "git_sha_of_runs": data["git_sha"], "plan_hash": data["plan_hash"], "sample_hash": data["sample_hash"],
                  "p_values_computed": False, "confidence_intervals_computed": False,
                  "figure_size_inches": [17, 8.4], "png_dpi": 300, "F1_scales": [0, 1],
                  "top2_ids": data["top2_ids_in_rank_order"], "limits": data["limits"]}
        code = 0
    except Exception as error:
        report = {"status": "failed", "error_type": type(error).__name__, "error": str(error)}
        code = 1
    # Include any partial output bytes if rendering failed; preserve them.
    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    report.update(created_at=datetime.now(timezone.utc).isoformat(),
                  script_path=str(Path(__file__).resolve()), script_sha256=sha256(Path(__file__)),
                  input_files=list(inputs.files.values()),
                  output_files=[{"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in files],
                  runtime={"python": sys.version, "matplotlib": matplotlib.__version__, "numpy": np.__version__, "platform": platform.platform()},
                  seed=None, scientific_implementation_imported=False, visual_review_completed=False)
    write_json(output_dir / "manifest.json", report)
    print(json.dumps({"status": report["status"], "output_dir": str(output_dir)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
