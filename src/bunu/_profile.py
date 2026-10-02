"""Shared, lazily-computed facts about a DataFrame.

Every rule asks this object instead of re-scanning the data, so each column's
null mask, value counts and dtype inference are computed at most once.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional

import numpy as np
import pandas as pd
from pandas.api import types as pdt

UNIQUE_SAMPLE_LIMIT = 200_000  # max distinct strings analysed per column


def family(dtype: Any) -> str:
    """Coarse dtype family, stable across pandas versions (object == str == 'text')."""
    if pdt.is_bool_dtype(dtype):
        return "bool"
    if pdt.is_integer_dtype(dtype):
        return "int"
    if pdt.is_float_dtype(dtype):
        return "float"
    if pdt.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pdt.is_timedelta64_dtype(dtype):
        return "timedelta"
    if isinstance(dtype, pd.CategoricalDtype):
        return "category"
    if pdt.is_string_dtype(dtype):
        return "text"
    return "other"


class VC(NamedTuple):
    """Distinct non-null values with exact row counts (a faster, leaner value_counts)."""
    values: np.ndarray   # object array of distinct values
    counts: np.ndarray   # rows per value
    nulls: int

    def __len__(self):
        return len(self.values)


@dataclass
class StrInfo:
    values: List[str]      # distinct string values (possibly a sample)
    counts: np.ndarray     # rows per value
    scale: float           # multiply sampled row counts by this to estimate full counts
    total_rows: int        # non-null string rows in the full column
    sampled: bool

    @property
    def stripped(self) -> List[str]:
        if "s" not in self.__dict__:
            self.__dict__["s"] = [v.strip() for v in self.values]
        return self.__dict__["s"]

    @property
    def folded(self) -> List[str]:
        if "f" not in self.__dict__:
            self.__dict__["f"] = [s.casefold() for s in self.stripped]
        return self.__dict__["f"]

    def rows(self, mask) -> int:
        return int(round(float(self.counts[np.asarray(mask, dtype=bool)].sum()) * self.scale))


class Context:
    def __init__(self, df: pd.DataFrame, want_info: bool = False):
        self.df = df
        self.want_info = want_info  # compute INFO-only findings (costs extra scans)
        self.n = len(df)
        self.ncols = df.shape[1]
        self.names: List[str] = [str(c) for c in df.columns]
        self._series: Dict[int, pd.Series] = {}
        self._cache: Dict[Any, Any] = {}

    def _memo(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def series(self, i: int) -> pd.Series:
        if i not in self._series:
            self._series[i] = self.df.iloc[:, i]
        return self._series[i]

    def family(self, i: int) -> str:
        return family(self.series(i).dtype)

    def is_text(self, i: int) -> bool:
        return self.family(i) == "text"

    def nulls(self, i: int) -> int:
        if self.is_text(i):
            vc = self.value_counts(i)
            if vc is not None:
                return vc.nulls
        return self._memo(("nulls", i), lambda: int(self.series(i).isna().sum()))

    def nonnull(self, i: int) -> int:
        return self.n - self.nulls(i)

    def infer(self, i: int) -> str:
        return self._memo(("infer", i), lambda: pd.api.types.infer_dtype(self.series(i), skipna=True))

    def value_counts(self, i: int) -> Optional[VC]:
        """Exact counts of distinct non-null values; None if values are unhashable."""
        def compute():
            try:
                codes, uniq = pd.factorize(self.series(i))
            except TypeError:
                return None
            neg = codes < 0
            nulls = int(neg.sum())
            counts = np.bincount(codes[~neg] if nulls else codes, minlength=len(uniq))
            return VC(np.asarray(uniq, dtype=object), counts, nulls)
        return self._memo(("vc", i), compute)

    def nunique(self, i: int) -> int:
        def compute():
            s = self.series(i)
            if self.family(i) in ("text", "other"):
                vc = self.value_counts(i)
                if vc is not None:
                    return len(vc)
                return int(s.dropna().astype(str).nunique())
            return int(s.nunique(dropna=True))
        return self._memo(("nunique", i), compute)

    def strinfo(self, i: int) -> Optional[StrInfo]:
        """Distinct *string* values with row counts; shared by all string rules."""
        def compute():
            if not self.is_text(i):
                return None
            vc = self.value_counts(i)
            if vc is None:
                return None
            idx, cnt = vc.values, vc.counts
            if self.infer(i) != "string":
                keep = np.fromiter((isinstance(v, str) for v in idx), dtype=bool, count=len(idx))
                idx, cnt = idx[keep], cnt[keep]
            total = int(cnt.sum())
            if total == 0:
                return None
            values = idx.tolist()
            sampled = False
            if len(values) > UNIQUE_SAMPLE_LIMIT:
                pick = np.sort(np.random.default_rng(0).choice(len(values), UNIQUE_SAMPLE_LIMIT, replace=False))
                values = [values[j] for j in pick]
                cnt = cnt[pick]
                sampled = True
            seen = int(cnt.sum())
            return StrInfo(values, cnt, total / seen if seen else 1.0, total, sampled)
        return self._memo(("strinfo", i), compute)


def estimate_memory(df: pd.DataFrame, sample_rows: int = 10_000) -> float:
    """Fast memory estimate: exact for numeric columns, sampled for object columns."""
    base = df.memory_usage(index=True, deep=False)
    total = float(base.sum())
    n = len(df)
    for i in range(df.shape[1]):
        dt = df.dtypes.iloc[i]
        if family(dt) in ("text", "other") and n:
            s = df.iloc[:, i]
            if n <= sample_rows:
                deep = float(s.memory_usage(index=False, deep=True))
            else:
                deep = float(s.iloc[:: max(1, n // sample_rows)].memory_usage(index=False, deep=True)) \
                    * (n / len(s.iloc[:: max(1, n // sample_rows)]))
            total += deep - float(s.memory_usage(index=False, deep=False))
    return total
