# backend/app/harness/tests/test_skill_tools.py
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip(
    "ruptures", reason="time-series skills require ruptures — skipped outside full dev env"
)

from app.harness.dispatcher import ToolDispatcher  # noqa: E402
from app.harness.skill_tools import register_core_tools  # noqa: E402


def test_register_core_tools_wires_all_expected_names() -> None:
    disp = ToolDispatcher()
    artifact_store = MagicMock()
    wiki = MagicMock()
    sandbox = MagicMock()
    register_core_tools(
        dispatcher=disp, artifact_store=artifact_store, wiki=wiki, sandbox=sandbox,
        session_id="s1",
    )
    for name in [
        "skill",
        "sandbox.run",
        "save_artifact", "update_artifact", "get_artifact",
        "write_working", "promote_finding",
        "correlation.correlate",
        "group_compare.compare",
        "stat_validate.validate",
        "time_series.characterize",
        "time_series.decompose",
        "time_series.find_anomalies",
        "time_series.find_changepoints",
        "time_series.lag_correlate",
        "distribution_fit.fit",
        "data_profiler.profile",
    ]:
        assert disp.has(name), f"missing tool: {name}"


def _fake_registry(node) -> MagicMock:
    reg = MagicMock()
    reg.get_skill.return_value = node
    reg.get_breadcrumb.return_value = ["root", node.metadata.name] if node else []
    reg.get_children.return_value = []
    reg.list_skills.return_value = ["foo", "bar"]
    return reg


def _fake_node(name: str = "foo") -> SimpleNamespace:
    meta = SimpleNamespace(
        name=name,
        version="1.0",
        description="desc",
        dependencies_requires=(),
        dependencies_used_by=(),
        dependencies_packages=(),
        error_templates={},
    )
    return SimpleNamespace(
        metadata=meta,
        instructions="hello",
        depth=2,
        package_path=None,
    )


def test_skill_load_emits_telemetry(monkeypatch, tmp_path: Path) -> None:
    disp = ToolDispatcher()
    node = _fake_node("foo")
    registry = _fake_registry(node)

    log_path = tmp_path / "skills.jsonl"
    from app.telemetry import skills_log

    monkeypatch.setattr(skills_log, "_default_path", lambda: log_path)

    register_core_tools(
        dispatcher=disp,
        artifact_store=MagicMock(),
        wiki=MagicMock(),
        sandbox=MagicMock(),
        session_id="s1",
        registry=registry,
    )
    result = disp.dispatch("skill", {"name": "foo"})
    assert result["name"] == "foo"

    assert log_path.exists()
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["actor"] == "skill:foo"
    assert rec["outcome"] == "ok"
    assert rec["detail"]["action"] == "load"
    assert rec["detail"]["depth"] == 2
    assert rec["detail"]["has_package"] is False


def test_skill_load_not_found_emits_error_and_raises(
    monkeypatch, tmp_path: Path
) -> None:
    disp = ToolDispatcher()
    registry = MagicMock()
    registry.get_skill.return_value = None
    registry.list_skills.return_value = ["alpha"]

    log_path = tmp_path / "skills.jsonl"
    from app.telemetry import skills_log

    monkeypatch.setattr(skills_log, "_default_path", lambda: log_path)

    register_core_tools(
        dispatcher=disp,
        artifact_store=MagicMock(),
        wiki=MagicMock(),
        sandbox=MagicMock(),
        session_id="s1",
        registry=registry,
    )
    with pytest.raises(KeyError):
        disp.dispatch("skill", {"name": "missing"})

    rec = json.loads(log_path.read_text().splitlines()[0])
    assert rec["outcome"] == "error"
    assert rec["actor"] == "skill:missing"
    assert rec["detail"]["reason"] == "not_found"


def test_skill_load_still_works_when_telemetry_fails(
    monkeypatch, tmp_path: Path
) -> None:
    disp = ToolDispatcher()
    node = _fake_node("foo")
    registry = _fake_registry(node)

    # Point telemetry at a path that cannot be written (parent is a file).
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    from app.telemetry import skills_log

    monkeypatch.setattr(
        skills_log, "_default_path", lambda: blocker / "skills.jsonl"
    )

    register_core_tools(
        dispatcher=disp,
        artifact_store=MagicMock(),
        wiki=MagicMock(),
        sandbox=MagicMock(),
        session_id="s1",
        registry=registry,
    )
    result = disp.dispatch("skill", {"name": "foo"})
    assert result["name"] == "foo"  # telemetry failure did not break load
