import re
from collections import Counter

import numpy as np
import pandas as pd

from ..issue import Issue, Severity

_ID_LIKE = re.compile(r"(^|[_\s-])(id|uuid|zip|zipcode|pin|pincode|phone|mobile|sku|ssn|code)$", re.I)
_LEADING_ZERO = re.compile(r"^[-+]?0\d")


def _group(v):
    if isinstance(v, (bool, np.bool_)):
        return "bool"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return "number"
    if isinstance(v, str):
        return "str"
    return type(v).__name__


def column(ctx, i):
    if not ctx.is_text(i) or ctx.nonnull(i) == 0:
        return []
    kind = ctx.infer(i)
    name = ctx.names[i]
    if kind.startswith("mixed"):
        return _mixed(ctx, i, name)
    if kind == "string":
        return _numeric_as_string(ctx, i, name)
    return []


def _mixed(ctx, i, name):
    vc = ctx.value_counts(i)
    pairs = zip(vc.values, vc.counts) if vc is not None else ((v, 1) for v in ctx.series(i).dropna())
    groups = Counter()
    for v, c in pairs:
        groups[_group(v)] += int(c)
    if len(groups) < 2:
        return []
    total = sum(groups.values())
    major = max(groups.values())
    desc = ", ".join(f"{g} ({c:,})" for g, c in groups.most_common())
    sugg = None
    if set(groups) == {"number", "str"}:
        sugg = (f"df[{name!r}] = pd.to_numeric(df[{name!r}], errors='coerce')"
                "  # non-numeric values become NaN; inspect them first")
    return [Issue("MIXED_TYPE", Severity.MEDIUM, f"Column mixes types: {desc}.", column=name,
                  affected_rows=total - major, suggestion=sugg, details={"types": dict(groups)})]


def _numeric_as_string(ctx, i, name):
    if _ID_LIKE.search(name):
        return []
    si = ctx.strinfo(i)
    if si is None:
        return []
    stripped = si.stripped
    nonblank = np.array([s != "" for s in stripped])
    if not nonblank.any():
        return []
    sub = [s for s, k in zip(stripped, nonblank) if k]
    parsed = pd.to_numeric(pd.Series(sub, dtype=object), errors="coerce").notna().to_numpy()
    cnt = si.counts[nonblank]
    total = float(cnt.sum())
    ok = float(cnt[parsed].sum())
    if total == 0 or ok / total < .95:
        return []
    if any(_LEADING_ZERO.match(s) and len(s) > 1 and s.lstrip("+-")[:2] != "0." for s, p in zip(sub, parsed) if p):
        return []  # '00123' is an identifier, not a number
    bad = [s for s, p in zip(sub, parsed) if not p]
    bad_rows = int(round((total - ok) * si.scale))
    ok_rows = int(round(ok * si.scale))
    if bad:
        msg = (f"{ok / total:.1%} of values are numbers stored as text; "
               f"{bad_rows:,} are not numeric (e.g. {', '.join(repr(b) for b in bad[:3])}).")
    else:
        msg = "Every non-blank value is a number stored as text."
    note = f"  # {bad_rows:,} value(s) will become NaN" if bad else ""
    return [Issue("NUMERIC_AS_STRING", Severity.MEDIUM, msg, column=name, affected_rows=ok_rows,
                  suggestion=f"df[{name!r}] = pd.to_numeric(df[{name!r}], errors='coerce'){note}",
                  details={"non_numeric_rows": bad_rows, "examples": bad[:5]})]
