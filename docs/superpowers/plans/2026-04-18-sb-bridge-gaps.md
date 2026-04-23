# SB Bridge Gaps Implementation Plan

> Historical note (2026-04-22): This plan was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the second-brain v2 digest surface to the agent (7 tools + pre-turn hook) and to the frontend (right-rail DigestPanel + 4 REST routes), with a sb-side pending-proposal merge.

**Architecture:** Additive. Seven new tool handlers in `sb_tools.py` wrap `second_brain.digest` module calls, mirroring existing `sb_search`/`sb_load` patterns with `_disabled()` envelope. A pre-turn hook reads today's digest, computes unread count, and injects a one-paragraph summary via `InjectorInputs.extras`. Frontend adds a Zustand-backed right-rail panel that polls `/api/sb/digest/today` and calls `apply`/`skip`/`read` endpoints. `sb_digest_propose` appends to `digests/pending.jsonl`; a new builder pre-pass merges that file into the next build.

**Tech Stack:** Python 3.13 / FastAPI / pytest for backend. React 18 / TypeScript / Zustand / vitest for frontend. Second-brain: existing `DigestApplier`, `SkipRegistry`, `DigestBuilder`, `Stats`, `HealthScore`. All gated by `SECOND_BRAIN_ENABLED` and `SB_DIGEST_HOOK_ENABLED`.

---

## File Structure

### New files

- `backend/app/tools/sb_digest_tools.py` — 7 new handlers (sb_digest_today, _list, _show, _apply, _skip, _propose, sb_stats)
- `backend/app/tools/tests/test_sb_digest_tools.py`
- `backend/app/hooks/__init__.py`
- `backend/app/hooks/sb_digest_hook.py` — `build_digest_summary(cfg) -> str | None`
- `backend/app/hooks/tests/__init__.py`
- `backend/app/hooks/tests/test_sb_digest_hook.py`
- `backend/app/api/sb_api.py` — 4 digest routes + router registration
- `backend/tests/api/test_sb_api.py`
- `frontend/src/lib/digest-store.ts` — Zustand store
- `frontend/src/components/digest/DigestPanel.tsx`
- `frontend/src/components/digest/DigestEntry.tsx`
- `frontend/src/components/digest/DigestHeader.tsx`
- `frontend/src/components/digest/digest.css`
- `frontend/src/components/digest/__tests__/DigestPanel.test.tsx`
- `frontend/src/components/digest/__tests__/DigestEntry.test.tsx`
- Second-brain repo: `src/second_brain/digest/pending.py` — `merge_pending(cfg, entries) -> list[DigestEntry]`
- Second-brain repo: `tests/digest/test_pending_merge.py`

### Modified files

- `backend/app/api/chat_api.py` — +7 ToolSchema, +7 dispatcher.register lines, add digest hook call in `_build_system_prompt`
- `backend/app/main.py` (or wherever FastAPI router is assembled) — include sb_api router
- `frontend/src/App.tsx` — mount DigestPanel in right rail
- Second-brain `src/second_brain/digest/builder.py` — call `merge_pending` in `build()`

---

## Batch 1 — Bridge tools

### Task 1: sb_digest_today handler

**Files:**
- Create: `backend/app/tools/sb_digest_tools.py`
- Test: `backend/app/tools/tests/test_sb_digest_tools.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/tools/tests/test_sb_digest_tools.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app import config as app_config


@pytest.fixture
def sb_home(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / "digests").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    return home


def _write_digest(home: Path, today: date, entries: list[dict]) -> None:
    digest_dir = home / "digests"
    md = f"# Digest {today.isoformat()}\n\n"
    for e in entries:
        md += f"## {e['section']}\n- [{e['id']}] {e['line']}\n"
    (digest_dir / f"{today.isoformat()}.md").write_text(md)
    sidecar = digest_dir / f"{today.isoformat()}.actions.jsonl"
    with sidecar.open("w") as f:
        for e in entries:
            f.write(json.dumps({"id": e["id"], "section": e["section"], "action": e["action"]}) + "\n")


def test_sb_digest_today_happy_path(sb_home):
    from app.tools.sb_digest_tools import sb_digest_today
    today = date.today()
    _write_digest(sb_home, today, [
        {"id": "r01", "section": "Reconciliation", "line": "upgrade clm_foo", "action": {"action": "upgrade_confidence", "claim_id": "clm_foo", "from": "low", "to": "medium", "rationale": "x"}},
    ])
    result = sb_digest_today({})
    assert result["ok"] is True
    assert result["date"] == today.isoformat()
    assert result["entry_count"] == 1
    assert result["unread"] == 1
    assert result["entries"][0]["id"] == "r01"


def test_sb_digest_today_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    from app.tools.sb_digest_tools import sb_digest_today
    result = sb_digest_today({})
    assert result == {"ok": False, "error": "second_brain_disabled"}


def test_sb_digest_today_missing(sb_home):
    from app.tools.sb_digest_tools import sb_digest_today
    result = sb_digest_today({})
    assert result["ok"] is True
    assert result["entry_count"] == 0
    assert result["entries"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest app/tools/tests/test_sb_digest_tools.py::test_sb_digest_today_happy_path -v`
Expected: ModuleNotFoundError: `app.tools.sb_digest_tools`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/tools/sb_digest_tools.py
"""Second-Brain digest tool handlers.

Each function returns a JSON-serializable dict.  When the KB is disabled,
each handler returns ``{"ok": False, "error": "second_brain_disabled"}``.
"""
from __future__ import annotations

import json
from datetime import date as date_t, datetime, timezone
from pathlib import Path
from typing import Any

from app import config


