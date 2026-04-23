from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.analytics.builder import AnalyticsBuilder
from second_brain.analytics.queries import (
    claims_by_taxonomy,
    contradiction_counts,
    orphan_claims,
    sources_by_kind,
    zero_claim_sources,
)
from second_brain.config import Config
from second_brain.frontmatter import dump_document


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _src(home: Path, slug: str, kind: str) -> None:
    folder = home / "sources" / slug
    folder.mkdir()
    dump_document(
        folder / "_source.md",
        {
            "id": slug,
            "title": slug,
            "kind": kind,
            "content_hash": f"sha-{slug}",
            "raw": [],
            "ingested_at": "2026-04-18T00:00:00Z",
        },
        "",
    )


def _claim(home: Path, slug: str, taxonomy: str,
           evidenced_by: list[str] | None = None) -> None:
    meta: dict = {
        "id": slug,
        "statement": slug,
        "kind": "empirical",
        "confidence": "low",
        "extracted_at": "2026-04-18T00:00:00Z",
        "taxonomy": taxonomy,
    }
    if evidenced_by is not None:
        meta["evidenced_by"] = evidenced_by
    dump_document(home / "claims" / f"{slug}.md", meta, "body")


def test_rebuild_produces_source_counts(sb_home: Path):
    _src(sb_home, "src_a", "note")
    _src(sb_home, "src_b", "note")
    _src(sb_home, "src_c", "pdf")

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()

    counts = dict(sources_by_kind(cfg))
    assert counts["note"] == 2
    assert counts["pdf"] == 1


def test_rebuild_produces_claim_counts_by_taxonomy(sb_home: Path):
    _claim(sb_home, "clm_a", "papers/ml")
    _claim(sb_home, "clm_b", "papers/ml")
    _claim(sb_home, "clm_c", "notes/ideas")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(claims_by_taxonomy(cfg))
    assert counts["papers/ml"] == 2
    assert counts["notes/ideas"] == 1


def test_rebuild_identifies_zero_claim_sources(sb_home: Path):
    _src(sb_home, "src_noclaims", "note")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    zeros = list(zero_claim_sources(cfg))
    assert "src_noclaims" in zeros


def test_rebuild_is_idempotent(sb_home: Path):
    _src(sb_home, "src_x", "note")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(sources_by_kind(cfg))
    assert counts["note"] == 1


def test_contradiction_counts_empty_on_fresh_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(contradiction_counts(cfg))
    assert counts.get("open", 0) == 0
    assert counts.get("resolved", 0) == 0


def test_orphan_claims_empty_on_fresh_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    assert list(orphan_claims(cfg)) == []


def test_queries_graceful_when_no_analytics_db(sb_home: Path):
    cfg = Config.load()
    # AnalyticsBuilder not invoked; queries must not raise.
    assert list(sources_by_kind(cfg)) == []
    assert list(claims_by_taxonomy(cfg)) == []
    assert list(zero_claim_sources(cfg)) == []
    assert list(orphan_claims(cfg)) == []
    assert list(contradiction_counts(cfg)) == []


def test_fs_fallback_marks_unreferenced_sources_as_zero_claim(sb_home: Path):
    # No graph DB. Create one referenced and one unreferenced source.
    _src(sb_home, "src_used", "note")
    _src(sb_home, "src_unused", "note")
    _claim(sb_home, "clm_a", "papers/ml", evidenced_by=[{"id": "src_used"}])

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    zeros = set(zero_claim_sources(cfg))
    assert "src_unused" in zeros
    assert "src_used" not in zeros
