"""Ingest the project's CSVs into a single local SQLite database.

The CSVs remain the source of truth; this builds an analytical copy in
``data/catalog/visem.db`` for fast SQL queries and easy browsing (e.g. with
DB Browser for SQLite) and plotting (pandas + seaborn in notebooks).

Tables built:
    detections  -- legacy detection rows below data/tests/**
    summaries   -- legacy pilot summaries below data/tests/**
    clinical    -- per-participant lab data in data/sources/visem/clinical
    counts_gt   -- ground-truth counts in data/sources/visem_tracking/metadata
    runs         -- immutable-run manifests below data/tests and data/results
    metrics_frame -- long metrics with metric_unit=frame/frame_pair/trajectory_window
    metrics_video -- module-specific metrics, one row per evaluated video
    costs        -- runtime, memory/training and other recorded run costs

Usage:
    python -m script.project.application.build_database [--db data/catalog/visem.db]
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

from src.core.paths import (
    CATALOG_DB,
    DATA_ROOT,
    EXPERIMENT_RESULTS_ROOT,
    EXPERIMENT_TESTS_ROOT,
    VISEM_CLINICAL_ROOT,
    VISEM_TRACKING_METADATA_ROOT,
)

from .run_ingest import load_run_tables

DATA_DIR = DATA_ROOT
TESTS_DIR = EXPERIMENT_TESTS_ROOT
RESULTS_DIR = EXPERIMENT_RESULTS_ROOT
RAW_DIR = VISEM_CLINICAL_ROOT
TRACKED_DIR = VISEM_TRACKING_METADATA_ROOT
DEFAULT_DB = CATALOG_DB

_KNOWN_METHODS = {
    "threshold", "blob", "hybrid_threshold", "bgsub", "mog2", "knn",
    "watershed", "yolo",
}


def _clean_col(name: str) -> str:
    """Snake_case ASCII column name (handles ⁶, accents, spaces, units)."""
    name = name.strip().replace("⁶", "6").replace("²", "2").replace("³", "3")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return name or "col"


def _method_from_stem(stem: str) -> str | None:
    """Resolve ``<video_id>_<method>`` including multi-token method names."""
    for method in sorted(_KNOWN_METHODS, key=len, reverse=True):
        if stem == method or stem.endswith(f"_{method}"):
            return method
    return None


# --------------------------------------------------------------------------- #
# Loaders (each returns a DataFrame or None)
# --------------------------------------------------------------------------- #
def _run_label(path: Path, results_dir: Path) -> str:
    """Identify which run/output folder a CSV came from (to keep repeated
    executions of the same video+method distinct)."""
    parent = path.parent
    try:
        rel = parent.relative_to(results_dir)
    except ValueError:
        rel = parent
    return str(rel).replace("\\", "/") or "."


def load_detections(
    results_dir: Path, *, relative_root: Path | None = None
) -> pd.DataFrame | None:
    files = [
        p for p in results_dir.rglob("*.csv")
        if not p.stem.endswith("_summary") and _method_from_stem(p.stem)
    ]
    frames = []
    for p in files:
        df = pd.read_csv(p)
        df["method"] = _method_from_stem(p.stem)
        df["run"] = _run_label(p, relative_root or results_dir)
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_summaries(
    results_dir: Path, *, relative_root: Path | None = None
) -> pd.DataFrame | None:
    files = list(results_dir.rglob("*_summary.csv"))
    frames = []
    for p in files:
        df = pd.read_csv(p)
        df["run"] = _run_label(p, relative_root or results_dir)
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_clinical(raw_dir: Path) -> pd.DataFrame | None:
    path = raw_dir / "semen_analysis_data.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    df.columns = [_clean_col(c) for c in df.columns]
    return df


def load_counts_gt(tracked_dir: Path) -> pd.DataFrame | None:
    path = tracked_dir / "sperm_counts_per_frame.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [_clean_col(c) for c in df.columns]
    # frame_name like "11_frame_0" -> video_id="11", frame=0
    parts = df["frame_name"].str.extract(r"^(?P<video_id>.+)_frame_(?P<frame>\d+)$")
    df["video_id"] = parts["video_id"]
    df["frame"] = pd.to_numeric(parts["frame"], errors="coerce").astype("Int64")
    return df


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build_database(
    db_path: Path = DEFAULT_DB,
    results_dir: Path | None = None,
    tests_dir: Path = TESTS_DIR,
    final_results_dir: Path = RESULTS_DIR,
    raw_dir: Path = RAW_DIR,
    tracked_dir: Path = TRACKED_DIR,
    verbose: bool = True,
) -> dict[str, int]:
    """Rebuild the analytical copy without scanning source/derived CSVs.

    ``results_dir`` is retained for callers that supply one self-contained
    fixture or historical root. In the official layout it stays ``None`` and
    only ``data/tests`` plus ``data/results`` are searched for experiment
    artifacts; manifests are discovered relative to ``data`` so their paths
    retain the storage class.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if results_dir is not None:
        experiment_root = Path(results_dir)
        artifact_roots = (experiment_root,)
        artifact_relative_root = experiment_root
    else:
        experiment_root = DATA_DIR
        artifact_roots = (Path(tests_dir), Path(final_results_dir))
        artifact_relative_root = DATA_DIR

    run_tables = load_run_tables(experiment_root)

    def load_artifacts(loader):
        frames = [
            frame
            for root in artifact_roots
            if (frame := loader(root, relative_root=artifact_relative_root)) is not None
            and not frame.empty
        ]
        return pd.concat(frames, ignore_index=True, sort=False) if frames else None

    loaders = {
        "detections": lambda: load_artifacts(load_detections),
        "summaries": lambda: load_artifacts(load_summaries),
        "clinical": lambda: load_clinical(raw_dir),
        "counts_gt": lambda: load_counts_gt(tracked_dir),
        "runs": lambda: run_tables["runs"],
        "metrics_frame": lambda: run_tables["metrics_frame"],
        "metrics_video": lambda: run_tables["metrics_video"],
        "costs": lambda: run_tables["costs"],
    }
    # Build into a fresh temp file, then swap atomically. This way readers of the
    # old .db (e.g. DB Browser) never block the build.
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    counts: dict[str, int] = {}
    conn = sqlite3.connect(tmp_path, timeout=10)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        for table, loader in loaders.items():
            df = loader()
            if df is None or df.empty:
                # The run-era tables form a stable public schema and therefore
                # exist even before a module starts producing that artifact.
                if table in run_tables:
                    df.to_sql(table, conn, if_exists="replace", index=False)
                if verbose:
                    print(f"  [skip] {table}: nenhum dado encontrado")
                counts[table] = 0
                continue
            df.to_sql(table, conn, if_exists="replace", index=False, chunksize=10_000)
            counts[table] = len(df)
            if verbose:
                print(f"  [ok]   {table}: {len(df)} linhas")
        _create_indexes(conn)
        conn.commit()
    finally:
        # sqlite3.Connection's context manager commits but does not close.  An
        # explicit close is required before os.replace on Windows.
        conn.close()

    try:
        os.replace(tmp_path, db_path)
    except PermissionError:
        print(
            f"\n[ERRO] Não consegui substituir {db_path} (arquivo em uso).\n"
            f"Feche o DB Browser/visualizador e rode de novo. O banco novo ficou em {tmp_path}."
        )
        return counts
    if verbose:
        print(f"\nBanco gerado em: {db_path}")
    return counts


