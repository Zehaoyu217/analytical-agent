"""Tests for SiblingArtifacts loader — reads integrity-out/{date}/{plugin}.json."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.integrity.plugins.autofix.loader import (
    read_today,
)


def _write(p: Path, payload: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))


def test_read_today_loads_all_present_artifacts(tmp_path: Path) -> None:
    today = date(2026, 4, 17)
    out = tmp_path / "integrity-out" / "2026-04-17"
    _write(out / "doc_audit.json", {"plugin": "doc_audit", "issues": [{"id": 1}]})
    _write(out / "config_registry.json", {"plugin": "config_registry", "issues": [{"id": 2}]})
    _write(out / "graph_lint.json", {"plugin": "graph_lint", "issues": [{"id": 3}]})
    _write(out / "report.json", {"date": "2026-04-17", "plugins": {}})

    artifacts = read_today(tmp_path / "integrity-out", today)

    assert artifacts.doc_audit == {"plugin": "doc_audit", "issues": [{"id": 1}]}
    assert artifacts.config_registry == {"plugin": "config_registry", "issues": [{"id": 2}]}
    assert artifacts.graph_lint == {"plugin": "graph_lint", "issues": [{"id": 3}]}
    assert artifacts.aggregate == {"date": "2026-04-17", "plugins": {}}
    assert artifacts.failures == {}


def test_missing_artifact_records_failure(tmp_path: Path) -> None:
    today = date(2026, 4, 17)
    out = tmp_path / "integrity-out" / "2026-04-17"
    _write(out / "doc_audit.json", {"plugin": "doc_audit", "issues": []})

    artifacts = read_today(tmp_path / "integrity-out", today)

    assert artifacts.doc_audit is not None
    assert artifacts.config_registry is None
    assert artifacts.graph_lint is None
    assert artifacts.aggregate is None
    assert artifacts.failures == {
        "config_registry": "missing",
        "graph_lint": "missing",
        "aggregate": "missing",
    }


def test_parse_error_records_failure(tmp_path: Path) -> None:
    today = date(2026, 4, 17)
    out = tmp_path / "integrity-out" / "2026-04-17"
    bad = out / "doc_audit.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not-json")

    artifacts = read_today(tmp_path / "integrity-out", today)

    assert artifacts.doc_audit is None
    assert "doc_audit" in artifacts.failures
    assert artifacts.failures["doc_audit"].startswith("parse_error: ")


def test_directory_missing_returns_all_failures(tmp_path: Path) -> None:
    today = date(2026, 4, 17)
    artifacts = read_today(tmp_path / "integrity-out", today)
    assert artifacts.doc_audit is None
    assert artifacts.config_registry is None
    assert artifacts.graph_lint is None
    assert artifacts.aggregate is None
    assert set(artifacts.failures.keys()) == {
        "doc_audit", "config_registry", "graph_lint", "aggregate",
    }
