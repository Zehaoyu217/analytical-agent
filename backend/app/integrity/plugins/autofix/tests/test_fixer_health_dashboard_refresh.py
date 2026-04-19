"""Tests for health_dashboard_refresh fixer."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.autofix.fixers.health_dashboard_refresh import propose
from app.integrity.plugins.autofix.loader import SiblingArtifacts


def _aggregate(date_iso: str = "2026-04-17", issue_count: int = 3) -> dict:
    return {
        "date": date_iso,
        "issue_total": issue_count,
        "by_severity": {"INFO": 1, "WARN": 1, "ERROR": 1},
        "plugins": {
            "graph_lint": {"issues": 1, "rules_run": ["lint.dead"]},
            "doc_audit": {"issues": 1, "rules_run": ["doc.broken_link"]},
            "config_registry": {"issues": 1, "rules_run": ["config.added"]},
        },
    }


def test_missing_aggregate_returns_empty(tmp_path: Path) -> None:
    artifacts = SiblingArtifacts(
        doc_audit={}, config_registry={}, graph_lint={},
        aggregate=None, failures={"aggregate": "missing"},
    )
    assert propose(artifacts, tmp_path, {}) == []


def test_emits_diff_when_dashboard_changed(tmp_path: Path) -> None:
    health = tmp_path / "docs" / "health"
    health.mkdir(parents=True, exist_ok=True)
    (health / "latest.md").write_text("# stale\n")
    (health / "trend.md").write_text("# stale\n")

    artifacts = SiblingArtifacts(
        doc_audit={}, config_registry={}, graph_lint={},
        aggregate=_aggregate(), failures={},
    )
    diffs = propose(artifacts, tmp_path, {})
    paths = {str(d.path) for d in diffs}
    assert "docs/health/latest.md" in paths


def test_skips_when_byte_identical(tmp_path: Path) -> None:
    health = tmp_path / "docs" / "health"
    health.mkdir(parents=True, exist_ok=True)

    artifacts = SiblingArtifacts(
        doc_audit={}, config_registry={}, graph_lint={},
        aggregate=_aggregate(), failures={},
    )
    diffs = propose(artifacts, tmp_path, {})
    for d in diffs:
        (tmp_path / d.path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / d.path).write_text(d.new_content)

    diffs2 = propose(artifacts, tmp_path, {})
    assert diffs2 == []
