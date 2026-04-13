from __future__ import annotations

import numpy as np

from app.skills.correlation.bootstrap import bootstrap_ci


def test_ci_brackets_true_correlation(linear_07) -> None:
    x, y = linear_07
    lo, hi = bootstrap_ci(x, y, method="pearson", n_resamples=500, seed=0)
    assert lo <= 0.7 <= hi
    assert lo < hi


def test_ci_narrows_with_more_data() -> None:
    from app.skills._stat_fixtures.generators import linear_xy
    x_sm, y_sm = linear_xy(n=50, rho=0.6, seed=1)
    x_lg, y_lg = linear_xy(n=2000, rho=0.6, seed=1)
    lo_s, hi_s = bootstrap_ci(x_sm, y_sm, method="pearson", n_resamples=300, seed=0)
    lo_l, hi_l = bootstrap_ci(x_lg, y_lg, method="pearson", n_resamples=300, seed=0)
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_bootstrap_raises_on_insufficient_variation() -> None:
    import pytest
    x = np.zeros(50)
    y = np.arange(50).astype(float)
    with pytest.raises(ValueError):
        bootstrap_ci(x, y, method="pearson", n_resamples=100, seed=0)
