from __future__ import annotations

import numpy as np
import pandas as pd

from app.skills.stat_validate.checks.confounder import check_confounder_risk
from app.skills.stat_validate.checks.effect_size import check_effect_size
from app.skills.stat_validate.checks.leakage import check_leakage
from app.skills.stat_validate.checks.multiple_comparisons import check_multiple_comparisons
from app.skills.stat_validate.checks.sample_size import check_sample_size
from app.skills.stat_validate.checks.simpsons import check_simpsons_paradox
from app.skills.stat_validate.checks.stationarity import check_stationarity_for_spurious


def test_effect_size_negligible_ci_fails() -> None:
    result = check_effect_size({"effect": {"value": 0.03, "ci_low": -0.06, "ci_high": 0.05,
                                           "name": "cohens_d"}})
    assert result is not None
    assert result.severity == "FAIL"
    assert result.code == "effect_size_negligible"


def test_effect_size_passing_returns_none() -> None:
    result = check_effect_size({"effect": {"value": 0.4, "ci_low": 0.2, "ci_high": 0.6,
                                           "name": "cohens_d"}})
    assert result is None


def test_sample_size_below_ten_fails() -> None:
    result = check_sample_size({"n_per_group": {"A": 8, "B": 50}})
    assert result is not None
    assert result.severity == "FAIL"


def test_multiple_comparisons_flags_more_than_five_without_correction() -> None:
    trace = [{"tool": "group_compare.compare", "p_value": 0.04, "correction": None}
             for _ in range(8)]
    result = check_multiple_comparisons(trace)
    assert result is not None
    assert result.severity == "WARN"
    assert "multiple_comparisons" in result.gotcha_refs


def test_multiple_comparisons_ok_with_correction() -> None:
    trace = [{"tool": "group_compare.compare", "p_value": 0.04, "correction": "bonferroni"}
             for _ in range(8)]
    assert check_multiple_comparisons(trace) is None


def test_simpsons_detected_when_pooled_flips_stratified(simpsons_df) -> None:
    payload = {"coefficient": np.corrcoef(simpsons_df["x"], simpsons_df["y"])[0, 1],
               "x": "x", "y": "y"}
    result = check_simpsons_paradox(payload, frame=simpsons_df,
                                    stratify_candidates=("stratum",))
    assert result is not None
    assert result.code == "simpsons_flip"
    assert result.severity == "FAIL"


def test_simpsons_not_flagged_when_direction_stable() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 500)
    y = 0.8 * x + rng.normal(0, 0.2, 500)
    df = pd.DataFrame({"x": x, "y": y, "segment": (["A", "B"] * 250)})
    payload = {"coefficient": np.corrcoef(x, y)[0, 1], "x": "x", "y": "y"}
    assert check_simpsons_paradox(payload, frame=df,
                                  stratify_candidates=("segment",)) is None


def test_confounder_risk_on_causal_claim_without_controls() -> None:
    payload = {"partial_on": []}
    result = check_confounder_risk(payload, claim_text="X drives Y")
    assert result is not None
    assert result.severity == "WARN"


def test_confounder_risk_absent_when_partial_on_present() -> None:
    payload = {"partial_on": ["z"]}
    assert check_confounder_risk(payload, claim_text="X drives Y") is None


def test_confounder_risk_absent_on_correlational_claim() -> None:
    payload = {"partial_on": []}
    assert check_confounder_risk(payload, claim_text="X and Y are associated") is None


def test_stationarity_check_warns_on_non_stationary_inputs_without_detrend(seasonal_240) -> None:
    s = seasonal_240
    result = check_stationarity_for_spurious(
        {"detrend": None},
        x_series=s.to_numpy(), y_series=s.to_numpy() + 1,
    )
    assert result is not None
    assert result.severity == "WARN"
    assert "non_stationarity" in result.gotcha_refs


def test_leakage_detects_future_feature_timestamp() -> None:
    payload = {"as_of": "2024-06-01", "feature_timestamps_max": "2024-07-15"}
    result = check_leakage(payload)
    assert result is not None
    assert result.severity == "WARN"
    assert "look_ahead_bias" in result.gotcha_refs


def test_leakage_clean_when_feature_le_as_of() -> None:
    payload = {"as_of": "2024-06-01", "feature_timestamps_max": "2024-05-15"}
    assert check_leakage(payload) is None
