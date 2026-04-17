from datetime import date
from pathlib import Path

import pytest
from backend.app.integrity.plugins.graph_lint.rules import orphan_growth
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def make_orphans(n: int) -> list[dict]:
    return [
        {"id": f"orphan_{i}", "label": f"o{i}", "file_type": "code",
         "source_file": f"backend/app/o{i}.py", "kind": "function"}
        for i in range(n)
    ]


def test_emit_when_orphans_grow_more_than_20pct(repo: Path):
    write_snapshot(repo, {"nodes": make_orphans(10), "links": []}, today=date(2026, 4, 10))
    today_graph = GraphSnapshot(nodes=make_orphans(13), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.orphan_growth"


def test_no_emit_when_growth_under_threshold(repo: Path):
    write_snapshot(repo, {"nodes": make_orphans(10), "links": []}, today=date(2026, 4, 10))
    today_graph = GraphSnapshot(nodes=make_orphans(11), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert issues == []


def test_no_baseline_emits_info(repo: Path):
    today_graph = GraphSnapshot(nodes=make_orphans(5), links=[])
    ctx = ScanContext(repo_root=repo, graph=today_graph)
    issues = orphan_growth.run(ctx, {"thresholds": {"orphan_growth_pct": 20}}, date(2026, 4, 17))
    assert len(issues) == 1
    assert issues[0].rule == "graph.orphan_growth.no_baseline"
