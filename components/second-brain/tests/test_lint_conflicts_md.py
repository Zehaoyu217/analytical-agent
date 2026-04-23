from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.lint.conflicts_md import render_conflicts_md
from second_brain.lint.rules import DEFAULT_GRACE_DAYS
from second_brain.lint.runner import run_lint


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _claim(cfg: Config, cid: str, *, contradicts=None, resolution=None,
           extracted_at: datetime | None = None) -> None:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": [], "contradicts": contradicts or [], "refines": [],
        "extracted_at": (extracted_at or datetime.now(UTC)).isoformat(),
        "status": "active", "resolution": resolution, "abstract": "",
    }
    dump_document(cfg.claims_dir / f"{cid}.md", fm, f"# {cid}\n")


def test_render_empty_report_has_placeholder(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    report = run_lint(cfg)
    md = render_conflicts_md(cfg, report)
    assert "# Conflicts" in md
    assert "no open debates" in md.lower()


def test_render_groups_open_and_resolved(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 5)
    _claim(cfg, "clm_open_a", contradicts=["clm_open_b"], extracted_at=old)
    _claim(cfg, "clm_open_b", extracted_at=old)
    _claim(cfg, "clm_resolved_a", contradicts=["clm_resolved_b"],
           extracted_at=old, resolution="claims/resolutions/x.md")
    _claim(cfg, "clm_resolved_b", extracted_at=old)
    report = run_lint(cfg)
    md = render_conflicts_md(cfg, report)
    assert "## Open debates" in md
    assert "clm_open_a" in md
    assert "## Healthy signal" in md
    assert "resolved contradictions: 1" in md


def test_write_conflicts_flag_writes_file(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_x")  # orphan, but doesn't affect conflicts.md directly
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--write-conflicts"])
    # Orphan claim means exit=1, but file should still be written.
    assert (cfg.home / "conflicts.md").exists()
    content = (cfg.home / "conflicts.md").read_text("utf-8")
    assert "# Conflicts" in content
