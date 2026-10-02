from collections import defaultdict

import numpy as np

from ..issue import Issue, Severity


def column(ctx, i):
    si = ctx.strinfo(i)
    if si is None:
        return []
    out = []
    name, col = ctx.names[i], repr(ctx.names[i])
    values, counts = si.values, si.counts
    stripped = si.stripped
    padded = np.fromiter((v is not s and v != s and s != "" for v, s in zip(values, stripped)),
                         dtype=bool, count=len(values))
    if padded.any():
        out.append(Issue("WHITESPACE_PADDED", Severity.LOW,
                         "Values have leading or trailing spaces.", column=name,
                         affected_rows=si.rows(padded),
                         suggestion=f"df[{col}] = df[{col}].str.strip()"))
    folded = si.folded
    nonblank = sum(1 for s in stripped if s)
    var_groups = []
    if len(set(folded)) - (1 if nonblank < len(folded) else 0) < nonblank:  # some values collide
        groups = defaultdict(list)
        for j, s in enumerate(stripped):
            if s:
                groups[folded[j]].append(j)
        var_groups = [g for g in groups.values() if len(g) > 1]
    if var_groups:
        minority = np.zeros(len(values), dtype=bool)
        examples = []
        for g in var_groups:
            top = max(g, key=lambda j: counts[j])
            for j in g:
                if j != top:
                    minority[j] = True
            if len(examples) < 3:
                examples.append(" / ".join(repr(values[j]) for j in g[:3]))
        out.append(Issue(
            "CASE_VARIANTS", Severity.LOW,
            f"{len(var_groups)} value(s) appear in several spellings that differ only by case "
            f"or spaces, e.g. {'; '.join(examples)}. Nothing was changed.",
            column=name, affected_rows=si.rows(minority),
            suggestion=f"df[{col}] = df[{col}].str.strip().str.casefold()  # only if these really mean the same thing",
            details={"groups": len(var_groups)}))
    nn, nu = si.total_rows, len(values)
    if 2 <= nu <= 50 and nn >= 200 and not si.sampled:
        rare = counts <= max(1, int(nn * .001))
        if rare.any() and (~rare).sum() >= 2 and counts[rare].sum() <= nn * .01:
            ex = [values[j] for j in np.flatnonzero(rare)[:3]]
            out.append(Issue(
                "RARE_CATEGORY", Severity.LOW,
                f"{int(rare.sum())} rare value(s) in a column with {int((~rare).sum())} common ones "
                f"(e.g. {', '.join(map(repr, ex))}); possible typos.",
                column=name, affected_rows=int(counts[rare].sum()), details={"examples": ex}))
    return out
