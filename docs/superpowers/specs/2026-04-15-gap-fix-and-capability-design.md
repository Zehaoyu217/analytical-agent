# Gap Fix + Capability Push Design

**Date:** 2026-04-15  
**Status:** approved  
**Branch:** feat/v2-os-platform  
**Supersedes:** N/A — extends docs/gap-analysis-v2.md and docs/progressive_plan_v3.md

---

## Context

All P15-P22 phases are confirmed complete by code inspection. A fresh audit identified concrete bugs, structural gaps, and two missing capability phases (hooks, filesystem tools) plus a quality pass. This document specifies three tiers of work to address them.

---

## True Current State (post-audit)

| Phase | Status confirmed |
|---|---|
| P15 — Harness wired to chat_api.py | ✅ complete |
| P16 — OS platform routing in App.tsx | ✅ complete |
| P17 — MicroCompact in loop | ✅ complete (compactor.py, loop.py) |
| P18 — Structured session memory | ✅ complete (wrap_up.py, injector.py) |
| P19 — In-session task tracking | ✅ complete (todo_store.py, TodosPanel.tsx) |
| P20 — load_skill tool | ✅ complete (`skill` ToolSchema in _CHAT_TOOLS) |
| P21 — Token budget awareness | ✅ complete (_token_budget_section in injector) |
| P22 — Plan mode gate | ✅ complete (filter_tools_for_plan_mode, _plan_mode_section) |

---

## Tier A — Bug Fixes + Gap Closures

### A1 — Restore `pytest-asyncio` in backend dev deps

**File:** `backend/pyproject.toml`  
**Problem:** `uv sync` from the repo root (which has no `pyproject.toml`) resets the backend venv, stripping dev packages including `pytest-asyncio`. Four async eval tests (`test_eval_judge`, `test_eval_runner`) fail with "async functions are not natively supported."  
**Fix:** Add `pytest-asyncio` to `[tool.uv.dev-dependencies]`. Also add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` to silence the `asyncio_mode` config warning.

### A2 — Fix Makefile test target

**File:** `Makefile`  
**Problem:** `make test-backend` runs `cd backend && pytest` — `pytest` is not on `PATH` (it lives in the backend `.venv`).  
**Fix:** Replace with `cd backend && uv run python -m pytest`.

### A3 — Wire MicroCompactor → ContextManager

**File:** `backend/app/api/chat_api.py`  
**Problem:** When the `MicroCompactor` fires during `run_stream()`, it emits a `micro_compact` SSE event to the frontend but never updates the `ContextManager`. The Context Inspector (`ContextSection`) shows stale compaction history — it has no record of micro-compact events.  
**Fix:** In `_stream_agent_loop()`, when an event of `type == "micro_compact"` is received from the loop generator, call:
```python
ctx.add_layer(ContextLayer(
    name="[micro_compact]",
    tokens=-(event.payload.get("tokens_before", 0) - event.payload.get("tokens_after", 0)),
    compactable=False,
    items=[{"name": "compact_event", "tokens": 0}],
))
```

### A4 — Guard startup fragility in chat_api.py

**File:** `backend/app/api/chat_api.py`  
**Problem:** `_SYSTEM_PROMPT = _build_system_prompt()` is called at module import time. If `data_scientist.md`, the wiki root, or the skill registry is missing, the entire `chat_api` module fails to import and FastAPI cannot start.  
**Fix:** Wrap in try/except with a safe fallback:
```python
try:
    _SYSTEM_PROMPT = _build_system_prompt()
except Exception as _e:
    import logging as _logging
    _logging.getLogger(__name__).warning("startup prompt build failed: %s", _e)
    _SYSTEM_PROMPT = "You are an analytical assistant."
```

### A5 — Minimum-turns guard for session notes

**File:** `backend/app/harness/wrap_up.py`  
**Problem:** `TurnWrapUp.finalize()` writes 9-section session notes on every turn regardless of session depth. Single-turn sessions with no tool calls produce nine "—" sections — noise in the wiki.  
**Fix:** In `finalize()`, skip `write_session_notes` if `turn_index < 2` or `len(state.as_trace()) == 0`.

### A6 — Implement `get_context_status` tool

**Files:** `backend/app/api/chat_api.py`, `backend/app/harness/skill_tools.py`  
**Problem:** P21 specified a `get_context_status` tool so the agent can query live context utilization. The token budget section is injected (done), but the agent can't check current utilization programmatically.  
**Design:**
```python
# In chat_api.py — register handler
def _get_context_status_handler(args: dict[str, Any]) -> dict[str, Any]:
    snap = ctx.snapshot()  # ctx = session_registry.get_or_create(session_id)
    return {
        "total_tokens": snap.get("total_tokens", 0),
        "max_tokens": 200_000,
        "utilization_pct": round(snap.get("utilization", 0.0) * 100),
        "layers": [(l["name"], l["tokens"]) for l in snap.get("layers", [])],
    }
