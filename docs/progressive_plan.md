# Implementation Plan: claude-code-agent — Full Target State

**Date:** 2026-04-14
**Status:** approved

---

## Current State Assessment

**What's already built (do not re-implement):**

| Layer | Status | Notes |
|---|---|---|
| Backend harness: `AgentLoop`, `SandboxExecutor`, `ToolDispatcher`, `PreTurnInjector`, `ModelRouter`, `TurnWrapUp` | ✅ Built | `backend/app/harness/` — all 7 components present |
| Skills: all 13 catalog entries (altair_charts 20 templates, correlation, group_compare, stat_validate, time_series, distribution_fit, data_profiler, sql_builder, html_tables, analysis_plan, report_builder, dashboard_builder) | ✅ Built | `backend/app/skills/` |
| Artifact store, EventBus, distillation | ✅ Built | `backend/app/artifacts/` |
| Trace system (assembler, bus, recorder, store, timeline, judge_replay) | ✅ Built | `backend/app/trace/` |
| Wiki engine, gotchas knowledge base | ✅ Built | `backend/app/wiki/`, `knowledge/gotchas/` |
| All backend APIs (chat, conversations, files, settings, slash, trace, sop, models) | ✅ Built | `backend/app/api/` |
| Frontend: 3-panel shell, Chat (MessageBubble, markdown, CodeBlock, VirtualList), Sidebar (5 tabs: chats/history/files/devtools/settings), command palette, shortcuts, a11y | ✅ Built | `frontend/src/` |
| Eval framework (5 levels, judge, grading, rubric) | ✅ Built | `backend/app/evals/`, `backend/tests/evals/` |

**What's broken or missing:**

| Item | Root cause | Priority |
|---|---|---|
| 36 skill test import errors (`ModuleNotFoundError: No module named 'tests.test_builder'`) | Missing/broken `conftest.py` in skill subdirs — pytest can't resolve cross-package imports | P0 — blocks all testing |
| Frontend: no **Agents tab** in sidebar | Not yet added — sidebar has 5 tabs, needs 2 more | P1 |
| Frontend: no **Skills tab** in sidebar | Not yet added | P1 |
| Frontend: right panel (tool inspector, artifact viewer, scratchpad) | Plan P4–P9 was shipped as empty stubs; real wiring deferred to BE1 | P1 |
| Frontend: per-agent monitoring page | New requirement — dedicated devtools view per session | P1 |
| Frontend: A2A streaming visualization | No A2A protocol yet on FE or BE | P2 |
| Backend: `SandboxExecutor` missing DuckDB + pre-injected globals | `sandbox_bootstrap.py` exists but not integrated with DuckDB session management | P1 |
| Backend: `AgentLoop` → `chat_api.py` SSE wiring | Loop runs synchronously; chat API needs to emit SSE events during tool calls | P1 |
| Backend: A2A protocol (agent-to-agent delegation via `delegate_subagent`) | Spec'ed in design but no implementation | P2 |
| Eval tests: levels 1–5 need to pass against the local agent loop | Evals exist but haven't been run end-to-end against the wired loop | P2 |

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Skill test import failures may mask real test failures | HIGH | Fix in Phase 0 before anything else |
| SSE streaming from a synchronous AgentLoop requires architectural change | HIGH | Wrap loop in background thread + queue; ship incremental events |
| DuckDB globals in sandbox must not leak across sessions | HIGH | One DuckDB connection per session ID; tear down on session close |
| A2A is architecturally new; don't block UI on it | MEDIUM | Ship FE as empty-state stub; A2A is Phase 5 |
| Eval levels 4–5 require multi-turn + finding promotion; local Gemma may fail | MEDIUM | Accept partial eval pass; annotate expected failures for small models |
| openfang's sidebar design is Rust-based (no matching TS code found) | LOW | Adopt the design concept (icon rail + expandable tab content) in React without porting code |

---

## Phase Summary

| Phase | Deliverable | Effort |
|---|---|---|
| **P0** | Fix 36 skill test import errors — all 418 tests + skill tests pass | Small |
| **P1-A** | Frontend: Agents tab + Skills tab in left sidebar | Medium |
| **P1-B** | Frontend: Right panel wired — artifact viewer, scratchpad, tool inspector | Medium |
| **P1-C** | Frontend: Per-agent monitoring page (trace + artifacts + scratchpad + timeline) | Medium |
| **P2-A** | Backend: DuckDB session integration + sandbox pre-injected globals | Medium |
| **P2-B** | Backend: AgentLoop → SSE streaming wired to `chat_api.py` | Medium |
| **P3** | Frontend: Wire streaming events to right panel + chat progress indicators | Small |
| **P4** | Backend: A2A delegation (`delegate_subagent` tool → subprocess agent) | Large |
| **P5** | Frontend: A2A visualization in chat + sidebar agents tree | Medium |
| **P6** | Eval: Run all 5 levels; document pass/fail against local Gemma + Claude Sonnet | Medium |

