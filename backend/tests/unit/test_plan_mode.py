"""Tests for Plan Mode (P22).

Plan Mode is a soft gate that tells the agent to plan only — no execution,
no artifact writes, no finding promotion. We enforce it two ways:

1. System prompt gains a "Plan Mode" section instructing the agent to stop
   and propose a plan instead of acting.
2. The tool catalog exposed to the LLM is narrowed to a read-only subset
   so accidental tool calls cannot mutate state even if the model forgets
   the prompt instruction.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.harness.clients.base import ToolSchema
from app.harness.injector import InjectorInputs, PreTurnInjector


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


class _StubGotchas:
    def as_injection(self) -> str:
        return ""


@pytest.fixture()
def injector(tmp_path: Path) -> PreTurnInjector:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("STATIC BASE PROMPT")
    return PreTurnInjector(
        prompt_path=prompt,
        wiki=_StubWiki(),
        skill_registry=_StubSkills(),
        gotcha_index=_StubGotchas(),
    )


def test_plan_mode_off_by_default(injector: PreTurnInjector) -> None:
    out = injector.build(InjectorInputs())
    assert "Plan Mode" not in out
    assert "PLAN MODE" not in out


def test_plan_mode_section_appears_when_enabled(injector: PreTurnInjector) -> None:
    out = injector.build(InjectorInputs(plan_mode=True))
    assert "## Plan Mode" in out
    lowered = out.lower()
    # Must tell the agent to stop short of execution.
    assert "do not execute" in lowered or "plan only" in lowered
    # Must mention the deliverable so the model knows what to produce.
    assert "todo_write" in lowered or "plan" in lowered


def test_plan_mode_section_overrides_budget_ordering(injector: PreTurnInjector) -> None:
    """Plan Mode is a high-salience instruction — it should come last so it
    sits adjacent to the assistant's next message (recency bias)."""
    out = injector.build(InjectorInputs(plan_mode=True))
    plan_idx = out.index("## Plan Mode")
    # Nothing that the injector itself emits should come after Plan Mode —
    # extras attached via `inputs.extras` are allowed to follow.
    assert "## Context Budget" not in out[plan_idx:]
    assert "## Skill Menu" not in out[plan_idx:]


def test_filter_tools_for_plan_mode_drops_mutating_tools() -> None:
    from app.api.chat_api import _CHAT_TOOLS, filter_tools_for_plan_mode

    filtered = filter_tools_for_plan_mode(_CHAT_TOOLS)
    names = {t.name for t in filtered}

    # These tools write state or run code — they MUST be dropped.
    assert "execute_python" not in names
    assert "save_artifact" not in names
    assert "promote_finding" not in names
    assert "delegate_subagent" not in names


def test_filter_tools_for_plan_mode_keeps_planning_tools() -> None:
    from app.api.chat_api import _CHAT_TOOLS, filter_tools_for_plan_mode

    filtered = filter_tools_for_plan_mode(_CHAT_TOOLS)
    names = {t.name for t in filtered}

    # Planning essentials — agent still needs these to plan effectively.
    assert "todo_write" in names
    assert "skill" in names
    assert "write_working" in names


def test_filter_tools_preserves_schemas() -> None:
    from app.api.chat_api import _CHAT_TOOLS, filter_tools_for_plan_mode

    filtered = filter_tools_for_plan_mode(_CHAT_TOOLS)
    for tool in filtered:
        assert isinstance(tool, ToolSchema)
        assert tool.name
        assert tool.description
        assert isinstance(tool.input_schema, dict)


def test_plan_mode_request_accepts_flag() -> None:
    from app.api.chat_api import ChatRequest

    req = ChatRequest(message="hello", plan_mode=True)
    assert req.plan_mode is True

    default = ChatRequest(message="hello")
    assert default.plan_mode is False
