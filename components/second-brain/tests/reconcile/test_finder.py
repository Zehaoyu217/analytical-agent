from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.reconcile.finder import find_open_debates


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _write_claim(cfg: Config, slug: str, *, contradicts: list[str],
                 resolution: str | None, extracted_at: datetime) -> None:
    body = "\n".join([
        "---",
        f"id: {slug}",
        f"statement: 'stmt for {slug}'",
        "kind: empirical",
        "confidence: high",
        "scope: ''",
        f"contradicts: {contradicts}",
        "supports: []",
        "refines: []",
        f"extracted_at: {extracted_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "status: active",
        f"resolution: {resolution if resolution else 'null'}",
        "abstract: ''",
        "---",
        "",
    ])
    (cfg.claims_dir / f"{slug}.md").write_text(body, encoding="utf-8")


def test_find_open_debates_returns_unresolved_past_grace(tmp_path):
    cfg = _cfg(tmp_path)
    old = datetime.now(UTC) - timedelta(days=30)
    fresh = datetime.now(UTC) - timedelta(days=2)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], resolution=None, extracted_at=old)
    _write_claim(cfg, "clm_b", contradicts=[], resolution=None, extracted_at=old)
    _write_claim(cfg, "clm_c", contradicts=["clm_d"], resolution=None, extracted_at=fresh)
    _write_claim(cfg, "clm_d", contradicts=[], resolution=None, extracted_at=fresh)

    debates = find_open_debates(cfg, Habits.default())
    pair_ids = {(d.left_id, d.right_id) for d in debates}
    assert ("clm_a", "clm_b") in pair_ids
    assert ("clm_c", "clm_d") not in pair_ids  # within grace window


def test_find_open_debates_skips_resolved(tmp_path):
    cfg = _cfg(tmp_path)
    old = datetime.now(UTC) - timedelta(days=30)
    _write_claim(cfg, "clm_x", contradicts=["clm_y"],
                 resolution="claims/resolutions/x-y.md", extracted_at=old)
    _write_claim(cfg, "clm_y", contradicts=[], resolution=None, extracted_at=old)
    debates = find_open_debates(cfg, Habits.default())
    assert not debates
