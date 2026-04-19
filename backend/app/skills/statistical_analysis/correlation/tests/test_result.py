from __future__ import annotations

from app.skills.statistical_analysis.correlation.result import CorrelationResult


def test_result_is_frozen_and_serializable() -> None:
    r = CorrelationResult(
        coefficient=0.72,
        ci_low=0.65,
        ci_high=0.78,
        p_value=1.2e-12,
        method_used="pearson",
        nonlinear_warning=False,
        n_effective=400,
        na_dropped=0,
        x="price",
        y="quantity",
        partial_on=(),
        detrend=None,
    )
    assert r.coefficient == 0.72
    d = r.to_dict()
    assert d["method_used"] == "pearson"
    assert d["partial_on"] == []


def test_result_rejects_mutation() -> None:
    import dataclasses

    import pytest
    r = CorrelationResult(
        coefficient=0.1, ci_low=0.0, ci_high=0.2, p_value=0.3,
        method_used="spearman", nonlinear_warning=True,
        n_effective=50, na_dropped=2, x="a", y="b",
        partial_on=(), detrend=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.coefficient = 0.9  # type: ignore[misc]
