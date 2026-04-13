from __future__ import annotations

import numpy as np

from app.skills.group_compare.effect_size import (
    cliffs_delta,
    cohens_d,
    eta_squared,
)


def test_cohens_d_matches_known_value() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 200)
    b = rng.normal(0.5, 1, 200)
    d = cohens_d(a, b)
    assert 0.35 < d < 0.65


def test_cohens_d_zero_for_identical_samples() -> None:
    a = np.array([1.0, 2, 3, 4, 5])
    assert abs(cohens_d(a, a.copy())) < 1e-9


def test_cliffs_delta_bounds() -> None:
    a = np.array([1, 2, 3, 4, 5], dtype=float)
    b = np.array([6, 7, 8, 9, 10], dtype=float)
    d = cliffs_delta(a, b)
    assert d == -1.0


def test_eta_squared_zero_for_no_effect() -> None:
    rng = np.random.default_rng(2)
    groups = [rng.normal(0, 1, 100) for _ in range(3)]
    eta = eta_squared(groups)
    assert eta < 0.05


def test_eta_squared_large_when_means_differ() -> None:
    rng = np.random.default_rng(3)
    groups = [rng.normal(i * 2.0, 0.5, 100) for i in range(3)]
    eta = eta_squared(groups)
    assert eta > 0.5
