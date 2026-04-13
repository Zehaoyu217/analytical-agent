from __future__ import annotations

import numpy as np
import pandas as pd


def test_flags_heavy_skew() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    rng = np.random.default_rng(0)
    values = rng.exponential(scale=1.0, size=2000)
    values[-5:] = 1e6
    df = pd.DataFrame({"v": values})
    result = run(df)
    assert any(r.kind == "skew_heavy" for r in result["risks"])


def test_flags_constant_column() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    df = pd.DataFrame({"k": [1] * 100})
    result = run(df)
    assert any(r.kind == "constant_column" for r in result["risks"])


def test_flags_near_constant() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    df = pd.DataFrame({"mostly_one": [1] * 98 + [2, 3]})
    result = run(df)
    kinds = {r.kind for r in result["risks"]}
    assert "near_constant" in kinds
