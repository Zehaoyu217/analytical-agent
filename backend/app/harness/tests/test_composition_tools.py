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
