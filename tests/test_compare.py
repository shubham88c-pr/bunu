import numpy as np
import pandas as pd
import pytest

import bunu
from bunu import Severity


def make(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "customer_id": np.arange(n),
        "revenue": rng.normal(100, 10, n),
        "country": rng.choice(["IN", "US", "UK"], n),
        "signup": rng.choice([1.0, np.nan], n, p=[.99, .01]),
    })


def sev(c, code, col=None):
    return [i.severity for i in c.issues if i.code == code and (col is None or i.column == col)]


def test_identical_data_has_no_issues():
    df = make()
    assert not bunu.compare(df, df.copy()).issues


def test_schema_dtype_rows():
    old = make()
    new = old.drop(columns=["signup"]).assign(extra=1)
    new["revenue"] = new["revenue"].astype(str)
    c = bunu.compare(old, new)
    assert c.removed == ["signup"] and c.added == ["extra"]
    assert sev(c, "SCHEMA_COLUMN_REMOVED") == [Severity.HIGH]
    assert sev(c, "DTYPE_CHANGED", "revenue") == [Severity.HIGH]


def test_int_to_float_is_medium_not_high():
    c = bunu.compare(pd.DataFrame({"a": [1, 2, 3]}), pd.DataFrame({"a": [1.0, 2.0, np.nan]}))
    assert sev(c, "DTYPE_CHANGED") == [Severity.MEDIUM]


def test_row_count_levels():
    base = make(1000)
    assert sev(bunu.compare(base, make(1020)), "ROW_COUNT_CHANGED") == []          # info hidden
    assert sev(bunu.compare(base, make(1100)), "ROW_COUNT_CHANGED") == [Severity.LOW]
    assert sev(bunu.compare(base, make(400)), "ROW_COUNT_CHANGED") == [Severity.HIGH]


def test_null_rate_and_duplicate_keys_and_categories():
    old = make()
    new = old.copy()
    new.loc[:299, "signup"] = np.nan
    new.loc[:49, "customer_id"] = 7
    new.loc[:4, "country"] = "FR"
    c = bunu.compare(old, new)
    assert sev(c, "NULL_RATE_CHANGED", "signup") == [Severity.HIGH]
    assert sev(c, "DUPLICATES_GAINED", "customer_id") == [Severity.HIGH]
    assert sev(c, "NEW_CATEGORIES", "country") == [Severity.LOW]


def test_mean_shift_scales_with_std():
    old = make()
    big = old.assign(revenue=old.revenue + 50)
    tiny = old.assign(revenue=old.revenue + 1)
    assert sev(bunu.compare(old, big), "MEAN_SHIFT") == [Severity.HIGH]
    assert sev(bunu.compare(old, tiny), "MEAN_SHIFT") == []


def test_snapshot_roundtrip_and_compare_without_old_data(tmp_path):
    old = make()
    p = tmp_path / "yesterday.json"
    bunu.snapshot(old).save(p)
    assert p.stat().st_size < 5_000
    new = old.assign(revenue=old.revenue + 50)
    from_file = bunu.compare(p, new)
    from_df = bunu.compare(old, new)
    assert [i.code for i in from_file.issues] == [i.code for i in from_df.issues]
    assert bunu.Snapshot.load(p).rows == 1000


def test_compare_does_not_mutate():
    a, b = make(), make(seed=1)
    a0, b0 = a.copy(deep=True), b.copy(deep=True)
    bunu.compare(a, b)
    pd.testing.assert_frame_equal(a, a0); pd.testing.assert_frame_equal(b, b0)


def test_duplicate_column_names_in_snapshot():
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    names = [c.name for c in bunu.snapshot(df).columns]
    assert names == ["a", "a#2"]


def test_empty_old_dataset():
    c = bunu.compare(pd.DataFrame({"a": []}), pd.DataFrame({"a": [1, 2]}))
    assert sev(c, "ROW_COUNT_CHANGED") == [Severity.HIGH]


def test_report_text_mentions_row_delta():
    s = str(bunu.compare(make(1000), make(1100)))
    assert "1,000 -> 1,100 (+100)" in s
