from collections import Counter

from ..issue import Issue, Severity


def dataset(ctx):
    out = []
    if ctx.n == 0 or ctx.ncols == 0:
        out.append(Issue("EMPTY_DATAFRAME", Severity.HIGH,
                         f"DataFrame has {ctx.n} rows and {ctx.ncols} columns."))
        return out
    for name, k in Counter(ctx.names).items():
        if k > 1:
            out.append(Issue(
                "DUPLICATE_COLUMN", Severity.HIGH, f"Column name appears {k} times.", column=name,
                suggestion="df = df.loc[:, ~df.columns.duplicated()]  # keeps the first of each name",
                details={"count": k}))
    return out


def column(ctx, i):
    if ctx.n == 0:
        return []
    name, nn = ctx.names[i], ctx.nonnull(i)
    if nn == 0:
        return [Issue("EMPTY_COLUMN", Severity.MEDIUM, "Every value is missing.", column=name,
                      affected_rows=ctx.n, suggestion=f"df = df.drop(columns=[{name!r}])")]
    if ctx.n >= 2 and _is_constant(ctx, i, nn):
        val = ctx.series(i).dropna().iloc[0]
        return [Issue("CONSTANT_COLUMN", Severity.LOW,
                      f"Only one distinct value ({str(val)[:40]!r}); carries no information.",
                      column=name, affected_rows=nn)]
    if ctx.want_info and ctx.n >= 2 and nn == ctx.n and ctx.nunique(i) == nn:
        return [Issue("UNIQUE_COLUMN", Severity.INFO, "100% unique; possible key.", column=name)]
    return []


def _is_constant(ctx, i, nn):
    if ctx.is_text(i) or ctx.family(i) in ("other", "category"):
        return ctx.nunique(i) == 1
    s = ctx.series(i)
    if s.dtype.kind in "iuf":
        arr = s.to_numpy(dtype="float64", na_value=float("nan"))
        valid = arr[~(arr != arr)]
        return bool(len(valid) and valid.min() == valid.max())
    return ctx.nunique(i) == 1
