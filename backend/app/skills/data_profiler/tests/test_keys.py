from __future__ import annotations

import pandas as pd


def test_flags_high_cardinality_categorical() -> None:
    from app.skills.data_profiler.pkg.sections.keys import run

    df = pd.DataFrame({"uid": [f"u{i}" for i in range(100)]})
    result = run(df, key_candidates=None)
    kinds = {r.kind for r in result["risks"]}
    assert "high_cardinality_categorical" in kinds


def test_suggests_foreign_key_when_values_overlap_candidate() -> None:
    from app.skills.data_profiler.pkg.sections.keys import run

    df = pd.DataFrame({"ref": [1, 2, 3, 3, 2, 1]})
    result = run(df, key_candidates=["customer_id"])
    assert any(r.kind == "suspected_foreign_key" for r in result["risks"])
