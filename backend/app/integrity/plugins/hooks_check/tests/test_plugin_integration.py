"""Integration test — full plugin scan against tiny_repo_with_hooks."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.integrity.plugins.hooks_check.plugin import HooksCheckPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=[], links=[]))


def test_full_scan_against_tiny_repo(tiny_repo_with_hooks: Path) -> None:
    plugin = HooksCheckPlugin(
        config={
            "coverage_path": "config/hooks_coverage.yaml",
            "settings_path": ".claude/settings.json",
            "dry_run_timeout_seconds": 5,
            "tolerated": ["sb inject"],
            "disabled_rules": [],
        },
        today=date(2026, 4, 17),
    )
    result = plugin.scan(_ctx(tiny_repo_with_hooks))

    by_rule = {}
    for issue in result.issues:
        by_rule.setdefault(issue.rule, []).append(issue)

    assert len(by_rule.get("hooks.missing", [])) == 1
    assert by_rule["hooks.missing"][0].node_id == "c_missing"
    assert len(by_rule.get("hooks.broken", [])) == 1
    assert by_rule["hooks.broken"][0].node_id == "b_broken"
    assert by_rule.get("hooks.unused", []) == []


def test_plugin_writes_artifact(tiny_repo_with_hooks: Path) -> None:
    plugin = HooksCheckPlugin(
        config={"dry_run_timeout_seconds": 5, "tolerated": ["sb inject"]},
        today=date(2026, 4, 17),
    )
    result = plugin.scan(_ctx(tiny_repo_with_hooks))
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.exists()
    payload = json.loads(artifact.read_text())
    assert payload["plugin"] == "hooks_check"
    assert payload["date"] == "2026-04-17"
    assert "rules_run" in payload
    assert "coverage_summary" in payload
    assert payload["coverage_summary"]["rules_total"] == 3


def test_plugin_emits_error_when_coverage_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = HooksCheckPlugin(today=date(2026, 4, 17))
    result = plugin.scan(_ctx(repo))
    assert any(i.rule == "hooks.coverage_missing" for i in result.issues)
    assert any(i.severity == "ERROR" for i in result.issues)


def test_plugin_emits_error_on_settings_parse_error(tiny_repo_with_hooks: Path) -> None:
    settings = tiny_repo_with_hooks / ".claude" / "settings.json"
    settings.write_text("{not valid json")
    plugin = HooksCheckPlugin(
        config={"dry_run_timeout_seconds": 5, "tolerated": ["sb inject"]},
        today=date(2026, 4, 17),
    )
    result = plugin.scan(_ctx(tiny_repo_with_hooks))
    assert any(i.rule == "hooks.settings_parse" for i in result.issues)


def test_disabled_rules_are_skipped(tiny_repo_with_hooks: Path) -> None:
    plugin = HooksCheckPlugin(
        config={
            "dry_run_timeout_seconds": 5,
            "tolerated": ["sb inject"],
            "disabled_rules": ["hooks.broken"],
        },
        today=date(2026, 4, 17),
    )
    result = plugin.scan(_ctx(tiny_repo_with_hooks))
    rules_seen = {i.rule for i in result.issues}
    assert "hooks.broken" not in rules_seen


def test_per_rule_failure_is_caught_and_reported(
    tiny_repo_with_hooks: Path, monkeypatch
) -> None:
    """If a rule raises, plugin emits ERROR issue and siblings continue."""

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic")

    plugin = HooksCheckPlugin(
        config={"dry_run_timeout_seconds": 5, "tolerated": ["sb inject"]},
        today=date(2026, 4, 17),
        rules={
            "hooks.missing": boom,
            "hooks.broken": __import__(
                "backend.app.integrity.plugins.hooks_check.rules.broken",
                fromlist=["run"],
            ).run,
            "hooks.unused": __import__(
                "backend.app.integrity.plugins.hooks_check.rules.unused",
                fromlist=["run"],
            ).run,
        },
    )
    result = plugin.scan(_ctx(tiny_repo_with_hooks))
    error_issues = [i for i in result.issues if i.severity == "ERROR"]
    assert any(i.rule == "hooks.missing" and "synthetic" in i.message for i in error_issues)
    broken_issues = [i for i in result.issues if i.rule == "hooks.broken"]
    assert len(broken_issues) == 1
