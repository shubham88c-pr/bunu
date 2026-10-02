"""Report objects. Plain ASCII output so it never breaks on any terminal or log."""
from __future__ import annotations

import html as _html
import json
from typing import Any, Dict, Iterable, List, Optional, Union

from .issue import Issue, Severity

_RULE = "-" * 60


def _fmt_int(n: Optional[int]) -> str:
    return "-" if n is None else f"{n:,}"


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class DataQualityError(ValueError):
    """Raised by ``report.raise_if(...)`` so pipelines can stop on bad data."""

    def __init__(self, report: "_IssueReport", threshold: Severity):
        self.report = report
        self.threshold = threshold
        found = [i for i in report.issues if i.severity >= threshold]
        lines = [f"Bunu found {len(found)} issue(s) at or above '{threshold.label}':"]
        for i in found[:10]:
            where = f"[{i.column}] " if i.column else ""
            lines.append(f"  - {i.severity.label.upper()} {i.code} {where}{i.message}")
        if len(found) > 10:
            lines.append(f"  ... and {len(found) - 10} more")
        super().__init__("\n".join(lines))


class _IssueReport:
    title = "Bunu Report"

    def __init__(self, issues: Iterable[Issue], duration: float = 0.0):
        self.issues: List[Issue] = sorted(
            issues, key=lambda i: (-int(i.severity), i.column or "", i.code)
        )
        self.duration = duration  # seconds

    # ---- querying -------------------------------------------------------
    @property
    def errors(self) -> List[Issue]:
        """Issues with HIGH severity."""
        return [i for i in self.issues if i.severity == Severity.HIGH]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == Severity.HIGH for i in self.issues)

    @property
    def ok(self) -> bool:
        """True when nothing at LOW severity or above was found."""
        return not any(i.severity >= Severity.LOW for i in self.issues)

    @property
    def suggestions(self) -> List[str]:
        """Proposed pandas code. Bunu never runs these for you."""
        return [i.suggestion for i in self.issues if i.suggestion]

    def has(self, code: str, column: Optional[str] = None) -> bool:
        return any(i.code == code and (column is None or i.column == column) for i in self.issues)

    def get(self, code: Optional[str] = None, column: Optional[str] = None,
            min_severity: Union[str, Severity] = Severity.INFO) -> List[Issue]:
        floor = Severity.parse(min_severity)
        return [
            i for i in self.issues
            if (code is None or i.code == code)
            and (column is None or i.column == column)
            and i.severity >= floor
        ]

    def raise_if(self, severity: Union[str, Severity] = "high") -> "_IssueReport":
        """Raise DataQualityError if any issue is at or above ``severity``."""
        floor = Severity.parse(severity)
        if any(i.severity >= floor for i in self.issues):
            raise DataQualityError(self, floor)
        return self

    # ---- export ---------------------------------------------------------
    def _meta(self) -> Dict[str, Any]:
        return {}

    def to_dict(self) -> Dict[str, Any]:
        d = {"kind": self.title, "duration_ms": round(self.duration * 1000, 2)}
        d.update(self._meta())
        d["issues"] = [i.to_dict() for i in self.issues]
        return d

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    # ---- display --------------------------------------------------------
    def _header_lines(self) -> List[str]:
        return []

    def _issue_lines(self) -> List[str]:
        if not self.issues:
            return ["No issues found."]
        out = [f"{len(self.issues)} issue(s) found", ""]
        current = None
        for i in self.issues:
            if i.severity != current:
                current = i.severity
                out.append(current.label.upper())
            head = f"  {i.column}" if i.column else "  (dataset)"
            out.append(f"{head}  [{i.code}]")
            tail = i.message
            if i.affected_rows is not None:
                tail += f" ({_fmt_int(i.affected_rows)} row{'' if i.affected_rows == 1 else 's'})"
            out.append(f"  `- {tail}")
        return out

    def __str__(self) -> str:
        lines = [self.title, _RULE, *self._header_lines(), *([""] if self._header_lines() else []),
                 *self._issue_lines(), _RULE, f"Time: {self.duration * 1000:.0f} ms"]
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_html_(self) -> str:
        e = _html.escape
        colors = {Severity.HIGH: "#d32f2f", Severity.MEDIUM: "#e67e00",
                  Severity.LOW: "#a38800", Severity.INFO: "#607d8b"}
        counts = {s: sum(1 for i in self.issues if i.severity == s) for s in colors}
        badge = ("display:inline-block;padding:1px 8px;border-radius:10px;color:#fff;"
                 "font-size:11px;font-weight:600;letter-spacing:.3px;background:")
        head = "".join(f"<span style='margin-right:14px'>{e(line)}</span>" for line in self._header_lines())
        pills = "".join(f"<span style='{badge}{colors[s]};margin-right:6px'>{n} {s.label.upper()}</span>"
                        for s, n in counts.items() if n)
        if not self.issues:
            pills = f"<span style='{badge}#2e7d32'>ALL CLEAR</span>"
        rows = []
        for i in self.issues:
            msg = e(i.message) + (f" <b>({i.affected_rows:,})</b>" if i.affected_rows is not None else "")
            fix = (f"<details style='margin-top:3px'><summary style='cursor:pointer;opacity:.7'>"
                   f"suggested fix (not applied)</summary><pre style='margin:4px 0;white-space:pre-wrap'>"
                   f"{e(i.suggestion)}</pre></details>") if i.suggestion else ""
            rows.append(
                f"<tr style='border-top:1px solid rgba(128,128,128,.25)'>"
                f"<td style='padding:6px 8px;vertical-align:top'><span style='{badge}{colors[i.severity]}'>"
                f"{i.severity.label.upper()}</span></td>"
                f"<td style='padding:6px 8px;vertical-align:top'><b>{e(i.column) if i.column else '(dataset)'}</b>"
                f"<div style='opacity:.6;font-size:11px'>{e(i.code)}</div></td>"
                f"<td style='padding:6px 8px;vertical-align:top'>{msg}{fix}</td></tr>")
        table = (f"<table style='border-collapse:collapse;width:100%;text-align:left;margin-top:8px'>"
                 f"{''.join(rows)}</table>") if rows else ""
        return (f"<div style='font-family:system-ui,sans-serif;font-size:13px;border:1px solid rgba(128,128,128,.35);"
                f"border-radius:8px;padding:12px 14px;max-width:960px'>"
                f"<div style='font-size:15px;font-weight:700;margin-bottom:6px'>&#128054; {e(self.title)}</div>"
                f"<div style='opacity:.8;margin-bottom:8px'>{head}</div><div>{pills}</div>{table}"
                f"<div style='opacity:.55;font-size:11px;margin-top:8px'>{self.duration * 1000:.0f} ms &middot; "
                f"Bunu never modifies your data.</div></div>")

    def __len__(self) -> int:
        return len(self.issues)

    def __iter__(self):
        return iter(self.issues)


