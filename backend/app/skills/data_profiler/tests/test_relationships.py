from __future__ import annotations

import pandas as pd


def test_flags_collinear_pair() -> None:
    from app.skills.data_profiler.pkg.sections.relationships import run

    df = pd.DataFrame(
        {
            "x": list(range(100)),
            "y_dup": [v + 0.001 for v in range(100)],
            "z": [i % 4 for i in range(100)],
        }
    )
    result = run(df)
    assert any(
        r.kind == "collinear_pair" and set(r.columns) == {"x", "y_dup"} for r in result["risks"]
    )
