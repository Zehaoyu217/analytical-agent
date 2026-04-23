from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Job:
    key: str
    fn: Callable[[], None]
    ready_at: float


class SerialQueue:
    """FIFO queue with per-key dedupe + debounce. Not thread-safe drain."""

    def __init__(self) -> None:
        self._jobs: list[_Job] = []
        self._lock = threading.Lock()
        self.last_errors: list[str] = []

    def enqueue(
        self, key: str, fn: Callable[[], None], *, debounce: float, now: float
    ) -> None:
        ready_at = now + debounce
        with self._lock:
            for job in self._jobs:
                if job.key == key:
                    job.fn = fn
                    job.ready_at = ready_at
                    return
            self._jobs.append(_Job(key=key, fn=fn, ready_at=ready_at))

    def drain_until_empty(self, *, now: float) -> int:
        """Run all jobs whose ready_at <= now. Returns count executed."""
        executed = 0
        while True:
            job = self._pop_ready(now)
            if job is None:
                break
            try:
                job.fn()
            except Exception as exc:  # noqa: BLE001 — logging, not silencing
                self.last_errors.append(f"{job.key}: {exc!r}")
            executed += 1
        return executed

    def _pop_ready(self, now: float) -> _Job | None:
        with self._lock:
            for i, job in enumerate(self._jobs):
                if job.ready_at <= now:
                    return self._jobs.pop(i)
        return None

    def pending(self) -> int:
        with self._lock:
            return len(self._jobs)
