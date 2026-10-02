import json
import os
from pathlib import Path

import pandas as pd

from .snapshot import Snapshot


def _is_url(path) -> bool:
    return "://" in str(path)


def _ext(path) -> str:
    return os.path.splitext(str(path).split("?")[0])[1].lower()


def read_table(path) -> pd.DataFrame:
    """Read a data file. Remote URLs (hdfs://, s3://, gs://, abfs://, ...) go straight to
    pandas, which needs the matching fsspec/pyarrow filesystem installed."""
    p = str(path)  # never wrap URLs in pathlib: it would turn 'hdfs://x' into 'hdfs:/x'
    ext = _ext(p)
    if ext in (".csv", ".txt", ".gz", ".bz2", ".zip"):
        return pd.read_csv(p)
    if ext in (".tsv", ".tab"):
        return pd.read_csv(p, sep="\t")
    if ext in (".parquet", ".pq"):
        return pd.read_parquet(p)
    if ext in (".jsonl", ".ndjson"):
        return pd.read_json(p, lines=True)
    if ext == ".json":
        return pd.read_json(p)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p)
    raise ValueError(f"Unsupported file type {ext!r}. Use csv, tsv, parquet, json, jsonl or xlsx.")


def load_snapshot_or_frame(path):
    if not _is_url(path) and _ext(path) == ".json":
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(d, dict) and "bunu_snapshot" in d:
                return Snapshot.from_dict(d)
        except (ValueError, OSError):
            pass
    return read_table(path)
