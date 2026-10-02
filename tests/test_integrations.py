import warnings

import numpy as np
import pandas as pd
import pytest

import bunu
from bunu import _input


def test_numpy_and_dict_inputs():
    assert bunu.check(np.array([[1, 2], [3, 4], [5, 6]])).rows == 3
    assert bunu.check(np.arange(5)).rows == 5
    assert bunu.check({"a": [1, 2, 3]}).rows == 3
    with pytest.raises(TypeError, match="2-D"):
        bunu.check(np.zeros((2, 2, 2)))


def test_series_input():
    assert bunu.check(pd.Series([1, 2, 3], name="x")).n_columns == 1


class FakeSparkDF:
    """Duck-types pyspark.sql.DataFrame: .limit(n).toPandas()."""
    def __init__(self, pdf, n=None):
        self._pdf, self._n = pdf, n
    def limit(self, n):
        return FakeSparkDF(self._pdf, n)
    def toPandas(self):
        return self._pdf if self._n is None else self._pdf.iloc[: self._n]


def test_spark_dataframe_is_bounded(monkeypatch):
    monkeypatch.setattr(_input, "SPARK_MAX_ROWS", 100)
    big = FakeSparkDF(pd.DataFrame({"a": range(1000)}))
    with pytest.warns(UserWarning, match="first 100"):
        assert bunu.check(big).rows == 100
    small = FakeSparkDF(pd.DataFrame({"a": range(50)}))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert bunu.check(small).rows == 50


def test_compare_accepts_mixed_inputs(tmp_path):
    a = pd.DataFrame({"x": range(100)})
    b = FakeSparkDF(pd.DataFrame({"x": range(100)}).assign(y=1))
    assert bunu.compare(a, b).added == ["y"]


def test_html_repr_is_escaped_and_complete():
    df = pd.DataFrame({"<script>alert(1)</script>": [np.inf] + [1.0] * 40})
    h = bunu.check(df)._repr_html_()
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "INFINITE_VALUES" in h and "never modifies" in h
    assert "ALL CLEAR" in bunu.check(pd.DataFrame({"a": range(50)}))._repr_html_()
    old, new = bunu.demo(pair=True)
    assert "Dataset Comparison" in bunu.compare(old, new)._repr_html_()
    assert "<pre" in bunu.explain(df)._repr_html_()


def test_demo_is_reproducible_and_interesting():
    a, b = bunu.demo(), bunu.demo()
    pd.testing.assert_frame_equal(a, b)
    codes = {i.code for i in bunu.check(a).issues}
    assert {"DUPLICATE_KEY", "NUMERIC_AS_STRING", "DATETIME_MIXED_FORMAT", "NULL_TOKENS",
            "INFINITE_VALUES", "CASE_VARIANTS"} <= codes
    old, new = bunu.demo(pair=True)
    ccodes = {i.code for i in bunu.compare(old, new).issues}
    assert {"DUPLICATES_GAINED", "NULL_RATE_CHANGED", "SCHEMA_COLUMN_ADDED", "MEAN_SHIFT"} <= ccodes


def test_ascii_output_survives_cp1252_console():
    str(bunu.check(bunu.demo())).encode("cp1252")  # Windows consoles must never crash


@pytest.mark.parametrize("url,reader", [
    ("hdfs://namenode:8020/data/day1.parquet", "read_parquet"),
    ("s3://bucket/key/day1.csv", "read_csv"),
    ("gs://bucket/day1.csv.gz", "read_csv"),
    ("abfs://c@acct.dfs.core.windows.net/x.jsonl", "read_json"),
])
def test_remote_urls_reach_pandas_unmangled(monkeypatch, url, reader):
    from bunu._io import read_table
    seen = {}
    monkeypatch.setattr(pd, reader, lambda p, *a, **k: seen.setdefault("p", p) and pd.DataFrame({"a": [1]}))
    read_table(url)
    assert seen["p"] == url
