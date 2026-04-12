from __future__ import annotations

import pytest

from app.trace import bus
from app.trace.events import SessionEndEvent


@pytest.fixture(autouse=True)
def _reset_bus() -> None:
    bus.reset()


def _event(seq: int = 0) -> SessionEndEvent:
    return SessionEndEvent(
        seq=seq, timestamp="t", ended_at="t",
        duration_ms=1, outcome="ok", error=None,
    )


def test_publish_fans_out_to_all_subscribers() -> None:
    received_a: list[object] = []
    received_b: list[object] = []
    bus.subscribe(received_a.append)
    bus.subscribe(received_b.append)
    bus.publish(_event())
    assert len(received_a) == 1
    assert len(received_b) == 1


def test_publish_assigns_monotonic_seq() -> None:
    received: list[int] = []
    bus.subscribe(lambda e: received.append(e.seq))
    bus.publish(_event(seq=0))
    bus.publish(_event(seq=0))
    bus.publish(_event(seq=0))
    assert received == [1, 2, 3]


def test_publish_with_no_subscribers_is_noop() -> None:
    bus.publish(_event())  # must not raise


def test_reset_clears_subscribers_and_counter() -> None:
    received: list[object] = []
    bus.subscribe(received.append)
    bus.publish(_event())
    bus.reset()
    bus.publish(_event())
    assert len(received) == 1  # second publish had no subscriber


def test_seq_resets_with_reset() -> None:
    received: list[int] = []
    bus.publish(_event())  # seq 1, no subscriber
    bus.reset()
    bus.subscribe(lambda e: received.append(e.seq))
    bus.publish(_event())
    assert received == [1]