dispatcher.register("get_context_status", _get_context_status_handler)
```
Add `ToolSchema` to `_CHAT_TOOLS`.  
**Note:** `_build_dispatcher()` does not have access to `ctx` (the ContextManager). Register the handler as a closure **after** `_build_dispatcher()` returns, directly in `_stream_agent_loop()`:
```python
dispatcher = _build_dispatcher(...)
def _get_ctx_status(args: dict[str, Any]) -> dict[str, Any]:
    snap = ctx.snapshot()
    return {"total_tokens": snap.get("total_tokens", 0), ...}
dispatcher.register("get_context_status", _get_ctx_status)
```

### A7 — Verify `vega-embed` in frontend

**File:** `frontend/package.json`  
**Problem:** `VegaChart.tsx` exists but `vega-embed` availability in the installed packages is unverified.  
**Fix:** Confirm `vega-embed` is in `dependencies`; if absent, add it. Smoke-test: render a trivial Vega-Lite bar chart spec in the Artifacts panel end-to-end.

---

## Tier B — Capability Push

### P23 — User-configurable Hook System

**Priority:** HIGH  
**Modeled after:** CC-main `settings.json` hooks

#### Storage

`backend/config/hooks.json` (env override: `CCAGENT_HOOKS_PATH`):
```json
{
  "PreToolUse": [
    {
      "matcher": "execute_python",
      "command": "echo \"Running sandbox step\"",
      "description": "Log sandbox invocations"
    }
  ],
  "PostToolUse": [
    {
      "matcher": "save_artifact",
      "command": "echo \"Artifact saved: $TOOL_OUTPUT\"",
      "description": "Notify on artifact save"
    }
  ],
  "Stop": [
    {
      "command": "echo \"Session ended\"",
      "description": "End-of-session hook"
    }
  ]
}
```

**Env vars available to hook commands:**
- `TOOL_NAME` — name of the tool being called
- `TOOL_INPUT` — JSON-serialized tool arguments
- `TOOL_OUTPUT` — JSON-serialized tool result (PostToolUse only)
- `SESSION_ID` — current session id

#### Implementation

**New file: `backend/app/harness/hooks.py`**
```python
class HookRunner:
    def __init__(self, config_path: Path | None = None) -> None: ...
    def run_pre(self, tool_name: str, arguments: dict) -> None: ...
    def run_post(self, tool_name: str, result: dict) -> None: ...
    def run_stop(self, session_id: str) -> None: ...