---

## Phase 0 — Fix Skill Test Import Errors

**Problem:** `app/skills/*/tests/` directories are found by pytest but resolve imports as
`tests.test_builder` (treating the test file as a top-level module) instead of
`app.skills.sql_builder.tests.test_builder`. The fix is ensuring proper `conftest.py`
and `pythonpath` config so pytest resolves imports correctly.

**Files to change:**
- `backend/pyproject.toml` — ensure `pythonpath = ["."]` in `[tool.pytest.ini_options]`
- Each `backend/app/skills/<name>/tests/__init__.py` — verify these exist
- `backend/conftest.py` — add path fix hook if needed
- Investigate `data_profiler/tests/fixtures` — `ValueError: Plugin already registered` points at a duplicate conftest fixture conflict

**Success:** `pytest --co -q` collects all tests with 0 errors; `pytest` passes or shows only genuine logic failures (not import errors).

---

## Phase 1-A — Frontend: Agents Tab + Skills Tab

**Goal:** The left sidebar gains two new tabs so the sidebar now has 7 tabs:
Chats, Agents, Skills, History, Files, DevTools, Settings.

### Agents Tab (`AgentsTab.tsx`)

Shows all agent sessions grouped by agent name/role. Design: icon rail with expandable content panel (openfang-inspired).

**UX:**
```
AGENTS  [filter input]
─────────────────────
▾ data-scientist      (3 sessions)
    ○ session 2026-04-14/15:02  RUNNING
    ✓ session 2026-04-14/14:11  DONE
    ✗ session 2026-04-14/12:44  FAILED
▸ orchestrator        (1 session)
▸ summarizer          (1 session)
```

Clicking a session navigates to the per-agent monitoring page (Phase 1-C).

**Backend dependency:** `GET /api/trace/traces` already returns sessions. The tab reads from
this endpoint and groups by `agent_role` field. If that field is absent, add it to the
trace event schema.

**Files:**
- Create: `frontend/src/components/sidebar/AgentsTab.tsx`
- Create: `frontend/src/lib/api-agents.ts` (typed wrapper around trace API grouping)
- Modify: `frontend/src/components/layout/Sidebar.tsx` — add `agents` to TABS array
- Modify: `frontend/src/lib/store.ts` — add `SidebarTab` union update (`'agents' | 'skills'`)

### Skills Tab (`SkillsTab.tsx`)

Hierarchical read-only view of the skill catalog. Three-level tree:
Level 1 Primitives → Level 2 Analytical → Level 3 Composition.

**UX:**
```
SKILLS                        [search]
─────────────────────────────────────
LEVEL 1 — PRIMITIVES
  ○ theme_config    v1.0   always loaded
  ○ altair_charts   v1.0   always loaded
  ○ html_tables     v1.0   always loaded
  ○ data_profiler   v1.0   always loaded
  ○ sql_builder     v1.0   always loaded

LEVEL 2 — ANALYTICAL (on-demand)
  ○ correlation     v1.0
  ○ group_compare   v1.0
  ▸ (click to expand → shows description, entry point, dependencies)

LEVEL 3 — COMPOSITION (on-demand)
  ○ analysis_plan   v1.0
  ○ report_builder  v1.0
  ○ dashboard_builder v1.0
```

**Backend dependency:** `GET /api/skills/manifest` — expose `backend/app/skills/manifest.py` if not already routed.

**Files:**
- Create: `frontend/src/components/sidebar/SkillsTab.tsx`
- Create: `frontend/src/lib/api-skills.ts`
- Modify: `frontend/src/components/layout/Sidebar.tsx` — add `skills` tab
- Verify/add: `GET /api/skills/manifest` in `backend/app/api/` if missing

---

## Phase 1-B — Frontend: Right Panel

**Goal:** Activate the right panel in `ChatLayout.tsx`. Default collapsed (icon rail).
Expands to show the active session's inspector.

Three sub-panels accessible via tab icons in the rail:

| Tab | Icon | Content |
|---|---|---|
| **Artifacts** | `ImageIcon` | Card list of artifacts (chart embeds, table previews, HTML frames, profile summaries) |
| **Scratchpad** | `StickyNote` | Live view of the agent's TODO/COT/Findings/Evidence scratchpad (read-only, monospace) |
| **Tool Calls** | `Terminal` | Ordered log of tool calls this turn: name, input summary, status (ok/blocked/error), duration |

