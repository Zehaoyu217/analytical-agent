from second_brain.habits import Habits


def test_default_habits_are_valid_and_stable():
    h = Habits.default()
    assert h.injection.enabled is True
    assert h.injection.k == 5
    assert h.injection.max_tokens == 800
    assert h.injection.min_score == 0.2
    assert h.extraction.default_density == "moderate"
    assert h.extraction.by_taxonomy["papers/*"] == "dense"
    assert h.conflicts.grace_period_days == 14
    assert h.conflicts.cluster_threshold == 3
    assert h.autonomy.default == "hitl"
    assert h.autonomy.overrides["reconciliation.resolution"] == "hitl"
    assert h.autonomy.overrides["ingest.slug"] == "auto"


def test_habits_round_trip_through_dict_preserves_fields():
    h = Habits.default()
    raw = h.model_dump(mode="python")
    assert raw["injection"]["k"] == 5
    h2 = Habits.model_validate(raw)
    assert h2 == h


def test_habits_rejects_unknown_autonomy_mode():
    import pytest
    from pydantic import ValidationError
    raw = Habits.default().model_dump()
    raw["autonomy"]["default"] = "yolo"
    with pytest.raises(ValidationError):
        Habits.model_validate(raw)