def _disabled(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": "second_brain_disabled"}
    if extra:
        out.update(extra)
    return out


def _cfg():  # noqa: ANN202
    from second_brain.config import Config
    return Config.load()


def _parse_date(raw: str | None) -> date_t:
    if not raw:
        return date_t.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _entries_for(cfg, day: date_t) -> list[dict[str, Any]]:
    sidecar = cfg.digests_dir / f"{day.isoformat()}.actions.jsonl"
    if not sidecar.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in sidecar.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _applied_ids(cfg, day: date_t) -> set[str]:
    path = cfg.digests_dir / f"{day.isoformat()}.applied.jsonl"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for ln in path.read_text().splitlines():
        try:
            ids.add(json.loads(ln).get("id", ""))
        except json.JSONDecodeError:
            continue
    ids.discard("")
    return ids


def sb_digest_today(_args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    cfg = _cfg()
    today = date_t.today()
    entries = _entries_for(cfg, today)
    applied = _applied_ids(cfg, today)
    shaped = [
        {
            "id": e.get("id", ""),
            "section": e.get("section", ""),
            "line": e.get("action", {}).get("rationale")
                    or e.get("action", {}).get("action", ""),
            "action": e.get("action", {}).get("action", ""),
            "applied": e.get("id") in applied,
        }
        for e in entries
    ]
    unread = sum(1 for s in shaped if not s["applied"])
    return {
        "ok": True,
        "date": today.isoformat(),
        "entry_count": len(shaped),
        "unread": unread,
        "entries": shaped,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest app/tools/tests/test_sb_digest_tools.py -v`
Expected: all three `sb_digest_today_*` tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/sb_digest_tools.py backend/app/tools/tests/test_sb_digest_tools.py
git commit -m "feat(bridge): add sb_digest_today handler"
```

---

### Task 2: sb_digest_list and sb_digest_show handlers

**Files:** Same as Task 1.

- [ ] **Step 1: Write failing tests**

```python
# append to backend/app/tools/tests/test_sb_digest_tools.py
from datetime import timedelta

def test_sb_digest_list(sb_home):
    from app.tools.sb_digest_tools import sb_digest_list
    today = date.today()
    yday = today - timedelta(days=1)
    _write_digest(sb_home, today, [{"id": "r01", "section": "Reconciliation", "line": "a", "action": {"action": "keep"}}])
    _write_digest(sb_home, yday, [{"id": "r01", "section": "Taxonomy", "line": "b", "action": {"action": "keep"}}])
    result = sb_digest_list({"limit": 5})
    assert result["ok"] is True
    dates = [d["date"] for d in result["digests"]]
    assert dates == [today.isoformat(), yday.isoformat()]
    assert result["digests"][0]["entry_count"] == 1


def test_sb_digest_show(sb_home):
    from app.tools.sb_digest_tools import sb_digest_show
    today = date.today()
    _write_digest(sb_home, today, [{"id": "r01", "section": "Reconciliation", "line": "x", "action": {"action": "keep"}}])
    result = sb_digest_show({"date": today.isoformat()})
    assert result["ok"] is True
    assert result["date"] == today.isoformat()
    assert "Digest" in result["markdown"]
    assert result["entries"][0]["id"] == "r01"


def test_sb_digest_show_missing(sb_home):
    from app.tools.sb_digest_tools import sb_digest_show
    result = sb_digest_show({"date": "2099-01-01"})
    assert result == {"ok": False, "error": "digest_not_found", "date": "2099-01-01"}
```

- [ ] **Step 2: Verify failure** — `pytest ... -v` should error on missing symbols.

- [ ] **Step 3: Implement**

```python
# append to backend/app/tools/sb_digest_tools.py

def sb_digest_list(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"digests": []})
    limit = int(args.get("limit", 10))
    cfg = _cfg()
    digests_dir: Path = cfg.digests_dir
    if not digests_dir.exists():
        return {"ok": True, "digests": []}
    rows: list[dict[str, Any]] = []
    for md in sorted(digests_dir.glob("????-??-??.md"), reverse=True):
        day_str = md.stem
        try:
            day = _parse_date(day_str)
        except ValueError:
            continue
        entries = _entries_for(cfg, day)
        applied = _applied_ids(cfg, day)
        rows.append({
            "date": day_str,
            "entry_count": len(entries),
            "applied_count": len(applied),
            "read": (digests_dir / ".read_marks").exists()
                    and day_str in (digests_dir / ".read_marks").read_text().split(),
        })
        if len(rows) >= limit:
            break
    return {"ok": True, "digests": rows}


def sb_digest_show(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    date_str = str(args.get("date", "")).strip()
    if not date_str:
        return {"ok": False, "error": "missing date"}
    cfg = _cfg()
    md_path = cfg.digests_dir / f"{date_str}.md"
    if not md_path.exists():
        return {"ok": False, "error": "digest_not_found", "date": date_str}
    day = _parse_date(date_str)
    entries = _entries_for(cfg, day)
    applied = _applied_ids(cfg, day)
    shaped = [
        {
            "id": e.get("id", ""),
            "section": e.get("section", ""),
            "line": e.get("action", {}).get("rationale")
                    or e.get("action", {}).get("action", ""),
            "action": e.get("action", {}).get("action", ""),
            "applied": e.get("id") in applied,
            "skipped": False,
        }
        for e in entries
    ]
    return {
        "ok": True,
        "date": date_str,
        "markdown": md_path.read_text(),
        "entries": shaped,
    }
```

- [ ] **Step 4: Verify** — `pytest app/tools/tests/test_sb_digest_tools.py -v` passes all new tests.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add sb_digest_list and sb_digest_show handlers"
```

---

### Task 3: sb_digest_apply handler

**Files:** Same as Task 1.

- [ ] **Step 1: Write failing test**

```python
def test_sb_digest_apply_delegates_to_applier(sb_home, monkeypatch):
    from app.tools import sb_digest_tools
    today = date.today()
    called = {}
    class FakeResult:
        applied = ["r01"]
        skipped = []
        failed = []
    class FakeApplier:
        def __init__(self, cfg): called["cfg"] = cfg
        def apply(self, *, digest_date, entry_ids):
            called["date"] = digest_date
            called["ids"] = entry_ids
            return FakeResult()
    monkeypatch.setattr(sb_digest_tools, "_DigestApplier", FakeApplier, raising=False)
    result = sb_digest_tools.sb_digest_apply({"ids": ["r01"]})
    assert result == {"ok": True, "applied": ["r01"], "skipped": [], "failed": []}
    assert called["ids"] == ["r01"]
    assert called["date"] == today


def test_sb_digest_apply_invalid_args(sb_home):
    from app.tools.sb_digest_tools import sb_digest_apply
    assert sb_digest_apply({"ids": []})["ok"] is False
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# append to backend/app/tools/sb_digest_tools.py

def _load_applier():  # seam for tests
    from second_brain.digest.applier import DigestApplier
    return DigestApplier


_DigestApplier = None  # late-bound; tests may monkeypatch


def sb_digest_apply(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    raw_ids = args.get("ids")
    if raw_ids != "all" and not (isinstance(raw_ids, list) and raw_ids):
        return {"ok": False, "error": "ids required (list or 'all')"}
    date_str = args.get("date")
    day = _parse_date(date_str) if date_str else date_t.today()
    cfg = _cfg()
    if raw_ids == "all":
        ids = [e.get("id", "") for e in _entries_for(cfg, day)]
        ids = [i for i in ids if i]
    else:
        ids = [str(x) for x in raw_ids]
    applier_cls = _DigestApplier or _load_applier()
    result = applier_cls(cfg).apply(digest_date=day, entry_ids=ids)
    return {
        "ok": True,
        "applied": list(result.applied),
        "skipped": list(result.skipped),
        "failed": list(result.failed),
    }
```

- [ ] **Step 4: Verify tests pass.**

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add sb_digest_apply handler"
```

---

### Task 4: sb_digest_skip handler

- [ ] **Step 1: Write failing test**

```python
def test_sb_digest_skip_uses_registry(sb_home, monkeypatch):
    from app.tools import sb_digest_tools
    captured = {}
    class FakeRegistry:
        def __init__(self, cfg): captured["cfg"] = cfg
        def skip_by_id(self, digest_date, entry_id, *, ttl_days):
            captured["id"] = entry_id
            captured["ttl"] = ttl_days
            return ("sig_abc", "2099-01-01")
    monkeypatch.setattr(sb_digest_tools, "_SkipRegistry", FakeRegistry, raising=False)
    result = sb_digest_tools.sb_digest_skip({"id": "r01", "ttl_days": 30})
    assert result["ok"] is True
    assert result["signature"] == "sig_abc"
    assert captured["ttl"] == 30
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# append to backend/app/tools/sb_digest_tools.py

def _load_skip_registry():
    from second_brain.digest.skip import SkipRegistry
    return SkipRegistry


_SkipRegistry = None


def sb_digest_skip(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    entry_id = str(args.get("id", "")).strip()
    if not entry_id:
        return {"ok": False, "error": "id required"}
    ttl = int(args.get("ttl_days", 30))
    day = _parse_date(args.get("date"))
    cfg = _cfg()
    registry_cls = _SkipRegistry or _load_skip_registry()
    signature, expires_at = registry_cls(cfg).skip_by_id(day, entry_id, ttl_days=ttl)
    return {"ok": True, "signature": signature, "expires_at": str(expires_at)}
```

> The real `SkipRegistry.skip_by_id` returns either a signature or None; wrap with an adapter if needed. If it returns only a bool, adjust the implementation to read the signature index file after the call.

- [ ] **Step 4: Verify.** Run tests; adjust return-value handling if real signature shape differs from mock.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add sb_digest_skip handler"
```

---

### Task 5: sb_digest_propose handler (writes pending.jsonl)

- [ ] **Step 1: Write failing test**

```python
def test_sb_digest_propose_appends_pending(sb_home):
    from app.tools.sb_digest_tools import sb_digest_propose
    action = {"action": "upgrade_confidence", "claim_id": "clm_x", "from": "low", "to": "medium", "rationale": "r"}
    r1 = sb_digest_propose({"section": "Reconciliation", "action": action})
    assert r1["ok"] is True
    assert r1["pending_id"].startswith("pend_")
    pending = sb_home / "digests" / "pending.jsonl"
    assert pending.exists()
    lines = pending.read_text().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["section"] == "Reconciliation"
    assert payload["action"]["claim_id"] == "clm_x"


def test_sb_digest_propose_rejects_unknown_action(sb_home):
    from app.tools.sb_digest_tools import sb_digest_propose
    result = sb_digest_propose({"section": "Reconciliation", "action": {"action": "zzz"}})
    assert result == {"ok": False, "error": "invalid_action_type"}
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# append to backend/app/tools/sb_digest_tools.py

_VALID_ACTIONS = frozenset({
    "upgrade_confidence",
    "resolve_contradiction",
    "promote_wiki_to_claim",
    "backlink_claim_to_wiki",
    "add_taxonomy_root",
    "re_abstract_batch",
    "drop_edge",
    "keep",
})


def sb_digest_propose(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    section = str(args.get("section", "")).strip()
    action = args.get("action")
    if not section:
        return {"ok": False, "error": "section required"}
    if not isinstance(action, dict) or action.get("action") not in _VALID_ACTIONS:
        return {"ok": False, "error": "invalid_action_type"}
    cfg = _cfg()
    pending = cfg.digests_dir / "pending.jsonl"
    pending.parent.mkdir(parents=True, exist_ok=True)
    existing = pending.read_text().splitlines() if pending.exists() else []
    pending_id = f"pend_{len(existing) + 1:04d}"
    record = {
        "id": pending_id,
        "section": section,
        "action": action,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
    }
    with pending.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"ok": True, "pending_id": pending_id, "file": str(pending)}
```

- [ ] **Step 4: Verify.**

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add sb_digest_propose handler"
```

---

### Task 6: sb_stats handler

- [ ] **Step 1: Write failing test**

```python
def test_sb_stats_delegates(sb_home, monkeypatch):
    from app.tools import sb_digest_tools
    class FakeStats:
        def to_dict(self): return {"claims": 42, "unread_stale_digests": 0}
    class FakeHealth:
        def to_dict(self): return {"score": 87, "breakdown": {}}
    def fake_collect(cfg):
        return FakeStats(), FakeHealth()
    monkeypatch.setattr(sb_digest_tools, "_collect_stats", fake_collect, raising=False)
    result = sb_digest_tools.sb_stats({})
    assert result == {"ok": True, "stats": {"claims": 42, "unread_stale_digests": 0},
                      "health": {"score": 87, "breakdown": {}}}
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# append to backend/app/tools/sb_digest_tools.py

def _collect_stats(cfg):
    from second_brain.stats import collect_stats, compute_health
    s = collect_stats(cfg)
    h = compute_health(cfg, s)
    return s, h


def sb_stats(_args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    cfg = _cfg()
    stats, health = _collect_stats(cfg)
    return {
        "ok": True,
        "stats": stats.to_dict() if hasattr(stats, "to_dict") else dict(stats.__dict__),
        "health": health.to_dict() if hasattr(health, "to_dict") else dict(health.__dict__),
    }
```

> If `second_brain.stats` exposes different names (e.g. `Stats.collect`), adjust the imports inside `_collect_stats` only.

- [ ] **Step 4: Verify.**

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add sb_stats handler"
```

---

### Task 7: Register 7 new tools in chat_api.py

**Files:**
- Modify: `backend/app/api/chat_api.py:370-490` (ToolSchema block)
- Modify: `backend/app/api/chat_api.py:965-975` (dispatcher.register block)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/api/test_sb_tools_registered.py
def test_all_digest_tools_registered():
    from app.api.chat_api import _SB_DIGEST_TODAY, _SB_DIGEST_LIST, _SB_DIGEST_SHOW, \
        _SB_DIGEST_APPLY, _SB_DIGEST_SKIP, _SB_DIGEST_PROPOSE, _SB_STATS
    names = {s.name for s in [_SB_DIGEST_TODAY, _SB_DIGEST_LIST, _SB_DIGEST_SHOW,
                               _SB_DIGEST_APPLY, _SB_DIGEST_SKIP, _SB_DIGEST_PROPOSE, _SB_STATS]}
    assert names == {"sb_digest_today", "sb_digest_list", "sb_digest_show",
                     "sb_digest_apply", "sb_digest_skip", "sb_digest_propose", "sb_stats"}
```

- [ ] **Step 2: Verify failure** — ImportError on missing names.

- [ ] **Step 3: Add ToolSchema declarations and dispatcher registration**

Add after existing `_SB_*` schemas (around line 490):

```python
_SB_DIGEST_TODAY = ToolSchema(
    name="sb_digest_today",
    description="Return today's Second-Brain digest summary (date, entry_count, unread, structured entries). Use to see pending KB decisions.",
    input_schema={"type": "object", "properties": {}, "required": []},
)

_SB_DIGEST_LIST = ToolSchema(
    name="sb_digest_list",
    description="List recent digests newest-first with entry and applied counts.",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}},
        "required": [],
    },
)

_SB_DIGEST_SHOW = ToolSchema(
    name="sb_digest_show",
    description="Return the markdown + structured entries for a specific digest date.",
    input_schema={
        "type": "object",
        "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}},
        "required": ["date"],
    },
)

_SB_DIGEST_APPLY = ToolSchema(
    name="sb_digest_apply",
    description="Apply one or more digest entries by id. `ids` may be a list or the string 'all'.",
    input_schema={
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "ids": {"oneOf": [{"type": "array", "items": {"type": "string"}},
                              {"type": "string", "enum": ["all"]}]},
        },
        "required": ["ids"],
    },
)

_SB_DIGEST_SKIP = ToolSchema(
    name="sb_digest_skip",
    description="Skip a digest entry (suppress from future digests for ttl_days).",
    input_schema={
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "id": {"type": "string"},
            "ttl_days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365},
        },
        "required": ["id"],
    },
)

_SB_DIGEST_PROPOSE = ToolSchema(
    name="sb_digest_propose",
    description=(
        "Propose a KB action to be merged into the next digest build. "
        "Section is the heading; action is a dict with one of: upgrade_confidence, "
        "resolve_contradiction, promote_wiki_to_claim, backlink_claim_to_wiki, "
        "add_taxonomy_root, re_abstract_batch, drop_edge, keep."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "section": {"type": "string"},
            "action": {"type": "object"},
        },
        "required": ["section", "action"],
    },
)

_SB_STATS = ToolSchema(
    name="sb_stats",
    description="Return Second-Brain KB stats and health score (breakdown included).",
    input_schema={"type": "object", "properties": {}, "required": []},
)
```

Find the `_TOOLS` / tool-list aggregator near existing `_SB_*` constants and add the 7 new schemas to it.

Then in the dispatcher.register block (around line 972):

```python
            from app.tools import sb_digest_tools as _sbd
            dispatcher.register("sb_digest_today", _sbd.sb_digest_today)
            dispatcher.register("sb_digest_list", _sbd.sb_digest_list)
            dispatcher.register("sb_digest_show", _sbd.sb_digest_show)
            dispatcher.register("sb_digest_apply", _sbd.sb_digest_apply)
            dispatcher.register("sb_digest_skip", _sbd.sb_digest_skip)
            dispatcher.register("sb_digest_propose", _sbd.sb_digest_propose)
            dispatcher.register("sb_stats", _sbd.sb_stats)
```

- [ ] **Step 4: Verify** — run the new test; also run existing `test_slash_api.py` and `test_sb_search.py` (if any) to ensure no regression.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): register 7 new digest tools in chat_api"
```

---

## Batch 2 — Pre-turn hook

### Task 8: `sb_digest_hook.build_digest_summary`

**Files:**
- Create: `backend/app/hooks/__init__.py` (empty)
- Create: `backend/app/hooks/sb_digest_hook.py`
- Create: `backend/app/hooks/tests/__init__.py` (empty)
- Create: `backend/app/hooks/tests/test_sb_digest_hook.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/app/hooks/tests/test_sb_digest_hook.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app import config as app_config


@pytest.fixture
def hook_env(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / "digests").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.delenv("SB_DIGEST_HOOK_ENABLED", raising=False)
    return home


def _write(home: Path, today: date, entries: list[dict]) -> None:
    dig = home / "digests"
    (dig / f"{today.isoformat()}.md").write_text("# Digest")
    with (dig / f"{today.isoformat()}.actions.jsonl").open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def test_hook_disabled_flag(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    from app.hooks.sb_digest_hook import build_digest_summary
    assert build_digest_summary() is None


def test_hook_explicit_env_disable(hook_env, monkeypatch):
    monkeypatch.setenv("SB_DIGEST_HOOK_ENABLED", "false")
    from app.hooks.sb_digest_hook import build_digest_summary
    assert build_digest_summary() is None


def test_hook_missing_digest(hook_env):
    from app.hooks.sb_digest_hook import build_digest_summary
    assert build_digest_summary() is None


def test_hook_all_applied_returns_none(hook_env):
    today = date.today()
    _write(hook_env, today, [
        {"id": "r01", "section": "Reconciliation", "action": {"action": "keep"}},
    ])
    (hook_env / "digests" / f"{today.isoformat()}.applied.jsonl").write_text(
        json.dumps({"id": "r01", "action": {}}) + "\n"
    )
    from app.hooks.sb_digest_hook import build_digest_summary
    assert build_digest_summary() is None


def test_hook_returns_summary_with_unread(hook_env):
    today = date.today()
    _write(hook_env, today, [
        {"id": "r01", "section": "Reconciliation", "action": {"action": "keep"}},
        {"id": "r02", "section": "Reconciliation", "action": {"action": "keep"}},
        {"id": "t01", "section": "Taxonomy", "action": {"action": "keep"}},
    ])
    from app.hooks.sb_digest_hook import build_digest_summary
    s = build_digest_summary()
    assert s is not None
    assert "2 pending KB decisions" not in s  # 3 unread, not 2
    assert "3 pending KB decisions" in s
    assert today.isoformat() in s


def test_hook_never_raises(hook_env, monkeypatch):
    from app.hooks import sb_digest_hook
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(sb_digest_hook, "_load_config", boom)
    assert sb_digest_hook.build_digest_summary() is None
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# backend/app/hooks/sb_digest_hook.py
"""Pre-turn hook: summarize today's Second-Brain digest.

Returns a short string to inject into the system prompt, or None.
Never raises.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date as date_t
from pathlib import Path

from app import config as app_config

logger = logging.getLogger(__name__)


def _load_config():
    from second_brain.config import Config
    return Config.load()


def _read_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for ln in path.read_text().splitlines():
        try:
            out.add(json.loads(ln).get("id", ""))
        except json.JSONDecodeError:
            continue
    out.discard("")
    return out


def _read_marks(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text().splitlines() if ln.strip()}


def build_digest_summary() -> str | None:
    try:
        if not getattr(app_config, "SECOND_BRAIN_ENABLED", False):
            return None
        if os.environ.get("SB_DIGEST_HOOK_ENABLED", "true").lower() in ("0", "false", "no"):
            return None
        cfg = _load_config()
        today = date_t.today()
        sidecar = cfg.digests_dir / f"{today.isoformat()}.actions.jsonl"
        if not sidecar.exists():
            return None
        if today.isoformat() in _read_marks(cfg.digests_dir / ".read_marks"):
            return None
        entries: list[dict] = []
        for ln in sidecar.read_text().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                entries.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        applied = _read_ids(cfg.digests_dir / f"{today.isoformat()}.applied.jsonl")
        unread = [e for e in entries if e.get("id") not in applied]
        if not unread:
            return None
        sections = Counter(e.get("section", "unknown") for e in unread)
        section_summary = ", ".join(f"{n} {s}" for s, n in sections.most_common())
        return (
            f"You have {len(unread)} pending KB decisions ({today.isoformat()}). "
            f"Tools: sb_digest_show, sb_digest_apply, sb_digest_skip.\n"
            f"Section summary: {section_summary}.\n"
            "Offer to review only if relevant to the conversation."
        )
    except Exception:  # noqa: BLE001 — hook must never break a turn
        logger.exception("sb_digest_hook failed")
        return None
```

- [ ] **Step 4: Verify** — `pytest backend/app/hooks/tests/ -v` → all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/hooks/ && git commit -m "feat(bridge): add sb_digest pre-turn hook module"
```

---

### Task 9: Wire the hook into `_build_system_prompt`

**Files:**
- Modify: `backend/app/api/chat_api.py:534-551`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/api/test_prompt_digest_injection.py
from unittest.mock import patch

def test_system_prompt_includes_digest_summary():
    with patch("app.hooks.sb_digest_hook.build_digest_summary", return_value="2 pending KB decisions"):
        from app.api.chat_api import _build_system_prompt
        prompt = _build_system_prompt()
    assert "Pending knowledge base digest" in prompt
    assert "2 pending KB decisions" in prompt


def test_system_prompt_omits_section_when_no_digest():
    with patch("app.hooks.sb_digest_hook.build_digest_summary", return_value=None):
        from app.api.chat_api import _build_system_prompt
        prompt = _build_system_prompt()
    assert "Pending knowledge base digest" not in prompt
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Edit `_build_system_prompt`**

```python
def _build_system_prompt(
    active_profile_summary: str | None = None,
    plan_mode: bool = False,
    session_id: str = "",
) -> str:
    """Assemble the full data-scientist system prompt for this turn."""
    from app.hooks.sb_digest_hook import build_digest_summary
    injector = get_pre_turn_injector()
    extras: dict[str, str] = {}
    digest_summary = build_digest_summary()
    if digest_summary:
        extras["Pending knowledge base digest"] = digest_summary
    inputs = InjectorInputs(
        active_profile_summary=active_profile_summary,
        extras=extras,
        token_budget=TokenBudget(),
        plan_mode=plan_mode,
        session_id=session_id,
    )
    base = injector.build(inputs)
    data_ctx = get_data_context()
    if data_ctx:
        base = base + "\n\n## Live Data Context\n\n" + data_ctx
    return base
```

- [ ] **Step 4: Verify.** Run both new tests + existing prompt tests.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): wire sb_digest_hook into system prompt"
```

---

## Batch 3 — REST API + frontend

### Task 10: REST routes in `backend/app/api/sb_api.py`

**Files:**
- Create: `backend/app/api/sb_api.py`
- Create: `backend/tests/api/test_sb_api.py`
- Modify: wherever `FastAPI()` app aggregates routers (likely `backend/app/main.py`)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/api/test_sb_api.py
from datetime import date
from fastapi.testclient import TestClient


def _client():
    from app.main import app  # or wherever the FastAPI app instance lives
    return TestClient(app)


def test_digest_today_route(sb_home, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "SECOND_BRAIN_ENABLED", True, raising=False)
    # (write digest via helper from test_sb_digest_tools)
    r = _client().get("/api/sb/digest/today")
    assert r.status_code == 200
    body = r.json()
    assert "date" in body and "entries" in body


def test_digest_routes_404_when_disabled(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "SECOND_BRAIN_ENABLED", False, raising=False)
    r = _client().get("/api/sb/digest/today")
    assert r.status_code == 404


def test_digest_apply_route_delegates(monkeypatch, sb_home):
    from app import config
    monkeypatch.setattr(config, "SECOND_BRAIN_ENABLED", True, raising=False)
    called = {}
    def fake_apply(args):
        called["args"] = args
        return {"ok": True, "applied": args["ids"], "skipped": [], "failed": []}
    from app.tools import sb_digest_tools
    monkeypatch.setattr(sb_digest_tools, "sb_digest_apply", fake_apply)
    r = _client().post("/api/sb/digest/apply", json={"ids": ["r01"]})
    assert r.status_code == 200
    assert called["args"] == {"ids": ["r01"]}


def test_digest_read_route(sb_home, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "SECOND_BRAIN_ENABLED", True, raising=False)
    today = date.today().isoformat()
    r = _client().post("/api/sb/digest/read", json={"date": today})
    assert r.status_code == 200
    marks = (sb_home / "digests" / ".read_marks").read_text()
    assert today in marks
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# backend/app/api/sb_api.py
from __future__ import annotations

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
def digest_today() -> dict:
    _require_enabled()
    return sb_digest_tools.sb_digest_today({})


@router.post("/digest/apply")
def digest_apply(body: ApplyBody) -> dict:
    _require_enabled()
    return sb_digest_tools.sb_digest_apply(body.model_dump(exclude_none=True))


@router.post("/digest/skip")
def digest_skip(body: SkipBody) -> dict:
    _require_enabled()
    return sb_digest_tools.sb_digest_skip(body.model_dump(exclude_none=True))


@router.post("/digest/read")
def digest_read(body: ReadBody) -> dict:
    _require_enabled()
    from second_brain.config import Config
    cfg = Config.load()
    marks = cfg.digests_dir / ".read_marks"
    existing = marks.read_text().splitlines() if marks.exists() else []
    if body.date not in existing:
        existing.append(body.date)
    marks.write_text("\n".join(existing) + "\n")
    return {"ok": True, "date": body.date}
```

Then in `backend/app/main.py` (or router assembly site):

```python
from app.api.sb_api import router as sb_router
app.include_router(sb_router)
```

- [ ] **Step 4: Verify.**

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add /api/sb/digest REST routes"
```

---

### Task 11: Frontend Zustand store `digest-store.ts`

**Files:**
- Create: `frontend/src/lib/digest-store.ts`

- [ ] **Step 1: Write failing test**

```ts
// frontend/src/lib/__tests__/digest-store.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDigestStore } from '../digest-store';

describe('digest-store', () => {
  beforeEach(() => {
    useDigestStore.setState({ date: '', entries: [], unread: 0, loading: false, error: null });
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true, date: '2026-04-18', entry_count: 1, unread: 1,
        entries: [{ id: 'r01', section: 'Reconciliation', line: 'x', action: 'keep', applied: false }] }),
        { status: 200 }),
    ) as any;
  });

  it('refresh loads today', async () => {
    await useDigestStore.getState().refresh();
    expect(useDigestStore.getState().entries).toHaveLength(1);
    expect(useDigestStore.getState().unread).toBe(1);
  });

  it('apply posts ids and refreshes', async () => {
    await useDigestStore.getState().apply(['r01']);
    const calls = (global.fetch as any).mock.calls.map((c: any[]) => c[0]);
    expect(calls).toContain('/api/sb/digest/apply');
    expect(calls).toContain('/api/sb/digest/today');
  });
});
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/digest-store.ts
import { create } from 'zustand';

export type DigestEntry = {
  id: string;
  section: string;
  line: string;
  action: string;
  applied: boolean;
};

type State = {
  date: string;
  entries: DigestEntry[];
  unread: number;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  apply: (ids: string[]) => Promise<void>;
  skip: (id: string, ttlDays?: number) => Promise<void>;
  markRead: () => Promise<void>;
};

export const useDigestStore = create<State>((set, get) => ({
  date: '',
  entries: [],
  unread: 0,
  loading: false,
  error: null,
  async refresh() {
    set({ loading: true, error: null });
    try {
      const r = await fetch('/api/sb/digest/today');
      if (r.status === 404) {
        set({ entries: [], unread: 0, loading: false, date: '' });
        return;
      }
      const body = await r.json();
      set({
        date: body.date ?? '',
        entries: body.entries ?? [],
        unread: body.unread ?? 0,
        loading: false,
      });
    } catch (err) {
      set({ error: String(err), loading: false });
    }
  },
  async apply(ids) {
    await fetch('/api/sb/digest/apply', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    await get().refresh();
  },
  async skip(id, ttlDays = 30) {
    await fetch('/api/sb/digest/skip', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id, ttl_days: ttlDays }),
    });
    await get().refresh();
  },
  async markRead() {
    const { date } = get();
    if (!date) return;
    await fetch('/api/sb/digest/read', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ date }),
    });
  },
}));
```

- [ ] **Step 4: Verify.** Run `cd frontend && pnpm vitest run src/lib/__tests__/digest-store.test.ts`.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add digest Zustand store"
```

---

### Task 12: DigestEntry + DigestHeader + DigestPanel components

**Files:**
- Create: `frontend/src/components/digest/DigestEntry.tsx`
- Create: `frontend/src/components/digest/DigestHeader.tsx`
- Create: `frontend/src/components/digest/DigestPanel.tsx`
- Create: `frontend/src/components/digest/digest.css`
- Create: `frontend/src/components/digest/__tests__/DigestEntry.test.tsx`
- Create: `frontend/src/components/digest/__tests__/DigestPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// frontend/src/components/digest/__tests__/DigestEntry.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DigestEntry } from '../DigestEntry';

describe('DigestEntry', () => {
  it('renders id, line, and apply/skip controls', () => {
    const onApply = vi.fn();
    const onSkip = vi.fn();
    render(<DigestEntry entry={{ id: 'r01', section: 'Reconciliation', line: 'upgrade foo', action: 'upgrade_confidence', applied: false }} onApply={onApply} onSkip={onSkip} />);
    expect(screen.getByText('[r01]')).toBeTruthy();
    expect(screen.getByText(/upgrade foo/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith('r01');
  });

  it('shows strikethrough when applied', () => {
    render(<DigestEntry entry={{ id: 'r01', section: 'x', line: 'y', action: 'keep', applied: true }} onApply={() => {}} onSkip={() => {}} />);
    expect(screen.getByTestId('digest-entry').className).toMatch(/applied/);
  });
});
```

```tsx
// frontend/src/components/digest/__tests__/DigestPanel.test.tsx
import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { DigestPanel } from '../DigestPanel';
import { useDigestStore } from '../../../lib/digest-store';

describe('DigestPanel', () => {
  beforeEach(() => {
    useDigestStore.setState({
      date: '2026-04-18', unread: 2, loading: false, error: null,
      entries: [
        { id: 'r01', section: 'Reconciliation', line: 'a', action: 'keep', applied: false },
        { id: 't01', section: 'Taxonomy', line: 'b', action: 'keep', applied: false },
      ],
    });
  });

  it('renders entries grouped by section', () => {
    render(<DigestPanel open onClose={() => {}} />);
    expect(screen.getByText(/Reconciliation/)).toBeTruthy();
    expect(screen.getByText(/Taxonomy/)).toBeTruthy();
    expect(screen.getAllByTestId('digest-entry')).toHaveLength(2);
  });

  it('shows empty state when no entries', () => {
    useDigestStore.setState({ entries: [], unread: 0, loading: false });
    render(<DigestPanel open onClose={() => {}} />);
    expect(screen.getByText(/no pending/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/digest/DigestEntry.tsx
import type { DigestEntry as Entry } from '../../lib/digest-store';
import './digest.css';

export function DigestEntry({ entry, onApply, onSkip }: {
  entry: Entry;
  onApply: (id: string) => void;
  onSkip: (id: string) => void;
}) {
  return (
    <div data-testid="digest-entry" className={`digest-entry ${entry.applied ? 'applied' : ''}`}>
      <span className="digest-entry__id">[{entry.id}]</span>
      <span className="digest-entry__line">{entry.line}</span>
      {!entry.applied && (
        <span className="digest-entry__actions">
          <button onClick={() => onApply(entry.id)}>apply</button>
          <button onClick={() => onSkip(entry.id)}>skip</button>
        </span>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/digest/DigestHeader.tsx
export function DigestHeader({ date, unread, onMarkRead, onClose }: {
  date: string; unread: number; onMarkRead: () => void; onClose: () => void;
}) {
  return (
    <div className="digest-header">
      <div>
        <div className="digest-header__title">DIGEST</div>
        <div className="digest-header__meta">{date || '—'} · {unread} unread</div>
      </div>
      <div>
        <button onClick={onMarkRead}>mark read</button>
        <button onClick={onClose} aria-label="close">×</button>
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/components/digest/DigestPanel.tsx
import { useEffect } from 'react';
import { useDigestStore } from '../../lib/digest-store';
import { DigestEntry } from './DigestEntry';
import { DigestHeader } from './DigestHeader';
import './digest.css';

export function DigestPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { date, entries, unread, refresh, apply, skip, markRead } = useDigestStore();

  useEffect(() => {
    if (!open) return;
    refresh();
    const t = setInterval(refresh, 10_000);
    return () => clearInterval(t);
  }, [open, refresh]);

  if (!open) return null;

  const visible = entries.filter(e => !e.applied || true);
  const sections = Array.from(new Set(visible.map(e => e.section)));

  return (
    <aside className="digest-panel">
      <DigestHeader date={date} unread={unread} onMarkRead={markRead} onClose={onClose} />
      {visible.length === 0 ? (
        <div className="digest-panel__empty">no pending decisions</div>
      ) : (
        sections.map(sec => (
          <section key={sec} className="digest-section">
            <h3 className="digest-section__title">{sec}</h3>
            {visible.filter(e => e.section === sec).map(e => (
              <DigestEntry key={e.id} entry={e} onApply={apply && ((id) => apply([id]))} onSkip={skip} />
            ))}
          </section>
        ))
      )}
    </aside>
  );
}
```

```css
/* frontend/src/components/digest/digest.css */
.digest-panel {
  position: fixed;
  right: 0; top: 0; bottom: 0;
  width: 360px;
  background: #09090b;
  color: #e5e5e5;
  border-left: 1px solid #27272a;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 12px;
  overflow-y: auto;
  padding: 12px;
  z-index: 40;
}
.digest-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.digest-header__title { font-size: 10px; letter-spacing: 0.08em; color: #e0733a; }
.digest-header__meta { font-size: 11px; color: #71717a; }
.digest-section { border-top: 1px solid #27272a; padding: 8px 0; }
.digest-section__title { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #a1a1aa; margin: 0 0 6px; }
.digest-entry { display: grid; grid-template-columns: auto 1fr auto; gap: 6px; padding: 4px 0; align-items: baseline; }
.digest-entry.applied { opacity: 0.5; text-decoration: line-through; }
.digest-entry__id { color: #e0733a; }
.digest-entry__actions button { background: transparent; border: 1px solid #27272a; color: #e5e5e5; font-family: inherit; font-size: 11px; padding: 2px 6px; cursor: pointer; }
.digest-entry__actions button:hover { border-color: #e0733a; color: #e0733a; }
.digest-panel__empty { padding: 24px 0; text-align: center; color: #71717a; }
```

> `apply && ((id) => apply([id]))` guards against undefined during mount; adjust if store always exposes bound actions.

- [ ] **Step 4: Verify.** Run `cd frontend && pnpm vitest run src/components/digest/`.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): add DigestPanel right-rail component"
```

---

### Task 13: Mount DigestPanel in App.tsx with toggle

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing test (optional snippet for toggle)**

Rely on existing App tests for smoke; new integration is visual. Skip unit test for the toggle if existing tests already cover App layout.

- [ ] **Step 2: Manual — render app and confirm the panel opens when its icon is clicked.**

- [ ] **Step 3: Add toggle + mount**

Find the topbar or right-rail area of `App.tsx`. Add:

```tsx
import { useState } from 'react';
import { DigestPanel } from './components/digest/DigestPanel';
import { useDigestStore } from './lib/digest-store';

// inside App component:
const [digestOpen, setDigestOpen] = useState(false);
const unread = useDigestStore(s => s.unread);

// in topbar:
<button onClick={() => setDigestOpen(v => !v)} className="topbar-digest-btn">
  DIGEST{unread > 0 ? ` · ${unread}` : ''}
</button>

// at the end of the JSX:
<DigestPanel open={digestOpen} onClose={() => setDigestOpen(false)} />
```

- [ ] **Step 4: Verify.** `pnpm dev`, click button, confirm panel opens and renders.

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(bridge): mount DigestPanel in App with topbar toggle"
```

---

## Batch 4 — sb-side pending merge + docs

### Task 14: Second-brain `pending.py` merge module

**Files (in second-brain repo):**
- Create: `src/second_brain/digest/pending.py`
- Create: `tests/digest/test_pending_merge.py`

- [ ] **Step 1: Write failing test**

```python
# second-brain/tests/digest/test_pending_merge.py
import json
from datetime import date
from pathlib import Path

def test_merge_pending_absorbs_and_truncates(tmp_path):
    from second_brain.digest.pending import merge_pending
    from second_brain.digest.schema import DigestEntry
    digests = tmp_path / "digests"
    digests.mkdir()
    pending = digests / "pending.jsonl"
    pending.write_text(json.dumps({
        "id": "pend_0001",
        "section": "Reconciliation",
        "action": {"action": "keep"},
        "proposed_at": "2026-04-18T00:00:00Z",
    }) + "\n")

    class FakeCfg:
        digests_dir = digests

    existing = [DigestEntry(id="r01", section="Reconciliation", line="l", action={"action": "keep"})]
    merged = merge_pending(FakeCfg(), existing)
    assert len(merged) == 2
    assert any(e.section == "Reconciliation" and e.action == {"action": "keep"} for e in merged[1:])
    assert pending.read_text() == ""
```

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Implement**

```python
# second-brain/src/second_brain/digest/pending.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from second_brain.digest.schema import DigestEntry


def merge_pending(cfg, existing: list[DigestEntry]) -> list[DigestEntry]:
    """Merge proposals from ``digests/pending.jsonl`` into the entry list.

    Truncates the file on success so proposals only land in one build.
    """
    pending: Path = cfg.digests_dir / "pending.jsonl"
    if not pending.exists():
        return existing
    out = list(existing)
    for ln in pending.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec: dict[str, Any] = json.loads(ln)
        except json.JSONDecodeError:
            continue
        action = rec.get("action") or {}
        out.append(DigestEntry(
            id=rec.get("id", ""),
            section=rec.get("section", ""),
            line=action.get("rationale") or action.get("action", ""),
            action=action,
        ))
    pending.write_text("")
    return out
```

> `DigestEntry` field names must match `schema.py`; verify `line` attribute exists (it does per the existing applier using `.line` and `.action`).

- [ ] **Step 4: Verify.** `pytest tests/digest/test_pending_merge.py -v`.

- [ ] **Step 5: Commit (inside second-brain repo)**

```bash
cd ~/Developer/second-brain
git add -u && git commit -m "feat(digest): add merge_pending helper"
```

---

### Task 15: Call merge_pending from DigestBuilder.build

**Files:** `second-brain/src/second_brain/digest/builder.py`

- [ ] **Step 1: Write failing integration test**

```python
# second-brain/tests/digest/test_builder_pending_integration.py
import json
from datetime import date
from pathlib import Path

def test_builder_merges_pending(tmp_path, monkeypatch):
    # Drive the builder with a no-op passes list, capture merged entries in writer
    from second_brain.digest.builder import DigestBuilder
    # ... populate tmp_path with minimal cfg fixtures
    # assert written markdown contains 'pend_0001'
    # (Adapt to existing fixture patterns in tests/digest/)
    pass  # replace with real assertions from existing test patterns
```

> Use an existing digest-builder test as a template; key assertion: after seeding `pending.jsonl`, `builder.build(today)` yields a BuildResult whose entries include the pending record and `pending.jsonl` is empty afterward.

- [ ] **Step 2: Verify failure.**

- [ ] **Step 3: Edit `builder.py::build`**

```python
# near the end of build(), after passes produce entries and before writer writes:
from second_brain.digest.pending import merge_pending
entries = merge_pending(self._cfg, entries)
```

Locate where `entries` is assembled in `DigestBuilder.build()` (around line 92+) and insert the call before renumbering / writing.

- [ ] **Step 4: Verify.** Run digest builder test suite.

- [ ] **Step 5: Commit**

```bash
cd ~/Developer/second-brain
git add -u && git commit -m "feat(digest): builder merges pending.jsonl proposals"
```

---

### Task 16: Changelog + docs

**Files:**
- Modify: `claude-code-agent/docs/log.md` (add `[Unreleased]` entry)

- [ ] **Step 1: Add changelog entry**

```markdown
### Added
- **Second-Brain bridge (digest surface):** 7 new tools (`sb_digest_today`, `sb_digest_list`, `sb_digest_show`, `sb_digest_apply`, `sb_digest_skip`, `sb_digest_propose`, `sb_stats`), a pre-turn hook that injects pending-digest summary (toggle via `SB_DIGEST_HOOK_ENABLED`), 4 REST routes under `/api/sb/digest/*`, and a right-rail `DigestPanel` in the frontend. All gracefully degrade when `SECOND_BRAIN_ENABLED=False`. Second-brain builder now absorbs `digests/pending.jsonl` proposals into the next build.
```

- [ ] **Step 2: Commit**

```bash
git add docs/log.md && git commit -m "docs: changelog entry for sb bridge digest surface"
```

---

### Task 17: E2E Playwright smoke (optional, if frontend E2E infra exists)

**Files:**
- Create: `frontend/tests/e2e/digest.spec.ts` (if Playwright suite exists)

- [ ] Smoke: open app → click DIGEST → click apply on first entry → confirm strikethrough.

Skip if no existing Playwright harness is configured.

---

## Self-Review Checklist

After completing the plan, verify before marking done:

- [ ] All 7 bridge tools return `{ok: false, error: "second_brain_disabled"}` when flag off
- [ ] Hook never raises (test `test_hook_never_raises` covers this)
- [ ] `_build_system_prompt` returns prompt without digest section when `build_digest_summary()` returns None
- [ ] REST routes return 404 when disabled
- [ ] Frontend panel renders empty state when no entries
- [ ] `pending.jsonl` truncated after successful merge
- [ ] Action-type allowlist in `sb_digest_propose` matches the 7 (plus `keep`) valid types
- [ ] No placeholders remain; all code snippets complete
- [ ] Commit messages follow `<type>: <description>` convention