**Files:**
- Create: `frontend/src/components/right-panel/RightPanel.tsx` — container with icon rail + tab content
- Create: `frontend/src/components/right-panel/ArtifactsPanel.tsx`
- Create: `frontend/src/components/right-panel/ScratchpadPanel.tsx`
- Create: `frontend/src/components/right-panel/ToolCallsPanel.tsx`
- Modify: `frontend/src/components/chat/ChatLayout.tsx` — add right panel column, Zustand state for `rightPanelOpen` / `rightPanelTab`
- Modify: `frontend/src/lib/store.ts` — add right panel state slice

**Backend dependency:** Artifacts available at `GET /api/artifacts?session_id=X`.
Scratchpad and tool calls emitted via SSE (Phase 2-B and 3).

---

## Phase 1-C — Frontend: Per-Agent Monitoring Page

**Goal:** Clicking an agent session in the Agents tab opens a dedicated monitoring view.

**Route:** `/monitor/:session_id`

**Layout:** Three sections stacked vertically:
1. **Session header**: agent name, model, status, duration, turn count
2. **Trace timeline**: horizontal scroll — each turn is a block; within it, tool calls ordered by
   timestamp, color-coded by status. Click to expand details.
3. **Details drawer** (bottom split): When a trace event is selected — full input/output,
   guardrail outcomes, artifact links, scratchpad snapshot at that point in time

**Files:**
- Create: `frontend/src/pages/MonitorPage.tsx`
- Create: `frontend/src/components/monitor/SessionHeader.tsx`
- Create: `frontend/src/components/monitor/TraceTimeline.tsx`
- Create: `frontend/src/components/monitor/EventDetailDrawer.tsx`
- Modify: `frontend/src/App.tsx` — add `/monitor/:session_id` route
- Modify: `frontend/src/components/sidebar/AgentsTab.tsx` — link session row to `/monitor/:id`

**Backend dependency:** `GET /api/trace/traces/:session_id` (already exists in `trace_api.py`).

---

## Phase 2-A — Backend: DuckDB Session Integration + Sandbox Globals

**Goal:** When a user uploads or references a dataset, the harness registers it in DuckDB
under a session-scoped database, then pre-injects `df`, `duckdb`, `save_artifact`, and all
skill entry points into the sandbox globals.

**Files to modify/create:**
- Modify: `backend/app/harness/sandbox_bootstrap.py` — add `build_globals(session_id, dataset_path) -> str` that:
  - Opens/creates `data/<session_id>.duckdb`
  - Loads the dataset into DuckDB as a relation
  - Returns a Python preamble string that assigns `df`, `duckdb`, `save_artifact`, `profile`,
    `correlate`, `compare`, `characterize`, `fit`, `validate`, and all `altair_charts` templates
- Modify: `backend/app/harness/sandbox.py` — `SandboxExecutor` accepts `extra_globals_script`
  (already supports it) — wire to `build_globals()`
- Create: `backend/app/api/datasets_api.py` — `POST /api/datasets/upload` accepts CSV/Parquet,
  stores in `data/uploads/<session_id>/`, triggers DuckDB registration
- Modify: `backend/app/harness/loop.py` — pass `dataset_loaded=True` and correct
  `extra_globals_script` when a dataset is registered
- Modify: `backend/app/main.py` — register `datasets_api` router

**Test:** `backend/tests/unit/test_sandbox_bootstrap.py` — verify globals preamble executes
in subprocess without import errors.

---

## Phase 2-B — Backend: AgentLoop → SSE Streaming

**Goal:** `POST /api/chat` streams agent progress as Server-Sent Events instead of returning
a single JSON blob. Each tool call, tool result, scratchpad update, and final text is streamed
as an SSE event.

**Event types (JSON payload per event):**

```
event: turn_start       { session_id, step }
event: tool_call        { step, name, input_preview }
event: tool_result      { step, name, status, artifact_ids, preview }
event: scratchpad_delta { step, section, text }
event: turn_end         { final_text, stop_reason, steps }
event: error            { message }
```

**Architecture:** `AgentLoop.run()` becomes `AgentLoop.run_stream()` — a generator that yields
`StreamEvent` dataclasses. `chat_api.py` wraps the generator in a `StreamingResponse` with
`text/event-stream` content-type.

**Files:**
- Modify: `backend/app/harness/loop.py` — add `run_stream()` generator yielding `StreamEvent`
- Create: `backend/app/harness/stream_events.py` — `StreamEvent` dataclass + serializer
- Modify: `backend/app/api/chat_api.py` — switch `POST /api/chat` to `StreamingResponse`
- Modify: `frontend/src/lib/api-chat.ts` — switch from `fetch(json)` to `EventSource` /
  `fetch` with streaming body read

---

## Phase 3 — Frontend: Wire Streaming to UI

**Goal:** Connect SSE stream to live UI updates.

