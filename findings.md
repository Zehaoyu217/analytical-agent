# findings.md — claude-code-agent

---

## P0: Test Collection Errors — Root Cause Analysis (2026-04-14)

### Finding 1: importmode=prepend + tests/__init__.py mismatch

**Symptom:** `ModuleNotFoundError: No module named 'tests.test_X'` for all 35 skill tests
when running from `backend/` directory. Individual skill test files run fine.

**Root cause:**
- `app/skills/<name>/` directories have NO `__init__.py`
- `app/skills/<name>/tests/` directories DO have `__init__.py`
- pytest's default `prepend` importmode: when it finds a package (`tests/__init__.py`),
  it walks up to find the highest non-package ancestor, prepends that to sys.path,
  then imports as `tests.test_X`
- Since `app/skills/altair_charts/` has no `__init__.py`, pytest prepends
  `app/skills/altair_charts/` to sys.path → tries `tests.test_violin` → fails

**Fix:** `addopts = "--import-mode=importlib"` in `[tool.pytest.ini_options]`
importlib mode imports test files by path without sys.path manipulation.

### Finding 2: data_profiler conftest double-registration

**Symptom:** `ValueError: Plugin already registered: app.skills.data_profiler.tests.fixtures.conftest`

**Root cause:**
- `backend/conftest.py` lists it in `pytest_plugins = [...]` (explicit plugin)
- pytest also auto-discovers `conftest.py` files within testpaths (`app/skills/`)
- Double registration on the same module → ValueError

**Fix:** Remove the explicit entry from `pytest_plugins`. pytest auto-discovery
handles conftest.py files within testpaths, so the fixtures remain available.

### Finding 3: Frontend phase status

- Sidebar: only 3 actual tab components exist: `FilesTab.tsx`, `HistoryTab.tsx`, `SettingsTab.tsx`
- No `AgentsTab.tsx`, `SkillsTab.tsx`, `DevToolsTab.tsx`
- No `right-panel/` component directory
- No `MonitorPage.tsx`
- Frontend git commit `P4-P7 wire sidebar tabs + slash menu to BE1` refers to earlier plan phases,
  not to progressive_plan.md P1-A/B/C

### Finding 4: venv location

- `backend/.venv` using Python 3.13.12 (cpython-3.13.12-macos-aarch64)
- Always run tests with `backend/.venv/bin/python -m pytest` from `backend/`
- System Python 3.9 is on PATH — do NOT use for tests

---

## v2 Frontend Platform Planning (2026-04-14)

