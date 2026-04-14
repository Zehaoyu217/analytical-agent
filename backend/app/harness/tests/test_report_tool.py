# backend/app/harness/tests/test_report_tool.py
from __future__ import annotations


def test_report_build_tool_registered() -> None:
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
    assert disp.has("report.build")
