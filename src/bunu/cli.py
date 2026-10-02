from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .issue import Severity


def _build():
    p = argparse.ArgumentParser(prog="bunu", description="Health check and change detector for tabular data.")
    p.add_argument("--version", action="version", version=f"bunu {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="check one data file")
    c.add_argument("path")
    c.add_argument("--fail-on", default=None, metavar="SEVERITY",
                   help="exit with code 1 if any issue is at/above info|low|medium|high")
    c.add_argument("--min-severity", default="low")
    c.add_argument("--json", action="store_true", help="print JSON instead of text")

    d = sub.add_parser("compare", help="compare two data files or snapshots")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--fail-on", default=None, metavar="SEVERITY")
    d.add_argument("--min-severity", default="low")
    d.add_argument("--json", action="store_true")

    s = sub.add_parser("snapshot", help="save a tiny statistical fingerprint of a data file")
    s.add_argument("path")
    s.add_argument("-o", "--output", required=True)

    sub.add_parser("demo", help="try Bunu on a built-in messy dataset")

    e = sub.add_parser("explain", help="short human summary of a data file")
    e.add_argument("path")
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    args = _build().parse_args(argv)
    try:
        import bunu
        from ._io import read_table

        if args.cmd == "check":
            result = bunu.check(read_table(args.path), min_severity=args.min_severity)
        elif args.cmd == "compare":
            result = bunu.compare(args.old, args.new, min_severity=args.min_severity)
        elif args.cmd == "demo":
            print(bunu.check(bunu.demo()))
            return 0
        elif args.cmd == "snapshot":
            out = bunu.snapshot(read_table(args.path)).save(args.output)
            print(f"Snapshot saved to {out}")
            return 0
        else:
            print(bunu.explain(read_table(args.path)))
            return 0
    except Exception as exc:
        print(f"bunu: error: {exc}", file=sys.stderr)
        return 2

    print(result.to_json() if args.json else result)
    if args.fail_on and any(i.severity >= Severity.parse(args.fail_on) for i in result.issues):
        return 1
    return 0
