"""Unit tests for :mod:`app.integrity.drift_scan`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.integrity.drift_scan import (
    DriftFinding,
    DriftReport,
    scan_drift,
)


@dataclass(frozen=True)
class _Cfg:
    claims_dir: Path
    wiki_dir: Path


def _write_claim(
    claims_dir: Path,
    claim_id: str,
    *,
    wiki_path: str | None = None,
    updated_days_ago: int = 0,
) -> None:
    claims_dir.mkdir(parents=True, exist_ok=True)
    updated_at = (
        datetime.now(tz=UTC) - timedelta(days=updated_days_ago)
    ).isoformat()
    fm_lines = [
        "---",
        f"id: {claim_id}",
        f"updated_at: {updated_at}",
    ]
    if wiki_path is not None:
        fm_lines.append(f"wiki_path: {wiki_path}")
    fm_lines.append("---")
    body = f"# Claim {claim_id}\n\nbody text\n"
    (claims_dir / f"{claim_id}.md").write_text(
        "\n".join(fm_lines) + "\n" + body,
        encoding="utf-8",
    )


def _write_wiki(
    wiki_dir: Path,
    rel_path: str,
    *,
    backlinks: list[str] | None = None,
    updated_days_ago: int = 0,
) -> None:
    full = wiki_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    updated_at = (
        datetime.now(tz=UTC) - timedelta(days=updated_days_ago)
    ).isoformat()
    lines = [
        "---",
        f"updated_at: {updated_at}",
    ]
    if backlinks is not None:
        lines.append("backlinks:")
        for b in backlinks:
            lines.append(f"  - {b}")
    lines.append("---")
    full.write_text("\n".join(lines) + "\n\n# page\n", encoding="utf-8")


def test_scan_drift_empty_when_no_dirs(tmp_path: Path) -> None:
    cfg = _Cfg(
        claims_dir=tmp_path / "nope-claims",
        wiki_dir=tmp_path / "nope-wiki",
    )
    report = scan_drift(cfg)
    assert isinstance(report, DriftReport)
    assert report.total == 0
    assert report.findings == []
    assert report.by_kind == {}


def test_scan_drift_detects_orphan_claim(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    # Claim points at a wiki page that does not exist
    _write_claim(claims, "clm_ghost", wiki_path="missing/page.md")

    cfg = _Cfg(claims_dir=claims, wiki_dir=wiki)
    report = scan_drift(cfg)

    assert report.total == 1
    assert report.by_kind == {"orphan_claim": 1}
    assert report.findings[0].kind == "orphan_claim"
    assert report.findings[0].subject_id == "clm_ghost"


def test_scan_drift_detects_orphan_backlink(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    wiki = tmp_path / "wiki"
    claims.mkdir()

    # Wiki page backlinks to a claim that doesn't exist
    _write_wiki(wiki, "pages/topic.md", backlinks=["clm_missing"])

    cfg = _Cfg(claims_dir=claims, wiki_dir=wiki)
    report = scan_drift(cfg)

    assert report.by_kind.get("orphan_backlink") == 1
    orphan = [f for f in report.findings if f.kind == "orphan_backlink"][0]
    assert orphan.subject_id == "clm_missing"


def test_scan_drift_detects_stale_claim(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    wiki = tmp_path / "wiki"

    # Wiki page updated today, claim updated 120 days ago ⇒ stale
    _write_wiki(wiki, "pages/fresh.md", updated_days_ago=0)
    _write_claim(
        claims,
        "clm_stale",
        wiki_path="pages/fresh.md",
        updated_days_ago=120,
    )

    cfg = _Cfg(claims_dir=claims, wiki_dir=wiki)
    report = scan_drift(cfg, stale_threshold_days=30)

    assert report.by_kind.get("stale_claim") == 1
    stale = [f for f in report.findings if f.kind == "stale_claim"][0]
    assert stale.subject_id == "clm_stale"


def test_scan_drift_returns_empty_report_when_no_drift(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    wiki = tmp_path / "wiki"

    _write_wiki(wiki, "pages/fresh.md", updated_days_ago=0, backlinks=["clm_ok"])
    _write_claim(
        claims,
        "clm_ok",
        wiki_path="pages/fresh.md",
        updated_days_ago=0,
    )

    cfg = _Cfg(claims_dir=claims, wiki_dir=wiki)
    report = scan_drift(cfg, stale_threshold_days=30)

    assert report.total == 0
    assert report.findings == []


def test_scan_drift_multiple_findings(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    _write_claim(claims, "clm_orphan", wiki_path="missing.md")
    _write_wiki(wiki, "bad.md", backlinks=["clm_ghost2"])

    cfg = _Cfg(claims_dir=claims, wiki_dir=wiki)
    report = scan_drift(cfg)
    assert report.total == 2
    assert sorted(report.by_kind) == ["orphan_backlink", "orphan_claim"]


def test_drift_finding_frozen_dataclass() -> None:
    f = DriftFinding(kind="orphan_claim", subject_id="clm_x", detail={"a": 1})
    # Attempt to mutate should raise — frozen semantics
    try:
        f.kind = "stale_claim"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("DriftFinding should be frozen")
