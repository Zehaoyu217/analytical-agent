"""Pipeline state ledger — tracks last-run outcome per phase.

Three phases share a single JSON file at ``{sb_dir}/.state/pipeline.json``:
``ingest``, ``digest``, ``maintain``. Each slot stores an ISO timestamp
and a phase-specific result summary.

Writes are best-effort: a corrupt or missing state file never surfaces
as a route error, because the underlying phase already succeeded by the
time we reach the ledger.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Phase = Literal["ingest", "digest", "maintain"]
_EMPTY_SLOT: dict[str, Any] = {"last_run_at": None, "result": None}


def _state_path(cfg: Any) -> Path:
    return Path(cfg.sb_dir) / ".state" / "pipeline.json"


def _blank_state() -> dict[str, Any]:
    return {
        "ingest": dict(_EMPTY_SLOT),
        "digest": dict(_EMPTY_SLOT),
        "maintain": dict(_EMPTY_SLOT),
    }


def read_state(cfg: Any) -> dict[str, Any]:
    """Return the current state ledger; empty slots when file missing."""
    path = _state_path(cfg)
    if not path.exists():
        return _blank_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _blank_state()
    state = _blank_state()
    for phase in ("ingest", "digest", "maintain"):
        slot = raw.get(phase)
        if isinstance(slot, dict):
            state[phase] = {
                "last_run_at": slot.get("last_run_at"),
                "result": slot.get("result"),
            }
    return state


def write_phase(cfg: Any, phase: Phase, result: dict[str, Any]) -> bool:
    """Update one phase slot; swallow IO errors."""
    try:
        state = read_state(cfg)
        state[phase] = {
            "last_run_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "result": result,
        }
        path = _state_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return True
    except (OSError, TypeError, ValueError):
        return False


def run_maintain(cfg: Any) -> dict[str, Any]:
    """Invoke the MaintainRunner and return a JSON-safe summary.

    Writes the outcome into the state ledger. Propagates exceptions so
    the route layer can translate them to HTTP 500.
    """
    from second_brain.maintain.runner import MaintainRunner

    report = MaintainRunner(cfg).run(build_digest=False)
    lint_counts = dict(report.lint_counts)
    summary = {
        "lint_errors": int(lint_counts.get("error", 0)),
        "lint_warnings": int(lint_counts.get("warning", 0)),
        "lint_info": int(lint_counts.get("info", 0)),
        "open_contradictions": report.open_contradictions,
        "stale_abstracts": list(report.stale_abstracts),
        "stale_count": len(report.stale_abstracts),
        "analytics_rebuilt": report.analytics_rebuilt,
        "habit_proposals": report.habit_proposals,
        "fts_bytes_before": report.fts_bytes_before,
        "fts_bytes_after": report.fts_bytes_after,
        "duck_bytes_before": report.duck_bytes_before,
        "duck_bytes_after": report.duck_bytes_after,
    }
    write_phase(cfg, "maintain", summary)
    return summary
