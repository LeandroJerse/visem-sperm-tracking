"""Render completed validation metrics as a descriptive scientific PNG/SVG.

Read hashed run metadata only. Never open dataset sources, labels, videos or
frame caches. No detector, evaluator, hypothesis test or interval is executed.
The output directory must be new; failed and historical outputs are preserved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ("14", "19", "36", "52")
FRAMES = {"14": 1470, "19": 1470, "36": 1470, "52": 1440}
CANDIDATES = ("t219_o0_c2", "t218_o0_c2")
LABELS = {"t219_o0_c2": "T219", "t218_o0_c2": "T218"}
PROTOCOL = "center_distance_v3_individuals_ignore_clusters_10px"
INTERPRETATION = "validation_selection_not_independent_test_not_frozen"
OUTPUT = ROOT / "data/derived/detection/validation_reports/threshold_validation_v3_20260908"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(value not in (None, "") and not isinstance(value, bool), f"Invalid numeric value: {value!r}")
    result = float(value)
    require(math.isfinite(result), f"Nonfinite value: {value!r}")
    return result


def score(value):
    result = number(value)
    require(0 <= result <= 1, "F1 must lie in [0,1]")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(actual, expected, label):
    require(math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12), f"Inconsistent {label}")


class Inputs:
    def __init__(self):
        self.files = {}

    def load(self, value, expected_hash=None):
        path = Path(value).resolve()
        require(path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / "data/sources"),
                "Only repository metadata outside data/sources may be read")
        require(path.suffix.lower() in {".csv", ".json"}, "Only metadata CSV/JSON may be read")
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                f"Input changed during read: {path}")
        digest = hashlib.sha256(content).hexdigest()
        require(expected_hash is None or expected_hash == digest, f"Input SHA256 mismatch: {path}")
        previous = self.files.get(str(path))
        require(previous is None or previous["sha256"] == digest, f"Input changed across reads: {path}")
        self.files[str(path)] = {"path": str(path), "sha256": digest, "bytes": len(content),
                                 "expected_hash_verified": expected_hash is not None}
        text = content.decode("utf-8-sig")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "Duplicate or missing CSV headers")
        rows = list(reader)
        require(all(None not in row and all(value is not None for value in row.values()) for row in rows), "Malformed CSV row")
        return rows

    def artifact(self, manifest, manifest_path, filename):
        declared, hashes = manifest.get("artifacts", {}), manifest.get("artifact_hashes", {})
        require(set(declared) == set(hashes), "Every artifact needs a declared hash")
        matches = []
        for key, value in declared.items():
            path = Path(value)
            path = (path if path.is_absolute() else manifest_path.parent / path).resolve()
            if path.name == filename:
                require(path.parent == manifest_path.parent, "Artifact is outside its run directory")
                matches.append((path, hashes[key]))
        require(len(matches) == 1, f"Expected one hashed {filename}")
        return self.load(*matches[0])


def read_plot_data(manifest_path, inputs, verification_path=None):
    path = Path(manifest_path).resolve()
    batch = inputs.load(path)
    summary = batch.get("summary", {})
    require(batch.get("status") == "complete" and batch.get("git_dirty") is False,
            "Only a completed validation batch with clean recorded Git can be plotted")
    require(summary.get("complete") is True and summary.get("split") == "val"
            and summary.get("interpretation") == INTERPRETATION
            and summary.get("n_candidates") == 2 and summary.get("n_videos") == 4
            and summary.get("n_runs") == 8 and summary.get("frames_per_candidate") == 5850
            and summary.get("frame_evaluations") == 11700, "Validation universe is incomplete or incompatible")
    require(batch.get("provenance_verification", {}).get("status") == "verified", "Batch lacks final provenance verification")
    plan = batch["config"]["plan"]
    require(tuple(map(str, plan["protocol"]["validation_ids"])) == VIDEOS
            and {str(k): v for k, v in plan["input"]["expected_frames"].items()} == FRAMES,
            "Unexpected validation videos or expected frame counts")
    require(plan["evaluation"] == {"protocol_id": PROTOCOL, "class_policy": "individuals_ignore_clusters",
                                   "center_gate_px": 10, "sensitivity_gates_px": [15, 20]}, "Unexpected evaluation contract")
    ranking = inputs.artifact(batch, path, "ranking.csv")
    video_rows = inputs.artifact(batch, path, "video_metrics.csv")
    selection = inputs.artifact(batch, path, "selection.json")
    require(len(ranking) == 2 and {r["configuration_id"] for r in ranking} == set(CANDIDATES), "Expected both fixed training finalists")
    require([int(r["rank"]) for r in ranking] == [1, 2], "Invalid rank sequence")
    require(len(video_rows) == 8 and len({(r["configuration_id"], r["video_id"]) for r in video_rows}) == 8,
            "Missing or duplicated candidate/video pair")
    require({(r["configuration_id"], r["video_id"]) for r in video_rows} == {(c, v) for c in CANDIDATES for v in VIDEOS},
            "Unexpected candidate/video pair")
    require(selection.get("status") == "validation_selected_not_frozen" and selection.get("interpretation") == INTERPRETATION
            and selection.get("test_executed") is False and selection.get("five_fold_executed") is False,
            "Selection scope differs: this plot is validation selection, not test or freezing")
    winner = ranking[0]["configuration_id"]
    require(selection.get("configuration_id") == summary.get("selected_configuration_id") == winner,
            "Selection and batch disagree with ranking")
    metrics, macro = {}, {}
    for candidate in CANDIDATES:
        ranked = next(r for r in ranking if r["configuration_id"] == candidate)
        require(ranked.get("complete") == "True" and ranked.get("split") == "val"
                and ranked.get("interpretation") == INTERPRETATION and ranked.get("evaluation_protocol_id") == PROTOCOL
                and int(ranked["n_videos"]) == 4 and int(ranked["frames_total"]) == int(ranked["frames_annotated"]) == 5850,
                "Ranked candidate has incomplete or incompatible metrics")
        metrics[candidate] = []
        for video in VIDEOS:
            row = next(r for r in video_rows if r["configuration_id"] == candidate and r["video_id"] == video)
            require(row.get("status") == "complete" and row.get("split") == "val"
                    and row.get("frame_coverage_verified") == "True" and row.get("evaluation_protocol_id") == PROTOCOL
                    and int(row["frames_total"]) == int(row["frames_annotated"]) == int(row["count_evaluated_frames"]) == FRAMES[video]
                    and int(row["frames_unannotated"]) == 0, "Video summary is incomplete or incompatible")
            record = {"video_id": video, "frames": FRAMES[video], "f1": score(row["f1"]),
                      "precision": score(row["precision"]), "recall": score(row["recall"]),
                      "count_mae": number(row["count_mae"]), "count_bias": number(row["count_bias"])}
            metrics[candidate].append(record)
        macro[candidate] = {}
        for metric in ("f1", "precision", "recall", "count_mae", "count_bias"):
            value = statistics.fmean(row[metric] for row in metrics[candidate])
            close(value, number(ranked[f"macro_video_{metric}"]), f"macro {metric} for {candidate}")
            macro[candidate][metric] = value
        close(macro[candidate]["f1"], number(ranked["macro_video_f1_individuals_center_10px"]), "primary F1 alias")
    expected_order = sorted(CANDIDATES, key=lambda c: (-macro[c]["f1"], -macro[c]["recall"], macro[c]["count_mae"], c))
    require([r["configuration_id"] for r in ranking] == expected_order, "Ranking does not follow the registered order")
    verification = None
    if verification_path is not None:
        verification = inputs.load(verification_path)
        require(verification.get("status") == "passed"
                and Path(verification["batch_manifest"]).resolve() == path
                and verification.get("batch_manifest_sha256") == inputs.files[str(path)]["sha256"],
                "Independent verification does not certify this batch")
    differences = [{"video_id": v, "f1_t219_minus_t218": metrics[CANDIDATES[0]][i]["f1"] - metrics[CANDIDATES[1]][i]["f1"]}
                   for i, v in enumerate(VIDEOS)]
    delta_macro = macro[CANDIDATES[0]]["f1"] - macro[CANDIDATES[1]]["f1"]
    close(statistics.fmean(r["f1_t219_minus_t218"] for r in differences), delta_macro, "mean paired difference")
    return {"scope": INTERPRETATION, "batch_manifest": str(path), "run_id": batch["run_id"],
            "git_sha_of_runs": batch["git_sha"], "source_hash_of_runs": batch["source_hash"],
            "plan_hash": summary["plan_hash"], "evaluation_protocol_id": PROTOCOL,
            "video_ids": list(VIDEOS), "frames_per_video": FRAMES, "candidate_ids": list(CANDIDATES),
            "video_metrics": metrics, "macro_metrics": macro, "differences": differences,
            "macro_f1_t219_minus_t218": delta_macro, "validation_order": expected_order,
            "selected_configuration_id": winner, "verification_report": str(Path(verification_path).resolve()) if verification else None,
            "aggregation": "F1 from TP/FP/FN pooled within each video, then arithmetic mean across four videos with equal weights",
            "difference_definition": "T219 F1 minus T218 F1; the plotted unit is percentage points (100 times the raw difference)",
            "p_values_computed": False, "confidence_intervals_computed": False, "test_executed": False,
            "limits": ["Both candidates were selected using the validation videos shown here; this is not an independent test estimate.",
                       "Four videos are the comparison units; frames are not independent replicates.",
                       "The enlarged difference axis exposes small numerical effects without claiming statistical superiority.",
                       "This renderer checks plot input consistency and hashes; it does not repeat object matching or certify all scientific metrics."]}


def draw(data, output):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none",
                         "savefig.facecolor": "white", "axes.titlesize": 12.5})
    fig = plt.figure(figsize=(16, 8.5), facecolor="white")
    grid = fig.add_gridspec(1, 2, left=.125, right=.965, top=.78, bottom=.25, width_ratios=(1.1, 1), wspace=.24)
    ax = fig.add_subplot(grid[0, 0]); delta_ax = fig.add_subplot(grid[0, 1])
    y = np.array([0., 1., 2., 3., 4.35])
    colors, markers = ("#0072B2", "#D55E00"), ("o", "D")
    values = {c: [row["f1"] for row in data["video_metrics"][c]] + [data["macro_metrics"][c]["f1"]] for c in CANDIDATES}
    for i, candidate in enumerate(CANDIDATES):
        offset = -.15 if i == 0 else .15
        ax.scatter(values[candidate], y + offset, s=53, marker=markers[i], color=colors[i], label=LABELS[candidate], zorder=4)
        for x, row_y in zip(values[candidate], y + offset):
            ax.annotate(f"{x:.5f}".replace(".", ","), (x, row_y), xytext=(8 if x < .87 else -8, 0),
                        textcoords="offset points", ha="left" if x < .87 else "right", va="center", fontsize=9.4, color=colors[i])
    for i, row_y in enumerate(y):
        ax.plot([values[CANDIDATES[0]][i], values[CANDIDATES[1]][i]], [row_y-.15, row_y+.15], color="#A7B0BB", lw=1, zorder=2)
    ax.set(xlim=(0, 1), ylim=(4.95, -.6), xlabel="F1 dos indivíduos a 10 px (escala 0–1)", title="(A) F1 por vídeo e média macro")
    ax.set_yticks(y, [f"Vídeo {v}\n{FRAMES[v]:,} quadros".replace(",", ".") for v in VIDEOS] + ["Média macro\n4 vídeos, peso igual"])
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.1f}".replace(".", ",")))
    ax.grid(axis="x", color="#DCE1E6", lw=.7)
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.04), ncol=2, frameon=False)
    delta = np.array([r["f1_t219_minus_t218"] for r in data["differences"]] + [data["macro_f1_t219_minus_t218"]]) * 100
    extent = max(float(np.max(np.abs(delta))) * 1.55, .001)
    digits = min(7, max(3, int(math.ceil(-math.log10(extent))) + 2))
    delta_ax.axvline(0, color="#4C5968", lw=1)
    for i, value in enumerate(delta):
        color = "#233B53" if i == 4 else colors[0] if value >= 0 else colors[1]
        delta_ax.plot([0, value], [y[i], y[i]], color=color, lw=2, alpha=.75)
        delta_ax.scatter(value, y[i], color=color, marker="D" if i == 4 else "o", s=67 if i == 4 else 45, zorder=3)
        delta_ax.annotate(f"{value:+.{digits}f}".replace(".", ","), (value, y[i]),
                          xytext=(7 if value >= 0 else -7, 0), textcoords="offset points",
                          ha="left" if value >= 0 else "right", va="center", fontsize=9.8, color=color)
    delta_ax.set(xlim=(-extent, extent), ylim=ax.get_ylim(), title="(B) Diferenças pareadas (escala ampliada)",
                 xlabel="F1(T219) − F1(T218), em pontos percentuais")
    delta_ax.set_yticks(y, ["14", "19", "36", "52", "Macro"])
    delta_ax.xaxis.set_major_locator(MaxNLocator(nbins=5, symmetric=True))
    delta_ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.{digits}f}".replace(".", ",")))
    delta_ax.tick_params(axis="x", labelsize=9)
    delta_ax.grid(axis="x", color="#DCE1E6", lw=.7)
    delta_ax.text(.5, -.21, "Positivo favorece T219; negativo favorece T218.", ha="center", transform=delta_ax.transAxes, fontsize=9.5)
    for axis in (ax, delta_ax):
        axis.axhline(3.65, color="#A7B0BB", lw=.8, linestyle="--")
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Threshold fixo: comparação na validação completa", y=.96, fontsize=19, fontweight="bold")
    fig.text(.5, .906, "4 vídeos · 5.850 quadros por configuração · indivíduos a 10 px", ha="center", fontsize=12)
    winner = data["selected_configuration_id"]
    fig.text(.5, .858, f"Primeira na ordem registrada: {LABELS[winner]} (F1 macro = {data['macro_metrics'][winner]['f1']:.6f})".replace(".", ","),
             ha="center", fontsize=10.5, color="#344454")
    fig.text(.125, .085, "Média macro: média simples dos quatro F1 por vídeo. As duas configurações usam abertura zero e dois fechamentos.\n"
             "Seleção na própria validação; teste independente não executado. Sem p-valores ou intervalos de confiança.",
             fontsize=9.4, color="#344454", va="bottom")
    png, svg = output / "validacao_threshold_completa.png", output / "validacao_threshold_completa.svg"
    fig.savefig(png, dpi=300, metadata={"Title": "Threshold: seleção na validação completa, sem teste independente"})
    fig.savefig(svg, metadata={"Title": "Threshold: seleção na validação completa, sem teste independente", "Date": None})
    plt.close(fig)
    return {"figure_size_inches": [16, 8.5], "png_dpi": 300, "f1_axis_limits": [0, 1],
            "difference_axis_limits_percentage_points": [-extent, extent], "difference_annotation_decimal_places": digits}


def write_json(path, content):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(content, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest", required=True)
    parser.add_argument("--output-dir", default=str(OUTPUT))
    parser.add_argument("--verification-report")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    require(output.is_relative_to(ROOT / "data/derived/detection/validation_reports"), "Output must be a new validation-report directory")
    require(not output.exists(), "Output already exists; preserve previous figures and reports")
    inputs = Inputs()
    # Read and validate completed metadata before creating any figure output.
    data = read_plot_data(args.batch_manifest, inputs, args.verification_report)
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "scope": INTERPRETATION}
    try:
        write_json(output / "figure_data.json", data)
        geometry = draw(data, output)
        for record in inputs.files.values():
            require(sha256(Path(record["path"])) == record["sha256"], "Plot input changed during rendering")
        report.update(status="complete", batch_manifest=data["batch_manifest"], run_id=data["run_id"],
                      git_sha_of_runs=data["git_sha_of_runs"], source_hash_of_runs=data["source_hash_of_runs"],
                      plan_hash=data["plan_hash"], selected_configuration_id=data["selected_configuration_id"], **geometry)
        code = 0
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error)); code = 1
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    report.update(created_at=datetime.now(timezone.utc).isoformat(), seed=None, p_values_computed=False,
                  confidence_intervals_computed=False, test_executed=False, scientific_implementation_imported=False,
                  visual_review_completed=False, script_path=str(Path(__file__).resolve()), script_sha256=sha256(Path(__file__)),
                  input_files=list(inputs.files.values()),
                  output_files=[{"path": str(p), "sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()],
                  git_at_render={"head": git_head.stdout.strip(), "status_porcelain": git_status.stdout.strip()},
                  runtime={"python": sys.version, "matplotlib": matplotlib.__version__, "numpy": np.__version__, "platform": platform.platform()},
                  limits=data["limits"])
    write_json(output / "manifest.json", report)
    print(json.dumps({"status": report["status"], "output_dir": str(output)}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
