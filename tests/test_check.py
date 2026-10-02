import numpy as np
import pandas as pd
import pytest

import bunu
from bunu import Severity


def codes(r, col=None):
    return {i.code for i in r.issues if col is None or i.column == col}


def test_clean_data_is_ok(clean):
    r = bunu.check(clean)
    assert r.ok and not r.issues and not r.has_errors
    assert "No issues found." in str(r)


def test_check_never_mutates(clean):
    messy = clean.copy()
    messy["score"] = messy["score"].astype(object)
    messy.loc[0, "score"] = "x"
    snap = messy.copy(deep=True)
    bunu.check(messy)
    bunu.explain(messy)
    bunu.snapshot(messy)
    pd.testing.assert_frame_equal(messy, snap)


def test_missing_levels():
    n = 1000
    def col(k):
        return [np.nan] * k + [1.0] * (n - k)
    df = pd.DataFrame({"a": col(600), "b": col(300), "c": col(50), "d": col(2)})
    r = bunu.check(df, min_severity="info")
    sev = {i.column: i.severity for i in r.get("MISSING_VALUES")}
    assert sev == {"a": Severity.HIGH, "b": Severity.MEDIUM, "c": Severity.LOW, "d": Severity.INFO}
    assert "d" not in {i.column for i in bunu.check(df).get("MISSING_VALUES")}


def test_empty_blank_and_null_tokens():
    df = pd.DataFrame({"x": ["a", "", "  ", "N/A", "null", "b"] * 20})
    r = bunu.check(df)
    assert {"EMPTY_STRING", "WHITESPACE_ONLY", "NULL_TOKENS"} <= codes(r)
    assert r.get("EMPTY_STRING")[0].affected_rows == 20
    assert r.get("NULL_TOKENS")[0].affected_rows == 40


def test_duplicate_rows_and_columns():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    assert bunu.check(df).has("DUPLICATE_ROWS")
    dup = pd.DataFrame([[1, 2], [3, 4]], columns=["a", "a"])
    r = bunu.check(dup)
    assert r.has("DUPLICATE_COLUMN") and r.has_errors


def test_no_duplicate_rows_when_a_column_is_unique(clean):
    assert not bunu.check(clean).has("DUPLICATE_ROWS")


def test_duplicate_key():
    df = pd.DataFrame({"user_id": list(range(95)) + [1, 2, 3, 4, 5]})
    r = bunu.check(df)
    assert r.get("DUPLICATE_KEY")[0].severity == Severity.HIGH
    assert r.get("DUPLICATE_KEY")[0].affected_rows == 5
    repeated = pd.DataFrame({"user_id": [1, 2, 3] * 100})  # an events table: repeats are normal
    assert not bunu.check(repeated).has("DUPLICATE_KEY")


def test_constant_and_empty_columns():
    df = pd.DataFrame({"c": [7] * 10, "e": [np.nan] * 10, "ok": range(10)})
    r = bunu.check(df)
    assert r.has("CONSTANT_COLUMN", "c") and r.has("EMPTY_COLUMN", "e")
    assert not r.has("MISSING_VALUES", "e")


def test_unique_column_is_info_only(clean):
    assert bunu.check(clean, min_severity="info").has("UNIQUE_COLUMN", "customer_id")
    assert not bunu.check(clean).has("UNIQUE_COLUMN")


def test_mixed_type():
    df = pd.DataFrame({"age": [30, 40, "n/a", 50] * 25})
    i = bunu.check(df).get("MIXED_TYPE")[0]
    assert i.affected_rows == 25 and "to_numeric" in i.suggestion


def test_numeric_as_string_full_and_partial():
    full = pd.DataFrame({"p": ["1.5", "2", " 3 ", "4e2"] * 10})
    i = bunu.check(full).get("NUMERIC_AS_STRING")[0]
    assert i.affected_rows == 40 and i.details["non_numeric_rows"] == 0
    part = pd.DataFrame({"p": [str(x) for x in range(99)] + ["oops"]})
    j = bunu.check(part).get("NUMERIC_AS_STRING")[0]
    assert j.details["non_numeric_rows"] == 1 and "oops" in j.message


@pytest.mark.parametrize("name,vals", [
    ("zip", ["12345", "54321"] * 5),
    ("code", ["1", "2"] * 5),
    ("sku", ["10", "20"] * 5),
    ("ref", ["00123", "00456"] * 5),    # leading zeros => identifier, not a number
])
def test_identifiers_are_not_flagged_as_numbers(name, vals):
    assert not bunu.check(pd.DataFrame({name: vals})).has("NUMERIC_AS_STRING")


def test_numeric_text_not_flagged_when_mostly_words():
    df = pd.DataFrame({"t": ["apple", "pear", "12"] * 20})
    assert not bunu.check(df).has("NUMERIC_AS_STRING")


