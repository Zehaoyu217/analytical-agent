"""Sync in-process event bus for the trace subsystem.

Module-level singleton. Synchronous publish — no threads, no async.
"""
from __future__ import annotations

from collections.abc import Callable

from app.trace.events import TraceEvent

Subscriber = Callable[[TraceEvent], None]

_subscribers: list[Subscriber] = []
_seq_counter: int = 0


def publish(event: TraceEvent) -> None:
    """Assign monotonic seq, then fan out to all subscribers."""
    global _seq_counter
    _seq_counter += 1
    stamped = event.model_copy(update={"seq": _seq_counter})
    for sub in _subscribers:
        sub(stamped)


def subscribe(fn: Subscriber) -> None:
    _subscribers.append(fn)


def unsubscribe(fn: Subscriber) -> None:
    """Remove a previously-subscribed callback. No-op if not registered."""
    try:
        _subscribers.remove(fn)
    except ValueError:
        pass


def reset() -> None:
    """Clear subscribers and reset seq counter (test-only)."""
    global _seq_counter
    _subscribers.clear()
    _seq_counter = 0
