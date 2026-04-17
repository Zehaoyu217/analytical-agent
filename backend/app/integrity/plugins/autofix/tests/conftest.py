"""Synthetic mini-repo + integrity-out fixture for Plugin F tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write(*args: object) -> None:
    """_write(repo, rel, content) or _write(absolute_path, content)."""
    if len(args) == 3:
        repo, rel, content = args
        p = repo / rel  # type: ignore[operator]
    elif len(args) == 2:
        p, content = args  # type: ignore[assignment]
    else:
        raise TypeError(f"_write expected 2 or 3 args, got {len(args)}")
    assert isinstance(p, Path)
    assert isinstance(content, str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


@pytest.fixture
def tiny_repo_with_artifacts(tmp_path: Path) -> Path:
    """Repo + integrity-out/2026-04-17/ with all 4 sibling artifacts present."""
    repo = tmp_path / "repo"
    repo.mkdir()

    _write(repo, "CLAUDE.md", "# Project\n\n## Deeper Context\n\n- [Existing](docs/existing.md)\n")
    _write(repo, "docs/existing.md", "# Existing\n")
    _write(repo, "docs/foo.md", "# Foo\n\nbody\n")
    _write(repo, "config/manifest.yaml", "inputs: []\n")
    _write(repo, "graphify/graph.json", json.dumps({"nodes": [], "links": []}))
    _write(repo, "graphify/graph.augmented.json", json.dumps({"nodes": [], "links": []}))

    out = repo / "integrity-out" / "2026-04-17"
    _write(out / "doc_audit.json", json.dumps({
        "plugin": "doc_audit",
        "issues": [
            {"rule": "doc.unindexed",
             "evidence": {"path": "docs/foo.md"},
             "severity": "WARN",
             "node_id": "docs/foo.md", "location": "docs/foo.md",
             "message": "docs/foo.md not indexed",
             "fix_class": None, "first_seen": ""},
        ],
    }))
    _write(out / "config_registry.json", json.dumps({
        "plugin": "config_registry", "issues": [],
    }))
    _write(out / "graph_lint.json", json.dumps({
        "plugin": "graph_lint", "issues": [],
    }))
    _write(out / "report.json", json.dumps({
        "date": "2026-04-17", "issue_total": 1,
        "by_severity": {"WARN": 1, "INFO": 0, "ERROR": 0, "CRITICAL": 0},
        "plugins": {"doc_audit": {"issues": 1, "rules_run": ["doc.unindexed"]}},
    }))

    return repo
