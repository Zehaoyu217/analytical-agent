from __future__ import annotations

import numpy as np

from app.skills.correlation.method import detect_nonlinearity, pick_method


def test_pick_method_respects_explicit_choice() -> None:
    x = np.array([1.0, 2, 3, 4, 5])
    y = np.array([2.0, 4, 6, 8, 10])
    assert pick_method(x, y, requested="pearson") == "pearson"
    assert pick_method(x, y, requested="spearman") == "spearman"


def test_pick_method_auto_picks_pearson_for_linear(linear_07) -> None:
    x, y = linear_07
    assert pick_method(x, y, requested="auto") == "pearson"


def test_pick_method_auto_picks_spearman_for_monotonic_nonlinear(monotonic_df) -> None:
    picked = pick_method(monotonic_df["x"].to_numpy(), monotonic_df["y"].to_numpy(), requested="auto")
    assert picked == "spearman"


def test_detect_nonlinearity_on_linear_is_false(linear_07) -> None:
    x, y = linear_07
    assert detect_nonlinearity(x, y) is False


def test_detect_nonlinearity_on_monotonic_nonlinear_is_true(monotonic_df) -> None:
    assert detect_nonlinearity(
        monotonic_df["x"].to_numpy(), monotonic_df["y"].to_numpy()
    ) is True


def test_pick_method_rejects_unknown() -> None:
    import pytest
    with pytest.raises(ValueError):
        pick_method(np.array([1]), np.array([2]), requested="cosine")
