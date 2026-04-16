"""Unit tests for TurnState sampling rate-limit (H6.T1)."""
from __future__ import annotations

import pytest

from app.harness.turn_state import SAMPLING_LIMIT_PER_TURN, SamplingRateLimitError, TurnState


def test_sampling_call_increments_counter() -> None:
    state = TurnState()
    assert state.sampling_calls == 0
    state.record_sampling_call()
    assert state.sampling_calls == 1
    state.record_sampling_call()
    assert state.sampling_calls == 2


def test_sampling_limit_raises_on_sixth_call() -> None:
    """Five calls should succeed; the sixth must raise SamplingRateLimitError."""
    state = TurnState()
    for _ in range(SAMPLING_LIMIT_PER_TURN):
        state.record_sampling_call()  # must not raise

    assert state.sampling_calls == SAMPLING_LIMIT_PER_TURN

    with pytest.raises(SamplingRateLimitError):
        state.record_sampling_call()


def test_sampling_calls_reset_per_turn() -> None:
    """Each new TurnState instance starts with sampling_calls == 0."""
    state1 = TurnState()
    for _ in range(3):
        state1.record_sampling_call()

    state2 = TurnState()
    assert state2.sampling_calls == 0
