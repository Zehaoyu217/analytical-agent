from __future__ import annotations

import numpy as np
import pytest

from app.skills.stat_validate import validate


def test_clean_correlation_passes() -> None:
    payload = {
        "coefficient": 0.7, "ci_low": 0.6, "ci_high": 0.8,
        "n_effective": 400, "x": "price", "y": "quantity",
        "partial_on": [], "detrend": None,
    }
    v = validate(claim_kind="correlation", payload=payload,
                 turn_trace=[], frame=None,
                 stratify_candidates=(), claim_text="price and quantity are correlated")
    assert v.rollup_status() == "PASS"
    assert len(v.passes) >= 2


def test_simpsons_example_fails(simpsons_df) -> None:
    payload = {
        "coefficient": float(np.corrcoef(simpsons_df["x"], simpsons_df["y"])[0, 1]),
        "ci_low": -0.5, "ci_high": -0.1,
        "n_effective": len(simpsons_df),
        "x": "x", "y": "y",
        "partial_on": [], "detrend": None,
    }
    v = validate(claim_kind="correlation", payload=payload,
                 turn_trace=[], frame=simpsons_df,
                 stratify_candidates=("stratum",),
                 claim_text="x drives y")
    assert v.rollup_status() == "FAIL"
    assert any(vio.code == "simpsons_flip" for vio in v.failures)
    assert "simpsons_paradox" in v.gotcha_refs()


def test_negligible_effect_fails() -> None:
    payload = {"effect": {"value": 0.02, "ci_low": -0.04, "ci_high": 0.06,
                          "name": "cohens_d"},
               "n_per_group": {"A": 50, "B": 50}}
    v = validate(claim_kind="group_diff", payload=payload,
                 turn_trace=[], frame=None,
                 stratify_candidates=(), claim_text="A and B differ")
    assert v.rollup_status() == "FAIL"


def test_causal_claim_without_controls_warns() -> None:
    payload = {
        "coefficient": 0.5, "ci_low": 0.3, "ci_high": 0.7,
        "n_effective": 400, "partial_on": [], "detrend": None,
    }
    v = validate(claim_kind="correlation", payload=payload,
                 turn_trace=[], frame=None,
                 stratify_candidates=(),
                 claim_text="Marketing spend drives revenue")
    assert v.rollup_status() == "WARN"
    assert any(vio.code == "confounder_risk" for vio in v.warnings)


def test_unknown_claim_kind_raises() -> None:
    with pytest.raises(ValueError):
        validate(claim_kind="bogus", payload={}, turn_trace=[])


def test_multiple_comparisons_warn() -> None:
    trace = [
        {"tool": "correlation.correlate", "p_value": 0.02, "correction": None}
        for _ in range(7)
    ]
    payload = {
        "coefficient": 0.5, "ci_low": 0.3, "ci_high": 0.7,
        "n_effective": 400, "partial_on": ["z"], "detrend": None,
    }
    v = validate(claim_kind="correlation", payload=payload,
                 turn_trace=trace, frame=None,
                 stratify_candidates=(), claim_text="x and y are associated")
    assert v.rollup_status() == "WARN"
    assert "multiple_comparisons" in v.gotcha_refs()
