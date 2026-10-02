import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def clean(rng):
    n = 500
    return pd.DataFrame({
        "customer_id": np.arange(n),
        "score": rng.normal(50, 10, n),
        "country": rng.choice(["India", "USA", "UK"], n),
        "joined": pd.date_range("2024-01-01", periods=n, freq="h"),
    })
