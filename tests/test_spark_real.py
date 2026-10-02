"""Runs only where pyspark + Java exist (CI job 'spark'). Skipped elsewhere."""
import pytest

pyspark = pytest.importorskip("pyspark")
import pandas as pd  # noqa: E402

import bunu  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = SparkSession.builder.master("local[1]").appName("bunu-test").getOrCreate()
    yield s
    s.stop()


def test_check_real_spark_dataframe(spark):
    sdf = spark.createDataFrame(pd.DataFrame({"a": [1.0, float("inf")] * 30, "id": range(60)}))
    r = bunu.check(sdf)
    assert r.rows == 60 and r.has("INFINITE_VALUES", "a")


def test_compare_spark_vs_pandas(spark):
    pdf = pd.DataFrame({"x": range(100)})
    sdf = spark.createDataFrame(pdf.assign(y=1))
    assert bunu.compare(pdf, sdf).added == ["y"]
