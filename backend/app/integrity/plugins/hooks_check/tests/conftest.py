"""Synthetic mini-repo fixture for Plugin D tests.

Matches the spec's testing matrix: 3 hooks, 3 coverage rules.

Hooks:
  - PostToolUse Write|Edit `echo ok` (satisfies rule a)
  - PostToolUse Write|Edit `false` (satisfies rule b but exits 1 → broken)
  - UserPromptSubmit (no matcher) `sb inject ...` (no rule justifies →
    tolerated suppresses unused)

Coverage rules:
  - a: PostToolUse Write|Edit substring=ok          (satisfied)
  - b: PostToolUse Write|Edit substring=false       (satisfied but broken)
  - c: PostToolUse Write|Edit substring=mypy        (missing — no hook contains 'mypy')
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


@pytest.fixture
def tiny_repo_with_hooks(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    _write(repo, "config/integrity.yaml",
           "plugins:\n"
           "  hooks_check:\n"
           "    enabled: true\n"
           "    coverage_path: 'config/hooks_coverage.yaml'\n"
           "    settings_path: '.claude/settings.json'\n"
           "    dry_run_timeout_seconds: 10\n"
           "    tolerated:\n"
           "      - sb inject\n"
           "    disabled_rules: []\n")

    _write(repo, "config/hooks_coverage.yaml",
           "rules:\n"
           "  - id: a_satisfied\n"
           "    description: green hook\n"
           "    when: {paths: ['*.py']}\n"
           "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: ok}\n"
           "  - id: b_broken\n"
           "    description: matched but exits 1\n"
           "    when: {paths: ['*.py']}\n"
           "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: 'false'}\n"  # noqa: E501
           "  - id: c_missing\n"
           "    description: no hook ever matches\n"
           "    when: {paths: ['*.py']}\n"
           "    requires_hook: {event: PostToolUse, matcher: 'Write|Edit', command_substring: mypy}\n"  # noqa: E501
           "tolerated:\n"
           "  - sb inject\n")

    _write(repo, ".claude/settings.json", json.dumps({
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "echo ok"},
                ]},
                {"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": "false"},
                ]},
            ],
            "UserPromptSubmit": [
                {"hooks": [
                    {"type": "command", "command": "sb inject --k 5"},
                ]},
            ],
        },
    }, indent=2))

    _write(repo, "graphify/graph.json", json.dumps({"nodes": [], "links": []}))
    _write(repo, "graphify/graph.augmented.json", json.dumps({"nodes": [], "links": []}))

    return repo
