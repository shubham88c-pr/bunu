import numpy as np

from ..issue import Issue, Severity

_SAMPLE = 500_000


def column(ctx, i):
    s = ctx.series(i)
    if ctx.family(i) not in ("int", "float") or s.dtype.kind not in "iuf" or ctx.nonnull(i) == 0:
        return []
    name, out = ctx.names[i], []
    arr = s.to_numpy(dtype="float64", na_value=np.nan)
    finite = np.isfinite(arr)
    if s.dtype.kind == "f":
        inf = int(np.isinf(arr).sum())
        if inf:
            out.append(Issue("INFINITE_VALUES", Severity.HIGH,
                             "Contains inf / -inf, which break means, scalers and models.",
                             column=name, affected_rows=inf,
                             suggestion=f"df[{name!r}] = df[{name!r}].replace([float('inf'), float('-inf')], float('nan'))"))
    vals = arr[finite]
    if len(vals) >= 30:
        base = vals
        if len(vals) > _SAMPLE:
            base = vals[np.random.default_rng(0).choice(len(vals), _SAMPLE, replace=False)]
        q1, q3 = np.quantile(base, [.25, .75])
        iqr = q3 - q1
        if iqr > 0:
            lo, hi = q1 - 5 * iqr, q3 + 5 * iqr
            k = int(((vals < lo) | (vals > hi)).sum())
            if 0 < k <= len(vals) * .05:
                out.append(Issue("EXTREME_VALUES", Severity.LOW,
                                 f"{k:,} value(s) lie more than 5 IQR outside the middle 50% "
                                 f"(normal range ~ {lo:.4g} to {hi:.4g}).",
                                 column=name, affected_rows=k,
                                 details={"lower": float(lo), "upper": float(hi)}))
    return out