def test_datetime_as_string_and_mixed():
    one = pd.DataFrame({"d": ["2024-01-05", "2024-02-10"] * 10})
    r = bunu.check(one)
    assert r.has("DATETIME_AS_STRING") and not r.has("DATETIME_MIXED_FORMAT")
    assert "%Y-%m-%d" in r.get("DATETIME_AS_STRING")[0].suggestion
    mixed = pd.DataFrame({"d": ["2024-01-05"] * 18 + ["05/01/2024"] * 2})
    m = bunu.check(mixed).get("DATETIME_MIXED_FORMAT")[0]
    assert m.severity == Severity.HIGH and m.affected_rows == 2


def test_short_and_padded_dates_are_one_format():
    df = pd.DataFrame({"d": ["1/5/2024", "01/05/2024", "12/31/2024"] * 5})
    r = bunu.check(df)
    assert r.has("DATETIME_AS_STRING") and not r.has("DATETIME_MIXED_FORMAT")


def test_real_datetimes_are_fine(clean):
    assert not bunu.check(clean).has("DATETIME_AS_STRING")


def test_whitespace_and_case_variants():
    df = pd.DataFrame({"c": ["India"] * 50 + ["india"] * 5 + [" India"] * 3 + ["USA"] * 42})
    r = bunu.check(df)
    assert r.has("CASE_VARIANTS") and r.has("WHITESPACE_PADDED")
    assert r.get("CASE_VARIANTS")[0].affected_rows == 8       # minority spellings only
    assert r.get("WHITESPACE_PADDED")[0].affected_rows == 3


def test_rare_category_typo():
    df = pd.DataFrame({"c": ["India"] * 600 + ["USA"] * 399 + ["Indai"]})
    i = bunu.check(df).get("RARE_CATEGORY")[0]
    assert "Indai" in i.message and i.affected_rows == 1


def test_infinite_and_extreme():
    arr = np.r_[np.random.default_rng(0).normal(0, 1, 500), np.inf, -np.inf, 1e6]
    r = bunu.check(pd.DataFrame({"x": arr}))
    assert r.get("INFINITE_VALUES")[0].affected_rows == 2
    assert r.get("EXTREME_VALUES")[0].affected_rows == 1


def test_raise_if_and_has():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
    r = bunu.check(df)
    with pytest.raises(bunu.DataQualityError) as e:
        r.raise_if("medium")
    assert "DUPLICATE_ROWS" in str(e.value)
    r.raise_if("high") if not r.has_errors else None
    assert r.has("DUPLICATE_ROWS", column=None)


def test_json_roundtrip(clean):
    import json
    d = json.loads(bunu.check(clean.assign(k=1)).to_json())
    assert d["rows"] == 500 and d["issues"][0]["code"] == "CONSTANT_COLUMN"


def test_explain_buckets():
    df = pd.DataFrame({"ok": range(100), "bad": [np.inf] + [1.0] * 99})
    e = bunu.explain(df)
    assert e.healthy == ["ok"] and e.suspicious == ["bad"]
    assert "Bunu never modifies your data." in str(e)
    assert bunu.explain(bunu.check(df)).suspicious == ["bad"]


# ---- robustness ("boringly reliable") ---------------------------------------
def test_empty_frames():
    assert bunu.check(pd.DataFrame()).has("EMPTY_DATAFRAME")
    assert bunu.check(pd.DataFrame({"a": []})).has("EMPTY_DATAFRAME")


def test_weird_inputs_never_crash():
    df = pd.DataFrame({
        "lists": [[1], [2], [1]] * 10,
        "dicts": [{"a": 1}] * 30,
        "nullable": pd.array([1, None, 3] * 10, dtype="Int64"),
        "boolean": pd.array([True, None, False] * 10, dtype="boolean"),
        "cat": pd.Categorical(["a", "b", "a"] * 10),
        "td": pd.to_timedelta(range(30), unit="s"),
        "tz": pd.date_range("2024", periods=30, tz="UTC"),
        "bytes": [b"x"] * 30,
        "cplx": [1 + 2j] * 30,
        5: range(30),
    })
    r = bunu.check(df, min_severity="info")
    assert not r.has("RULE_ERROR"), [i.message for i in r.get("RULE_ERROR")]
    bunu.explain(df); bunu.snapshot(df)


def test_multiindex_columns_and_custom_index():
    df = pd.DataFrame([[1, 2], [3, 4]], columns=pd.MultiIndex.from_tuples([("a", "x"), ("a", "y")]),
                      index=["r1", "r2"])
    assert not bunu.check(df, min_severity="info").has("RULE_ERROR")


def test_accepts_objects_with_to_pandas():
    class Fake:
        def to_pandas(self):
            return pd.DataFrame({"a": [1, 2, 3]})
    assert bunu.check(Fake()).rows == 3
    with pytest.raises(TypeError, match="pandas DataFrame"):
        bunu.check([1, 2, 3])


def test_large_unique_strings_are_sampled_not_slow():
    n = 300_000
    df = pd.DataFrame({"s": [f"user{i}@example.com" for i in range(n)]})
    r = bunu.check(df)
    assert r.duration < 5 and r.rows == n
