"""Append-only skill-usage telemetry log.

One JSON record per line under ``<repo>/telemetry/skills.jsonl``. Writes
are best-effort — every failure is swallowed so the skill-load path
cannot regress on a telemetry bug.

Each record follows the shape from the umbrella spec (§4):

    {
      "timestamp": "2026-04-18T12:00:00Z",
      "actor": "skill:<name>",
      "duration_ms": 7,
      "input_tokens": 0,
      "output_tokens": 0,
      "cost_usd": 0.0,
      "outcome": "ok" | "error",
      "detail": {...}
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _default_path() -> Path:
    """Return ``<repo>/telemetry/skills.jsonl`` derived from this file."""
    try:
        from app.config import _REPO_ROOT  # type: ignore[attr-defined]

        return Path(_REPO_ROOT) / "telemetry" / "skills.jsonl"
    except Exception:  # noqa: BLE001
        return Path(__file__).resolve().parents[3] / "telemetry" / "skills.jsonl"


def append_skill_event(
    record: dict[str, Any], *, override_path: Path | None = None
) -> None:
    """Append ``record`` to the skills telemetry log.

    Any exception is swallowed — callers must never observe telemetry
    failures. ``override_path`` is provided so tests can redirect writes
    to a tmp location without touching the global repo path.
    """
    try:
        target = override_path or _default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001
        pass


def telemetry_path() -> Path:
    """Expose default path for the REST route to read from."""
    return _default_path()
