"""Snapshot: a tiny statistical fingerprint of a DataFrame (a few KB of JSON).

Store today's snapshot, compare tomorrow's data against it, and never keep the data.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from ._input import as_frame
from ._profile import Context
from ._version import __version__

MAX_CATEGORY_VALUES = 50


@dataclass
class ColumnStats:
    name: str
    dtype: str
    family: str
    nulls: int
    unique: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[Any] = None
    max: Optional[Any] = None
    inf: int = 0
    values: Optional[List[str]] = None


def _num(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


@dataclass
class Snapshot:
    rows: int
    columns: List[ColumnStats] = field(default_factory=list)
    bunu_version: str = __version__

    def to_dict(self) -> Dict[str, Any]:
        return {"bunu_snapshot": 1, "bunu_version": self.bunu_version, "rows": self.rows,
                "columns": [asdict(c) for c in self.columns]}

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Union[str, Path]) -> Path:
        p = Path(path)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Snapshot":
        if not isinstance(d, dict) or "bunu_snapshot" not in d:
            raise ValueError("Not a Bunu snapshot file.")
        return cls(d["rows"], [ColumnStats(**c) for c in d["columns"]], d.get("bunu_version", "?"))

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Snapshot":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def by_name(self) -> Dict[str, ColumnStats]:
        return {c.name: c for c in self.columns}


def _unique_names(names: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}#{seen[n]}")
    return out


def snapshot(df) -> Snapshot:
    """Fingerprint ``df``: per-column dtype, nulls, uniqueness, and basic statistics."""
    df = as_frame(df, "snapshot()")
    ctx = Context(df)
    cols = []
    for i, name in enumerate(_unique_names(ctx.names)):
        s, fam = ctx.series(i), ctx.family(i)
        cs = ColumnStats(name, str(s.dtype), fam, ctx.nulls(i), ctx.nunique(i) if ctx.nonnull(i) else 0)
        if fam in ("int", "float") and s.dtype.kind in "iuf" and ctx.nonnull(i):
            arr = s.to_numpy(dtype="float64", na_value=np.nan)
            fin = arr[np.isfinite(arr)]
            cs.inf = int(np.isinf(arr).sum())
            if len(fin):
                cs.mean, cs.std = _num(fin.mean()), _num(fin.std(ddof=1)) if len(fin) > 1 else 0.0
                cs.min, cs.max = _num(fin.min()), _num(fin.max())
        elif fam == "datetime" and ctx.nonnull(i):
            cs.min, cs.max = str(s.min()), str(s.max())
        elif fam in ("text", "category") and 0 < cs.unique <= MAX_CATEGORY_VALUES:
            if fam == "text":
                vc = ctx.value_counts(i)
                vals = list(vc.values) if vc is not None else None
            else:
                vals = list(s.cat.categories) if hasattr(s, "cat") else None
            if vals is not None:
                cs.values = sorted(str(v) for v in vals)
        cols.append(cs)
    return Snapshot(ctx.n, cols)
