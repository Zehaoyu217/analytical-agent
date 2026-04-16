from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Event = dict[str, Any]
Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: list[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)

        return unsubscribe

    def emit(self, type_: str, data: dict[str, Any]) -> None:
        event = {"type": type_, "data": data}
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(event)
            except Exception:  # noqa: BLE001 - subscriber errors must not break emit
                logger.warning("EventBus subscriber %r raised", fn, exc_info=True)


_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