- `turn_start` → show "thinking..." indicator in chat, activate progress bar in header
- `tool_call` → append entry to Tool Calls panel (right panel)
- `tool_result` → update tool call status, add artifacts to Artifacts panel
- `scratchpad_delta` → stream text into Scratchpad panel
- `turn_end` → render final `MessageBubble`, clear progress

**Files:**
- Modify: `frontend/src/lib/store.ts` — add streaming state slice (in-flight tool calls,
  scratchpad buffer, artifact accumulator)
- Modify: `frontend/src/lib/api-chat.ts` — `streamChat()` function that reads SSE and
  dispatches to store
- Modify: `frontend/src/components/chat/ChatInput.tsx` — call `streamChat()` on submit
- Modify: `frontend/src/components/chat/ChatWindow.tsx` — show in-progress assistant turn
  with streaming cursor
- Create: `frontend/src/hooks/useChatStream.ts` — hook encapsulating stream lifecycle

---

## Phase 4 — Backend: A2A Delegation

**Goal:** The `delegate_subagent` tool in the agent loop spawns a sub-agent in a background
thread, streams its result back as an artifact, and returns control to the parent.

**Design:**
- Parent calls `delegate_subagent(task: str, tools_allowed: list[str])`
- Dispatcher spawns a new `AgentLoop` with a reduced tool set and runs it in a thread pool
- Sub-agent result (final text + artifacts) is saved as an `analysis` artifact
- Parent receives `{ artifact_id, summary }` as the tool result

**Files:**
- Create: `backend/app/harness/a2a.py` — `SubagentDispatcher.dispatch(task, tools_allowed, parent_session_id) -> SubagentResult`
- Modify: `backend/app/harness/dispatcher.py` — register `delegate_subagent` tool
- Modify: `backend/app/harness/loop.py` — emit `a2a_start` / `a2a_end` SSE events for parent

---

## Phase 5 — Frontend: A2A Visualization

**Goal:** When an A2A delegation occurs, the chat shows a nested sub-agent card and the
Agents sidebar tab shows a child session under the parent.

**Files:**
- Create: `frontend/src/components/chat/SubagentCard.tsx` — expandable card showing
  sub-agent task, status, artifact produced
- Modify: `frontend/src/components/chat/MessageBubble.tsx` — detect `a2a_start`/`a2a_end`
  events, render `SubagentCard`
- Modify: `frontend/src/components/sidebar/AgentsTab.tsx` — show child sessions indented
  under parent

---

## Phase 6 — Eval Pipeline: Run and Document

**Goal:** All 5 eval levels execute cleanly; pass/fail rates documented for local Gemma
and Claude Sonnet.

**Pre-requisites:** P0 (tests pass), P2-A (DuckDB + globals), P2-B (streaming loop wired
to eval runner).

**Eval levels (from `backend/tests/evals/`):**
- L1: Tool calling correctness
- L2: Data profiling output quality
- L3: Statistical analysis (correlation, group compare)
- L4: Multi-turn with finding promotion
- L5: Full scientific loop (7 steps)

**Tasks:**
- Run `pytest backend/tests/evals/ -v --model=gemma_fast` — document results
- Run again with `--model=claude_sonnet` — document delta
- Add CI job in `.github/workflows/test.yml` that runs L1–L3 only (fast, cloud-free)
- Mark L4–L5 as `@pytest.mark.slow` — excluded from CI, run manually

---

## Execution Order

```
P0  ──────────────────────────────────────────── unblocks all tests
P1-A + P1-B + P1-C  ──────────────────────────── run in parallel (FE-only)
P2-A + P2-B  ─────────────────────────────────── run in parallel (BE-only)
P3  ────────── after P1-B + P2-B complete ─────── wire FE+BE stream
P4  ────────── after P2-B complete ────────────── A2A BE
P5  ────────── after P4 + P3 complete ─────────── A2A FE
P6  ────────── after P0 + P2-A + P2-B ─────────── eval run
```

---

## Definition of Done

- [ ] `pytest backend/` — 0 collection errors, ≥80% pass rate
- [ ] Frontend builds (`pnpm build`) with 0 TypeScript errors
- [ ] Sidebar has 7 tabs; Agents and Skills tabs render real data from backend
- [ ] Right panel shows artifacts, scratchpad, tool calls for an active session
- [ ] Monitor page shows trace timeline for a completed session
- [ ] Chat streams — tool call cards appear in real time, final message appears on `turn_end`
- [ ] Uploading a CSV triggers DuckDB registration; sandbox code can reference `df`
- [ ] Eval L1–L3 pass against Claude Sonnet; L1–L2 pass against Gemma
- [ ] A2A: `delegate_subagent` tool call visible in chat and Agents sidebar
