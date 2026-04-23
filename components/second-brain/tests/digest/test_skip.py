from __future__ import annotations

import json
from datetime import date

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry
from second_brain.digest.skip import SkipRegistry


def _entry(action: dict) -> DigestEntry:
    return DigestEntry(id="", section="Reconciliation", line="x", action=action)


def test_signature_stable_for_same_primary_target(digest_cfg: Config) -> None:
    reg = SkipRegistry(digest_cfg)
    sig1 = reg.signature(_entry({"action": "upgrade_confidence", "claim_id": "clm_a"}))
    sig2 = reg.signature(_entry({"action": "upgrade_confidence", "claim_id": "clm_a"}))
    assert sig1 == sig2


def test_signature_differs_by_target(digest_cfg: Config) -> None:
    reg = SkipRegistry(digest_cfg)
    a = reg.signature(_entry({"action": "upgrade_confidence", "claim_id": "clm_a"}))
    b = reg.signature(_entry({"action": "upgrade_confidence", "claim_id": "clm_b"}))
    assert a != b


def test_skip_and_is_skipped(digest_cfg: Config) -> None:
    reg = SkipRegistry(digest_cfg)
    e = _entry({"action": "upgrade_confidence", "claim_id": "clm_a"})
    today = date(2026, 4, 18)
    assert reg.is_skipped(e, today=today) is False
    reg.skip(e, today=today, ttl_days=7)
    assert reg.is_skipped(e, today=today) is True


def test_ttl_expiry_purges_entry(digest_cfg: Config) -> None:
    reg = SkipRegistry(digest_cfg)
    e = _entry({"action": "upgrade_confidence", "claim_id": "clm_a"})
    reg.skip(e, today=date(2026, 4, 1), ttl_days=3)
    # After TTL (4-4), still alive on same day, dead tomorrow.
    assert reg.is_skipped(e, today=date(2026, 4, 4)) is True
    assert reg.is_skipped(e, today=date(2026, 4, 5)) is False
    # Purge happened — reload and confirm it's no longer recorded.
    raw = json.loads(reg.path.read_text(encoding="utf-8"))
    assert raw == {}


def test_skip_by_id_reads_sidecar(digest_cfg: Config) -> None:
    d = date(2026, 4, 18)
    sidecar = digest_cfg.digests_dir / f"{d.isoformat()}.actions.jsonl"
    sidecar.write_text(
        json.dumps({"id": "r01", "section": "Reconciliation", "action": {"action": "keep", "claim_id": "clm_a"}}) + "\n",
        encoding="utf-8",
    )
    reg = SkipRegistry(digest_cfg)
    assert reg.skip_by_id(digest_date=d, entry_id="r01", today=d, ttl_days=30) is True
    # File now has one entry recorded.
    assert reg.path.exists()
    data = json.loads(reg.path.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_skip_by_id_missing_entry_returns_false(digest_cfg: Config) -> None:
    d = date(2026, 4, 18)
    sidecar = digest_cfg.digests_dir / f"{d.isoformat()}.actions.jsonl"
    sidecar.write_text(
        json.dumps({"id": "r01", "section": "Reconciliation", "action": {"action": "keep", "claim_id": "clm_a"}}) + "\n",
        encoding="utf-8",
    )
    reg = SkipRegistry(digest_cfg)
    assert reg.skip_by_id(digest_date=d, entry_id="does_not_exist", today=d) is False
