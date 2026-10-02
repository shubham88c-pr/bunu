import re

from ..issue import Issue, Severity

_ID_NAME = re.compile(r"(^|[_\s-])(id|uuid|guid|email|key|pk)$|^(id|uuid|guid)([_\s-]|$)", re.I)


def dataset(ctx):
    n = ctx.n
    if n < 2 or ctx.ncols == 0:
        return []
    usable = []
    for i in range(ctx.ncols):
        if ctx.is_text(i) and ctx.value_counts(i) is None:
            continue  # unhashable values
        usable.append(i)
        if ctx.nulls(i) == 0 and ctx.nunique(i) == n:
            return []  # a fully unique column means no two rows can be identical
    if not usable:
        return []
    k = int(ctx.df.iloc[:, usable].duplicated().sum())
    if not k:
        return []
    r = k / n
    return [Issue("DUPLICATE_ROWS", Severity.HIGH if r >= .10 else Severity.MEDIUM,
                  f"{r:.1%} of rows repeat an earlier row exactly.", affected_rows=k,
                  suggestion="df = df.drop_duplicates()  # review first with df[df.duplicated(keep=False)]")]


def column(ctx, i):
    n, nn = ctx.n, ctx.nonnull(i)
    fam = ctx.family(i)
    if nn < 2 or fam not in ("text", "int", "other", "category"):
        return []
    name = ctx.names[i]
    looks_id = bool(_ID_NAME.search(name))
    if fam == "int" and nn > 50_000 and not looks_id:
        head = ctx.series(i).iloc[:50_000]
        if head.nunique() < 0.98 * len(head):  # cannot be >=99% unique overall
            return []
    extra = nn - ctx.nunique(i)
    if extra <= 0:
        return []
    ratio = ctx.nunique(i) / nn
    if looks_id and ratio >= .90:
        sev = Severity.HIGH
    elif not looks_id and ratio >= .99 and n >= 100:
        sev = Severity.MEDIUM
    else:
        return []
    return [Issue("DUPLICATE_KEY", sev,
                  f"{ratio:.1%} unique, but {extra:,} value(s) repeat; expected to be a unique key.",
                  column=name, affected_rows=extra, details={"unique_ratio": ratio})]
