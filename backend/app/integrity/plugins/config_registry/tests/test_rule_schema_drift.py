"""Tests for config.schema_drift rule."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.integrity.plugins.config_registry.manifest import empty_manifest
from app.integrity.plugins.config_registry.rules.schema_drift import run
from app.integrity.protocol import ScanContext
from app.integrity.schema import GraphSnapshot


def _ctx(repo: Path) -> ScanContext:
    return ScanContext(repo_root=repo, graph=GraphSnapshot.load(repo))


def test_invalid_pyproject_emits_warn(tiny_repo: Path) -> None:
    bad = tiny_repo / "pyproject.toml"
    bad.write_text('[other]\nname = "x"\n')
    current = empty_manifest()
    current["configs"] = [{"id": "pyproject.toml", "type": "pyproject",
                           "path": "pyproject.toml", "sha": "x"}]
    cfg = {"_prior_manifest": empty_manifest(),
           "_current_manifest": current,
           "schema_drift": {"enabled": True, "strict_mode": False}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert len(issues) >= 1
    drift = next(i for i in issues if i.rule == "config.schema_drift")
    assert drift.severity == "WARN"
    assert drift.node_id == "pyproject.toml"
    assert "validation_failures" in drift.evidence


def test_valid_pyproject_no_issue(tiny_repo: Path) -> None:
    current = empty_manifest()
    current["configs"] = [{"id": "pyproject.toml", "type": "pyproject",
                           "path": "pyproject.toml", "sha": "x"}]
    cfg = {"_prior_manifest": empty_manifest(),
           "_current_manifest": current,
           "schema_drift": {"enabled": True, "strict_mode": False}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert issues == []


def test_unknown_type_skipped_in_lenient(tiny_repo: Path) -> None:
    """Unknown type with strict_mode=False → no issue, no failure."""
    current = empty_manifest()
    current["configs"] = [{"id": "weird.cfg", "type": "made_up_type",
                           "path": "weird.cfg", "sha": "x"}]
    cfg = {"_prior_manifest": empty_manifest(),
           "_current_manifest": current,
           "schema_drift": {"enabled": True, "strict_mode": False}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert issues == []


def test_unknown_type_warns_in_strict(tiny_repo: Path) -> None:
    current = empty_manifest()
    current["configs"] = [{"id": "weird.cfg", "type": "made_up_type",
                           "path": "weird.cfg", "sha": "x"}]
    cfg = {"_prior_manifest": empty_manifest(),
           "_current_manifest": current,
           "schema_drift": {"enabled": True, "strict_mode": True}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert any(i.rule == "config.schema_drift" and "no schema" in i.message.lower() for i in issues)


def test_missing_file_silently_skipped(tiny_repo: Path) -> None:
    """Manifest entry whose file no longer exists → skipped (covered by removed rule)."""
    current = empty_manifest()
    current["configs"] = [{"id": "ghost.toml", "type": "pyproject",
                           "path": "ghost.toml", "sha": "x"}]
    cfg = {"_prior_manifest": empty_manifest(),
           "_current_manifest": current,
           "schema_drift": {"enabled": True, "strict_mode": False}}
    issues = run(_ctx(tiny_repo), cfg, date(2026, 4, 17))
    assert issues == []
