from __future__ import annotations

import dataclasses

import pytest

from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    CostEstimate,
    PassEstimate,
    Proposal,
    RunResult,
)


def test_proposal_is_frozen_and_serializable() -> None:
    p = Proposal(
        pass_name="extract",
        section="claims",
        line="foo",
        action={"type": "promote_claim"},
        input_refs=["src-1"],
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.001,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.pass_name = "other"  # type: ignore[misc]

    data = dataclasses.asdict(p)
    assert data["pass_name"] == "extract"
    assert data["origin"] == "gardener"
    assert data["action"] == {"type": "promote_claim"}
    assert data["input_refs"] == ["src-1"]


def test_proposal_equality() -> None:
    a = Proposal(pass_name="x", section="s", line="L", action={})
    b = Proposal(pass_name="x", section="s", line="L", action={})
    assert a == b


def test_budget_charge_accumulates() -> None:
    b = Budget(max_cost_usd_per_run=1.0, max_tokens_per_source=8000)
    b.charge(0.3, tokens=100)
    b.charge(0.4, tokens=200)
    assert b.spent_usd == pytest.approx(0.7)
    assert b.tokens_spent == 300
    assert b.remaining_usd() == pytest.approx(0.3)


def test_budget_raises_when_exceeded() -> None:
    b = Budget(max_cost_usd_per_run=0.50, max_tokens_per_source=8000)
    b.charge(0.40)
    with pytest.raises(BudgetExceeded):
        b.charge(0.20)


def test_cost_estimate_totals() -> None:
    est = CostEstimate(
        passes={
            "extract": PassEstimate(tokens=1000, cost_usd=0.01),
            "re_abstract": PassEstimate(tokens=500, cost_usd=0.005),
        }
    )
    assert est.total_tokens == 1500
    assert est.total_cost_usd == pytest.approx(0.015)


def test_run_result_defaults() -> None:
    r = RunResult(
        passes_run=["extract"],
        proposals_added=3,
        total_tokens=1200,
        total_cost_usd=0.02,
        duration_ms=420,
    )
    assert r.errors == []
