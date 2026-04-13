# backend/app/skills/data_profiler/tests/fixtures/conftest.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def small_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5],
            "age": [25, 30, np.nan, 40, 45],
            "country": ["US", "UK", "US", None, "US"],
            "signup_date": pd.to_datetime(
                ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-20", "2024-03-01"]
            ),
            "revenue": [100.0, 200.0, 150.0, np.nan, 300.0],
        }
    )


@pytest.fixture
def duplicated_key_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"customer_id": [1, 2, 2, 3], "revenue": [10.0, 20.0, 25.0, 30.0]}
    )


@pytest.fixture
def heavy_missing_df() -> pd.DataFrame:
    import numpy as np
    return pd.DataFrame(
        {
            "id": range(10),
            "email": [None] * 8 + ["a@b", "c@d"],
            "score": [1.0, np.nan, 3.0, np.nan, 5.0, np.nan, 7.0, np.nan, 9.0, np.nan],
        }
    )


@pytest.fixture
def date_gap_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"ts": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-10", "2024-01-11"])}
    )
