from ..issue import Issue, Severity

NULL_TOKENS = frozenset({
    "n/a", "na", "#n/a", "null", "none", "nan", "nil", "-", "--", "?", "missing", "undefined",
})


def column(ctx, i):
    out = []
    name, n = ctx.names[i], ctx.n
    nulls = ctx.nulls(i)
    if n and 0 < nulls < n:  # fully-empty columns are reported as EMPTY_COLUMN
        r = nulls / n
        sev = Severity.HIGH if r >= .5 else Severity.MEDIUM if r >= .2 else Severity.LOW if r >= .01 else Severity.INFO
        out.append(Issue("MISSING_VALUES", sev, f"{r:.1%} of values are missing.",
                         column=name, affected_rows=nulls, details={"ratio": r}))
    si = ctx.strinfo(i)
    if si is None:
        return out
    empty = whitespace = tokens = 0
    found = []
    for v, s, c in zip(si.values, si.stripped, si.counts):
        if v == "":
            empty += int(c)
        else:
            if s == "":
                whitespace += int(c)
            elif s.lower() in NULL_TOKENS:
                tokens += int(c)
                if len(found) < 5 and v not in found:
                    found.append(v)
    f = si.scale
    empty, whitespace, tokens = (int(round(x * f)) for x in (empty, whitespace, tokens))
    col = repr(name)
    if empty:
        out.append(Issue("EMPTY_STRING", Severity.MEDIUM if empty / n >= .01 else Severity.LOW,
                         "Empty strings are not NaN, so isna() and dropna() miss them.",
                         column=name, affected_rows=empty,
                         suggestion=f"df[{col}] = df[{col}].replace('', pd.NA)"))
    if whitespace:
        out.append(Issue("WHITESPACE_ONLY", Severity.MEDIUM if whitespace / n >= .01 else Severity.LOW,
                         "Values contain only whitespace; isna() will not see them.",
                         column=name, affected_rows=whitespace,
                         suggestion=f"df[{col}] = df[{col}].replace(r'^\\s*$', pd.NA, regex=True)"))
    if tokens:
        out.append(Issue("NULL_TOKENS", Severity.MEDIUM,
                         f"Text that looks like missing data ({', '.join(map(repr, found))}).",
                         column=name, affected_rows=tokens, details={"tokens": found},
                         suggestion=f"df[{col}] = df[{col}].replace({found!r}, pd.NA)"))
    return out
