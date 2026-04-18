"""Second-Brain REST routes — digest surface.

Thin shells that delegate to :mod:`app.tools.sb_digest_tools` handlers.
When ``SECOND_BRAIN_ENABLED`` is false every route returns 404 via
:func:`_require_enabled`, matching the ``_disabled`` envelope the
underlying tools already use.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config
from app.tools import sb_digest_tools

router = APIRouter(prefix="/api/sb", tags=["second-brain"])


def _require_enabled() -> None:
    if not getattr(config, "SECOND_BRAIN_ENABLED", False):
        raise HTTPException(status_code=404, detail="second_brain_disabled")


class ApplyBody(BaseModel):
    date: str | None = None
    ids: list[str] | str


class SkipBody(BaseModel):
    date: str | None = None
    id: str
    ttl_days: int | None = 30


class ReadBody(BaseModel):
    date: str


@router.get("/digest/today")
def digest_today() -> dict[str, Any]:
    _require_enabled()
    return sb_digest_tools.sb_digest_today({})


@router.post("/digest/apply")
def digest_apply(body: ApplyBody) -> dict[str, Any]:
    _require_enabled()
    return sb_digest_tools.sb_digest_apply(body.model_dump(exclude_none=True))


@router.post("/digest/skip")
def digest_skip(body: SkipBody) -> dict[str, Any]:
    _require_enabled()
    return sb_digest_tools.sb_digest_skip(body.model_dump(exclude_none=True))


@router.post("/digest/read")
def digest_read(body: ReadBody) -> dict[str, Any]:
    _require_enabled()
    from second_brain.config import Config

    cfg = Config.load()
    cfg.digests_dir.mkdir(parents=True, exist_ok=True)
    marks = cfg.digests_dir / ".read_marks"
    existing = (
        [ln.strip() for ln in marks.read_text().splitlines() if ln.strip()]
        if marks.exists()
        else []
    )
    if body.date not in existing:
        existing.append(body.date)
    marks.write_text("\n".join(existing) + "\n")
    return {"ok": True, "date": body.date}


@router.get("/stats")
def sb_stats() -> dict[str, Any]:
    _require_enabled()
    return sb_digest_tools.sb_stats({})
