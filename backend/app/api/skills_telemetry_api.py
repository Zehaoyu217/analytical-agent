"""Skills telemetry REST route.

Reads ``telemetry/skills.jsonl`` (newline-delimited JSON records produced
by :mod:`app.telemetry.skills_log`) and returns the most recent ``limit``
events in reverse-chronological order.

Intentionally **not** gated on ``SECOND_BRAIN_ENABLED`` — skill telemetry
is knowledge-base independent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.telemetry.skills_log import telemetry_path

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _telemetry_path() -> Path:
    """Seam for tests to override the log location."""
    return telemetry_path()


@router.get("/telemetry")
def skills_telemetry(limit: int = 200) -> dict[str, Any]:
    path = _telemetry_path()
    if not path.exists():
        return {"ok": True, "count": 0, "events": []}
    lines = path.read_text().splitlines()
    events: list[dict[str, Any]] = []
    for raw in reversed(lines[-limit:]):
        line = raw.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"ok": True, "count": len(events), "events": events}
