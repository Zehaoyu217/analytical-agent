"""Second-Brain REST routes — digest surface.

Thin shells that delegate to :mod:`app.tools.sb_digest_tools` handlers.
When ``SECOND_BRAIN_ENABLED`` is false every route returns 404 via
:func:`_require_enabled`, matching the ``_disabled`` envelope the
underlying tools already use.
"""
from __future__ import annotations

import json
import time
from datetime import date as date_t
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import config
from app.telemetry.sidecar import write_meta
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


class IngestBody(BaseModel):
    path: str


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


def _write_build_meta(
    cfg: Any,
    *,
    started: float,
    outcome: str,
    entries: int,
    emitted: bool,
) -> None:
    """Persist per-build telemetry sidecar.

    Writes to ``{cfg.digests_dir}/YYYY-MM-DD.meta.json``. Failures are
    swallowed — telemetry must never mask a real request outcome.
    """
    try:
        today = date_t.today().isoformat()
        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "actor": "digest.build",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "outcome": outcome,
            "detail": {"entries": entries, "emitted": emitted, "date": today},
        }
        write_meta(cfg.digests_dir / f"{today}.meta.json", record)
    except Exception:  # noqa: BLE001 — telemetry is best-effort
        pass


@router.post("/digest/build")
def digest_build() -> dict[str, Any]:
    _require_enabled()
    cfg = _sb_cfg()
    started = time.monotonic()
    try:
        habits = _load_habits(cfg)
        result = _run_build(cfg, habits)
    except Exception as exc:  # noqa: BLE001
        _write_build_meta(
            cfg, started=started, outcome="error", entries=0, emitted=False
        )
        raise HTTPException(status_code=500, detail=f"digest_build_failed: {exc}")
    entries = list(getattr(result, "entries", []) or [])
    emitted = len(entries) > 0
    _write_build_meta(
        cfg, started=started, outcome="ok", entries=len(entries), emitted=emitted
    )
    return {"ok": True, "emitted": emitted, "entries": len(entries)}


@router.get("/digest/costs")
def digest_costs(date: str | None = None) -> dict[str, Any]:
    """Return today's digest-build sidecar, or ``record: null`` when absent."""
    _require_enabled()
    day = date_t.fromisoformat(date) if date else date_t.today()
    cfg = _sb_cfg()
    meta = cfg.digests_dir / f"{day.isoformat()}.meta.json"
    if not meta.exists():
        return {"ok": True, "record": None}
    try:
        return {"ok": True, "record": json.loads(meta.read_text())}
    except json.JSONDecodeError:
        return {"ok": True, "record": None, "error": "malformed_meta"}


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


# ── Graph viz seam ──────────────────────────────────────────────────


_KIND_BY_PREFIX = {"clm_": "claim", "src_": "source"}


def _node_kind(node_id: str) -> str:
    for pfx, kind in _KIND_BY_PREFIX.items():
        if node_id.startswith(pfx):
            return kind
    return "wiki"


