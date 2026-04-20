"""Pipeline execution surface — status + maintain endpoints.

Sibling to :mod:`app.api.sb_api`. The ingest and digest routes live there
and write their outcomes into the shared pipeline state ledger via
:mod:`app.tools.sb_pipeline_state`. This module exposes:

- ``GET  /api/sb/pipeline/status`` — aggregate ledger snapshot
- ``POST /api/sb/maintain/run``     — invoke MaintainRunner, write outcome
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app import config
from app.tools import sb_pipeline_state

router = APIRouter(prefix="/api/sb", tags=["second-brain"])


def _require_enabled() -> None:
    if not getattr(config, "SECOND_BRAIN_ENABLED", False):
        raise HTTPException(status_code=404, detail="second_brain_disabled")


def _cfg() -> Any:
    from second_brain.config import Config

    return Config.load()


@router.get("/pipeline/status")
def pipeline_status() -> dict[str, Any]:
    _require_enabled()
    state = sb_pipeline_state.read_state(_cfg())
    return {"ok": True, **state}


@router.post("/maintain/run")
def maintain_run() -> dict[str, Any]:
    _require_enabled()
    try:
        summary = sb_pipeline_state.run_maintain(_cfg())
    except Exception as exc:  # noqa: BLE001 — surface as structured 500
        raise HTTPException(
            status_code=500, detail=f"maintain_run_failed: {exc}"
        ) from exc
    return {"ok": True, "result": summary}
