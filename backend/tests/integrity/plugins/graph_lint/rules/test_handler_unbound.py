from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from backend.app.integrity.plugins.graph_lint.rules import handler_unbound
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_emits_for_handler_without_routes_to(repo: Path):
    nodes = [
        {"id": "x_get_users", "label": "get_users", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["x_get_users"]


def test_skips_handler_with_routes_to_edge(repo: Path):
    nodes = [
        {"id": "route_get_users", "label": "GET /users", "file_type": "code",
         "source_file": "backend/app/api/x.py"},
        {"id": "x_get_users", "label": "get_users", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    links = [{"source": "route_get_users", "target": "x_get_users", "relation": "routes_to", "confidence": "EXTRACTED"}]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=links))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_skips_underscore_prefixed_functions(repo: Path):
    nodes = [
        {"id": "x__internal_helper", "label": "_internal_helper", "file_type": "code",
         "source_file": "backend/app/api/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_skips_non_api_paths(repo: Path):
    nodes = [
        {"id": "x_helper", "label": "helper", "file_type": "code",
         "source_file": "backend/app/lib/x.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert issues == []


def test_includes_harness_paths(repo: Path):
    nodes = [
        {"id": "h_run", "label": "run", "file_type": "code",
         "source_file": "backend/app/harness/h.py", "kind": "function"},
    ]
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=nodes, links=[]))
    issues = handler_unbound.run(ctx, {}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["h_run"]
