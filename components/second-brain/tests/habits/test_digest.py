from __future__ import annotations

import pytest
from pydantic import ValidationError

from second_brain.habits import DigestHabits, Habits


def test_default_digest_habits_disabled_with_all_passes_on() -> None:
    h = Habits.default()
    assert h.digest.enabled is False
    assert h.digest.min_entries_to_emit == 0
    assert h.digest.skip_ttl_days == 14
    assert h.digest.passes == {
        "reconciliation": True,
        "wiki_bridge": True,
        "taxonomy_drift": True,
        "stale_review": True,
        "edge_audit": True,
    }


def test_digest_habits_round_trip_through_dict() -> None:
    h = Habits.default()
    raw = h.model_dump(mode="python")
    assert raw["digest"]["enabled"] is False
    assert raw["digest"]["passes"]["reconciliation"] is True
    h2 = Habits.model_validate(raw)
    assert h2 == h


def test_digest_habits_is_frozen() -> None:
    d = DigestHabits()
    with pytest.raises(ValidationError):
        d.enabled = True  # type: ignore[misc]


def test_digest_habits_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        DigestHabits(enabled=True, wat=1)  # type: ignore[call-arg]
