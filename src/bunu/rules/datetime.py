import re
from collections import Counter

from ..issue import Issue, Severity

_DATE = re.compile(
    r"^(\d{1,4})([-/.])(\d{1,2})\2(\d{1,4})"
    r"(?:[T ](\d{1,2}):\d{2}(?::\d{2}(?:\.\d+)?)?(?:\s?[AaPp][Mm])?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)
_ISO_FORMATS = {"YMD": "%Y-%m-%d"}


def _key(s):
    m = _DATE.match(s)
    if not m:
        return None
    a, sep, _, c, hour = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    if len(a) == 4:
        order = "Y-first"
    elif len(c) == 4:
        order = "Y-last"
    else:
        order = "short"
    return f"{order} '{sep}'" + (" +time" if hour is not None else "")


def column(ctx, i):
    if not ctx.is_text(i) or ctx.infer(i) != "string":
        return []
    si = ctx.strinfo(i)
    if si is None:
        return []
    name = ctx.names[i]
    keys = Counter()
    example = {}
    budget = 0.10 * sum(int(c) for s, c in zip(si.stripped, si.counts) if s)  # non-date rows tolerated
    nonblank = misses = 0
    for s, c in zip(si.stripped, si.counts):
        if not s:
            continue
        nonblank += int(c)
        k = _key(s)
        if k:
            keys[k] += int(c)
            example.setdefault(k, s)
        else:
            misses += int(c)
            if misses > budget:
                return []  # exact early exit: can no longer reach 90% date-like
    like = sum(keys.values())
    if not nonblank or like / nonblank < .90:
        return []
    f = si.scale
    detail = {k: int(round(c * f)) for k, c in keys.most_common()}
    if len(keys) == 1:
        (k,) = keys
        fmt = "%Y-%m-%d" if k == "Y-first '-'" else None
        base = f"pd.to_datetime(df[{name!r}]" + (f", format={fmt!r}" if fmt else "") + ", errors='coerce')"
        note = "" if fmt else "  # check day/month order, then add format=..."
        return [Issue("DATETIME_AS_STRING", Severity.MEDIUM, "Values look like dates but are stored as text.",
                      column=name, affected_rows=int(round(like * f)),
                      suggestion=f"df[{name!r}] = {base}{note}", details={"formats": detail})]
    minority = like - max(keys.values())
    desc = ", ".join(f"like {example[k]!r}: {v:,}" for k, v in detail.items())
    return [Issue("DATETIME_MIXED_FORMAT", Severity.HIGH,
                  f"Dates are written in {len(keys)} different formats ({desc}); "
                  "parsing them together can silently swap day and month or produce NaT.",
                  column=name, affected_rows=int(round(minority * f)),
                  suggestion="# parse each format separately with an explicit format=, then combine",
                  details={"formats": detail})]
