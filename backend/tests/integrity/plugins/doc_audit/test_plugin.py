from datetime import date
from pathlib import Path

from backend.app.integrity.plugins.doc_audit.plugin import DocAuditPlugin
from backend.app.integrity.protocol import ScanContext
from backend.app.integrity.schema import GraphSnapshot


def _empty_graph(repo_root: Path) -> None:
    g = repo_root / "graphify"
    g.mkdir(parents=True, exist_ok=True)
    (g / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")


def test_plugin_runs_with_no_docs_and_no_rules_registered(tmp_path: Path):
    _empty_graph(tmp_path)
    cfg = {
        "doc_roots": ["docs/**/*.md"],
        "excluded_paths": [],
        "claude_ignore_file": ".claude-ignore",
        "seed_docs": ["CLAUDE.md"],
        "thresholds": {"stale_days": 90},
        "coverage_required": [],
        "rename_lookback": "30.days.ago",
        "disabled_rules": [],
    }
    plugin = DocAuditPlugin(config=cfg, today=date(2026, 4, 17), rules={})
    ctx = ScanContext(repo_root=tmp_path, graph=GraphSnapshot.load(tmp_path))
    result = plugin.scan(ctx)

    assert result.plugin_name == "doc_audit"
    assert result.plugin_version == "1.0.0"
    assert result.issues == []
    assert result.failures == []
    artifact = tmp_path / "integrity-out" / "2026-04-17" / "doc_audit.json"
    assert artifact.exists()
    assert artifact in result.artifacts


def test_plugin_catches_rule_exception(tmp_path: Path):
    _empty_graph(tmp_path)
    cfg = {
        "doc_roots": [],
        "excluded_paths": [],
        "claude_ignore_file": ".claude-ignore",
        "seed_docs": ["CLAUDE.md"],
        "thresholds": {"stale_days": 90},
        "coverage_required": [],
        "rename_lookback": "30.days.ago",
        "disabled_rules": [],
    }

    def boom(ctx, plugin_cfg, today):
        raise RuntimeError("boom")

    plugin = DocAuditPlugin(
        config=cfg, today=date(2026, 4, 17), rules={"doc.boom": boom}
    )
    ctx = ScanContext(repo_root=tmp_path, graph=GraphSnapshot.load(tmp_path))
    result = plugin.scan(ctx)

    assert any(i.severity == "ERROR" and i.rule == "doc.boom" for i in result.issues)
    assert any("doc.boom" in f and "RuntimeError" in f for f in result.failures)


def test_plugin_skips_disabled_rules(tmp_path: Path):
    _empty_graph(tmp_path)
    cfg = {
        "doc_roots": [],
        "excluded_paths": [],
        "claude_ignore_file": ".claude-ignore",
        "seed_docs": ["CLAUDE.md"],
        "thresholds": {"stale_days": 90},
        "coverage_required": [],
        "rename_lookback": "30.days.ago",
        "disabled_rules": ["doc.boom"],
    }
    called = {"count": 0}

    def boom(ctx, plugin_cfg, today):
        called["count"] += 1
        raise RuntimeError("boom")

    plugin = DocAuditPlugin(
        config=cfg, today=date(2026, 4, 17), rules={"doc.boom": boom}
    )
    plugin.scan(ScanContext(repo_root=tmp_path, graph=GraphSnapshot.load(tmp_path)))
    assert called["count"] == 0
