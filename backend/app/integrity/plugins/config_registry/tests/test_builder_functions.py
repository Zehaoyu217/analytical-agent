"""Tests for FunctionsBuilder (AST-based)."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.builders.functions import (
    FunctionEntry,
    FunctionsBuilder,
)


def test_extracts_router_decorators(tiny_repo: Path) -> None:
    builder = FunctionsBuilder(
        repo_root=tiny_repo,
        search_globs=["backend/app/api/**/*.py"],
        decorators=["router", "app", "api_router"],
        event_handlers=["startup", "shutdown", "lifespan"],
    )
    entries, failures = builder.build()
    by_id = {e.id: e for e in entries}
    assert "backend.app.api.foo_api.trace_endpoint" in by_id
    trace = by_id["backend.app.api.foo_api.trace_endpoint"]
    assert trace.decorator == "router.post"
    assert trace.target == "/api/trace"
    assert trace.path == "backend/app/api/foo_api.py"
    assert failures == []


def test_extracts_on_event(tiny_repo: Path) -> None:
    builder = FunctionsBuilder(
        repo_root=tiny_repo,
        search_globs=["backend/app/main.py"],
        decorators=["router", "app", "api_router"],
        event_handlers=["startup", "shutdown", "lifespan"],
    )
    entries, _ = builder.build()
    by_id = {e.id: e for e in entries}
    assert "backend.app.main.startup" in by_id
    startup = by_id["backend.app.main.startup"]
    assert startup.decorator == "app.on_event"
    assert startup.target == "startup"


def test_undecorated_function_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "backend/app/api/x.py"
    src.parent.mkdir(parents=True)
    src.write_text("def plain(): pass\n")
    builder = FunctionsBuilder(
        repo_root=repo, search_globs=["backend/app/api/**/*.py"],
        decorators=["router", "app"], event_handlers=["startup"],
    )
    entries, failures = builder.build()
    assert entries == []
    assert failures == []


def test_syntax_error_yields_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src = repo / "backend/app/api/bad.py"
    src.parent.mkdir(parents=True)
    src.write_text("def x(:\n  pass\n")  # syntax error
    builder = FunctionsBuilder(
        repo_root=repo, search_globs=["backend/app/api/**/*.py"],
        decorators=["router"], event_handlers=[],
    )
    entries, failures = builder.build()
    assert entries == []
    assert any("bad.py" in f for f in failures)


def test_empty_search_globs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    builder = FunctionsBuilder(
        repo_root=repo, search_globs=[], decorators=["router"], event_handlers=[],
    )
    entries, failures = builder.build()
    assert entries == []
    assert failures == []
