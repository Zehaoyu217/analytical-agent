from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.digest.passes.reconciliation import (
    STALE_LOW_CONF_DAYS,
    ReconciliationPass,
)
from second_brain.digest.schema import DigestPassError


def test_pass_conforms_to_protocol() -> None:
    from second_brain.digest.passes import Pass

    assert isinstance(ReconciliationPass(), Pass)
    assert ReconciliationPass().prefix == "r"
    assert ReconciliationPass().section == "Reconciliation"


def test_empty_kb_returns_empty(digest_cfg) -> None:
    assert ReconciliationPass().run(digest_cfg, client=None) == []


def test_missing_fake_env_raises_when_candidates_present(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SB_DIGEST_FAKE_RECONCILIATION", raising=False)
    old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=old)
    with pytest.raises(DigestPassError, match="no client"):
        ReconciliationPass().run(digest_cfg, client=None)


def test_fake_env_bad_path_raises(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=old)
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(tmp_path / "nope.json"))
    with pytest.raises(DigestPassError, match="does not exist"):
        ReconciliationPass().run(digest_cfg, client=None)


def test_fake_env_invalid_json_raises(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=old)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(bad))
    with pytest.raises(DigestPassError, match="invalid"):
        ReconciliationPass().run(digest_cfg, client=None)


def test_fake_env_missing_entries_key_raises(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=old)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"other": []}), encoding="utf-8")
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(bad))
    with pytest.raises(DigestPassError, match="entries"):
        ReconciliationPass().run(digest_cfg, client=None)


def test_invalid_action_raises(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=old)
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"entries": [{"action": "explode", "target_id": "clm_stale", "rationale": ""}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(bad))
    with pytest.raises(DigestPassError, match="not in"):
        ReconciliationPass().run(digest_cfg, client=None)


def test_one_contradiction_plus_one_low_conf_yields_two_entries(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old = datetime.now(UTC) - timedelta(days=30)
    stale_old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)

    # Open contradiction past grace window.
    write_claim(digest_cfg, "clm_a", contradicts=["clm_b"], extracted_at=old)
    write_claim(digest_cfg, "clm_b", extracted_at=old)

    # Stale low-confidence active claim.
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=stale_old)

    canned = {
        "entries": [
            {
                "action": "resolve_contradiction",
                "target_id": "clm_a",
                "rationale": "scope differs",
            },
            {
                "action": "upgrade_confidence",
                "target_id": "clm_stale",
                "rationale": "two sources corroborate",
            },
        ]
    }
    fake = tmp_path / "canned.json"
    fake.write_text(json.dumps(canned), encoding="utf-8")
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(fake))

    entries = ReconciliationPass().run(digest_cfg, client=None)
    assert len(entries) == 2

    contradictions = [e for e in entries if e.action["action"] == "resolve_contradiction"]
    upgrades = [e for e in entries if e.action["action"] == "upgrade_confidence"]
    assert len(contradictions) == 1
    assert len(upgrades) == 1

    c_payload = contradictions[0].action
    assert c_payload["left_id"] == "clm_a"
    assert c_payload["right_id"] == "clm_b"
    assert c_payload["rationale"] == "scope differs"
    assert contradictions[0].section == "Reconciliation"
    assert contradictions[0].id == ""

    u_payload = upgrades[0].action
    assert u_payload["claim_id"] == "clm_stale"
    assert u_payload["from"] == "low"
    assert u_payload["to"] == "medium"


def test_missing_decision_defaults_to_keep(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale_old = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS + 5)
    write_claim(digest_cfg, "clm_stale", confidence="low", extracted_at=stale_old)

    fake = tmp_path / "canned.json"
    fake.write_text(json.dumps({"entries": []}), encoding="utf-8")
    monkeypatch.setenv("SB_DIGEST_FAKE_RECONCILIATION", str(fake))

    entries = ReconciliationPass().run(digest_cfg, client=None)
    assert len(entries) == 1
    assert entries[0].action == {
        "action": "keep",
        "claim_id": "clm_stale",
        "rationale": "",
    }


def test_fresh_low_conf_is_not_candidate(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fresh (< 60 days) → excluded.
    fresh = datetime.now(UTC) - timedelta(days=10)
    write_claim(digest_cfg, "clm_fresh", confidence="low", extracted_at=fresh)
    monkeypatch.delenv("SB_DIGEST_FAKE_RECONCILIATION", raising=False)
    # No candidates → no env-var required, just empty.
    assert ReconciliationPass().run(digest_cfg, client=None) == []
