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


# ── Seams for digest pending / build (monkeypatched in tests) ──────


def _sb_cfg():  # noqa: ANN202
    from second_brain.config import Config

    return Config.load()


def _read_pending(cfg):  # noqa: ANN001, ANN202
    from second_brain.digest.pending import read_pending

    return read_pending(cfg)


def _load_habits(cfg):  # noqa: ANN001, ANN202
    from second_brain.habits.loader import load_habits

    return load_habits(cfg)


def _run_build(cfg, habits):  # noqa: ANN001, ANN202
    from datetime import date

    from second_brain.digest.builder import DigestBuilder

    return DigestBuilder(cfg, habits=habits).build(today=date.today())


@router.get("/digest/pending")
def digest_pending() -> dict[str, Any]:
    _require_enabled()
    cfg = _sb_cfg()
    proposals = [
        {
            "id": getattr(p, "id", ""),
            "section": getattr(p, "section", ""),
            "line": getattr(p, "line", ""),
            "action": getattr(p, "action", {}) or {},
        }
        for p in _read_pending(cfg)
    ]
    return {"ok": True, "count": len(proposals), "proposals": proposals}


@router.post("/digest/build")
def digest_build() -> dict[str, Any]:
    _require_enabled()
    cfg = _sb_cfg()
    habits = _load_habits(cfg)
    result = _run_build(cfg, habits)
    entries = list(getattr(result, "entries", []) or [])
    return {"ok": True, "emitted": len(entries) > 0, "entries": len(entries)}


# ── KB recall (devtools memory layer) ───────────────────────────────


def _last_user_prompt_for(session_id: str) -> str | None:
    """Return the most recent user-role message text for ``session_id``.

    Returns ``None`` if the session is missing or has no user messages.
    Session lookup uses :class:`app.storage.session_db.SessionDB` so the
    route can be tested without touching the real DB (monkeypatch this
    helper directly).
    """
    try:
        from app.harness.wiring import get_session_db
    except Exception:  # noqa: BLE001
        return None
    session = get_session_db().get_session(session_id, include_messages=True)
    if session is None:
        return None
    for msg in reversed(session.messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return None


def _build_injection(cfg, habits, prompt):  # noqa: ANN001, ANN202
    from second_brain.inject.runner import build_injection

    return build_injection(cfg, habits, prompt)


@router.get("/memory/session/{session_id}")
def sb_memory_session(session_id: str, prompt: str | None = None) -> dict[str, Any]:
    _require_enabled()
    resolved_prompt = prompt if prompt else _last_user_prompt_for(session_id)
    if not resolved_prompt:
        return {"ok": True, "hits": [], "block": "", "skipped_reason": "no_user_prompt"}
    cfg = _sb_cfg()
    habits = _load_habits(cfg)
    result = _build_injection(cfg, habits, resolved_prompt)
    return {
        "ok": True,
        "hits": [{"id": h} for h in getattr(result, "hit_ids", []) or []],
        "block": getattr(result, "block", "") or "",
        "skipped_reason": getattr(result, "skipped_reason", None),
    }
