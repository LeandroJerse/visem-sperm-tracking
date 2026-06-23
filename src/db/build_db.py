"""Ingest the project's CSVs into a single local SQLite database.

The CSVs remain the source of truth; this builds an analytical copy in
``results/visem.db`` for fast SQL queries and easy browsing (e.g. with
DB Browser for SQLite) and plotting (pandas + seaborn in notebooks).

Tables built:
    detections  -- every detection/manual row (from results/**/<v>_<method>.csv)
    summaries   -- one row per run (from results/**/<v>_<method>_summary.csv)
    clinical    -- per-participant lab data (data/raw/semen_analysis_data.csv)
    counts_gt   -- per-frame ground-truth counts (data/tracked/sperm_counts_per_frame.csv)

Usage:
    python -m src.db.build_db [--db results/visem.db]
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path("results")
RAW_DIR = Path("data/raw")
TRACKED_DIR = Path("data/tracked")
DEFAULT_DB = RESULTS_DIR / "visem.db"

_KNOWN_METHODS = {"threshold", "blob", "bgsub", "watershed", "yolo"}


def _clean_col(name: str) -> str:
    """Snake_case ASCII column name (handles ⁶, accents, spaces, units)."""
    name = name.strip().replace("⁶", "6").replace("²", "2").replace("³", "3")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return name or "col"


def _method_from_stem(stem: str) -> str | None:
    """Detection CSV is ``<video_id>_<method>``; method is the last token."""
    method = stem.rsplit("_", 1)[-1]
    return method if method in _KNOWN_METHODS else None


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


def load_detections(results_dir: Path) -> pd.DataFrame | None:
    files = [
        p for p in results_dir.rglob("*.csv")
        if not p.stem.endswith("_summary") and _method_from_stem(p.stem)
    ]
    frames = []
    for p in files:
        df = pd.read_csv(p)
        df["method"] = _method_from_stem(p.stem)
        df["run"] = _run_label(p, results_dir)
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_summaries(results_dir: Path) -> pd.DataFrame | None:
    files = list(results_dir.rglob("*_summary.csv"))
    frames = []
    for p in files:
        df = pd.read_csv(p)
        df["run"] = _run_label(p, results_dir)
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
    results_dir: Path = RESULTS_DIR,
    raw_dir: Path = RAW_DIR,
    tracked_dir: Path = TRACKED_DIR,
    verbose: bool = True,
) -> dict[str, int]:
    """(Re)build the SQLite database from the CSVs. Returns row counts per table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    loaders = {
        "detections": lambda: load_detections(results_dir),
        "summaries": lambda: load_summaries(results_dir),
        "clinical": lambda: load_clinical(raw_dir),
        "counts_gt": lambda: load_counts_gt(tracked_dir),
    }
    # Build into a fresh temp file, then swap atomically. This way readers of the
    # old .db (e.g. DB Browser) never block the build.
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    counts: dict[str, int] = {}
    with sqlite3.connect(tmp_path, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout=10000")
        for table, loader in loaders.items():
            df = loader()
            if df is None or df.empty:
                if verbose:
                    print(f"  [skip] {table}: nenhum dado encontrado")
                counts[table] = 0
                continue
            df.to_sql(table, conn, if_exists="replace", index=False, chunksize=10_000)
            counts[table] = len(df)
            if verbose:
                print(f"  [ok]   {table}: {len(df)} linhas")
        _create_indexes(conn)

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
    ]
    for s in stmts:
        try:
            conn.execute(s)
        except sqlite3.OperationalError:
            pass  # table may not exist if its CSV was missing


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Ingere os CSVs do projeto em um SQLite local.")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Caminho do .db (default: results/visem.db)")
    p.add_argument("--results-dir", default=str(RESULTS_DIR))
    p.add_argument("--raw-dir", default=str(RAW_DIR))
    p.add_argument("--tracked-dir", default=str(TRACKED_DIR))
    args = p.parse_args(argv)
    print("Construindo banco SQLite...")
    build_database(
        db_path=Path(args.db),
        results_dir=Path(args.results_dir),
        raw_dir=Path(args.raw_dir),
        tracked_dir=Path(args.tracked_dir),
    )


if __name__ == "__main__":
    main()
