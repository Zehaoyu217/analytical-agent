"""Gardener HTTP surface.

Exposes five endpoints under ``/api/sb/gardener``:

- ``GET  /status``    — ledger slot + enabled passes + model tiers
- ``POST /run``       — execute enabled passes, optionally dry-run
- ``POST /habits``    — patch ``GardenerHabits`` on the habits.yaml
- ``GET  /estimate``  — pre-flight cost estimate per enabled pass
- ``GET  /log``       — tail the audit JSONL, filterable by pass name

The runner and pass implementations live in the ``second_brain`` package
(see ``src/second_brain/gardener/``). This module is a thin adapter.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.tools import sb_pipeline_state

router = APIRouter(prefix="/api/sb/gardener", tags=["second-brain", "gardener"])


# ----------------------------------------------------------------------
# env/config helpers
# ----------------------------------------------------------------------


def _require_enabled() -> None:
    if not getattr(config, "SECOND_BRAIN_ENABLED", False):
        raise HTTPException(status_code=404, detail="second_brain_disabled")


def _cfg() -> Any:
    from second_brain.config import Config

    return Config.load()


def _load_habits(cfg: Any) -> Any:
    from second_brain.habits.loader import load_habits

    return load_habits(cfg)


def _save_habits(cfg: Any, habits: Any) -> None:
    from second_brain.habits.loader import save_habits

    save_habits(cfg, habits)


def _build_runner(cfg: Any, habits: Any) -> Any:
    from second_brain.gardener.runner import GardenerRunner

    return GardenerRunner(cfg, habits)


# ----------------------------------------------------------------------
# request bodies
# ----------------------------------------------------------------------


class RunRequest(BaseModel):
    dry_run: bool | None = None
    passes: list[str] | None = None


class HabitsPatch(BaseModel):
    mode: Literal["proposal", "autonomous"] | None = None
    models: dict[str, str] | None = None
    passes: dict[str, bool] | None = None
    max_cost_usd_per_run: float | None = Field(default=None, ge=0.0)
    max_tokens_per_source: int | None = Field(default=None, ge=0)
    dry_run: bool | None = None


# ----------------------------------------------------------------------
# routes
# ----------------------------------------------------------------------


@router.get("/status")
def gardener_status() -> dict[str, Any]:
    _require_enabled()
    cfg = _cfg()
    habits = _load_habits(cfg)
    state = sb_pipeline_state.read_state(cfg)
    slot = state.get("gardener", {"last_run_at": None, "result": None})
    g = habits.gardener
    return {
        "ok": True,
        "slot": slot,
        "habits": {
            "mode": g.mode,
            "models": dict(g.models),
            "passes": dict(g.passes),
            "max_cost_usd_per_run": g.max_cost_usd_per_run,
            "max_tokens_per_source": g.max_tokens_per_source,
            "dry_run": g.dry_run,
        },
        "enabled_passes": [name for name, on in g.passes.items() if on],
    }


@router.post("/run")
def gardener_run(body: RunRequest | None = None) -> dict[str, Any]:
    _require_enabled()
    cfg = _cfg()
    habits = _load_habits(cfg)
    runner = _build_runner(cfg, habits)
    try:
        result = runner.run(
            dry_run=body.dry_run if body else None,
            only=body.passes if body else None,
        )
    except Exception as exc:  # noqa: BLE001 - surface as structured 500
        raise HTTPException(
            status_code=500, detail=f"gardener_run_failed: {exc}"
        ) from exc

    summary = {
        "passes_run": list(result.passes_run),
        "proposals_added": result.proposals_added,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
        "duration_ms": result.duration_ms,
        "errors": list(result.errors),
    }
    # The runner best-effort writes the ledger; mirror it here for dry-run too.
    if not (body and body.dry_run):
        sb_pipeline_state.write_phase(cfg, "gardener", summary)
    return {"ok": True, "result": summary}


@router.post("/habits")
def gardener_habits_patch(body: HabitsPatch) -> dict[str, Any]:
    _require_enabled()
    cfg = _cfg()
    habits = _load_habits(cfg)

    patch = body.model_dump(exclude_none=True)
    current = habits.gardener.model_dump()
    # Deep-merge dict fields (models, passes); shallow overwrite for the rest.
    for key, value in patch.items():
        if key in ("models", "passes") and isinstance(value, dict):
            merged = dict(current.get(key, {}))
            merged.update(value)
            current[key] = merged
        else:
            current[key] = value

    try:
        updated = habits.model_copy(update={"gardener": habits.gardener.model_copy(update=current)})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid_habits: {exc}") from exc

    _save_habits(cfg, updated)
    return {"ok": True, "gardener": current}


@router.get("/estimate")
def gardener_estimate() -> dict[str, Any]:
    _require_enabled()
    cfg = _cfg()
    habits = _load_habits(cfg)
    runner = _build_runner(cfg, habits)
    est = runner.estimate()
    return {
        "ok": True,
        "passes": {
            name: {"tokens": p.tokens, "cost_usd": p.cost_usd}
            for name, p in est.passes.items()
        },
        "total_tokens": est.total_tokens,
        "total_cost_usd": est.total_cost_usd,
    }


@router.get("/log")
def gardener_log(n: int = 50, pass_name: str | None = None) -> dict[str, Any]:
    _require_enabled()
    from second_brain.gardener import audit

    cfg = _cfg()
    rows = audit.tail(cfg, n=n, filter_pass=pass_name)
    return {"ok": True, "rows": rows}
