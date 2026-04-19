"""Acceptance-gate proof: 5 coverage rules, every rule satisfied, every hook green.

Runs against a synthetic fixture mirroring the §5 MVP shape (NOT the real repo —
that's tested in test_real_repo_acceptance via the Makefile target). The synthetic
fixture uses harmless `echo` commands containing the required substrings.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.integrity.plugins.hooks_check.plugin import HooksCheckPlugin
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot(nodes=[], links=[]))


@pytest.fixture
def synthetic_5_rule_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    coverage = (
        "rules:\n"
        "  - id: r1\n"
        "    description: ruff\n"
        "    when: {paths: ['*.py']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: ruff}\n"
        "  - id: r2\n"
        "    description: eslint\n"
        "    when: {paths: ['*.tsx']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: eslint}\n"  # noqa: E501
        "  - id: r3\n"
        "    description: doc_audit\n"
        "    when: {paths: ['*.md']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: doc_audit}\n"  # noqa: E501
        "  - id: r4\n"
        "    description: skill-check\n"
        "    when: {paths: ['*SKILL.md']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: skill-check}\n"  # noqa: E501
        "  - id: r5\n"
        "    description: integrity-config\n"
        "    when: {paths: ['*.toml']}\n"
        "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: integrity-config}\n"  # noqa: E501
        "tolerated: []\n"
    )
    (repo / "config").mkdir()
    (repo / "config" / "hooks_coverage.yaml").write_text(coverage)
    (repo / "config" / "integrity.yaml").write_text(
        "plugins:\n  hooks_check:\n    enabled: true\n"
    )

    settings = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo ruff-ok"},
                ]},
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo eslint-ok"},
                ]},
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo doc_audit-ok"},
                ]},
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo skill-check-ok"},
                ]},
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo integrity-config-ok"},
                ]},
            ],
        },
    }
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2))
    (repo / "graphify").mkdir()
    (repo / "graphify" / "graph.json").write_text('{"nodes":[],"links":[]}')
    (repo / "graphify" / "graph.augmented.json").write_text('{"nodes":[],"links":[]}')
    return repo


def test_acceptance_gate_all_satisfied(synthetic_5_rule_repo: Path) -> None:
    plugin = HooksCheckPlugin(
        config={"dry_run_timeout_seconds": 5, "tolerated": []},
        today=date(2026, 4, 17),
    )
    result = plugin.scan(_ctx(synthetic_5_rule_repo))

    by_rule: dict[str, list] = {}
    for issue in result.issues:
        by_rule.setdefault(issue.rule, []).append(issue)

    assert by_rule.get("hooks.missing", []) == [], (
        f"hooks.missing should be empty, got: "
        f"{[i.message for i in by_rule.get('hooks.missing', [])]}"
    )
    assert by_rule.get("hooks.broken", []) == [], (
        f"hooks.broken should be empty, got: "
        f"{[i.message for i in by_rule.get('hooks.broken', [])]}"
    )

    artifact = result.artifacts[0]
    payload = json.loads(artifact.read_text())
    assert payload["coverage_summary"]["rules_total"] == 5
    assert payload["coverage_summary"]["rules_satisfied"] == 5
    assert payload["coverage_summary"]["hooks_total"] == 5
    assert payload["coverage_summary"]["hooks_dry_run_green"] == 5
