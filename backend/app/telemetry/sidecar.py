"""Telemetry sidecar writer.

A single-record meta sidecar lives next to the artifact it describes (for
example ``digests/2026-04-18.meta.json`` next to ``digests/2026-04-18.md``).
The shape follows the umbrella spec (§4 — Telemetry sidecar format):

    {
      "timestamp": "...",
      "actor": "...",
      "duration_ms": 1234,
      "input_tokens": 0,
      "output_tokens": 0,
      "cost_usd": 0.0,
      "outcome": "ok" | "error",
      "detail": {...}
    }

``write_meta`` is intentionally tiny — the contract is ``dict`` in, file on
disk out, deterministic JSON. Callers own the path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_meta(path: Path, record: dict[str, Any]) -> None:
    """Write ``record`` to ``path`` as pretty-printed, key-sorted JSON.

    The parent directory is created if it does not exist. Raises the
    underlying OSError on filesystem failures — callers decide whether to
    swallow.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True))
