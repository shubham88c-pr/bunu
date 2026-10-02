"""Issue and Severity: the vocabulary Bunu speaks."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Optional, Union


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: Union[str, int, "Severity"]) -> "Severity":
        if isinstance(value, Severity):
            return value
        if isinstance(value, str):
            try:
                return cls[value.strip().upper()]
            except KeyError:
                raise ValueError(
                    f"Unknown severity {value!r}. Use one of: info, low, medium, high."
                ) from None
        return cls(value)


@dataclass(frozen=True)
class Issue:
    """One finding. ``code`` is stable across versions and safe to use in pipelines."""

    code: str
    severity: Severity
    message: str
    column: Optional[str] = None
    affected_rows: Optional[int] = None
    suggestion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.label,
            "column": self.column,
            "message": self.message,
            "affected_rows": self.affected_rows,
            "suggestion": self.suggestion,
            "details": self.details,
        }
