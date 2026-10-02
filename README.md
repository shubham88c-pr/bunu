# Bunu

**A health check and change detector for your DataFrame.**
Observe first. Mutate never by surprise.

```bash
pip install bunu
```

```python
import bunu

report = bunu.check(df)          # what is wrong with this data?
diff   = bunu.compare(old, new)  # what changed since yesterday?
bunu.explain(df)                 # what should I look at first?
```

```text
Bunu Data Check
------------------------------------------------------------
Rows     5,000
Columns  10

HIGH
  email  [DUPLICATE_KEY]
  `- 99.8% unique, but 10 value(s) repeat; expected to be a unique key. (10 rows)
  signup_date  [DATETIME_MIXED_FORMAT]
  `- Dates are written in 2 different formats (like '2024-01-05': 4,521, like '05/01/2024': 479) ...
MEDIUM
  age  [NUMERIC_AS_STRING]
  `- 99.3% of values are numbers stored as text; 37 are not numeric (e.g. 'unknown'). (4,963 rows)
```

Bunu never changes your data. Every finding carries a proposed pandas fix in
`issue.suggestion`; you decide whether to run it.

## What it catches

| Code | Meaning |
|---|---|
| `MISSING_VALUES`, `EMPTY_COLUMN` | NaN share per column; fully empty columns |
| `EMPTY_STRING`, `WHITESPACE_ONLY`, `NULL_TOKENS` | text that is really missing (`""`, `"  "`, `"N/A"`) |
| `DUPLICATE_ROWS`, `DUPLICATE_KEY`, `DUPLICATE_COLUMN` | repeated rows, broken keys, repeated column names |
| `CONSTANT_COLUMN`, `UNIQUE_COLUMN` (info) | no-information columns, key candidates |
| `MIXED_TYPE`, `NUMERIC_AS_STRING` | `int` + `str` in one column, numbers stored as text |
| `DATETIME_AS_STRING`, `DATETIME_MIXED_FORMAT` | dates stored as text, several formats in one column |
| `WHITESPACE_PADDED`, `CASE_VARIANTS`, `RARE_CATEGORY` | `"India"`/`"india"`/`" India"`, probable typos |
| `INFINITE_VALUES`, `EXTREME_VALUES` | `inf`, values far outside the normal range |

`bunu.compare` adds: `SCHEMA_COLUMN_ADDED/REMOVED`, `DTYPE_CHANGED`, `ROW_COUNT_CHANGED`,
`NULL_RATE_CHANGED`, `DUPLICATES_GAINED`, `CARDINALITY_CHANGED`, `NEW_CATEGORIES`,
`CATEGORIES_GONE`, `MEAN_SHIFT`, `INFINITE_VALUES`.

Codes are stable: safe to use in pipelines.

## Use it in pipelines

```python
bunu.check(df).raise_if("high")            # raises DataQualityError
assert not bunu.check(df).has("DUPLICATE_ROWS")
```

Keep a few-KB fingerprint instead of yesterday's data:

```python
bunu.snapshot(df).save("yesterday.json")
...
bunu.compare("yesterday.json", today_df).raise_if("medium")
```

Command line (non-zero exit code makes it CI-friendly):

```bash
bunu check customers.csv --fail-on high
bunu snapshot today.parquet -o today.json
bunu compare yesterday.json today.parquet --fail-on medium
bunu explain customers.csv
```

## Works with

Tested (not just claimed):

| Where | Status |
|---|---|
| Python 3.9, 3.10, 3.11, 3.12, 3.13 | tested |
| pandas 2.0.3, 2.1, 2.2, 2.3, 3.0 (incl. new `str` dtype) | tested |
| NumPy 1.26 and 2.x (2-D arrays accepted directly) | tested |
| PySpark 4.x DataFrames (`bunu.check(spark_df)`) | tested locally; checks at most the first 1,000,000 rows and warns |
| Jupyter, VS Code notebooks, Colab, Databricks | rich HTML tables via `_repr_html_`; Jupyter kernel run tested |
| Polars / PyArrow tables | converted via `.to_pandas()` (duck-typed) |
| Hadoop / HDFS, S3, GCS, ADLS | Bunu reads `hdfs://`, `s3://` ... through pandas; needs the matching `fsspec` / `pyarrow` filesystem installed |
| Windows / macOS / Linux | plain-ASCII output (never crashes a cp1252 console); full OS matrix runs in CI |

Bunu does not run inside Spark; it collects a bounded slice to the driver. A distributed
engine is on the roadmap, not in 0.1.

## Roadmap (0.2 ideas, vote with an issue)

- Robust drift: median / quantile / PSI instead of mean +/- std.
- `bunu.fix(df, ...)`: show a before/after preview first; explicit, never silent.
- Row-level, key-aware `compare(old, new, key="id")`.
- Polars- and Arrow-native engines, optional Spark-native checks.
- `report.to_html()` / `report.save("report.html")` for sharing.
- Your own rules: `bunu.rule("MY_CODE")`.

## Design rules

- Only dependency: `pandas`. No AI, no network, deterministic output.
- One bad column never crashes a check (`RULE_ERROR` info instead).
- Not a replacement for pandas, a cleaning framework, a schema/validation framework, or a profiler.

## Performance

20 columns (numbers, low/high-cardinality text, dates-as-text), pandas 3.0, Python 3.12, one sandbox core:

| rows | `check` |
|---|---|
| 100,000 | ~0.26 s |
| 1,000,000 | ~1.8 s |

Reproduce: `python benchmarks/benchmark_check.py`. Detection is exact (no row sampling).

## Why Bunu?

Bunu was named in memory of someone very special.

## License
MIT
