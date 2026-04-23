from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.lint.rules import (
    DEFAULT_GRACE_DAYS,
    LOPSIDED_THRESHOLD,
    LintIssue,
    Severity,
    check_circular_supersedes,
    check_dangling_edge,
    check_hash_mismatch,
    check_lopsided_contradiction,
    check_orphan_claim,
    check_sparse_source,
    check_stale_abstract,
    check_unresolved_contradiction,
)
from second_brain.lint.snapshot import load_snapshot


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _write_source(cfg: Config, sid: str, *, cites=None, supersedes=None, raw_bytes=b"# x\n",
                  content_hash: str | None = None, abstract: str = "") -> Path:
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
        "cites": cites or [], "related": [], "supersedes": supersedes or [],
        "abstract": abstract,
    }
    dump_document(folder / "_source.md", fm, "# body\n")
    return folder


def _write_claim(cfg: Config, cid: str, *, supports=None, contradicts=None, refines=None,
                 status="active", resolution=None,
                 extracted_at: datetime | None = None) -> Path:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    p = cfg.claims_dir / f"{cid}.md"
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": supports or [], "contradicts": contradicts or [], "refines": refines or [],
        "extracted_at": (extracted_at or datetime.now(UTC)).isoformat(),
        "status": status, "resolution": resolution, "abstract": "",
    }
    dump_document(p, fm, f"# {cid}\n")
    return p


def test_orphan_claim_flags_no_supports(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=[])
    issues = check_orphan_claim(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["ORPHAN_CLAIM"]
    assert issues[0].subject_id == "clm_a"
    assert issues[0].severity == Severity.ERROR


def test_orphan_claim_ignores_retracted(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=[], status="retracted")
    issues = check_orphan_claim(load_snapshot(cfg))
    assert issues == []


def test_dangling_edge_on_source_cites(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", cites=["src_missing"])
    issues = check_dangling_edge(load_snapshot(cfg))
    kinds = {(i.rule, i.subject_id) for i in issues}
    assert ("DANGLING_EDGE", "src_a") in kinds


def test_dangling_edge_on_claim_supports(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=["src_missing"])
    issues = check_dangling_edge(load_snapshot(cfg))
    assert any(i.subject_id == "clm_a" for i in issues)


def test_dangling_edge_fragments_are_stripped(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_claim(cfg, "clm_x", supports=["src_a#sec-3.2"])
    issues = check_dangling_edge(load_snapshot(cfg))
    assert issues == []


def test_circular_supersedes(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", supersedes=["src_b"])
    _write_source(cfg, "src_b", supersedes=["src_a"])
    issues = check_circular_supersedes(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["CIRCULAR_SUPERSEDES"] * 1
    assert set(issues[0].details["cycle"]) == {"src_a", "src_b"}


def test_hash_mismatch_detects_drift(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# original\n", content_hash="sha256:deadbeef")
    issues = check_hash_mismatch(load_snapshot(cfg), cfg)
    assert [i.rule for i in issues] == ["HASH_MISMATCH"]
    assert issues[0].subject_id == "src_a"


def test_hash_match_no_issue(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# original\n")  # content_hash derived from bytes
    issues = check_hash_mismatch(load_snapshot(cfg), cfg)
    assert issues == []


def test_stale_abstract_flags_hash_drift_with_abstract(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(
        cfg, "src_a",
        raw_bytes=b"# original\n",
        content_hash="sha256:deadbeef",
        abstract="Previously generated abstract",
    )
    issues = check_stale_abstract(load_snapshot(cfg), cfg)
    assert [i.rule for i in issues] == ["STALE_ABSTRACT"]


def test_stale_abstract_ignores_hash_drift_when_abstract_empty(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# x\n", content_hash="sha256:deadbeef", abstract="")
    issues = check_stale_abstract(load_snapshot(cfg), cfg)
    assert issues == []


def test_sparse_source_flags_source_with_zero_claims(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    issues = check_sparse_source(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["SPARSE_SOURCE"]
    assert issues[0].subject_id == "src_a"


def test_sparse_source_ignores_sourced_claims(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_claim(cfg, "clm_a", supports=["src_a"])
    issues = check_sparse_source(load_snapshot(cfg))
    assert issues == []


def test_unresolved_contradiction_past_grace(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 1)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=old)
    _write_claim(cfg, "clm_b", extracted_at=old)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["UNRESOLVED_CONTRADICTION"]
    assert issues[0].subject_id == "clm_a"


def test_unresolved_contradiction_within_grace_no_flag(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    fresh = datetime.now(UTC) - timedelta(days=1)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=fresh)
    _write_claim(cfg, "clm_b", extracted_at=fresh)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert issues == []


def test_unresolved_contradiction_with_resolution_no_flag(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 5)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=old,
                 resolution="claims/resolutions/x.md")
    _write_claim(cfg, "clm_b", extracted_at=old)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert issues == []


def test_lopsided_contradiction(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_center")
    contradictors = [f"clm_opp_{i}" for i in range(LOPSIDED_THRESHOLD)]
    for cid in contradictors:
        _write_claim(cfg, cid, contradicts=["clm_center"])
    issues = check_lopsided_contradiction(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["LOPSIDED_CONTRADICTION"]
    assert issues[0].subject_id == "clm_center"


def test_lopsided_contradiction_ignores_if_outbound_exists(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    contradictors = [f"clm_opp_{i}" for i in range(LOPSIDED_THRESHOLD)]
    _write_claim(cfg, "clm_center", contradicts=contradictors[:1])
    for cid in contradictors:
        _write_claim(cfg, cid, contradicts=["clm_center"])
    issues = check_lopsided_contradiction(load_snapshot(cfg))
    assert issues == []


def test_lint_issue_is_hashable():
    i = LintIssue(rule="ORPHAN_CLAIM", severity=Severity.ERROR, subject_id="clm_a",
                  message="x", details={"k": "v"})
    assert hash(i) is not None
