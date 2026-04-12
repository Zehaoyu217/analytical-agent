"""REST endpoints for the trace subsystem."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.trace.assembler import StepNotFoundError, assemble_prompt
from app.trace.judge_replay import MissingApiKeyError, run_judge_variance
from app.trace.store import TraceNotFoundError, list_traces, load_trace
from app.trace.timeline import build_timeline

router = APIRouter(prefix="/api/trace", tags=["trace"])

_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_STEP_ID_RE = re.compile(r"^s\d+$")


def _traces_dir() -> Path:
    return Path(os.environ.get("TRACE_DIR", "traces"))


def _threshold() -> float:
    return float(os.environ.get("JUDGE_VARIANCE_THRESHOLD", "0.10"))


def _validate_trace_id(trace_id: str) -> None:
    if not _TRACE_ID_RE.match(trace_id):
        raise HTTPException(status_code=400, detail="invalid trace_id")


def _validate_step_id(step_id: str) -> None:
    if not _STEP_ID_RE.match(step_id):
        raise HTTPException(status_code=400, detail="invalid step_id")


def _load_trace_or_raise(trace_id: str) -> object:
    _validate_trace_id(trace_id)
    try:
        return load_trace(_traces_dir(), trace_id)
    except TraceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Failed to load trace") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail="Failed to load trace") from exc


@router.get("/traces")
def list_traces_endpoint() -> dict[str, object]:
    try:
        summaries = list_traces(_traces_dir())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=500, detail="Failed to list traces") from exc
    return {"traces": [s.model_dump() for s in summaries]}


# Sub-resource routes must be registered BEFORE the catch-all /:path route.

@router.get("/traces/{trace_id}/prompt/{step_id}")
def get_prompt_assembly(trace_id: str, step_id: str) -> dict[str, object]:
    _validate_step_id(step_id)
    trace = _load_trace_or_raise(trace_id)
    try:
        return assemble_prompt(trace, step_id)  # type: ignore[arg-type]
    except StepNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/traces/{trace_id}/timeline")
def get_timeline(trace_id: str) -> dict[str, object]:
    trace = _load_trace_or_raise(trace_id)
    return build_timeline(trace)  # type: ignore[arg-type]


@router.get("/traces/{trace_id}/judge-variance")
def get_judge_variance(
    trace_id: str,
    refresh: int = Query(default=0),
    n: int = Query(default=5, ge=1, le=20),
) -> dict[str, object]:
    trace = _load_trace_or_raise(trace_id)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    try:
        return run_judge_variance(
            trace,  # type: ignore[arg-type]
            n=n,
            refresh=bool(refresh),
            threshold=_threshold(),
            live_runner=None,
            api_key=api_key,
        )
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/traces/{trace_id}/events")
def get_events(
    trace_id: str, kind: str | None = Query(default=None),
) -> dict[str, object]:
    trace = _load_trace_or_raise(trace_id)
    events = trace.events  # type: ignore[attr-defined]
    if kind is not None:
        events = [e for e in events if e.kind == kind]
    return {"events": [e.model_dump() for e in events]}


# Catch-all: use :path so percent-encoded slashes (e.g. ..%2F..) are captured
# and rejected by _validate_trace_id rather than causing a 404.
@router.get("/traces/{trace_id:path}")
def get_trace(trace_id: str) -> dict[str, object]:
    trace = _load_trace_or_raise(trace_id)
    return cast(dict[str, object], trace.model_dump())  # type: ignore[attr-defined]