### Finding 5: openfang Layout Pattern (for OS-platform UX)
- Layout: narrow icon rail (48px) → clicking icon switches to full-screen section
- Sections (NOT tabs): each is a self-contained view — Agents, Skills, Sessions, Memory, etc.
- Skills section has 3 sub-tabs: Installed / ClawHub / MCP — each with search, badges, list
- Agents section: grouped by role, per-session status (RUNNING/DONE/FAILED), click → detail
- Theme: orange accent (#FF5C00), near-black bg (#0F0E0E), tight monospace, no decorative chrome
- Rust code is NOT portable — adopt the UX/design concept, implement in React

### Finding 6: Analytical-chatbot Progress Panel (terminal style)
- AnimatePresence-based terminal log with rotating fun verbs per tool type
- Per-tool verb maps for: query_duckdb, run_python, save_artifact, load_skill, get_schema, etc.
- Live timer (LiveTimer component), elapsed badge on completion
- Terminal standby messages when idle
- ArtifactsPanel: Vega-Lite chart rendering (VegaChart.tsx), DataTable, HTML frames
- MermaidDiagram.tsx for flow diagrams
- SSE client (lib/sse.ts): EventSource wrapper dispatching typed events to Zustand stores

### Finding 7: claude-code-agent Context Manager Status
- ContextManager in backend/app/context/manager.py tracks ContextLayer objects
- Each layer: name, tokens, compactable, items
- snapshot() → full layer breakdown
- record_compaction() → stores before/after token counts + removed/survived layer names
- Publishes compaction events to trace bus
- PROBLEM: Single global context manager, not per-session
- PROBLEM: L1 (system prompt) and L2 (skill injection) are not explicitly tagged as layers
- API: GET /api/context → returns global snapshot (needs session_id param)

### Finding 8: claude-code-main Architecture Gaps vs claude-code-agent
- Memory: CC-main has file-based persistent memory (MEMORY.md + typed files); agent has none
- Compaction: CC-main relies on model provider; agent has manual threshold + ContextManager
- Hooks: CC-main has pre/postToolUse + Stop hooks; agent has none
- Planning mode: CC-main has EnterPlanMode; agent has none
- Task management: CC-main has TaskCreate/Update/Stop; agent has none
- Skills: CC-main uses SKILL.md markdown files; agent has Python package skills with manifest
- Tools: CC-main = filesystem specialist; agent = data/sandbox specialist (complementary)
- Prompts: CC-main has systemPrompt.ts + per-tool prompt.ts files; no registry UI

### Finding 9: Backend Skills API
- GET /api/skills/manifest already exists (skills_api.py)
- skills/manifest.py has SkillManifest with dependency graph check
- skills/registry.py has SkillRegistry with discover() and get_dependency_graph()
- Each skill dir has: SKILL.md, __init__.py, Python modules
- Source code for skills is filesystem-readable (not encrypted)
- Need to add: GET /api/skills/{name}/source → return SKILL.md + Python files

### Finding 10: Prompts in claude-code-agent
- PreTurnInjector in backend/app/harness/injector.py — builds system prompt
- Skill SKILL.md files are injected as L2 context
- No centralized prompts registry or API endpoint yet
- CC-main pattern: per-tool prompt.ts files under src/tools/{ToolName}/prompt.ts
- Need: GET /api/prompts → returns all registered prompts (system, skill, injector, tool)

---

## V3 Analysis Findings (2026-04-15)

### Finding 12: CRITICAL — Harness-API Disconnect

**Symptom:** Users interact with a "financial analyst" agent that calls execute_python AT MOST ONCE per turn. The sophisticated data scientist harness (13 skills, DuckDB globals, wiki injection, guardrails, A2A) is invisible.

**Root cause:** `chat_api.py` defines its own local `_build_dispatcher()` with 2 tools and uses `_SYSTEM_PROMPT_BASE` (hardcoded string). It never calls:
- `PreTurnInjector.build()` (real system prompt with skills + wiki + gotchas)
- `register_core_tools()` from skill_tools.py (15+ tools)
- `WikiEngine` / `SkillRegistry`
- `TurnWrapUp` at end of session

**Fix:** Replace local functions in chat_api.py with wired harness imports.  
**Priority:** P15 — CRITICAL  
**Effort:** Medium (all components exist, pure wiring work)

### Finding 13: CRITICAL — Frontend Routing Disconnect

**Symptom:** All 7 OS-platform sections (AgentsSection, ContextSection, SkillsSection, PromptsSection, etc.) are built and visible in the repo but unreachable from the UI.

**Root cause:** `App.tsx` renders `<SessionLayout />` as root. `IconRail.tsx` exists in `components/layout/` but is never rendered in `App.tsx`. The hash route only handles `/monitor/:id`.

**Fix:** Update `App.tsx` to render `<IconRail /> + <SectionContent />` at root.  
**Priority:** P16 — HIGH  
**Effort:** Small

### Finding 14: CC-main Has Four Compaction Strategies; Agent Has Zero

CC-main's compact service has:
1. `compact.ts` — full compaction (conversation → summary via LLM call)
2. `microCompact.ts` — drops tool result blocks from message history (no LLM call needed)
3. `apiMicrocompact.ts` — uses Anthropic API `context_management.edits` (clear_tool_uses_20250919)
4. `sessionMemoryCompact.ts` — trims session memory before injection

Agent: ContextManager.compaction_needed is a property that checks utilization ≥ threshold. It is never read by the loop. No compaction code exists.

**Fix:** Implement microCompact in loop.py (Tier 1 — free, fast, handles 80% of cases).  
**Priority:** P17 — HIGH  
**Effort:** Medium

### Finding 15: CC-main SessionMemory Has a 9-Section Structured Template

Template sections: Current State, Task specification, Files and Functions, Workflow, Errors & Corrections, Codebase Documentation, Learnings, Key results, Worklog.

Updated at session end by an LLM edit call. Injected as system prompt context next session.

Agent: working.md exists (200 line limit, free-form), injected via _operational_state(). But:
- Not wired (PreTurnInjector not called from chat_api.py)
- Not structured (no template)
- Not automatically updated at session end (TurnWrapUp not called)
- No cross-session recall (working.md persists but isn't treated as session history)

**Fix (P18):** Add structured session notes template; write on TurnWrapUp; inject most recent notes in next session.

### Finding 16: write_working Tool in chat_api.py Is In-Memory Only

In chat_api.py, the `_write_working` handler:
```python
def _write_working(args: dict[str, Any]) -> dict[str, Any]:
    content = str(args.get("content", ""))
    return {"ok": True, "content": content}  # no filesystem write!
```

The scratchpad_delta SSE event is emitted so the UI shows the content, but it's never saved to wiki/working.md. After the session ends, the scratchpad is lost.

In the real harness (skill_tools.py), write_working calls `wiki.write_working(content)` which writes to the filesystem.

**Fix:** Part of P15 — when harness is wired, the real write_working handler is used.

### Finding 17: A-H Decomposition Framework — Current Mapping

From the earlier brainstorming session (before P0-P14), a decomposition into 8 sub-projects was proposed. Mapping to current state:

| Subsystem | April 2026 Status |
|---|---|
| A: Core harness (AgentLoop, ToolDispatcher, PreTurnInjector, SandboxExecutor) | BUILT — not wired to API |
| B: Skill system (13 skills, manifest, load_skill) | MOSTLY BUILT — load_skill not wired |
| C: Permissions + Hooks | PARTIAL — guardrails exist; no hook system |
| D: Context + Compaction + TokenEstimation | PARTIAL — tracking exists; no compaction engine or tokenizer |
| E: Memory & Session (wiki engine, session notes) | PARTIAL — wiki built; no session notes; not wired |
| F: Task system | NOT BUILT |
| G: MCP client | NOT BUILT |
| H: UX services (AgentSummary, PromptSuggestion, Tips) | NOT BUILT |

V3 plan targets: A wiring (P15), D compaction (P17), E session notes (P18), F tasks (P19).

### Finding 11: Gap Summary (for documentation)
| Domain | Agent has | Agent missing vs CC-main | Agent better than Analytical |
|---|---|---|---|
| Memory | session-scoped | persistent cross-session | both lack |
| Context tracking | ContextManager (L1-L3) | none (CC-main defers to model) | agent wins |
| Compaction | manual threshold + history | CC-main auto | agent has visibility |
| Hooks | none | pre/postToolUse hooks | both lack |
| Skills | 13 Python packages + manifest | SKILL.md transparency | agent has manifest |
| Tools | DuckDB + sandbox | filesystem tools | agent = data specialist |
| Streaming | SSE | not applicable | agent wins |
| A2A | delegate_subagent | AgentTool in CC-main | equivalent |
| Eval | 5-level eval framework | CC-main lacks | agent wins |
