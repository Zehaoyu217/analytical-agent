from datetime import date
from pathlib import Path

import pytest
from backend.app.integrity.plugins.graph_lint.rules import density_drop
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot
from backend.app.integrity.snapshots import write_snapshot


def make_module(name: str, num_nodes: int, num_edges: int) -> tuple[list[dict], list[dict]]:
    nodes = [
        {"id": f"{name}_n{i}", "source_file": f"backend/app/{name}.py", "kind": "function"}
        for i in range(num_nodes)
    ]
    links = []
    for i in range(num_edges):
        a, b = f"{name}_n{i % num_nodes}", f"{name}_n{(i + 1) % num_nodes}"
        links.append({"source": a, "target": b, "relation": "calls", "confidence": "EXTRACTED"})
    return nodes, links


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_emits_when_density_drops_more_than_25pct(repo: Path):
    week_nodes, week_links = make_module("m", 10, 20)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("m", 10, 10)  # density: 1.0 vs 2.0 → 50% drop
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert len(issues) == 1
    assert "backend/app/m.py" in issues[0].location


def test_no_emit_when_drop_under_threshold(repo: Path):
    week_nodes, week_links = make_module("m", 10, 20)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("m", 10, 18)  # 10% drop
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert issues == []


def test_skips_small_modules(repo: Path):
    week_nodes, week_links = make_module("tiny", 4, 8)
    write_snapshot(repo, {"nodes": week_nodes, "links": week_links}, today=date(2026, 4, 10))
    today_nodes, today_links = make_module("tiny", 4, 0)
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert issues == []


def test_no_baseline_emits_info(repo: Path):
    today_nodes, today_links = make_module("m", 10, 10)
    ctx = ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=today_nodes, links=today_links))
    issues = density_drop.run(
        ctx, {"thresholds": {"density_drop_pct": 25, "module_min_nodes": 5}}, date(2026, 4, 17)
    )
    assert len(issues) == 1
    assert issues[0].rule == "graph.density_drop.no_baseline"
