"""Tests for the token-budget section injected into the system prompt (P21)."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.harness.injector import InjectorInputs, PreTurnInjector, TokenBudget


class _StubWiki:
    def working_digest(self) -> str:
        return ""

    def index_digest(self) -> str:
        return ""

    def latest_session_notes(self, exclude_session_id: str = "") -> str:
        return ""


class _StubSkills:
    def list_top_level(self) -> list:
        return []


@pytest.fixture()
def injector(tmp_path: Path) -> PreTurnInjector:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("STATIC BASE PROMPT")
    return PreTurnInjector(
        prompt_path=prompt,
        wiki=_StubWiki(),
        skill_registry=_StubSkills(),
    )


def test_budget_defaults_are_sane() -> None:
    budget = TokenBudget()
    assert budget.max_tokens == 200_000
    assert 0.0 < budget.compact_threshold < 1.0
    assert budget.char_budget > 0
    assert budget.keep_recent_tool_results >= 1


def test_budget_is_frozen() -> None:
    budget = TokenBudget()
    with pytest.raises(dataclasses.FrozenInstanceError):
        budget.max_tokens = 50_000  # type: ignore[misc]


def test_budget_section_absent_when_no_budget(injector: PreTurnInjector) -> None:
    out = injector.build(InjectorInputs())
    assert "Context Budget" not in out
    assert out.startswith("STATIC BASE PROMPT")


def test_budget_section_renders_numbers(injector: PreTurnInjector) -> None:
    budget = TokenBudget(
        max_tokens=200_000,
        compact_threshold=0.80,
        char_budget=40_000,
        keep_recent_tool_results=3,
    )
    out = injector.build(InjectorInputs(token_budget=budget))
    assert "## Context Budget" in out
    assert "200,000 tokens" in out
    assert "80% utilization" in out
    assert "40,000 chars" in out
    assert "last 3" in out
    assert "get_artifact" in out  # points agent at recovery path
    assert "save_artifact" in out  # steers agent toward artifact pattern


def test_budget_section_respects_custom_values(injector: PreTurnInjector) -> None:
    budget = TokenBudget(
        max_tokens=100_000,
        compact_threshold=0.5,
        char_budget=8_000,
        keep_recent_tool_results=1,
    )
    out = injector.build(InjectorInputs(token_budget=budget))
    assert "100,000 tokens" in out
    assert "50% utilization" in out
    assert "8,000 chars" in out
    assert "last 1" in out


def test_budget_section_ordering_follows_profile(injector: PreTurnInjector) -> None:
    """Budget section should appear after the Active Dataset Profile so the
    agent reads 'here is your data' before 'here is how much you can print.'"""
    budget = TokenBudget()
    out = injector.build(
        InjectorInputs(
            active_profile_summary="rows=10 cols=2",
            token_budget=budget,
        )
    )
    profile_idx = out.index("## Active Dataset Profile")
    budget_idx = out.index("## Context Budget")
    assert profile_idx < budget_idx
