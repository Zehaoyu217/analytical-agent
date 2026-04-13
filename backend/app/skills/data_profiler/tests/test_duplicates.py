# backend/app/skills/data_profiler/tests/test_duplicates.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_detects_duplicate_rows() -> None:
    from app.skills.data_profiler.pkg.sections.duplicates import run

    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
    result = run(df, key_candidates=None)
    assert any(r.kind == "duplicate_rows" and r.severity == "HIGH" for r in result["risks"])


def test_duplicate_key_is_blocker(duplicated_key_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.duplicates import run

    result = run(duplicated_key_df, key_candidates=["customer_id"])
    kinds = {(r.kind, r.severity) for r in result["risks"]}
    assert ("duplicate_key", "BLOCKER") in kinds
