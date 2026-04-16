"""Prometheus metrics for the analytical agent backend.

Import this module early (done in main.py) so gauges are registered before
the first scrape.  Other modules update the gauges by importing from here:

    from app.metrics import active_sessions_gauge
    active_sessions_gauge.inc()   # session started
    active_sessions_gauge.dec()   # session ended
"""
from __future__ import annotations

try:
    from prometheus_client import Gauge

    active_sessions_gauge = Gauge(
        "active_sessions",
        "Number of currently active chat sessions",
        ["app"],
    )
    # Initialise the label set so Grafana sees the series immediately.
    active_sessions_gauge.labels(app="claude-code-server")

except ImportError:
    # prometheus_client not installed — create a no-op stub so other modules
    # can safely import and call .inc()/.dec() without conditional guards.
    class _Noop:  # type: ignore[no-redef]
        def labels(self, **_: object) -> "_Noop":
            return self

        def inc(self, amount: float = 1) -> None:
            pass

        def dec(self, amount: float = 1) -> None:
            pass

        def set(self, value: float) -> None:
            pass

    active_sessions_gauge = _Noop()  # type: ignore[assignment]
