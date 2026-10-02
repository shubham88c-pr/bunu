from __future__ import annotations

from typing import Dict

from ._input import as_frame
from .check import check
from .issue import Severity
from .report import Report, _RULE, _fmt_int


class Explanation:
    def __init__(self, report: Report):
        self.report = report
        st = report.column_status
        self.healthy = [c for c, s in st.items() if s < Severity.LOW]
        self.attention = [c for c, s in st.items() if Severity.LOW <= s < Severity.HIGH]
        self.suspicious = [c for c, s in st.items() if s >= Severity.HIGH]

    def to_dict(self) -> Dict:
        return {"healthy": self.healthy, "needs_attention": self.attention,
                "suspicious": self.suspicious, "top_issues": [i.to_dict() for i in self.report.issues[:5]]}

    def __str__(self) -> str:
        r = self.report
        lines = ["DataFrame", _RULE, f"{_fmt_int(r.rows)} rows x {r.n_columns} columns", "",
                 f"Healthy          {len(self.healthy):>4} column(s)",
                 f"Needs attention  {len(self.attention):>4} column(s)",
                 f"Suspicious       {len(self.suspicious):>4} column(s)", ""]
        top = r.issues[:5]
        if not top:
            lines.append("Nothing suspicious found. This DataFrame looks trustworthy.")
        else:
            lines.append("Most important")
            for k, i in enumerate(top, 1):
                where = f"{i.column}: " if i.column else ""
                lines.append(f"  {k}. [{i.severity.label.upper()}] {where}{i.message}")
            first = next((i for i in r.issues if i.suggestion), None)
            if first:
                lines += ["", "Suggested next step (not applied)", f"  {first.suggestion}"]
        lines += [_RULE, "Bunu never modifies your data."]
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self) -> str:
        import html
        return ("<pre style='font-family:ui-monospace,monospace;font-size:12.5px;line-height:1.45'>"
                + html.escape(str(self)) + "</pre>")


def explain(df_or_report) -> Explanation:
    """A short, human summary: which columns are fine, which are not, what to do first."""
    rep = df_or_report if isinstance(df_or_report, Report) else check(as_frame(df_or_report, "explain()"))
    return Explanation(rep)
