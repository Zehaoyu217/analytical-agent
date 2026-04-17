from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from backend.app.integrity.plugins.graph_lint.rules import drift
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_drift_added_emits_for_new_node(repo: Path):
    yesterday = {"nodes": [{"id": "old", "source_file": "x.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "old", "source_file": "x.py"}, {"id": "new", "source_file": "y.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = drift.run_added(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["new"]
    assert all(i.severity == "INFO" for i in issues)


def test_drift_removed_emits_warn_for_removed_node(repo: Path):
    yesterday = {
        "nodes": [{"id": "old", "source_file": "x.py"}, {"id": "kept", "source_file": "y.py"}],
        "links": [],
    }
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "kept", "source_file": "y.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={}):
        issues = drift.run_removed(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.node_id for i in issues] == ["old"]
    assert all(i.severity == "WARN" for i in issues)


def test_drift_removed_downgrades_to_info_on_rename(repo: Path):
    yesterday = {"nodes": [{"id": "old_node", "source_file": "old/x.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(
        nodes=[{"id": "renamed_node", "source_file": "new/x.py"}],
        links=[],
    )
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={"old/x.py": "new/x.py"}):
        issues = drift.run_removed(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert [i.severity for i in issues] == ["INFO"]


def test_drift_excludes_test_paths(repo: Path):
    yesterday = {"nodes": [{"id": "old_test", "source_file": "tests/x_test.py"}], "links": []}
    write_snapshot(repo, yesterday, today=date(2026, 4, 16))
    today_graph = GraphSnapshot(nodes=[], links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    with patch.object(drift, "recent_renames", return_value={}):
        issues = drift.run_removed(ctx, {"excluded_paths": ["tests/**"]}, date(2026, 4, 17))
    assert issues == []


def test_drift_no_baseline_emits_info_once(repo: Path):
    today_graph = GraphSnapshot(nodes=[{"id": "x", "source_file": "x.py"}], links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = drift.run_added(ctx, {"excluded_paths": []}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.drift.no_baseline"
    assert issues[0].severity == "INFO"
