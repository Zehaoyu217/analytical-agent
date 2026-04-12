"""REST endpoints for DevTools SOP views."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.sop.ladder_loader import load_all_ladders
from app.sop.log import list_entries, read_entry
from app.sop.preflight import JUDGE_VARIANCE_THRESHOLD

router = APIRouter(prefix="/api/sop", tags=["sop"])


def _log_dir() -> Path:
    return Path(os.environ.get("SOP_LOG_DIR", "docs/superpowers/sop-log"))


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    return {"sessions": [e.model_dump() for e in list_entries(_log_dir())]}


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    try:
        entry = read_entry(session_id, _log_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return entry.model_dump()


@router.get("/ladders")
def list_ladders() -> dict[str, Any]:
    return {"ladders": [ld.model_dump() for ld in load_all_ladders()]}


def compute_judge_variance(trace_id: str, n: int) -> dict[str, float]:
    """Placeholder stub — returns empty variance.

    Real implementation re-runs the judge N times and computes per-dimension
    variance. Deferred to v2 (see app/sop/judge_replay.py in the plan).
    """
    _ = (trace_id, n)
    return {}


@router.get("/judge-variance/{trace_id}")
def judge_variance(trace_id: str, n: int = 5) -> dict[str, object]:
    variance = compute_judge_variance(trace_id, n)
    exceeded = [dim for dim, v in variance.items() if v > JUDGE_VARIANCE_THRESHOLD]
    return {"variance": variance, "threshold_exceeded": exceeded}
