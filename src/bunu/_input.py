import warnings

import numpy as np
import pandas as pd

SPARK_MAX_ROWS = 1_000_000  # Bunu never collects more than this from a Spark DataFrame


def as_frame(obj, what="data"):
    """Turn supported inputs into a pandas DataFrame (pandas is always the engine)."""
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, pd.Series):
        return obj.to_frame()
    if isinstance(obj, np.ndarray):
        if obj.ndim in (1, 2):
            return pd.DataFrame(obj)
        raise TypeError(f"bunu needs a 1-D or 2-D array for {what}, got {obj.ndim}-D.")
    if isinstance(obj, dict):
        return pd.DataFrame(obj)
    mod = type(obj).__module__ or ""
    if mod.startswith("pyspark.pandas") and hasattr(obj, "head"):
        return _bounded(obj.head(SPARK_MAX_ROWS + 1).to_pandas())
    if hasattr(obj, "toPandas") and hasattr(obj, "limit"):  # pyspark.sql.DataFrame
        return _bounded(obj.limit(SPARK_MAX_ROWS + 1).toPandas())
    if hasattr(obj, "to_pandas"):  # polars, pyarrow, modin, ...
        return obj.to_pandas()
    raise TypeError(
        f"bunu expects a pandas DataFrame for {what}, got {type(obj).__name__}. "
        "Convert it first, e.g. pd.DataFrame(obj)."
    )


def _bounded(pdf):
    if len(pdf) > SPARK_MAX_ROWS:
        warnings.warn(
            f"Spark DataFrame has more than {SPARK_MAX_ROWS:,} rows; bunu analysed only the first "
            f"{SPARK_MAX_ROWS:,}. Filter or sample in Spark first for a representative check.",
            UserWarning, stacklevel=4)
        return pdf.iloc[:SPARK_MAX_ROWS]
    return pdf
