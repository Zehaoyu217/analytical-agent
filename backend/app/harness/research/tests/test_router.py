from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.harness.research.router import RoutingAgent
from app.harness.research.types import RoutePlan


def _mock_api(json_content: dict) -> MagicMock:
    mock_api = MagicMock()
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = json.dumps(json_content)
    mock_msg.content = [mock_block]
    mock_api.messages.create.return_value = mock_msg
    return mock_api


def test_route_parallel_query():
    plan_json = {
        "modules": ["papers", "code"],
        "sub_queries": {"papers": "calibration methods", "code": "calibration sklearn"},
        "budgets": {"papers": 90_000, "code": 60_000},
        "parallel_ok": True,
        "rationale": "independent queries",
    }
    router = RoutingAgent(api_client=_mock_api(plan_json))
    plan = router.route(
        query="isotonic calibration LightGBM",
        context="",
        sources=["papers", "code", "web"],
        budget_tokens=150_000,
    )
    assert isinstance(plan, RoutePlan)
    assert plan.parallel_ok is True
    assert "papers" in plan.modules
    assert plan.budgets["papers"] == 90_000


def test_route_falls_back_on_invalid_json():
    mock_api = MagicMock()
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "not valid json at all"
    mock_msg.content = [mock_block]
    mock_api.messages.create.return_value = mock_msg

    router = RoutingAgent(api_client=mock_api)
    plan = router.route(
        query="test", context="", sources=["papers", "code"], budget_tokens=100_000,
    )
    assert set(plan.modules) == {"papers", "code"}
    assert plan.parallel_ok is True


def test_route_falls_back_on_api_error():
    mock_api = MagicMock()
    mock_api.messages.create.side_effect = Exception("API error")

    router = RoutingAgent(api_client=mock_api)
    plan = router.route(
        query="test", context="", sources=["papers"], budget_tokens=50_000,
    )
    assert "papers" in plan.modules
    assert plan.budgets["papers"] == 50_000


def test_budget_not_allocated_to_unselected_modules():
    plan_json = {
        "modules": ["papers"],
        "sub_queries": {"papers": "distribution shift finance"},
        "budgets": {"papers": 150_000},
        "parallel_ok": True,
        "rationale": "papers only",
    }
    router = RoutingAgent(api_client=_mock_api(plan_json))
    plan = router.route("finance", "", ["papers", "code", "web"], 150_000)
    assert "code" not in plan.modules
    assert "web" not in plan.modules


def test_route_plan_modules_is_tuple():
    plan_json = {
        "modules": ["papers", "code"],
        "sub_queries": {"papers": "q1", "code": "q2"},
        "budgets": {"papers": 75_000, "code": 75_000},
        "parallel_ok": True,
        "rationale": "test",
    }
    router = RoutingAgent(api_client=_mock_api(plan_json))
    plan = router.route("q", "", ["papers", "code"], 150_000)
    assert isinstance(plan.modules, tuple)
