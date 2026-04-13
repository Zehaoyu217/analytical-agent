from __future__ import annotations

import numpy as np

from app.skills.group_compare.assumptions import (
    AssumptionReport,
    check_assumptions,
)


def test_normal_homoscedastic_two_groups_marked_parametric() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 200)
    b = rng.normal(0.3, 1, 200)
    report = check_assumptions([a, b])
    assert isinstance(report, AssumptionReport)
    assert report.all_normal is True
    assert report.homoscedastic is True


def test_heavy_tailed_flagged_non_normal() -> None:
    rng = np.random.default_rng(1)
    a = rng.standard_t(df=2, size=200)
    b = rng.normal(0, 1, 200)
    report = check_assumptions([a, b])
    assert report.all_normal is False


def test_unequal_variance_flagged() -> None:
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1.0, 200)
    b = rng.normal(0, 5.0, 200)
    report = check_assumptions([a, b])
    assert report.homoscedastic is False


def test_three_groups() -> None:
    rng = np.random.default_rng(3)
    groups = [rng.normal(i, 1, 100) for i in range(3)]
    report = check_assumptions(groups)
    assert report.k == 3
    assert isinstance(report.all_normal, bool)
