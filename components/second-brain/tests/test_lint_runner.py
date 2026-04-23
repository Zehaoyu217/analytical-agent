from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.lint.runner import LintReport, run_lint


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _source(cfg: Config, sid: str, *, cites=None, raw_bytes=b"# body\n",
            content_hash: str | None = None) -> None:
    folder = cfg.sources_dir / sid
    folder.mkdir(parents=True)
    (folder / "raw").mkdir()
    (folder / "raw" / "original.md").write_bytes(raw_bytes)
    raw_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    fm = {
        "id": sid, "title": sid, "kind": "note",
        "authors": [], "year": 2024, "source_url": None, "tags": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "content_hash": content_hash or raw_hash,
        "habit_taxonomy": None,
        "raw": [{"path": "raw/original.md", "kind": "original", "sha256": raw_hash}],
        "cites": cites or [], "related": [], "supersedes": [], "abstract": "",
    }
    dump_document(folder / "_source.md", fm, "# body\n")


def test_empty_report_has_no_issues(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    report = run_lint(cfg)
    assert isinstance(report, LintReport)
    assert report.issues == []
    assert report.ok is True
    assert report.counts_by_severity == {"error": 0, "warning": 0, "info": 0}


def test_report_aggregates_rules(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _source(cfg, "src_a", cites=["src_missing"])          # DANGLING_EDGE + SPARSE_SOURCE
    report = run_lint(cfg)
    rules = {i.rule for i in report.issues}
    assert "DANGLING_EDGE" in rules
    assert "SPARSE_SOURCE" in rules
    assert report.ok is False
    assert report.counts_by_severity["error"] >= 1
    assert report.counts_by_severity["warning"] >= 1


def test_report_to_dict_round_trip(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _source(cfg, "src_a", cites=["src_missing"])
    report = run_lint(cfg)
    data = report.to_dict()
    assert data["ok"] is False
    assert data["counts_by_severity"]["error"] >= 1
    assert all(set(issue) >= {"rule", "severity", "subject_id", "message"}
               for issue in data["issues"])
