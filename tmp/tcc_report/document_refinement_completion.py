"""Prepare/update completion documentation only after both independent QAs.

This local helper is not an experiment and changes no HTML, source, config,
run or manuscript. Default invocation authenticates and previews the file list;
--apply writes the proposed Markdown after exclusive backups of every target.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "ca68f16ef5ca4ef8fae91b85cb8a00bc132bbd0d"
SUMMARY = "data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json"
BACKUP = "data/derived/project_audits/general_20260911/classical_refinement_edition/documentation_before"
MARKER = "<!-- refinement-dataset-completion-20260911 -->"
TRAIN = ("11", "12", "13", "15", "21", "22", "23", "29", "30", "35", "60", "82")
VAL = ("14", "19", "36", "52")
FAMILIES = {"otsu": ("Otsu", "otsu.md", 8), "adaptive_threshold": ("Adaptativo", "threshold_adaptativo.md", 13), "hybrid_threshold": ("Híbrido CLAHE", "threshold_hibrido.md", 11), "blob": ("Blob", "blob.md", 6), "watershed": ("Watershed", "watershed.md", 7)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject(value):
        raise ValueError(f"Nonfinite JSON value: {value}")
    def floating(value):
        result = float(value)
        require(math.isfinite(result), "Nonfinite JSON number")
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject, parse_float=floating)


def path_in(root, value, parent=None):
    require(type(value) in (str, Path) or isinstance(value, Path), "Invalid path type")
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    require(path.is_relative_to((parent or root).resolve()), f"Path outside allowed workspace: {path}")
    return path


def pin(root, value, expected, evidence, parent=None):
    path = path_in(root, value, parent)
    require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected), "Invalid SHA256")
    require(sha(path) == expected, f"SHA256 mismatch: {path}")
    evidence[path.relative_to(root).as_posix()] = expected
    return path


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def numeric(value, expected, label):
    require(type(value) in (int, float) and math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12), label)


def count(record, key, expected):
    require(type(record.get(key)) is int and record[key] == expected, f"Invalid count: {key}")


def artifacts(root, manifest, directory, evidence):
    require(type(manifest.get("artifacts")) is dict and set(manifest["artifacts"]) == set(manifest.get("artifact_hashes", {})), "Incomplete artifact hashes")
    result = {}
    for key, value in manifest["artifacts"].items():
        path = pin(root, value, manifest["artifact_hashes"][key], evidence, directory)
        require(path.parent == directory and path.name not in result and path.name != "manifest.json", "Unexpected/repeated run artifact")
        result[path.name] = path
    return result


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), "Duplicate/missing CSV fields")
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows), "Malformed CSV row")
    return rows


def run_provenance(root, manifest):
    require(manifest.get("status") == "complete" and manifest.get("git_dirty") is False, "Run must be complete with clean recorded Git")
    revision = manifest.get("git_sha")
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{7,40}", revision), "Invalid run revision")
    resolved = subprocess.run(["git", "rev-parse", "--verify", revision + "^{commit}"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    require(resolved == COMMIT, "Run does not belong to the approved ca68f16 commit")
    capture, verification = manifest.get("provenance_capture", {}), manifest.get("provenance_verification", {})
    require(verification.get("status") == "verified" and verification.get("snapshot_sha256") == capture.get("snapshot_sha256") and type(capture.get("snapshot_sha256")) is str, "Run provenance was not revalidated")


def authenticate(root, summary_path, dataset_manifest_path, dataset_qa_path):
    """Read final artifacts and hashes; never decode a JPEG or rerun metrics."""
    evidence = {}
    summary_path = path_in(root, summary_path, root / "data/derived/detection/comparison_reports")
    result = read_json(summary_path)
    evidence[summary_path.relative_to(root).as_posix()] = sha(summary_path)
    require(result.get("scope") == "descriptive_training_local_refinement", "Wrong result scope")
    manifest_path = pin(root, result["source_manifest"], result["source_manifest_sha256"], evidence, root / "data/tests/detection/classical_refinement")
    qa_path = pin(root, result["verification"], result["verification_sha256"], evidence, root / "data/tests/detection/classical_refinement")
    manifest, qa = read_json(manifest_path), read_json(qa_path)
    run_provenance(root, manifest)
    require(manifest.get("stage") == "refinement" and result.get("run_commit") == manifest["git_sha"], "Wrong refinement stage/commit")
    batch = manifest["summary"]
    require(batch.get("complete") is True and batch.get("selection_allowed") is True and all(batch.get(key) is False for key in ("promotion_allowed", "validation_released", "historical_threshold_reference_reexecuted")), "Refinement completion/interpretation differs")
    for key, expected in {"completed_candidates": 45, "frames_per_candidate": 576, "frame_evaluations": 25920, "parent_parity_controls": 10}.items():
        count(batch, key, expected)
    require(same(result["batch_summary"], batch), "Derived batch summary differs from the run")
    numeric(result["elapsed_seconds"], manifest["elapsed_seconds"], "Refinement runtime differs")
    require(qa.get("status") == "passed" and qa.get("mode") == "refinement" and path_in(root, qa["manifest"]) == manifest_path and qa.get("manifest_sha256") == result["source_manifest_sha256"] and qa.get("plan_hash") == batch["plan_hash"], "Refinement QA not approved for this exact run")
    for key, expected in {"candidates": 45, "frames_per_candidate": 576, "frame_evaluations": 25920}.items():
        count(qa, key, expected)
    require(qa.get("parent_parity", {}).get("status") == "passed", "Parent parity not approved")
    count(qa["parent_parity"], "controls", 10); count(qa["parent_parity"], "frames_per_control", 576)
    for key, value in result["qa_counts"].items():
        require(same(value, qa[key]), "Derived QA count differs")
    files = artifacts(root, manifest, manifest_path.parent, evidence)
    ranking, finalists = csv_rows(files["ranking.csv"]), read_json(files["family_finalists.json"])
    require(len(ranking) == 45 and len({r["configuration_id"] for r in ranking}) == 45 and len(finalists) == 10 and [r["configuration_id"] for r in finalists] == qa["family_finalist_ids"], "Refinement ranking/finalists differ")
    require({r["family"] for r in ranking} == set(FAMILIES) and all(sum(row["family"] == family for row in finalists) == 2 for family in FAMILIES), "Wrong finalist families")
    records = manifest["candidate_manifests"]
    require(type(records) is list and len(records) == 45, "Refinement children incomplete")
    children = {}
    for record in records:
        path = pin(root, record["path"], record["sha256"], evidence, root / "data/tests/detection")
        child = read_json(path)
        require(child.get("status") == "complete" and child.get("stage") == "refinement" and child.get("git_sha") == manifest["git_sha"] and child.get("source_hash") == manifest["source_hash"] and child.get("git_dirty") is False, "Refinement child not complete/compatible")
        identifier = child["config"]["configuration_id"]
        require(identifier not in children, "Duplicate refinement child")
        child_files = artifacts(root, child, path.parent, evidence)
        children[identifier] = (child, child_files, path)
    require(set(children) == {r["configuration_id"] for r in ranking}, "Refinement child universe differs")
    require(type(result["best_per_family"]) is list and len(result["best_per_family"]) == 5 and {r["family"] for r in result["best_per_family"]} == set(FAMILIES), "Five family results required")
    metric_keys = {"f1": "macro_video_f1", "precision": "macro_video_precision", "recall": "macro_video_recall", "detection_ms": "macro_video_detection_ms_mean", "f1_15px": "macro_video_f1_at_15px", "f1_20px": "macro_video_f1_at_20px"}
    for row in result["best_per_family"]:
        ranked = next(item for item in ranking if item["family"] == row["family"])
        require(row["configuration_id"] == ranked["configuration_id"], "Reported family representative is not first in complete ranking")
        child, child_files, path = children[row["configuration_id"]]
        require(path_in(root, row["manifest"]) == path and row["manifest_sha256"] == sha(path), "Family child reference differs")
        require(same(row["params"], child["config"]["params"]) and same(row["lineage"], child["config"]["refinement_lineage"]), "Family parameters/lineage differ")
        for target, source in metric_keys.items():
            numeric(row[target], float(ranked[source]), f"Family metric differs: {target}")
        count(row, "n_predictions_ignored", int(ranked["n_predictions_ignored"]))
        videos = csv_rows(child_files["video_summary.csv"])
        require(tuple(v["video_id"] for v in videos) == TRAIN and [v["video_id"] for v in row["videos"]] == list(TRAIN), "Family video universe differs")
        for report_video, original_video in zip(row["videos"], videos):
            numeric(report_video["f1"], float(original_video["f1"]), "Family per-video F1 differs")
    prior_path = pin(root, result["prior_summary"], result["prior_summary_sha256"], evidence)
    prior = read_json(prior_path)
    require(result["prior_summary_sha256"] == "d2f6889e80f971d2684cbf7277208b91fa80301608f15030ee0b4cfcc45ef282", "Historical report identity changed")
    for row in result["best_per_family"]:
        old = next(item for item in prior["best_per_family"] if item["family"] == row["family"])
        require(row["previous_configuration_id"] == old["configuration_id"], "Previous representative differs")
        numeric(row["previous_f1"], old["f1"], "Previous F1 differs")
        numeric(row["delta_f1"], row["f1"] - old["f1"], "F1 difference differs")
    historical = next(row for row in prior["best_per_family"] if row["family"] == "threshold")
    require(same(result["historical_threshold"], historical), "Historical T218 summary differs")
    old_reference = read_json(files["historical_reference.json"])
    require(old_reference.get("reexecuted") is False, "T218 must remain historical")
    pin(root, old_reference["parent_manifest"]["path"], old_reference["parent_manifest"]["sha256"], evidence)
    for name, digest in result["figures"].items():
        require(Path(name).name == name and Path(name).suffix in {".png", ".svg"}, "Invalid figure reference")
        pin(root, summary_path.parent / name, digest, evidence, summary_path.parent)

    dataset_manifest_path = path_in(root, dataset_manifest_path, root / "data/datasets/yolo/materialized")
    dataset_qa_path = path_in(root, dataset_qa_path, root / "data/datasets/yolo/materialized")
    dataset, dataset_qa = read_json(dataset_manifest_path), read_json(dataset_qa_path)
    evidence[dataset_manifest_path.relative_to(root).as_posix()] = sha(dataset_manifest_path)
    evidence[dataset_qa_path.relative_to(root).as_posix()] = sha(dataset_qa_path)
    run_provenance(root, dataset)
    require(dataset.get("module") == "yolo" and dataset.get("method") == "dataset" and dataset.get("stage") == "preparation" and dataset.get("training_allowed") is False and dataset.get("consumer_clone_required") is True, "Dataset stage/policy differs")
    require(dataset_qa.get("status") == "passed" and path_in(root, dataset_qa["manifest"]) == dataset_manifest_path and dataset_qa.get("manifest_sha256") == sha(dataset_manifest_path), "Dataset QA not approved for this exact run")
    require(dataset_qa["summary"].get("source_commit") == COMMIT and dataset_qa["summary"].get("scope") == "independent_dataset_integrity_and_annotation_parity_not_training_quality", "Dataset QA scope/commit differs")
    require(same(dataset["summary"]["counts"], {"train": 17466, "val": 5850, "unlabeled": 174}), "Dataset counts differ")
    require(same(dataset_qa["summary"]["counts"], dataset["summary"]["counts"]) and same(dataset_qa["summary"]["class_counts"], dataset["summary"]["class_counts"]), "Dataset QA counts differ")
    for key, expected in {"copied_jpegs_decoded": 23316, "copied_file_count": 46632, "descriptor_files": 3}.items():
        count(dataset_qa["summary"], key, expected)
    require(dataset_qa["summary"].get("test_sources_traversed") is False and dataset_qa["summary"].get("legacy_cache_contents_opened") is False, "Dataset QA traversed forbidden inputs")
    require(set(dataset["artifacts"]) == {"source_metadata", "dataset_manifest"}, "Dataset artifact schema differs")
    dataset_files = {}
    for name, entry in dataset["artifacts"].items():
        path = pin(root, entry["path"], entry["sha256"], evidence, dataset_manifest_path.parent)
        require(path == dataset_manifest_path.parent / (name + ".json"), "Dataset artifact identity differs")
        dataset_files[name] = path
    materialized = read_json(dataset_files["dataset_manifest"])
    for key in ("counts", "class_counts", "dataset_bytes", "resources"):
        require(same(materialized[key], dataset["summary"][key]), "Dataset summary differs from materialization")
    require(materialized.get("trained") is False and materialized.get("sources_modified") is False and materialized.get("test_traversed") is False and materialized.get("originals_rehashed_after") is True and materialized.get("consumer_policy") == "clone_to_new_consumer_run_before_library_access", "Dataset preparation is not sealed/untrained")
    # Rehash the files covered by the already approved QA; this repeats no
    # geometry check or JPEG decoding and catches post-QA byte changes.
    require(type(dataset_qa.get("files")) is dict and bool(dataset_qa["files"]), "Dataset QA lacks its file witness")
    source_root = root / "data/sources/visem_tracking/dataset/Train"
    for name, entry in dataset_qa["files"].items():
        path = path_in(root, name)
        if path.is_relative_to(source_root):
            require(path.relative_to(source_root).parts[0] in TRAIN + VAL, "Dataset QA witness includes a forbidden video")
        pin(root, path, entry["sha256"], evidence)
        require(type(entry["bytes"]) is int and path.stat().st_size == entry["bytes"], "Dataset witness size changed")
    return {"refinement": result, "refinement_manifest": manifest, "refinement_qa": qa, "finalists": finalists, "dataset": dataset, "dataset_qa": dataset_qa, "materialized": materialized, "summary_path": summary_path, "refinement_manifest_path": manifest_path, "refinement_qa_path": qa_path, "dataset_manifest_path": dataset_manifest_path, "dataset_qa_path": dataset_qa_path, "authenticated_files": evidence}


def number(value, digits=6):
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def integer(value):
    return f"{value:,}".replace(",", ".")


def md_link(root, document, target, label):
    destination = path_in(root, target)
    relative = Path(os.path.relpath(destination, (root / document).parent)).as_posix()
    return f"[{label}]({relative})"


def table(rows):
    text = "| Família | Melhor configuração local | F1 macro 10 px | Precisão | Recall | ms/quadro |\n|---|---|---:|---:|---:|---:|\n"
    for row in rows:
        text += f"| {FAMILIES[row['family']][0]} | `{row['configuration_id']}` | {number(row['f1'])} | {number(row['precision'])} | {number(row['recall'])} | {number(row['detection_ms'], 3)} |\n"
    return text


def after_title(text, block):
    require(text.startswith("# ") and "\n" in text, "Expected one Markdown title")
    title, rest = text.split("\n", 1)
    return title + "\n\n" + block.strip() + "\n\n" + rest.lstrip("\n")


def once(text, old, new):
    require(text.count(old) == 1, f"Expected unique documentary anchor: {old[:100]}")
    return text.replace(old, new, 1)


def build_updates(root, data):
    """Construct all edits in memory. No filesystem writes occur here."""
    result, batch, qa = data["refinement"], data["refinement"]["batch_summary"], data["refinement_qa"]
    dataset, dqa, materialized = data["dataset"], data["dataset_qa"], data["materialized"]
    rows = result["best_per_family"]
    paths = {key: data[key].relative_to(root).as_posix() for key in ("summary_path", "refinement_manifest_path", "refinement_qa_path", "dataset_manifest_path", "dataset_qa_path")}
    source_hash = data["refinement_manifest"]["source_hash"]
    require(source_hash == dataset["source_hash"], "Contemporary runs must share the registered source snapshot")
    originals, updates = {}, {}
    def read(name):
        raw = (root / name).read_bytes()
        require(MARKER.encode() not in raw, f"Completion already documented: {name}")
        originals[name] = raw
        return raw.decode("utf-8").replace("\r\n", "\n")
    def save(name, text):
        require(MARKER in text, "Missing completion marker")
        newline = "\r\n" if b"\r\n" in originals[name] else "\n"
        updates[name] = text.replace("\n", newline).encode("utf-8")
    def link(document, key, label):
        return md_link(root, document, paths[key], label)
    def outcome(document, detailed=False):
        text = f"Refinamento concluído e conferido em `{COMMIT[:7]}`, com Git limpo na execução: **45 configurações × 576 quadros = 25.920 avaliações**, somente nos 12 treinos. A vizinhança previamente definida gerou 54 propostas, 51 válidas e 45 configurações únicas. Os dez pais passaram na paridade de objetos brutos e métricas; T218 permaneceu histórico, sem nova execução. Há dez finalistas, duas por família, sem promoção ou liberação automática da validação.\n\n"
        text += f"Bateria: {number(result['elapsed_seconds'])} s; RSS amostrado {number(batch['ram_rss_peak_mb'], 3)} MiB; {integer(batch['candidate_artifact_bytes'])} bytes dos artefatos das candidatas, excluindo o agregador. QA: {integer(qa['files_checked'])} arquivos, {integer(qa['comparisons'])} comparações, {integer(qa['numeric_comparisons'])} numéricas e {integer(qa['scipy_matchings'])} matchings SciPy em {number(qa['elapsed_seconds'])} s; diferença numérica máxima {qa['maximum_numeric_difference']:.12g}.\n\n"
        text += f"{link(document, 'refinement_manifest_path', 'Manifesto do refinamento')} · {link(document, 'refinement_qa_path', 'Conferência independente')} · {link(document, 'summary_path', 'Resumo e resultados por vídeo')}.\n"
        if detailed:
            text += f"\nSHA256 do manifesto: `{result['source_manifest_sha256']}`.\nSHA256 do QA: `{result['verification_sha256']}`.\nFontes da execução: `{source_hash}`.\n"
        return text
    def dataset_outcome(document, detailed=False):
        text = f"Dataset YOLO materializado e conferido em `{COMMIT[:7]}`: **23.316 pares JPEG/anotação**, sendo 17.466 de treino e 5.850 de validação; 174 lacunas de anotação excluídas. Preservadas as três classes e as caixas da referência FTID. O conjunto contém {integer(sum(dataset['summary']['class_counts'].values()))} observações anotadas, não indivíduos únicos. Foram copiados 46.632 arquivos e gerados três descritores.\n\n"
        text += f"Preparação: {number(dataset['elapsed_seconds'])} s; RSS amostrado {number(dataset['summary']['resources']['ram_rss_peak_mb'], 3)} MiB; dataset com {integer(dataset['summary']['dataset_bytes'])} bytes. QA: {integer(dqa['files_checked'])} arquivos, {integer(dqa['comparisons'])} comparações e {integer(dqa['summary']['copied_jpegs_decoded'])} cópias JPEG decodificadas em {number(dqa['elapsed_seconds'])} s. A conferência verificou paridade de {integer(dqa['annotation_rows'])} anotações, com diferença máxima {dqa['maximum_reference_difference']:.12g}.\n\n"
        text += f"{link(document, 'dataset_manifest_path', 'Manifesto do dataset')} · {link(document, 'dataset_qa_path', 'Conferência independente')}. O teste ficou fora da preparação. **Não houve treinamento YOLO:** `training_allowed=false` e `consumer_clone_required=true`; o consumidor deve gerar outro clone independente dentro de sua própria run antes de chamar a biblioteca.\n"
        text += "\nA paridade geométrica entre anotações YOLO e FTID não certifica igualdade de pixels entre JPEG e MP4. Os JPEGs servem ao treinamento e à validação nativa do modelo aprendido. Para comparar F1 v3 com os clássicos, YOLO deverá processar os mesmos quadros MP4/cache usados por eles, com pré-processamento explicitamente registrado. Essa distinção delimita o derivado e o futuro contrato de comparação; não representa falha na organização atual do dataset.\n"
        if detailed:
            text += f"\nSHA256 do manifesto: `{sha(data['dataset_manifest_path'])}`.\nSHA256 do QA: `{sha(data['dataset_qa_path'])}`.\n"
        return text
    pending = "Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold."
    interpretation = "Os números abaixo descrevem a melhor configuração da vizinhança por família no treino. Frames e configurações não são réplicas independentes; F1 é calculado dentro de cada vídeo e depois recebe peso igual entre vídeos. Esforço desigual e seleção prévia de T218 impedem interpretar este ranking como superioridade universal ou detector final da pipeline. Tempo com imagem em cache não mede a cadeia completa."

    name = "README.md"; text = read(name)
    start, finish = text.index("**Estado em 11/09/2026:**"), text.index("\n\n## Comece por aqui")
    require(start < finish, "README state anchor order differs")
    text = text[:start] + MARKER + "\n**Estado em 11/09/2026:** refinamento das cinco famílias clássicas concluído e\nconferido no treino: 45 configurações, 576 quadros e 25.920 avaliações; dez\nfinalistas seguem para validação completa. Dataset YOLO materializado e\nconferido com 23.316 pares de treino/validação; ainda sem treinamento.\nT218 é referência histórica. A escolha da cadeia de tracking/predição\npermanece posterior às comparações e validações pertinentes." + text[finish:]
    save(name, text)

    name = "docs/metodologia/REFINAMENTO_CLASSICOS_V1.md"; text = read(name)
    block = f"\n\n{MARKER}\n## Resultados do refinamento e conferência — 11/09/2026\n\n" + outcome(name, True) + "\n" + table(rows) + "\n" + interpretation + "\n\n"
    block += "Finalistas para o próximo contrato, preservando todos os parâmetros e a linhagem:\n\n"
    for family in FAMILIES:
        identifiers = [r["configuration_id"] for r in data["finalists"] if r["family"] == family]
        block += f"- {FAMILIES[family][0]}: " + " e ".join(f"`{key}`" for key in identifiers) + ".\n"
    block += "\n" + pending + "\n\nO commit documental posterior não altera o commit do código, os hashes ou os recursos das runs. Os registros prospectivos acima permanecem como histórico do plano executado.\n"
    save(name, text.rstrip() + block)

    name = "docs/metodologia/DATASET_YOLO_V1.md"; text = read(name)
    block = f"\n\n{MARKER}\n## Materialização e conferência concluídas — 11/09/2026\n\n" + dataset_outcome(name, True)
    block += "\nContagens de observações por classe: " + "; ".join(f"classe {key}: {integer(value)}" for key, value in sorted(dataset["summary"]["class_counts"].items())) + ".\n\nO dataset selado não contém pesos nem qualidade de um detector aprendido. O próximo contrato deve fixar arquitetura/pesos, augmentations, seeds, checkpoint, seleção e preservação de scores. Não repetir a materialização concluída nem modificar suas fontes/cópias; caches pertencem apenas ao clone consumidor.\n"
    save(name, text.rstrip() + block)

    name = "docs/projeto/DIARIO.md"; text = read(name)
    block = f"{MARKER}\n## 2026-09-11 — refinamento clássico e dataset YOLO concluídos e conferidos\n\n" + outcome(name) + "\n" + table(rows) + "\n" + interpretation + "\n\n" + dataset_outcome(name) + "\n" + pending + "\n\nCódigo, planos e execuções pertencem a `ca68f16`; o commit documental de fechamento é posterior e não altera essa proveniência. Entradas seguintes registram os marcos anteriores."
    save(name, after_title(text, block))

    name = "docs/projeto/MATRIZ_EXPERIMENTOS.md"; text = read(name)
    block = f"{MARKER}\n## Estado vigente — refinamento clássico e dataset conferidos\n\n" + outcome(name) + "\n" + table(rows) + "\n" + interpretation + "\n\n" + dataset_outcome(name) + "\n" + pending + "\n\nAs tabelas e etapas seguintes preservam os resultados anteriores; suas pendências de busca/refinamento/preparação correspondem ao momento histórico indicado."
    text = once(text, "### Comparação estática concluída e conferida — 11/09/2026", "### Histórico — busca estática concluída e conferida — 11/09/2026")
    save(name, after_title(text, block))

    for family, (label, filename, candidates) in FAMILIES.items():
        name = "docs/algoritmos/deteccao/" + filename; text = read(name)
        row = next(r for r in rows if r["family"] == family)
        selected = [r["configuration_id"] for r in data["finalists"] if r["family"] == family]
        params = json.dumps(row["params"], ensure_ascii=False, sort_keys=True)
        block = f"{MARKER}\n## Refinamento de treino concluído e conferido — 11/09/2026\n\nForam avaliadas {candidates} configurações locais desta família, nos mesmos 576 quadros dos 12 treinos, dentro da bateria completa de 45 configurações em `ca68f16`. Melhor da vizinhança: `{row['configuration_id']}`, F1 macro a 10 px **{number(row['f1'])}**, precisão {number(row['precision'])}, recall {number(row['recall'])}; F1 a 15/20 px {number(row['f1_15px'])}/{number(row['f1_20px'])}. Detecção média em cache: {number(row['detection_ms'], 3)} ms/quadro; {integer(row['n_predictions_ignored'])} previsões ignoradas a 10 px.\n\nParâmetros completos: `{params}`.\n\nFinalistas: `{selected[0]}` e `{selected[1]}`. A paridade dos pais e as métricas passaram no QA independente; a validação comparativa completa ainda precisa de contrato e execução. A diferença local de F1 em relação à melhor da busca anterior foi {number(row['delta_f1'])}; é seleção no mesmo treino, sem confirmação independente, promoção ou demonstração de melhor tracking.\n\n" + md_link(root, name, "docs/metodologia/REFINAMENTO_CLASSICOS_V1.md", "Protocolo, resultados e hashes") + " · " + link(name, "summary_path", "Resumo e valores por vídeo") + ".\n\nA seção da busca abaixo é histórica; os parâmetros e números anteriores foram preservados."
        text = once(text, "## Resultado de treino conferido — 11/09/2026", "## Histórico — resultado da busca de treino — 11/09/2026")
        save(name, after_title(text, block))

    name = "docs/algoritmos/deteccao/yolo.md"; text = read(name)
    block = f"{MARKER}\n## Dataset concluído e conferido — 11/09/2026\n\n" + dataset_outcome(name) + "\n" + md_link(root, name, "docs/metodologia/DATASET_YOLO_V1.md", "Contrato, recursos e hashes do dataset") + ".\n\nA GPU permanece validada sinteticamente; qualidade de treinamento YOLO no protocolo vigente continua pendente. Arquitetura/pesos, receita, checkpoints e seeds devem ser registrados antes do smoke/treino. A infraestrutura e os pilotos descritos abaixo são históricos e não substituem o novo consumidor estrito."
    text = once(text, "## Infraestrutura existente e preparação necessária", "## Infraestrutura histórica e preparação do treinamento")
    save(name, after_title(text, block))

    name = "docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md"; text = read(name)
    block = f"{MARKER}\n## Direção e estado após o refinamento — 11/09/2026\n\n" + outcome(name) + "\n" + dataset_outcome(name) + "\n" + pending + "\n\nNão repetir busca, refinamento, preparação YOLO ou as baterias já conferidas de predição/fluxo. Preservar referências, regras de causalidade e exposição histórica do teste. A numeração do roteiro abaixo é histórica: não torna a ablação requisito anterior obrigatório à comparação dos detectores. Tempo é monitorado sem corte em novos planos, preservando memória, disco e completude."
    text = once(text, "## Direção e estado", "## Histórico — direção e estado antes deste refinamento")
    save(name, after_title(text, block))

    for name in ("docs/projeto/NAVEGACAO.md", "AGENTS.md"):
        text = read(name)
        block = f"{MARKER}\n## Continuidade vigente — refinamento e dataset conferidos em 11/09/2026\n\n" + outcome(name, True) + "\n" + dataset_outcome(name, True) + "\n" + pending + "\n\nNão repetir as baterias concluídas, não reescrever pais/runs ou YAMLs históricos e não entregar o dataset selado diretamente à biblioteca de treinamento. O commit do código/run é `ca68f16`; o commit documental final será registrado no fechamento. HTMLs, guia local, instruções locais e monografia permanecem fora dos commits. Contagens editoriais de figuras/capítulos/laboratórios dependem da revisão própria do relatório e não são atestadas por este registro científico.\n\n" + md_link(root, name, "docs/projeto/NAVEGACAO.md", "Guia permanente, seção 21") + ". Os registros de continuidade abaixo são históricos e conservam suas datas e proveniência."
        old_heading = "## Continuidade vigente — comparação clássica conferida em 11/09/2026"
        text = once(text, old_heading, "## Histórico — comparação clássica conferida em 11/09/2026")
        text = after_title(text, block)
        if name.endswith("NAVEGACAO.md"):
            require(not re.search(r"^## 21\.", text, re.M), "Navigation section21 already exists")
            section = "\n\n## 21. Refinamento clássico e dataset YOLO — entradas e retomada\n\n"
            entries = [
                ("Plano do refinamento", "configs/detection/comparison/classical_refinement_v1.yaml"),
                ("Executor do refinamento", "src/experiments/classical_detection_refinement.py"),
                ("CLI do refinamento", "script/detection/test/refine_classical.py"),
                ("QA independente do refinamento", "script/detection/test/verify_classical_refinement.py"),
                ("Resultados e lógica do refinamento", "docs/metodologia/REFINAMENTO_CLASSICOS_V1.md"),
                ("Manifesto do refinamento", paths["refinement_manifest_path"]),
                ("QA do refinamento", paths["refinement_qa_path"]),
                ("Figura e resumo autenticados", paths["summary_path"]),
                ("Plano do dataset YOLO", "configs/detection/yolo/dataset_v1.yaml"),
                ("Produtor do dataset", "src/detection/yolo_dataset.py"),
                ("CLI de materialização", "script/detection/test/yolo/prepare_dataset.py"),
                ("Manifesto do dataset", paths["dataset_manifest_path"]),
                ("QA independente do dataset", paths["dataset_qa_path"]),
                ("Contrato do dataset e clones consumidores", "docs/metodologia/DATASET_YOLO_V1.md"),
                ("Comandos oficiais", "script/README.md"),
            ]
            section += "| Procurar | Abrir |\n|---|---|\n" + "".join(f"| {label} | {md_link(root, name, target, label)} |\n" for label, target in entries)
            section += "\n" + pending + "\n\nO descriptor e os arquivos selados são somente referência autenticada para criar o clone consumidor. Este marco não treinou YOLO, não executou a validação completa dos novos detectores e não avaliou a hipótese de contribuição do fluxo. A seção 19 conserva a busca anterior; esta seção registra sua continuidade.\n"
            text = text.rstrip() + section
        save(name, text)
    return originals, updates


def apply_updates(root, data, originals, updates):
    """Back up every target first; never overwrite a previous receipt/backup."""
    backup = root / BACKUP
    require(not backup.exists(), "Documentation backup already exists; preserve prior application")
    for name, raw in originals.items():
        require((root / name).read_bytes() == raw, f"Document changed after rendering: {name}")
    # Recheck the two approved QA/manifest links and derived summary immediately
    # before edits. All their constituent bytes were authenticated above.
    for key in ("summary_path", "refinement_manifest_path", "refinement_qa_path", "dataset_manifest_path", "dataset_qa_path"):
        path = data[key]
        require(sha(path) == data["authenticated_files"][path.relative_to(root).as_posix()], "Evidence changed before editing")
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    for name, raw in originals.items():
        target = backup / name; target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        records.append({"path": name, "before_sha256": hashlib.sha256(raw).hexdigest(), "after_sha256": hashlib.sha256(updates[name]).hexdigest(), "backup": target.relative_to(root).as_posix()})
    receipt = {"status": "backed_up_before_first_edit", "created_at": datetime.now(timezone.utc).isoformat(), "run_commit": COMMIT, "documents": records, "evidence": data["authenticated_files"], "html_changed": False, "manuscript_changed": False, "scientific_source_changed": False}
    with (backup / "before_documentation_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
    written = []
    try:
        for name, content in updates.items():
            require((root / name).read_bytes() == originals[name], f"Document changed before write: {name}")
            (root / name).write_bytes(content)
            written.append(name)
        completion = {"status": "applied", "documents": records, "run_commit": COMMIT, "final_documentation_commit": None, "report_editorial_counts_attested": False}
        with (backup / "documentation_applied.json").open("x", encoding="utf-8") as stream:
            json.dump(completion, stream, ensure_ascii=False, indent=2)
    except BaseException as exc:
        with (backup / "documentation_failed.json").open("x", encoding="utf-8") as stream:
            json.dump({"status": "failed", "written": written, "error": f"{type(exc).__name__}: {exc}"}, stream, ensure_ascii=False, indent=2)
        raise
    return backup / "documentation_applied.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / SUMMARY)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-qa", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply only after evidence authentication and exclusive backups")
    args = parser.parse_args(argv)
    data = authenticate(ROOT, args.summary, args.dataset_manifest, args.dataset_qa)
    originals, updates = build_updates(ROOT, data)
    result = {"status": "authenticated_preview", "documents": list(updates), "run_commit": COMMIT, "authenticated_files": len(data["authenticated_files"]), "scientific_source_changed": False, "html_changed": False}
    if args.apply:
        result.update(status="applied", receipt=str(apply_updates(ROOT, data, originals, updates)))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
