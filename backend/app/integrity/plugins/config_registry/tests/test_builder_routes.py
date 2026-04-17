"""Tests for RoutesBuilder."""
from __future__ import annotations

from pathlib import Path

from backend.app.integrity.plugins.config_registry.builders.routes import (
    RouteEntry,
    RoutesBuilder,
)
from backend.app.integrity.schema import GraphSnapshot


def test_re_exports_three_routes(tiny_repo: Path) -> None:
    graph = GraphSnapshot.load(tiny_repo)
    builder = RoutesBuilder(graph=graph)
    entries, failures = builder.build()
    ids = sorted(e.id for e in entries)
    assert ids == [
        "route::DELETE::/api/legacy",
        "route::GET::/api/health",
        "route::POST::/api/trace",
    ]
    assert failures == []


def test_route_entry_fields(tiny_repo: Path) -> None:
    graph = GraphSnapshot.load(tiny_repo)
    builder = RoutesBuilder(graph=graph)
    entries, _ = builder.build()
    by_id = {e.id: e for e in entries}
    trace = by_id["route::POST::/api/trace"]
    assert trace.method == "POST"
    assert trace.path == "/api/trace"
    assert trace.source_file == "backend/app/api/foo_api.py"
    assert trace.source_location == 5
    assert trace.extractor == "fastapi_routes"


def test_absent_graph_yields_empty_with_failure() -> None:
    """Empty snapshot (no routes, no nodes) → empty entries + graph-absent failure."""
    graph = GraphSnapshot(nodes=[], links=[])
    builder = RoutesBuilder(graph=graph)
    entries, failures = builder.build()
    assert entries == []
    assert any("graph" in f.lower() for f in failures)
