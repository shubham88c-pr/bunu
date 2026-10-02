import numpy as np
import pandas as pd


def demo(n: int = 2000, pair: bool = False):
    """A deliberately messy, reproducible DataFrame so you can try Bunu in 10 seconds.

    ``demo(pair=True)`` returns ``(yesterday, today)`` to try ``bunu.compare``.
    """
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "customer_id": np.arange(n),
        "email": [f"user{i % (n - 12)}@example.com" for i in range(n)],
        "age": [str(x) for x in rng.integers(18, 80, n)],
        "revenue": rng.normal(100, 15, n).round(2),
        "country": rng.choice(["India", "USA", "UK", "Germany"], n),
        "signup_date": np.where(rng.random(n) < .93, "2024-03-05", "05/03/2024"),
        "phone_note": np.where(rng.random(n) < .25, "N/A", "ok"),
        "plan": "free",
    })
    df.loc[:24, "age"] = "unknown"
    df.loc[df.index[::97], "country"] = df.loc[df.index[::97], "country"].str.lower()
    df.loc[5, "country"] = " India"
    df.loc[3, "revenue"] = np.inf
    df.loc[10, "revenue"] = 99999.0
    df.loc[rng.random(n) < .08, "revenue"] = np.nan
    if not pair:
        return df
    old = df.copy()  # "yesterday" had no inf / outlier yet
    old.loc[[3, 10], "revenue"] = 100.0
    new = df.copy()
    new["revenue"] = new["revenue"].replace(np.inf, np.nan) + 40
    new.loc[:int(n * .3), "signup_date"] = None
    new.loc[:30, "customer_id"] = 1
    new.loc[:5, "country"] = "France"
    new = pd.concat([new, new.iloc[:int(n * .25)]], ignore_index=True).assign(channel="web")
    return old, new
