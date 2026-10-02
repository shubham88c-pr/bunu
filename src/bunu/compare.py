from __future__ import annotations

import time
from pathlib import Path
from typing import List, Union

from ._input import as_frame
from .issue import Issue, Severity
from .report import Comparison
from .snapshot import ColumnStats, Snapshot, snapshot

_NUM = ("int", "float")


def _resolve(x, which) -> Snapshot:
    if isinstance(x, Snapshot):
        return x
    if isinstance(x, (str, Path)):
        from ._io import load_snapshot_or_frame
        x = load_snapshot_or_frame(x)
        if isinstance(x, Snapshot):
            return x
    return snapshot(as_frame(x, f"the {which} dataset"))


def compare(old, new, *, min_severity: Union[str, Severity] = "low") -> Comparison:
    """Explain what changed between two versions of a dataset.

    ``old`` / ``new`` may be DataFrames, :class:`Snapshot` objects, or paths to a
    data file / snapshot JSON. Neither input is modified.
    """
    t0 = time.perf_counter()
    a, b = _resolve(old, "old"), _resolve(new, "new")
    floor = Severity.parse(min_severity)
    A, B = a.by_name, b.by_name
    added = [n for n in B if n not in A]
    removed = [n for n in A if n not in B]
    out: List[Issue] = []

    for n in removed:
        out.append(Issue("SCHEMA_COLUMN_REMOVED", Severity.HIGH, "Column disappeared.", column=n))
    for n in added:
        out.append(Issue("SCHEMA_COLUMN_ADDED", Severity.MEDIUM, "New column appeared.", column=n))
    out += _rows(a.rows, b.rows)
    for n in A:
        if n in B:
            out += _column(A[n], B[n], a.rows, b.rows)
    shown = [i for i in out if i.severity >= floor]
    return Comparison(shown, a.rows, b.rows, added, removed, time.perf_counter() - t0)


def _rows(o, n):
    if o == n:
        return []
    if o == 0:
        return [Issue("ROW_COUNT_CHANGED", Severity.HIGH, f"Rows went from 0 to {n:,}.")]
    pct = (n - o) / o
    a = abs(pct)
    sev = Severity.HIGH if a >= .5 else Severity.MEDIUM if a >= .2 else Severity.LOW if a >= .05 else Severity.INFO
    return [Issue("ROW_COUNT_CHANGED", sev, f"Rows changed by {pct:+.1%} ({o:,} -> {n:,}).",
                  affected_rows=abs(n - o))]


def _column(o: ColumnStats, n: ColumnStats, orows: int, nrows: int):
    out, name = [], o.name
    if o.family != n.family:
        sev = Severity.MEDIUM if {o.family, n.family} == {"int", "float"} else Severity.HIGH
        out.append(Issue("DTYPE_CHANGED", sev, f"Type changed: {o.dtype} -> {n.dtype}.", column=name))
    elif o.dtype != n.dtype and o.family != "text":
        out.append(Issue("DTYPE_CHANGED", Severity.LOW, f"Type width changed: {o.dtype} -> {n.dtype}.", column=name))

    # missingness
    orate = o.nulls / orows if orows else 0.0
    nrate = n.nulls / nrows if nrows else 0.0
    d = nrate - orate
    if d >= .01:
        sev = Severity.HIGH if d >= .20 else Severity.MEDIUM if d >= .05 else Severity.LOW
    elif d <= -.05:
        sev = Severity.LOW
    else:
        sev = None
    if sev is not None:
        out.append(Issue("NULL_RATE_CHANGED", sev,
                         f"Missing values: {orate:.1%} -> {nrate:.1%}.", column=name,
                         details={"old": orate, "new": nrate}))

    # keys that lost uniqueness
    on, nn = orows - o.nulls, nrows - n.nulls
    if on > 1 and o.unique == on and nn > 0 and n.unique < nn:
        out.append(Issue("DUPLICATES_GAINED", Severity.HIGH,
                         f"Was 100% unique, now has {nn - n.unique:,} duplicate value(s).",
                         column=name, affected_rows=nn - n.unique))

    # cardinality of categorical-like columns
    if o.family in ("text", "category") and n.family in ("text", "category") and o.unique and n.unique:
        change = (n.unique - o.unique) / o.unique
        if abs(n.unique - o.unique) >= 5 and abs(change) >= .5 and not (on > 1 and o.unique == on):
            out.append(Issue("CARDINALITY_CHANGED", Severity.MEDIUM if abs(change) >= 2 else Severity.LOW,
                             f"Distinct values: {o.unique:,} -> {n.unique:,}.", column=name))
    if o.values is not None and n.values is not None:
        new_v, gone = sorted(set(n.values) - set(o.values)), sorted(set(o.values) - set(n.values))
        if new_v:
            out.append(Issue("NEW_CATEGORIES", Severity.LOW,
                             f"{len(new_v)} new value(s): {', '.join(map(repr, new_v[:5]))}"
                             + (" ..." if len(new_v) > 5 else ""), column=name, details={"values": new_v}))
        if gone:
            out.append(Issue("CATEGORIES_GONE", Severity.LOW,
                             f"{len(gone)} value(s) no longer present: {', '.join(map(repr, gone[:5]))}"
                             + (" ..." if len(gone) > 5 else ""), column=name, details={"values": gone}))

    # numeric drift
    if o.family in _NUM and n.family in _NUM:
        if n.inf > 0 and o.inf == 0:
            out.append(Issue("INFINITE_VALUES", Severity.HIGH, f"{n.inf:,} infinite value(s) appeared.",
                             column=name, affected_rows=n.inf))
        if None not in (o.mean, n.mean, o.std):
            if o.std and o.std > 0:
                z = abs(n.mean - o.mean) / o.std
                if z >= .5:
                    sev = Severity.HIGH if z >= 3 else Severity.MEDIUM if z >= 1 else Severity.LOW
                    out.append(Issue("MEAN_SHIFT", sev,
                                     f"Mean moved {o.mean:.4g} -> {n.mean:.4g} ({z:.1f} old std devs).",
                                     column=name, details={"z": z}))
            elif n.mean != o.mean:
                out.append(Issue("MEAN_SHIFT", Severity.MEDIUM,
                                 f"Mean moved {o.mean:.4g} -> {n.mean:.4g} (old data was constant).", column=name))
    return out
