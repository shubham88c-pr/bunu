"""Run:  python benchmarks/benchmark_check.py [rows ...]

Builds a realistic 20-column frame (ints, floats, low/high-cardinality strings,
dates as text, nulls) and times bunu.check / snapshot / compare.
"""
import platform
import sys
import time

import numpy as np
import pandas as pd

import bunu


def make(n, seed=0):
    rng = np.random.default_rng(seed)
    d = {"id": np.arange(n)}
    for k in range(6):
        d[f"f{k}"] = np.where(rng.random(n) < .02, np.nan, rng.normal(size=n))
    for k in range(4):
        d[f"i{k}"] = rng.integers(0, 10_000, n)
    cats = np.array(["India", "USA", "UK", "Germany", "France", "Brazil", "Japan"])
    for k in range(4):
        d[f"cat{k}"] = cats[rng.integers(0, len(cats), n)]
    d["email"] = pd.Series(rng.integers(0, n, n)).astype(str) + "@x.com"
    d["name"] = "user_" + pd.Series(rng.integers(0, n // 2 + 1, n)).astype(str)
    d["amount_txt"] = pd.Series(rng.integers(0, 10_000, n)).astype(str)
    d["date_txt"] = pd.Series(pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D")).dt.strftime("%Y-%m-%d")
    d["flag"] = rng.random(n) < .5
    return pd.DataFrame(d)


def best(fn, repeat=3):
    t = []
    for _ in range(repeat):
        s = time.perf_counter(); fn(); t.append(time.perf_counter() - s)
    return min(t) * 1000


if __name__ == "__main__":
    sizes = [int(x) for x in sys.argv[1:]] or [100_000, 1_000_000, 5_000_000]
    print(f"python {platform.python_version()} | pandas {pd.__version__} | numpy {np.__version__} | bunu {bunu.__version__}")
    print(f"{'rows':>10} {'cols':>5} {'check ms':>10} {'snapshot ms':>12} {'compare ms':>11} {'df MB':>8}")
    for n in sizes:
        a, b = make(n), make(n, seed=1)
        mb = a.memory_usage(deep=True).sum() / 1e6
        sa = bunu.snapshot(a)
        print(f"{n:>10,} {a.shape[1]:>5} {best(lambda: bunu.check(a)):>10.0f} "
              f"{best(lambda: bunu.snapshot(a)):>12.0f} {best(lambda: bunu.compare(sa, b), 1):>11.0f} {mb:>8.0f}")