```

- `_match(matcher, tool_name)` — simple glob/substring match against tool name
- Hook subprocess: `subprocess.run(command, shell=True, env={...}, timeout=10)`
- Non-zero exit: log warning, never block the turn
- Missing config file: silently no-op (hooks are optional)

**Integration in `AgentLoop.run_stream()` (`backend/app/harness/loop.py`):**
- Before `dispatcher.dispatch(call)`: `hook_runner.run_pre(call.name, call.arguments)`
- After dispatch: `hook_runner.run_post(call.name, result.payload or {})`

**Integration in `chat_api._run_wrap_up()` (`backend/app/api/chat_api.py`):**
- After `wrap.finalize(...)`: `hook_runner.run_stop(session_id)`

**`AgentLoop.__init__`:** Add `hook_runner: HookRunner | None = None` parameter.

**New API endpoint: `GET /api/hooks`** in new `backend/app/api/hooks_api.py`:
- Returns current hook config JSON (read-only; editing hooks is out of scope for this phase)

**Frontend:** Hook executions surfaced in `TerminalPanel` as tool-log entries with `name = '__hook__'` and a `⚙` prefix verb. No new UI components needed.

#### Files to create/modify

| File | Change |
|---|---|
| `backend/app/harness/hooks.py` | New — HookRunner class |
| `backend/app/harness/loop.py` | Add hook_runner param, call pre/post |
| `backend/app/api/chat_api.py` | Instantiate HookRunner, pass to AgentLoop, call run_stop |
| `backend/app/api/hooks_api.py` | New — GET /api/hooks |
| `backend/app/main.py` | Register hooks_router |
| `frontend/src/components/right-panel/TerminalPanel.tsx` | Handle `__hook__` tool entries |

#### Success criteria

- `POST /api/chat/stream` with `execute_python` triggers a `PreToolUse` hook command
- Hook stdout/stderr is logged; non-zero exit does not crash the turn
- `GET /api/hooks` returns the current config
- Missing `hooks.json` does not break startup

---

### P25 — Filesystem Tools for the Agent

**Priority:** HIGH  
**Scope:** Read-only (write tools require git integration — deferred)

#### Tools

| Tool name | Description |
|---|---|
| `read_file` | Read a file's content. Path relative to project root. |
| `glob_files` | List files matching a glob pattern relative to project root. |
| `search_text` | Search for a regex pattern in files under a path. |

#### Safety model

All paths resolved against `CCAGENT_PROJECT_ROOT` (defaults to repo root = `backend/../..`). Any resolved path that does not start with the project root raises `PathEscapeError` returned as a tool error — never a hard crash.

Banned paths (even within root):
- `.env`, `*.key`, `*.pem`, `secrets/`, `.git/` — matched by suffix/name, returned as `{"error": "path_forbidden"}`

#### Implementation

**New file: `backend/app/harness/fs_tools.py`**
```python
class FsTools:
    def __init__(self, project_root: Path) -> None: ...
    def read_file(self, args: dict) -> dict: ...
    def glob_files(self, args: dict) -> dict: ...
    def search_text(self, args: dict) -> dict: ...
```

`read_file` returns `{"ok": True, "content": "...", "lines": N}` or `{"ok": False, "error": "..."}`.  
`glob_files` returns `{"ok": True, "files": [...], "count": N}` — capped at 200 results.  
`search_text` returns `{"ok": True, "matches": [{"file": "...", "line": N, "text": "..."}]}` — capped at 50 matches.

**Registration in `register_core_tools()` (`backend/app/harness/skill_tools.py`):**
```python
fs = FsTools(project_root=_REPO_ROOT)
dispatcher.register("read_file", fs.read_file)
dispatcher.register("glob_files", fs.glob_files)
dispatcher.register("search_text", fs.search_text)
```

**`ToolSchema` entries added to `_CHAT_TOOLS` in `chat_api.py`.**

#### Files to create/modify

| File | Change |
|---|---|
| `backend/app/harness/fs_tools.py` | New — FsTools class |
| `backend/app/harness/skill_tools.py` | Register 3 handlers in register_core_tools() |
| `backend/app/api/chat_api.py` | Add 3 ToolSchema entries to _CHAT_TOOLS |

#### Success criteria

- Agent can call `read_file({"path": "docs/gotchas.md"})` and receive the file content
- `read_file({"path": "../../../etc/passwd"})` returns `{"ok": False, "error": "path_escape"}`
- `glob_files({"pattern": "backend/app/skills/**/*.py"})` returns a list of matching paths
- `search_text({"pattern": "def correlate", "path": "backend/app/skills"})` returns match locations

---

## Tier C — Quality Pass

### C1 — Test infrastructure to 80% coverage

- A1 already adds `pytest-asyncio` — async eval tests unblocked
- Add unit tests for: `HookRunner` (P23 matcher logic, subprocess env vars, no-op on missing config), `FsTools` (path escape guard, banned path guard, glob cap, search cap), `get_context_status` handler (A6)
- Add integration tests for: hook subprocess execution end-to-end, `read_file` traversal guard
- Fix `asyncio_mode` config warning: add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`
- Target: `uv run python -m pytest --cov=app --cov-report=term-missing` ≥ 80%

### C2 — Context Inspector accuracy

- A3 wires MicroCompact → ContextManager
- Add `GET /api/context/{session_id}/compactions` to `context_api.py` — returns list of compaction records from `ContextManager`
- `ContextSection.tsx` renders compaction events as a collapsible timeline below the existing stacked bar chart
- `ContextManager` needs a `compaction_log: list[dict]` field and `record_compaction(...)` method

### C3 — Session notes quality

Three improvements to `wrap_up.py` and `_render_session_notes()`:
1. Min-turns guard (A5 — already specified)
2. Auto-populate `Worklog` section from tool trace: `"step N: tool_name → status"` lines
3. Cap rendered notes at 3000 chars before writing (injector already caps at 4000 on read, but unbounded writes are wasteful)