def _create_indexes(conn: sqlite3.Connection) -> None:
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_det_vfm ON detections(video_id, frame, method, run)",
        "CREATE INDEX IF NOT EXISTS idx_det_source ON detections(source)",
        "CREATE INDEX IF NOT EXISTS idx_counts_vf ON counts_gt(video_id, frame)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_id ON runs(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_runs_mss ON runs(module, method, stage, status)",
        "CREATE INDEX IF NOT EXISTS idx_mframe_rvf ON metrics_frame(run_id, video_id, frame)",
        "CREATE INDEX IF NOT EXISTS idx_mvideo_rv ON metrics_video(run_id, video_id)",
        "CREATE INDEX IF NOT EXISTS idx_costs_run ON costs(run_id)",
    ]
    for s in stmts:
        try:
            conn.execute(s)
        except sqlite3.OperationalError:
            pass  # table may not exist if its CSV was missing


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Ingere os CSVs do projeto em um SQLite local.")
    p.add_argument(
        "--db", default=str(DEFAULT_DB),
        help="Caminho do .db (default: data/catalog/visem.db)",
    )
    p.add_argument(
        "--tests-dir", default=str(TESTS_DIR),
        help="Testes exploratórios e validações (default: data/tests).",
    )
    p.add_argument(
        "--results-dir", dest="final_results_dir", default=str(RESULTS_DIR),
        help="Teste congelado, OOF e aplicação (default: data/results).",
    )
    p.add_argument(
        "--clinical-dir", "--raw-dir", dest="raw_dir", default=str(RAW_DIR),
    )
    p.add_argument(
        "--tracking-metadata-dir", "--tracked-dir", dest="tracked_dir",
        default=str(TRACKED_DIR),
    )
    args = p.parse_args(argv)
    print("Construindo banco SQLite...")
    build_database(
        db_path=Path(args.db),
        tests_dir=Path(args.tests_dir),
        final_results_dir=Path(args.final_results_dir),
        raw_dir=Path(args.raw_dir),
        tracked_dir=Path(args.tracked_dir),
    )


if __name__ == "__main__":
    main()
