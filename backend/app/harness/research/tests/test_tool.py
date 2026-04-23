from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.research.tool import RESEARCH_SCHEMAS, ResearchTool
from app.harness.research.types import (
    CodeResult,
    PapersResult,
    ResearchResult,
    RoutePlan,
    WebResult,
)


def _make_result(summary: str = "done") -> ResearchResult:
    return ResearchResult(
        summary=summary, papers=(), code_examples=(), web_refs=(),
        follow_up_questions=(), modules_ran=("papers",),
        total_ms=100, budget_tokens_used=150_000,
    )


def _make_plan(modules: tuple[str, ...] = ("papers",), parallel_ok: bool = True) -> RoutePlan:
    return RoutePlan(
        modules=modules,
        sub_queries={m: "test" for m in modules},
        budgets={m: 50_000 for m in modules},
        parallel_ok=parallel_ok,
        rationale="test",
    )


def _tool_with_mocks() -> ResearchTool:
    tool = ResearchTool.__new__(ResearchTool)
    tool._routing_agent = MagicMock()
    tool._routing_agent.route.return_value = _make_plan()
    tool._papers_module = MagicMock()
    tool._papers_module.run.return_value = PapersResult()
    tool._code_module = MagicMock()
    tool._code_module.run.return_value = CodeResult()
    tool._web_module = MagicMock()
    tool._web_module.run.return_value = WebResult()
    tool._synthesis_agent = MagicMock()
    tool._synthesis_agent.synthesise.return_value = _make_result()
    tool._jobs = MagicMock()
    return tool


def test_schemas_define_three_tools():
    names = [s.name for s in RESEARCH_SCHEMAS]
    assert "research" in names
    assert "research_start" in names
    assert "research_get" in names


def test_execute_clamps_budget_over_1m():
    tool = _tool_with_mocks()
    result = tool.execute(
        query="test", context="", sources=["papers"], budget_tokens=2_000_000,
    )
    assert result.budget_warning is not None
    assert "1,000,000" in result.budget_warning


def test_execute_returns_research_result():
    tool = _tool_with_mocks()
    tool._synthesis_agent.synthesise.return_value = _make_result("calibration summary")
    result = tool.execute(
        query="calibration", context="", sources=["papers"], budget_tokens=150_000,
    )
    assert result.summary == "calibration summary"


def test_start_returns_job_id():
    tool = _tool_with_mocks()
    tool._jobs.create.return_value = "job-123"

    payload = tool.start(query="test", context="", sources=["papers"], budget_tokens=50_000)
    assert payload["job_id"] == "job-123"
    assert "estimated_seconds" in payload


def test_get_delegates_to_registry():
    tool = _tool_with_mocks()
    tool._jobs.get.return_value = {"status": "running", "progress": {}}

    result = tool.get("job-abc")
    assert result["status"] == "running"
    tool._jobs.get.assert_called_once_with("job-abc")


def test_handle_research_returns_dict():
    tool = _tool_with_mocks()
    tool._synthesis_agent.synthesise.return_value = _make_result("done")
    result = tool.handle_research({"query": "test", "sources": ["papers"]})
    assert isinstance(result, dict)
    assert result["summary"] == "done"


def test_register_research_tools_adds_three_handlers():
    from app.harness.dispatcher import ToolDispatcher
    from app.harness.research.tool import register_research_tools

    disp = ToolDispatcher()
    register_research_tools(disp)

    assert disp.has("research")
    assert disp.has("research_start")
    assert disp.has("research_get")
