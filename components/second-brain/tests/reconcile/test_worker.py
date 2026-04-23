from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits
from second_brain.reconcile.client import FakeReconcilerClient
from second_brain.reconcile.worker import run_reconcile


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _seed_pair(cfg: Config) -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for slug, other in [("clm_a", "clm_b"), ("clm_b", "clm_a")]:
        (cfg.claims_dir / f"{slug}.md").write_text(
            "\n".join([
                "---",
                f"id: {slug}",
                f"statement: '{slug}'",
                "kind: empirical",
                "confidence: high",
                "scope: ''",
                f"contradicts: [{other}]",
                "supports: []",
                "refines: []",
                f"extracted_at: {old}",
                "status: active",
                "resolution: null",
                "abstract: ''",
                "---",
                "",
            ]),
            encoding="utf-8",
        )


def test_run_reconcile_writes_resolutions_for_each_debate(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=10)
    assert report.resolved == 1
    assert report.skipped == 0
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta["resolution"].startswith("claims/resolutions/")


def test_run_reconcile_respects_limit(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=0)
    assert report.resolved == 0


def test_run_reconcile_dry_run_does_not_mutate(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=10, dry_run=True)
    assert report.resolved == 0
    assert report.proposed == 1
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta.get("resolution") in (None, "null", "")
