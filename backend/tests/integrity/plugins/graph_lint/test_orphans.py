from __future__ import annotations

from backend.app.integrity.plugins.graph_lint.orphans import find_orphans
from backend.app.integrity.schema import GraphSnapshot


def make(nodes, links):
    return GraphSnapshot(nodes=nodes, links=links)


def test_returns_node_with_no_inbound_extracted():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[],
    )
    assert find_orphans(g) == ["a", "b"]


def test_excludes_nodes_with_inbound_extracted():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[
            {"source": "a", "target": "b", "relation": "calls", "confidence": "EXTRACTED"},
        ],
    )
    assert find_orphans(g) == ["a"]


def test_ignores_inferred_edges():
    g = make(
        nodes=[
            {"id": "a", "label": "a", "file_type": "code", "source_file": "backend/app/x.py"},
            {"id": "b", "label": "b", "file_type": "code", "source_file": "backend/app/y.py"},
        ],
        links=[
            {"source": "a", "target": "b", "relation": "calls", "confidence": "INFERRED"},
        ],
    )
    assert "b" in find_orphans(g)


def test_excludes_test_files_and_entry_points():
    g = make(
        nodes=[
            {
                "id": "main_app", "label": "main",
                "file_type": "code", "source_file": "backend/app/main.py",
            },
            {
                "id": "x_test_a", "label": "test_a",
                "file_type": "code", "source_file": "backend/tests/x_test.py",
            },
            {
                "id": "init_x", "label": "x",
                "file_type": "code", "source_file": "backend/app/x/__init__.py",
            },
        ],
        links=[],
    )
    assert find_orphans(g) == []


def test_excludes_non_code_file_types():
    g = make(
        nodes=[
            {"id": "doc", "label": "doc", "file_type": "document", "source_file": "docs/x.md"},
        ],
        links=[],
    )
    assert find_orphans(g) == []
