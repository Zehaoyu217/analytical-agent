from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.frontmatter import dump_document


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _claim(cfg: Config, cid: str, *, supports=None) -> None:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": supports or [], "contradicts": [], "refines": [],
        "extracted_at": datetime.now(UTC).isoformat(),
        "status": "active", "resolution": None, "abstract": "",
    }
    dump_document(cfg.claims_dir / f"{cid}.md", fm, f"# {cid}\n")


def test_sb_lint_clean(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, ["lint"])
    assert result.exit_code == 0
    assert "ok" in result.output.lower() or "no issues" in result.output.lower()


def test_sb_lint_reports_issues(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_orphan")
    runner = CliRunner()
    result = runner.invoke(cli, ["lint"])
    assert result.exit_code == 1
    assert "ORPHAN_CLAIM" in result.output
    assert "clm_orphan" in result.output


def test_sb_lint_json(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_orphan")
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert any(i["rule"] == "ORPHAN_CLAIM" for i in data["issues"])
