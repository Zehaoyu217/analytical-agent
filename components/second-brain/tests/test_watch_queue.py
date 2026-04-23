from __future__ import annotations

from second_brain.watch.queue import SerialQueue


def test_queue_runs_fn_after_debounce(monkeypatch):
    q = SerialQueue()
    called: list[str] = []

    q.enqueue("a", lambda: called.append("a"), debounce=1.0, now=0.0)
    q.drain_until_empty(now=0.5)
    assert called == []  # debounce window
    q.drain_until_empty(now=1.2)
    assert called == ["a"]


def test_queue_dedupes_repeated_key_and_bumps_ready_at():
    q = SerialQueue()
    called: list[float] = []

    q.enqueue("same", lambda: called.append(0.0), debounce=1.0, now=0.0)
    q.enqueue("same", lambda: called.append(1.0), debounce=1.0, now=0.8)  # bumps to 1.8

    q.drain_until_empty(now=1.5)
    assert called == []  # not yet ready — debounce reset on second enqueue

    q.drain_until_empty(now=2.0)
    assert called == [1.0]  # only most recent fn executed, once


def test_queue_runs_fifo_for_distinct_keys():
    q = SerialQueue()
    called: list[str] = []
    q.enqueue("a", lambda: called.append("a"), debounce=0.0, now=0.0)
    q.enqueue("b", lambda: called.append("b"), debounce=0.0, now=0.0)
    q.drain_until_empty(now=0.0)
    assert called == ["a", "b"]


def test_queue_swallows_fn_exceptions_and_continues():
    q = SerialQueue()
    called: list[str] = []

    def boom() -> None:
        raise RuntimeError("x")

    q.enqueue("a", boom, debounce=0.0, now=0.0)
    q.enqueue("b", lambda: called.append("b"), debounce=0.0, now=0.0)
    q.drain_until_empty(now=0.0)
    assert called == ["b"]
    assert q.last_errors and "x" in q.last_errors[0]
