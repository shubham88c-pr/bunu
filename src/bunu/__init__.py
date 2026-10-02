"""Bunu - a health check and change detector for your DataFrame.

    import bunu
    report = bunu.check(df)        # what is wrong with this data?
    diff = bunu.compare(old, new)  # what changed since yesterday?
    bunu.explain(df)               # what should I look at first?

Observe first. Mutate never by surprise.
"""
from ._version import __version__
from .check import check
from .compare import compare
from .demo import demo
from .explain import explain
from .issue import Issue, Severity
from .report import Comparison, DataQualityError, Report
from .snapshot import Snapshot, snapshot

__all__ = [
    "check", "compare", "explain", "snapshot", "Snapshot", "demo",
    "Report", "Comparison", "Issue", "Severity", "DataQualityError", "__version__",
]
