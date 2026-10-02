from __future__ import annotations

import os
import time
from typing import Dict, List, Union

from ._input import as_frame
from ._profile import Context, estimate_memory
from .issue import Issue, Severity
from .report import Report
from .rules import ALL


def check(df, *, min_severity: Union[str, Severity] = "low") -> Report:
    """Run every health check on ``df`` and return a :class:`Report`.

    The DataFrame is never modified. ``min_severity="info"`` also shows
    informational findings (e.g. unique columns, tiny amounts of missing data).
    """
    t0 = time.perf_counter()
    df = as_frame(df, "check()")
    floor = Severity.parse(min_severity)
    ctx = Context(df, want_info=floor <= Severity.INFO)
    issues: List[Issue] = []
    debug = bool(os.environ.get("BUNU_DEBUG"))

    for mod in ALL:
        label = mod.__name__.rsplit(".", 1)[-1]
        if hasattr(mod, "dataset"):
            _guard(issues, label, None, lambda m=mod: m.dataset(ctx), debug)
        if hasattr(mod, "column"):
            for i in range(ctx.ncols):
                _guard(issues, label, ctx.names[i], lambda m=mod, i=i: m.column(ctx, i), debug)
        if ctx.n == 0:
            break

    status: Dict[str, Severity] = {n: Severity.INFO for n in ctx.names}
    for it in issues:
        if it.column in status and it.severity > status[it.column]:
            status[it.column] = it.severity
    shown = [i for i in issues if i.severity >= floor]
    return Report(shown, ctx.n, ctx.ncols, estimate_memory(df), status, time.perf_counter() - t0)


def _guard(issues, label, column, fn, debug):
    try:
        issues.extend(fn())
    except Exception as exc:  # one odd column must never break the whole check
        if debug:
            raise
        issues.append(Issue("RULE_ERROR", Severity.INFO,
                            f"Check '{label}' was skipped: {type(exc).__name__}: {exc}", column=column))