class Report(_IssueReport):
    """Result of :func:`bunu.check`."""

    title = "Bunu Data Check"

    def __init__(self, issues, rows: int, columns: int, memory_bytes: float,
                 column_status: Dict[str, Severity], duration: float = 0.0):
        super().__init__(issues, duration)
        self.rows = rows
        self.n_columns = columns
        self.memory_bytes = memory_bytes
        self.column_status = column_status

    @property
    def summary(self) -> Dict[str, Any]:
        counts = {s.label: 0 for s in sorted(Severity, reverse=True)}
        for i in self.issues:
            counts[i.severity.label] += 1
        return {
            "rows": self.rows, "columns": self.n_columns,
            "memory_bytes": int(self.memory_bytes), "issues": len(self.issues),
            "by_severity": counts, "duration_ms": round(self.duration * 1000, 2),
        }

    @property
    def columns(self) -> Dict[str, str]:
        """Worst severity seen per column ('ok' if clean)."""
        return {c: (s.label if s >= Severity.LOW else "ok") for c, s in self.column_status.items()}

    def _meta(self):
        return {"rows": self.rows, "columns": self.n_columns,
                "memory_bytes": int(self.memory_bytes)}

    def _header_lines(self):
        return [f"Rows     {_fmt_int(self.rows)}", f"Columns  {self.n_columns}",
                f"Memory   {_fmt_bytes(self.memory_bytes)}"]


class Comparison(_IssueReport):
    """Result of :func:`bunu.compare`."""

    title = "Bunu Dataset Comparison"

    def __init__(self, issues, old_rows: int, new_rows: int, added: List[str],
                 removed: List[str], duration: float = 0.0):
        super().__init__(issues, duration)
        self.old_rows, self.new_rows = old_rows, new_rows
        self.added, self.removed = added, removed

    def _meta(self):
        return {"old_rows": self.old_rows, "new_rows": self.new_rows,
                "columns_added": self.added, "columns_removed": self.removed}

    def _header_lines(self):
        delta = self.new_rows - self.old_rows
        return [f"Rows     {_fmt_int(self.old_rows)} -> {_fmt_int(self.new_rows)} ({delta:+,})",
                f"Columns  +{len(self.added)} / -{len(self.removed)}"]
