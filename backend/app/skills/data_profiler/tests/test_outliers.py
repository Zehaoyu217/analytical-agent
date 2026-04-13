from __future__ import annotations

import numpy as np
import pandas as pd


def test_flags_extreme_outliers() -> None:
    from app.skills.data_profiler.pkg.sections.outliers import run

    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, size=1000)
    values[-3:] = [1e9, -1e9, 5e8]
    df = pd.DataFrame({"v": values})
    result = run(df)
    assert any(r.kind == "outliers_extreme" for r in result["risks"])


def test_does_not_flag_normal_distribution() -> None:
    from app.skills.data_profiler.pkg.sections.outliers import run

    rng = np.random.default_rng(1)
    df = pd.DataFrame({"v": rng.normal(0, 1, size=1000)})
    result = run(df)
    assert not any(r.kind == "outliers_extreme" for r in result["risks"])
