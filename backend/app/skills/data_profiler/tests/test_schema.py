# backend/app/skills/data_profiler/tests/test_schema.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_schema_reports_column_types_and_null_counts(small_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.schema import run

    result = run(small_df)
    cols = {c["name"]: c for c in result["columns"]}
    assert cols["age"]["null_count"] == 1
    assert cols["country"]["null_count"] == 1
    assert cols["customer_id"]["dtype"].startswith("int")
    assert cols["signup_date"]["dtype"].startswith("datetime")


def test_schema_flags_mixed_types() -> None:
    from app.skills.data_profiler.pkg.sections.schema import run

    df = pd.DataFrame({"mix": [1, "two", 3.0]})
    result = run(df)
    risks = result["risks"]
    assert any(r.kind == "mixed_types" for r in risks)