def _query_graph(
    cfg: Any,
    *,
    center: str | None,
    depth: int,
    limit: int,
) -> dict[str, Any]:
    """Query the property-graph DuckDB store for nodes and edges.

    When ``center`` is provided, returns edges within ``depth`` hops of
    that node. When missing, returns the top-N highest-degree nodes and
    the edges among them. Degrades to an empty payload when the store
    is missing, empty, or lacks the expected ``edges`` table.
    """
    import duckdb

    path = getattr(cfg, "duckdb_path", None)
    if path is None or not Path(path).exists():
        return {"ok": True, "center": center, "nodes": [], "edges": [], "note": "no graph data"}

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except Exception:  # noqa: BLE001
        return {"ok": True, "center": center, "nodes": [], "edges": [], "note": "no graph data"}

    try:
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables"
            ).fetchall()}
        except Exception:  # noqa: BLE001
            tables = set()
        if "edges" not in tables:
            return {
                "ok": True,
                "center": center,
                "nodes": [],
                "edges": [],
                "note": "no graph data",
            }

        edges: list[dict[str, str]] = []
        node_ids: set[str] = set()
        if center:
            frontier = {center}
            visited: set[str] = set()
            for _ in range(max(1, depth)):
                if not frontier:
                    break
                placeholders = ",".join(["?"] * len(frontier))
                rows = conn.execute(
                    f"SELECT src_id, dst_id, relation FROM edges "
                    f"WHERE src_id IN ({placeholders}) OR dst_id IN ({placeholders}) "
                    f"LIMIT {int(limit)}",
                    list(frontier) + list(frontier),
                ).fetchall()
                visited |= frontier
                next_frontier: set[str] = set()
                for src, dst, rel in rows:
                    edges.append({"src": src, "dst": dst, "kind": rel})
                    node_ids.add(src)
                    node_ids.add(dst)
                    for nb in (src, dst):
                        if nb not in visited:
                            next_frontier.add(nb)
                frontier = next_frontier
                if len(edges) >= limit:
                    break
            node_ids.add(center)
        else:
            # Pick nodes with highest degree, then fetch their edges.
            deg_rows = conn.execute(
                "SELECT node_id, cnt FROM ("
                "  SELECT src_id AS node_id FROM edges "
                "  UNION ALL SELECT dst_id FROM edges"
                ") GROUP BY node_id ORDER BY COUNT(*) DESC LIMIT ?",
                [int(limit)],
            ).fetchall()
            top_ids = [r[0] for r in deg_rows]
            if not top_ids:
                return {
                    "ok": True,
                    "center": None,
                    "nodes": [],
                    "edges": [],
                    "note": "no graph data",
                }
            placeholders = ",".join(["?"] * len(top_ids))
            rows = conn.execute(
                f"SELECT src_id, dst_id, relation FROM edges "
                f"WHERE src_id IN ({placeholders}) AND dst_id IN ({placeholders}) "
                f"LIMIT {int(limit)}",
                top_ids + top_ids,
            ).fetchall()
            node_ids.update(top_ids)
            for src, dst, rel in rows:
                edges.append({"src": src, "dst": dst, "kind": rel})

        # Resolve labels when the `claims` / `sources` tables exist.
        labels: dict[str, str] = {}
        if node_ids:
            placeholders = ",".join(["?"] * len(node_ids))
            if "claims" in tables:
                try:
                    for r in conn.execute(
                        f"SELECT id, statement FROM claims WHERE id IN ({placeholders})",
                        list(node_ids),
                    ).fetchall():
                        labels[r[0]] = (r[1] or r[0])[:80]
                except Exception:  # noqa: BLE001
                    pass
            if "sources" in tables:
                try:
                    for r in conn.execute(
                        f"SELECT id, title FROM sources WHERE id IN ({placeholders})",
                        list(node_ids),
                    ).fetchall():
                        labels[r[0]] = (r[1] or r[0])[:80]
                except Exception:  # noqa: BLE001
                    pass

        nodes = [
            {"id": nid, "kind": _node_kind(nid), "label": labels.get(nid, nid)}
            for nid in node_ids
        ]
    finally:
        conn.close()

    return {"ok": True, "center": center, "nodes": nodes, "edges": edges}


@router.get("/graph")
def sb_graph(
    center: str | None = None, depth: int = 1, limit: int = 60
) -> dict[str, Any]:
    _require_enabled()
    cfg = _sb_cfg()
    return _query_graph(
        cfg,
        center=center,
        depth=max(1, min(depth, 2)),
        limit=max(1, min(limit, 200)),
    )


# ── Ingest ─────────────────────────────────────────────────────────


@router.post("/ingest")
def sb_ingest_route(body: IngestBody) -> dict[str, Any]:
    _require_enabled()
    from app.tools import sb_tools

    return sb_tools.sb_ingest(body.model_dump())


@router.post("/ingest/upload")
async def sb_ingest_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    """Accept a browser file upload, stage it on disk, and run ingest.

    Browsers deliberately hide real filesystem paths, so the file has to
    travel as multipart bytes. We stage under a per-day temp dir inside
    the second_brain inbox, then hand the path to the existing ingest
    tool — which treats it exactly like a dropped local file.
    """
    _require_enabled()
    import tempfile
    from app.tools import sb_tools

    raw = await file.read()
    if not raw:
        return {"ok": False, "error": "empty file"}

    suffix = Path(file.filename or "upload").suffix or ""
    stem = Path(file.filename or "upload").stem or "upload"
    tmp_dir = Path(tempfile.gettempdir()) / "sb-ingest-uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    staged = tempfile.NamedTemporaryFile(
        dir=tmp_dir, prefix=f"{stem}-", suffix=suffix, delete=False
    )
    try:
        staged.write(raw)
    finally:
        staged.close()

    return sb_tools.sb_ingest({"path": staged.name})


# ── Drift (graph↔wiki) ──────────────────────────────────────────────


def _drift_dir() -> Path:
    """Telemetry dir for drift snapshots — overridable in tests."""
    return Path(getattr(config, "DRIFT_TELEMETRY_DIR", None)
                or Path(__file__).resolve().parents[3] / "telemetry" / "drift")


def _drift_path(day: date_t) -> Path:
    return _drift_dir() / f"{day.isoformat()}.json"


@router.get("/drift")
def sb_drift(date: str | None = None) -> dict[str, Any]:
    """Return the drift snapshot for ``date`` (default: today).

    Returns ``{"ok": True, "report": null}`` when no snapshot exists so
    the UI can render an empty state without special-casing 404.
    """
    _require_enabled()
    day = date_t.fromisoformat(date) if date else date_t.today()
    path = _drift_path(day)
    if not path.exists():
        return {"ok": True, "report": None}
    try:
        return {"ok": True, "report": json.loads(path.read_text(encoding="utf-8"))}
    except json.JSONDecodeError:
        return {"ok": True, "report": None, "error": "malformed_report"}

