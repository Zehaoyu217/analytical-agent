from __future__ import annotations

import pydantic
import pytest

from second_brain.habits.schema import GardenerHabits, Habits


def test_default_habits_have_gardener_block() -> None:
    h = Habits.default()
    assert isinstance(h.gardener, GardenerHabits)
    assert h.gardener.mode == "proposal"
    assert h.gardener.passes["extract"] is True
    assert h.gardener.passes["dedupe"] is False
    assert h.gardener.max_cost_usd_per_run == 0.50
    assert h.gardener.max_tokens_per_source == 8000
    assert h.gardener.dry_run is False
    assert "cheap" in h.gardener.models
    assert "default" in h.gardener.models
    assert "deep" in h.gardener.models


def test_missing_gardener_block_uses_defaults() -> None:
    h = Habits.model_validate({"identity": {"name": "test"}})
    assert h.gardener.mode == "proposal"
    assert h.gardener.max_cost_usd_per_run == 0.50


def test_partial_gardener_block_merges_defaults() -> None:
    h = Habits.model_validate(
        {"gardener": {"mode": "autonomous", "max_cost_usd_per_run": 1.25}}
    )
    assert h.gardener.mode == "autonomous"
    assert h.gardener.max_cost_usd_per_run == 1.25
    assert h.gardener.max_tokens_per_source == 8000
    assert h.gardener.passes["extract"] is True


def test_gardener_habits_is_frozen() -> None:
    h = GardenerHabits()
    with pytest.raises(pydantic.ValidationError):
        h.mode = "autonomous"  # type: ignore[misc]
