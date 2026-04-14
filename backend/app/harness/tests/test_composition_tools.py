# backend/app/harness/tests/test_composition_tools.py
from __future__ import annotations


def test_analysis_plan_and_dashboard_tools_registered() -> None:
    from app.harness.dispatcher import ToolDispatcher
    from app.harness.skill_tools import register_core_tools

    disp = ToolDispatcher()
    register_core_tools(
        disp,
        artifact_store=None,  # type: ignore[arg-type]
        wiki=None,  # type: ignore[arg-type]
        sandbox=None,  # type: ignore[arg-type]
        session_id="test-session",
    )
    assert disp.has("analysis_plan.plan")
    assert disp.has("dashboard.build")
    assert disp.has("report.build")


def test_composition_tool_lambdas_accept_positional_dict(tmp_path, monkeypatch) -> None:
    """Regression test for lambda arity: dispatcher calls handler(dict), so the
    registered lambdas must accept one positional arg (not **kw)."""
    from app.harness.clients.base import ToolCall
    from app.harness.dispatcher import ToolDispatcher
    from app.harness.skill_tools import register_core_tools
    from app.skills.analysis_plan.pkg import plan as plan_mod

    monkeypatch.setattr(plan_mod, "WIKI_DIR", tmp_path / "wiki")

    disp = ToolDispatcher()
    register_core_tools(
        disp,
        artifact_store=None,  # type: ignore[arg-type]
        wiki=None,  # type: ignore[arg-type]
        sandbox=None,  # type: ignore[arg-type]
        session_id="test-session",
    )

    call = ToolCall(
        id="t1",
        name="analysis_plan.plan",
        arguments={"question": "Is X correlated with Y?", "depth": "quick"},
    )
    result = disp.dispatch(call)

    assert result.ok, f"dispatch failed: {result.error_message}"
    assert (tmp_path / "wiki" / "working.md").exists()