### C4 — TodosPanel as a proper tab

**Problem:** `RightPanelTab = 'artifacts' | 'scratchpad' | 'tools'` has no `'tasks'` value. `TodosPanel` is always-visible in `SessionRightPanel` when todos exist rather than being a selectable tab.

**Changes:**
- `frontend/src/lib/store.ts`: add `'tasks'` to `RightPanelTab` union
- `frontend/src/components/right-panel/SessionRightPanel.tsx`: add Tasks tab button (only shown when `todos.length > 0`); auto-switch to tasks tab on first `todos_update` event **only if the right panel is already open** (don't hijack focus when the user is reading Artifacts or Scratchpad)
- Move `TodosPanel` into the tab-conditional slot alongside Artifacts / Scratchpad / Tools

---

## Execution Order

```
A1 + A2        ← dev infra, unblocks CI immediately
A3 + A4        ← runtime reliability
A5 + A6 + A7   ← gap closures
     ↓
P23            ← hooks (new file + wiring)
P25            ← filesystem tools (new file + wiring)
     ↓
C1 ←─ parallel with P25 tail
C2
C3
C4
```

**Parallel opportunities:**
- A1-A7 are independent of each other (run in any order within the tier)
- C1 test authoring can start as soon as P23/P25 interfaces are defined
- C3 (session notes) and C4 (todos tab) are independent, run in parallel

---

## Files Changed Summary

| File | Tier | Change |
|---|---|---|
| `backend/pyproject.toml` | A1 | Add pytest-asyncio, asyncio_mode=auto |
| `Makefile` | A2 | Fix test-backend target |
| `backend/app/api/chat_api.py` | A3, A4, A6, P23, P25 | MicroCompact→ctx, startup guard, get_context_status, hook wiring, fs tool schemas |
| `backend/app/harness/wrap_up.py` | A5, C3 | Min-turns guard, worklog auto-populate, char cap |
| `backend/app/harness/loop.py` | P23 | Add hook_runner param and pre/post calls |
| `backend/app/harness/hooks.py` | P23 | New — HookRunner |
| `backend/app/api/hooks_api.py` | P23 | New — GET /api/hooks |
| `backend/app/harness/fs_tools.py` | P25 | New — FsTools |
| `backend/app/harness/skill_tools.py` | P25 | Register fs tool handlers |
| `backend/app/main.py` | P23 | Register hooks_router |
| `backend/app/api/context_api.py` | C2 | Add /compactions endpoint |
| `backend/app/context/manager.py` | C2 | Add compaction_log field |
| `frontend/src/lib/store.ts` | C4 | Add 'tasks' to RightPanelTab |
| `frontend/src/components/right-panel/SessionRightPanel.tsx` | C4 | Tasks tab |
| `frontend/src/components/right-panel/TerminalPanel.tsx` | P23 | __hook__ entry rendering |
| `frontend/package.json` | A7 | Verify vega-embed |

---

## Definition of Done

**A-Tier:**
- [ ] `uv run python -m pytest` passes all 174 unit tests (including 4 async eval tests)
- [ ] `make test-backend` runs without error
- [ ] Context Inspector shows micro-compact events after a long session
- [ ] API starts correctly even when `data_scientist.md` is temporarily missing
- [ ] Session notes are only written for turns with ≥ 1 tool call and turn_index ≥ 2
- [ ] Agent can call `get_context_status` and receive utilization data
- [ ] VegaChart renders a Vega-Lite spec in Artifacts panel

**B-Tier:**
- [ ] `POST /api/chat/stream`: `execute_python` triggers a `PreToolUse` hook subprocess
- [ ] Non-zero hook exit does not crash or block the turn
- [ ] `GET /api/hooks` returns current hook config
- [ ] Agent can call `read_file({"path": "docs/gotchas.md"})` and receive content
- [ ] Path escape attempt returns `{"ok": False, "error": "path_escape"}`
- [ ] `glob_files` and `search_text` work end-to-end

**C-Tier:**
- [ ] Test coverage ≥ 80% (`--cov=app`)
- [ ] Context Inspector `/compactions` endpoint returns real compaction history
- [ ] Session notes Worklog section auto-populated from tool trace
- [ ] TodosPanel appears as a selectable "Tasks" tab in the right panel
