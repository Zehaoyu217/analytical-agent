"""Test v2 hybrid-retrieval additions on RetrievalHabits."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from second_brain.habits.schema import Habits, RetrievalHabits


def test_retrieval_habits_defaults():
    r = RetrievalHabits()
    assert r.mode == "hybrid"
    assert r.embedding_model == "local"
    assert r.rrf_k == 60
    # Pre-existing defaults still in place.
    assert r.prefer == "claims"
    assert r.default_k == 10
    assert r.default_scope == "both"
    assert r.max_depth_content == 1


def test_retrieval_habits_roundtrip_with_hybrid_mode():
    r = RetrievalHabits(mode="hybrid", embedding_model="claude", rrf_k=42)
    dumped = r.model_dump()
    assert dumped["mode"] == "hybrid"
    assert dumped["embedding_model"] == "claude"
    assert dumped["rrf_k"] == 42
    parsed = RetrievalHabits.model_validate(dumped)
    assert parsed == r


def test_retrieval_habits_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        RetrievalHabits(mode="keyword")  # type: ignore[arg-type]


def test_retrieval_habits_rejects_invalid_embedding_model():
    with pytest.raises(ValidationError):
        RetrievalHabits(embedding_model="openai")  # type: ignore[arg-type]


def test_retrieval_habits_is_frozen():
    r = RetrievalHabits()
    with pytest.raises(ValidationError):
        r.mode = "hybrid"  # type: ignore[misc]


def test_habits_default_retrieval_has_new_fields():
    h = Habits.default()
    assert h.retrieval.mode == "hybrid"
    assert h.retrieval.embedding_model == "local"
    assert h.retrieval.rrf_k == 60
