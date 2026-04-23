from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from second_brain.digest import DigestEntry, DigestPassError


def test_digest_entry_is_frozen() -> None:
    e = DigestEntry(id="r01", section="Reconciliation", line="Keep?", action={"action": "keep"})
    with pytest.raises(FrozenInstanceError):
        e.id = "r02"  # type: ignore[misc]


def test_digest_entry_json_round_trip() -> None:
    e = DigestEntry(
        id="r01",
        section="Reconciliation",
        line="Upgrade clm_a to medium?",
        action={
            "action": "upgrade_confidence",
            "claim_id": "clm_a",
            "from": "low",
            "to": "medium",
            "rationale": "stale-but-corroborated",
        },
    )
    raw = json.dumps(e.to_dict())
    back = json.loads(raw)
    assert back["id"] == "r01"
    assert back["action"]["action"] == "upgrade_confidence"
    assert back["action"]["from"] == "low"


def test_digest_pass_error_is_runtime_error() -> None:
    assert issubclass(DigestPassError, RuntimeError)
    with pytest.raises(DigestPassError, match="missing"):
        raise DigestPassError("missing fake client env var")
