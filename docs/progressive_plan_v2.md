# Implementation Plan v2: claude-code-agent — OS Platform Frontend

**Date:** 2026-04-14  
**Status:** planning  
**Builds on:** docs/progressive_plan.md (all P0–P6 complete)

---

## Context

All original phases (P0–P6) are complete. This plan covers the next generation of the frontend:
an OS-style platform shell (openfang-inspired), enhanced context transparency, Skills/Prompts
explorer pages, terminal-quality progress panel, chart rendering parity with Analytical-chatbot,
and a formal gap analysis document.

---

## Current State (Post-v1)

| Area | Status |
|---|---|
| Backend APIs (chat, trace, skills, context, artifacts, datasets, slash, sop, models, health) | ✅ |
| Context Manager (layer tracking, compaction history, snapshot) | ✅ — global only, needs per-session |
| Frontend: 7-tab sidebar in ChatLayout | ✅ — needs OS-platform restructure |
| Frontend: Right panel (Artifacts, Scratchpad, ToolCalls) | ✅ — needs chart rendering + terminal style |
| Frontend: Monitor page `/monitor/:session_id` | ✅ — needs monitoring dashboard (cards) |
| Skills source viewer | ❌ not built |
| Prompts registry page | ❌ not built |
| Context Inspector page | ❌ not built |
| Chart rendering (Vega-Lite / Altair) | ❌ not wired |
| Terminal-style progress panel | ❌ ToolCallsPanel is minimal table |
| OS-platform icon rail layout | ❌ still single ChatLayout |
| Gap analysis document | ❌ not written |

---

## Phase 7 — OS-Platform Layout Restructure

**Goal:** Replace the single `ChatLayout` with a top-level section router. A narrow icon rail
(48px) on the far left selects the active section. Each section occupies the full remaining area.

### Icon Rail (`IconRail.tsx`)

Seven icons stacked vertically in a `48px` column:

| Icon | Section | Key |
|---|---|---|
| `MessageSquare` | Chat | C |
| `Monitor` | Agents | A |
| `Puzzle` | Skills | S |
| `FileText` | Prompts | P |
| `Layers` | Context | X |
| `Code2` | DevTools | D |
| `Settings` | Settings | G |

Active section: icon background = `--color-accent` (purple), `#8b5cf6`. Inactive: `--color-text-muted`.

### Section Router

`App.tsx` top-level layout:

```
┌─────────────────────────────────────────────────────┐
│ IconRail (48px) │         Active Section             │
│                 │                                    │
│   [icon]        │  ChatSection / AgentsSection /     │
│   [icon]        │  SkillsSection / PromptsSection /  │
│   [icon]        │  ContextSection / DevtoolsSection / │
│   [icon]        │  SettingsSection                   │
└─────────────────────────────────────────────────────┘
```

### Chat Section (`ChatSection.tsx`)

Three-panel layout (replaces current `ChatLayout`):

```
┌──────────────────────────────────────────────────────┐
│ ConvList (220px) │  ChatMain (flex)  │ RightPanel    │
│                  │                   │ (280px)       │
│  New Chat [+]    │  MessageBubbles   │               │
│  ──────────────  │                   │  [Artifacts]  │
│  conv 1          │  ChatInput        │  [Scratchpad] │
│  conv 2          │                   │  [Terminal]   │
│  conv 3          │                   │               │
└──────────────────────────────────────────────────────┘
```

- ConvList: conversation history (replaces HistoryTab), new chat button
- ChatMain: existing chat + streaming cursor
- RightPanel: **three tabs** — Artifacts (chart-capable), Scratchpad, Terminal (tool progress)

**Files to create/modify:**
- Create: `frontend/src/components/layout/IconRail.tsx`
- Create: `frontend/src/components/layout/SectionRouter.tsx`
- Create: `frontend/src/sections/ChatSection.tsx` — wraps current ChatLayout
- Create: `frontend/src/sections/AgentsSection.tsx` — monitoring dashboard (Phase 9)
- Create: `frontend/src/sections/SkillsSection.tsx` — skills explorer (Phase 8)
- Create: `frontend/src/sections/PromptsSection.tsx` — prompts registry (Phase 10)
- Create: `frontend/src/sections/ContextSection.tsx` — context inspector (Phase 11)
- Create: `frontend/src/sections/DevtoolsSection.tsx` — existing devtools moved here
- Create: `frontend/src/sections/SettingsSection.tsx` — existing settings moved here
- Modify: `frontend/src/App.tsx` — replace hash router with section router
- Modify: `frontend/src/lib/store.ts` — add `activeSection` state, remove sidebar tab state
- Modify: `frontend/src/styles/globals.css` — add `--icon-rail-width: 48px` token

**Success:** App launches with icon rail. Clicking icons switches sections. Chat section works identically to current app.

> **Spec Drift Note (2026-04-16):** `components/layout/SectionRouter.tsx` was not created
> as a standalone file. Section routing is implemented directly in `App.tsx` via a small
> `activeSection` switch over the seven sections. The plan's intent (a dedicated router)
> was met by the inline implementation; no behavioural gap exists.

---

## Phase 8 — Skills Explorer Page

**Goal:** A full-page skills browser showing the 3-level hierarchy, per-skill detail panel,
Python source code viewer, and dependency graph. Read-only.

### Layout

```
┌─────────────────────────────────────────────────────┐
│  SKILLS                              [search input] │
│  ──────────────────────────────────────────────── │
│  Skill List (280px)  │  Detail Panel (flex)         │
│  ────────────────    │  ─────────────────────────── │
│  LEVEL 1 — PRIMITIVES│  altair_charts               │
│   ○ theme_config     │  v1.0 · always loaded        │
│   ○ altair_charts ◀  │                              │
│   ○ html_tables      │  Description                 │
│   ○ data_profiler    │  ───────────────             │
│   ○ sql_builder      │  [SKILL.md content]          │
│                      │                              │
│  LEVEL 2 — ANALYTICAL│  Dependencies                │
│   ○ correlation      │  ─────────────               │
│   ○ group_compare    │  altair_charts → theme_config│
│   ○ time_series      │                              │
│   ○ stat_validate    │  Source Files                │
│   ○ distribution_fit │  ─────────────               │
│                      │  [SKILL.md] [__init__.py]    │
│  LEVEL 3 — COMPOSITION│  [charts.py] [templates/]  │
│   ○ analysis_plan    │                              │
│   ○ report_builder   │  [file content in CodeBlock] │
│   ○ dashboard_builder│                              │
└─────────────────────────────────────────────────────┘
```

### Backend additions

`GET /api/skills/{name}/detail` — returns:
```json
{
  "name": "altair_charts",
  "level": 1,
  "description": "...",
  "entry_point": "altair_charts.charts",
  "requires": ["theme_config"],
  "required_by": ["correlation", "group_compare", ...],
  "skill_md": "...",
  "source_files": [
    {"path": "SKILL.md", "content": "..."},
    {"path": "__init__.py", "content": "..."},
    {"path": "charts.py", "content": "..."}
  ]
}
```

Reads from filesystem at `backend/app/skills/{name}/`. Excludes `__pycache__/`, `.pyc`.

**Files:**
- Create: `frontend/src/sections/SkillsSection.tsx` — main container with list + detail split
- Create: `frontend/src/components/skills/SkillList.tsx` — grouped by level, search filter
- Create: `frontend/src/components/skills/SkillDetail.tsx` — SKILL.md + source viewer
- Create: `frontend/src/components/skills/SkillDependencyGraph.tsx` — simple SVG tree
- Create: `frontend/src/lib/api-skills-detail.ts` — typed wrapper for `/api/skills/{name}/detail`
- Modify: `backend/app/api/skills_api.py` — add `GET /api/skills/{name}/detail` endpoint
- Modify: `backend/app/api/skills_api.py` — add `GET /api/skills/{name}/source/{file}` for raw file

**Success:** Clicking a skill shows its SKILL.md rendered as markdown, lists dependency arrows, and shows all Python source in scrollable CodeBlocks.

> **Spec Drift Note (2026-04-16):** The `frontend/src/components/skills/` directory was
> never created. `SkillList.tsx`, `SkillDetail.tsx`, and `SkillDependencyGraph.tsx` were
> intentionally collapsed into `frontend/src/sections/SkillsSection.tsx` as inline
> sub-components (`SkillListPanel`, `SkillDetailPanel`, `DependencyGraph`). The page
> ships the full feature set described above; only the file-layout differs. Don't search
> for `SkillDependencyGraph.tsx` — it lives inside `SkillsSection.tsx`.

---

## Phase 9 — Monitoring Dashboard (Agent Cards)

**Goal:** Replace the current Agents section (which is just the AgentsTab from the sidebar)
with a full-screen monitoring dashboard: a card grid for running/recent agents, click → detail.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  MONITORING          [filter: all | running | done | failed] │
│  ──────────────────────────────────────────────────────── │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ data-scientist│  │orchestrator │  │ summarizer  │     │
│  │ ● RUNNING   │  │ ✓ DONE      │  │ ✗ FAILED    │     │
│  │ session/... │  │ 4m 22s      │  │ 1m 08s      │     │
│  │ turn 7/∞    │  │ 12 artifacts│  │ error msg   │     │
│  │ 18,442 tok  │  │ 0 errors    │  │             │     │
│  │ [View ↗]   │  │ [View ↗]   │  │ [View ↗]   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                          │
│  ─── Recent Sessions ────────────────────────────────── │
│  [agent cards for completed sessions, newest first]      │
└──────────────────────────────────────────────────────────┘
```

### Agent Card details on click

Navigates to `/monitor/:session_id` (existing MonitorPage — already built).

### Live Updates

Running agents poll `/api/trace/traces` every 3 seconds to update card status/turn count/tokens.

**Files:**
- Create: `frontend/src/sections/AgentsSection.tsx` — card grid + filter bar
- Create: `frontend/src/components/agents/AgentCard.tsx` — status card component
- Create: `frontend/src/components/agents/AgentCardSkeleton.tsx` — loading state
- Modify: `frontend/src/lib/api-agents.ts` — add `listAllSessions()` for card data
- Modify: existing `MonitorPage.tsx` — already works; no changes needed

**Success:** Monitoring section shows a card per agent session. Running agents animate their token counter. Click navigates to existing monitor detail page.

> **Spec Drift Note (2026-04-16):** The `frontend/src/components/agents/` directory was
> never created. `AgentCard.tsx` and `AgentCardSkeleton.tsx` were intentionally collapsed
> into `frontend/src/sections/AgentsSection.tsx` as inline sub-components. The card grid,
> filter bar, status badges, and live polling all live inside the section file. Don't
> search for `AgentCard.tsx` — it lives inside `AgentsSection.tsx`.

---

## Phase 10 — Prompts Registry Page

**Goal:** A read-only page listing every prompt registered in the system — system prompt,
per-skill prompts (SKILL.md injection text), injector templates, and tool-level prompts.
Helps users understand exactly what's in the model's context.

### Layout

```
┌────────────────────────────────────────────────────────────┐
│  PROMPTS                                    [search]       │
│  ──────────────────────────────────────────────────────── │
│  Prompt List (260px)    │  Prompt Detail (flex)            │
│  ────────────────────   │  ─────────────────────────────  │
│  SYSTEM                 │  system_prompt                   │
│   ○ system_prompt ◀     │  Type: system · Always injected  │
│                         │  Tokens: ~2,800                  │
│  SKILL INJECTIONS (L2)  │                                  │
│   ○ altair_charts       │  [Full prompt text in monospace] │
│   ○ html_tables         │                                  │
│   ○ data_profiler       │  Usage                          │
│   ○ sql_builder         │  ────────                        │
│   ○ ... (on demand)     │  Injected at turn start via      │
│                         │  PreTurnInjector when skill is   │
│  INJECTOR TEMPLATES     │  loaded.                         │
│   ○ tool_result_fmt     │                                  │
│   ○ scratchpad_fmt      │  Where it appears               │
│   ○ error_fmt           │  ───────────────                 │
│                         │  L2 — Skill injection layer      │
│  TOOL DESCRIPTIONS      │  (compactable)                   │
│   ○ query_duckdb        │                                  │
│   ○ run_python          │                                  │
│   ○ save_artifact       │                                  │
│   ○ ...                 │                                  │
└────────────────────────────────────────────────────────────┘
```

### Backend additions

`GET /api/prompts` — returns all registered prompts:
```json
[
  {
    "id": "system_prompt",
    "category": "system",
    "label": "System Prompt",
    "description": "Always-present system prompt (L1 layer)",
    "layer": "L1",
    "compactable": false,
    "approx_tokens": 2800,
    "text": "..."
  },
  {
    "id": "skill_altair_charts",
    "category": "skill_injection",
    "label": "altair_charts skill injection",
    "layer": "L2",
    "compactable": true,
    "approx_tokens": 1200,
    "text": "..."
  },
  ...
]
```

Source of truth:
- `system_prompt` — read from `backend/app/harness/injector.py`
- skill injections — read SKILL.md from each skill directory
- injector templates — read from `injector.py` template strings
- tool descriptions — read from `dispatcher.py` tool schemas

**Files:**
- Create: `frontend/src/sections/PromptsSection.tsx` — list + detail split
- Create: `frontend/src/components/prompts/PromptList.tsx`
- Create: `frontend/src/components/prompts/PromptDetail.tsx` — token count badge, monospace viewer
- Create: `frontend/src/lib/api-prompts.ts`
- Modify: `backend/app/api/` — add `prompts_api.py` with `GET /api/prompts`
- Modify: `backend/app/main.py` — register prompts_api router

**Success:** Prompts section shows categorized list. Clicking any prompt shows its full text, estimated token count, and where in the context it appears (layer + compactable flag).

> **Spec Drift Note (2026-04-16):** The `frontend/src/components/prompts/` directory was
> never created. `PromptList.tsx` and `PromptDetail.tsx` were intentionally collapsed
> into `frontend/src/sections/PromptsSection.tsx` as inline sub-components. The
> categorized list, search, monospace detail viewer, and token-count badges all live
> inside the section file.

---

## Phase 11 — Context Inspector Page

**Goal:** A dedicated page for understanding context window composition in real time —
layer breakdown, per-session tracking, and compaction diff view for information loss analysis.

### Layout — Context Inspector

```
┌────────────────────────────────────────────────────────────┐
│  CONTEXT                       Session: [dropdown]  [live] │
│  ──────────────────────────────────────────────────────── │
│  Context Bar (full width)                                  │
│  ┌──────────────────────────────────────────┬────────┐    │
│  │ ████████ L1:system │ ██████ L2:skills │ ████ conv │ av │
│  └──────────────────────────────────────────┴────────┘    │
│  18,442 / 32,768 tokens  (56.3%)                          │
│                                                            │
│  Layer Breakdown                    Compaction History     │
│  ────────────────                   ────────────────────   │
│  L1 system_prompt  2,800  (15%)    #1  48% → 22% freed    │
│  L2 altair_charts  1,200  (6.5%)        removed: conv[1-8]│
│  L2 html_tables      840  (4.6%)                          │
│  L2 data_profiler    620  (3.4%)   #2  71% → 31% freed    │
│  conversation      9,200  (50%)        removed: conv[9-16]│
│  tool_results      3,782  (20.5%)                         │
│  ─────────────────────────────────────────────────────    │
│  Compaction Diff (click event to view)                     │
│  ┌──────────────────┬────────────────────┐                │
│  │  BEFORE (71%)    │  AFTER (31%)        │                │
│  │  conv[1] 1,240 ✗ │  conv[17] 890 ✓    │                │
│  │  conv[2]   980 ✗ │  conv[18] 760 ✓    │                │
│  │  conv[3]   830 ✗ │  L1 system   2,800 ✓│                │
│  │  ... [8 removed] │  L2 skills   2,660 ✓│                │
│  └──────────────────┴────────────────────┘                │
│  Information loss: 40% of context freed                    │
│  Quality risk: HIGH (long conversation truncated)          │
└────────────────────────────────────────────────────────────┘
```

### Backend additions

1. **Per-session context manager**: `ContextManager` needs a session_id key. Store in a dict in `context_api.py` (or add to session state in `loop.py`).

2. **Explicit L1/L2 layer registration**: `PreTurnInjector` must call `context_manager.add_layer()` with:
   - `ContextLayer(name="system_prompt", tokens=N, compactable=False, items=[...])`
   - `ContextLayer(name="skill_{name}", tokens=N, compactable=True, items=[...])`

3. **Conversation + tool_results layers**: `AgentLoop` registers/updates these each turn.

4. **New API endpoints**:
   - `GET /api/context/{session_id}` → full snapshot for session
   - `GET /api/context/{session_id}/history` → list of compaction events
   - `GET /api/context/{session_id}/compaction/{id}/diff` → before/after detail for one event
   - `GET /api/context/sessions` → list all sessions with latest context utilization

**Files:**
- Create: `frontend/src/sections/ContextSection.tsx`
- Create: `frontend/src/components/context/ContextBar.tsx` — stacked bar (pure CSS, no chart lib)
- Create: `frontend/src/components/context/LayerBreakdown.tsx` — table with % and token counts
- Create: `frontend/src/components/context/CompactionHistory.tsx` — event list
- Create: `frontend/src/components/context/CompactionDiff.tsx` — before/after side-by-side
- Create: `frontend/src/lib/api-context.ts` — typed wrappers for context endpoints
- Modify: `backend/app/context/manager.py` — make per-session (add `session_id` param)
- Modify: `backend/app/harness/injector.py` — register L1/L2 layers on each injection
- Modify: `backend/app/harness/loop.py` — register/update conversation + tool_results layers each turn
- Modify: `backend/app/api/context_api.py` — add `/context/{session_id}`, `/context/{session_id}/history`, `/context/{session_id}/compaction/{id}/diff`, `/context/sessions`

**Success:** Context section shows live layer breakdown for any session. Selecting a compaction event shows exactly which layers were removed vs survived. Information loss percentage is calculated and flagged HIGH/MEDIUM/LOW.

> **Spec Drift Note (2026-04-16):** The `frontend/src/components/context/` directory was
> never created. `LayerBreakdown.tsx`, `CompactionHistory.tsx`, and `CompactionDiff.tsx`
> were intentionally collapsed into `frontend/src/sections/ContextSection.tsx` as inline
> sub-components (e.g. `CompactionDiffPanel()`). One exception: `ContextBar.tsx` was
> created as a standalone file at `frontend/src/components/layout/ContextBar.tsx`
> because it is reused outside the Context section (in the chat header). Don't search
> for `CompactionDiff.tsx` — it lives inside `ContextSection.tsx`.

---

## Phase 12 — Terminal Progress Panel

**Goal:** Replace `ToolCallsPanel.tsx` (a static table) with a terminal-style animated execution
log matching Analytical-chatbot's `ProgressPanel` quality — animated entries, live timers,
rotating status verbs per tool type.

### Design

```
TERMINAL                                              [clear]
─────────────────────────────────────────────────────────────
● RUNNING  data-scientist  turn 7                 [2:14.3]
─────────────────────────────────────────────────────────────
  ✓ query_duckdb          Quacking through SQL...   1.2s
    SELECT * FROM housing WHERE...

  ✓ run_python            Snake go brrrr...         3.8s
    import pandas as pd
    df.groupby('region').agg(...)
    >> (output)
    region      count   mean_price
    ...

  ◌ save_artifact         Stashing the goods...    [live]
```

- Each tool call = animated entry (AnimatePresence)
- Tool-type verb maps (same as Analytical-chatbot, adapted for agent's tool set)
- Python input: code block in monospace, collapsed by default, expand on click
- Python output: stdout/stderr lines, scrollable, max 40 lines shown
- Live timer per in-flight tool call
- Elapsed badge on completion
- `clear` button resets log for current session

### Changes needed
- `TerminalPanel.tsx` replaces `ToolCallsPanel.tsx` — completely rewritten
- SSE events from `tool_call` and `tool_result` stream types feed this panel
- `run_python` events need stdout/stderr in `tool_result` payload (add to `stream_events.py`)

**Files:**
- Create: `frontend/src/components/right-panel/TerminalPanel.tsx`
- Delete: `frontend/src/components/right-panel/ToolCallsPanel.tsx`
- Modify: `frontend/src/components/right-panel/RightPanel.tsx` — replace ToolCalls tab with Terminal
- Modify: `frontend/src/lib/store.ts` — terminal panel state (log entries per session)
- Modify: `backend/app/harness/stream_events.py` — include stdout/stderr in tool_result events
- Modify: `backend/app/harness/sandbox.py` — capture stdout/stderr and emit to stream

**Success:** Running a Python tool shows the code input and line-by-line stdout in the terminal panel with live timing.

---

## Phase 13 — Chart / Artifact Rendering

**Goal:** The Artifacts panel renders Altair/Vega-Lite charts inline, tables with sorting, and
HTML artifacts in sandboxed iframes. Parity with Analytical-chatbot's ArtifactsPanel.

### Chart Rendering

Use `vega-embed` (already likely in package.json — verify). If not present, add:
`pnpm add vega vega-lite vega-embed`

Chart artifacts from `/api/artifacts?session_id=X` have type `"chart"` with `spec` field
(Vega-Lite JSON). Render with `vegaEmbed(container, spec, {theme: 'dark', renderer: 'svg'})`.

### Artifact Card Types

| Artifact type | Rendering |
|---|---|
| `chart` | `VegaChart.tsx` — embed Vega-Lite spec |
| `table` | `DataTable.tsx` — virtual list, sortable columns |
| `html` | `<iframe sandbox>` — sandboxed HTML frame |
| `profile` | `ProfileCard.tsx` — key stats grid |
| `text` | `MarkdownBlock.tsx` — rendered markdown |
| `image` | `<img>` with object-fit: contain |

**Files:**
- Create: `frontend/src/components/right-panel/VegaChart.tsx` — vega-embed wrapper
- Create: `frontend/src/components/right-panel/DataTable.tsx` — sortable table
- Create: `frontend/src/components/right-panel/ArtifactCard.tsx` — type-routing card
- Modify: `frontend/src/components/right-panel/ArtifactsPanel.tsx` — use ArtifactCard per artifact
- Modify: `frontend/src/lib/api-artifacts.ts` — ensure `type` and `spec` fields are in type defs
- Add: `pnpm add vega vega-lite vega-embed @types/vega-embed` if not present

**Backend check:** Artifact store (`backend/app/artifacts/`) must include `type` and `spec` in
artifact payloads. Verify `ArtifactStore.get_session_artifacts()` returns these fields.

**Success:** A `query_duckdb` → `save_artifact(type="chart", spec={...})` flow results in a
rendered Vega-Lite chart appearing in the Artifacts panel in real time.

> **Spec Drift Note (2026-04-16):** `VegaChart.tsx` and `ArtifactCard.tsx` were not
> created as standalone files. The artifact-type routing (chart / table / html / profile
> / text / image) and the Vega-Lite embed are implemented inline inside
> `frontend/src/components/right-panel/ArtifactsPanel.tsx`. `DataTable.tsx` was extracted
> as planned because it is also reused by the Skills detail view. Don't search for
> `VegaChart.tsx` or `ArtifactCard.tsx` — both live inside `ArtifactsPanel.tsx`.

---

## Phase 14 — Gap Analysis Document

**Goal:** Write a concise, structured gap analysis comparing claude-code-agent to
Analytical-chatbot and to claude-code-main. Stored at `docs/gap-analysis.md`.

### Scope (per user request): memory, context, harness, agent loop, skill, tools

Already researched (see findings.md Finding 11). This phase writes the document.

**File to create:** `docs/gap-analysis.md`

Structure:
1. Executive Summary
2. Memory Layer comparison
3. Context Tracking comparison
4. Harness / Agent Loop comparison
5. Skills System comparison
6. Tools comparison
7. Priority gaps to close (ranked by data-scientist-user impact)
8. What claude-code-agent does BETTER than both (data sandbox, eval framework, artifact store, SSE streaming)

---

## Execution Order

```
Phase 7  ──────────────────────────────────── OS layout (unblocks all sections)
Phase 8 + 9 + 10  ─────────── parallel ─────── Skills / Agents / Prompts sections
Phase 11 ──────────────────────────────────── Context Inspector (needs P7 + BE changes)
Phase 12 + 13  ────────────── parallel ─────── Terminal + Charts (needs P7)
Phase 14 ──────────────────────────────────── Gap analysis (no code, just docs)
```

Phase 11 requires backend changes to `context_api.py`, `injector.py`, and `loop.py` before
the frontend can be completed.

---

## Backend Change Summary

| File | What changes | Phase |
|---|---|---|
| `backend/app/api/skills_api.py` | Add `GET /api/skills/{name}/detail` and `GET /api/skills/{name}/source/{file}` | P8 |
| `backend/app/api/prompts_api.py` | New file — `GET /api/prompts` | P10 |
| `backend/app/main.py` | Register prompts_api router | P10 |
| `backend/app/context/manager.py` | Add `session_id` param; make per-session | P11 |
| `backend/app/harness/injector.py` | Register L1/L2 layers with context manager | P11 |
| `backend/app/harness/loop.py` | Register conversation + tool_results layers each turn | P11 |
| `backend/app/api/context_api.py` | Add per-session endpoints + compaction diff | P11 |
| `backend/app/harness/stream_events.py` | Include stdout/stderr in tool_result events | P12 |
| `backend/app/harness/sandbox.py` | Capture stdout/stderr for streaming | P12 |

---

## Frontend New Files Summary

> **Note (2026-04-16):** Several `components/<area>/` subdirectories below were
> intentionally collapsed into their `sections/<Area>Section.tsx` files. See the
> "Spec Drift Note" callout at the end of Phases 7, 8, 9, 10, 11, and 13 for the
> exact mapping. The list below is the original plan, kept for historical reference.

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── IconRail.tsx                    P7
│   │   └── SectionRouter.tsx               P7
│   ├── agents/
│   │   ├── AgentCard.tsx                   P9
│   │   └── AgentCardSkeleton.tsx           P9
│   ├── skills/
│   │   ├── SkillList.tsx                   P8
│   │   ├── SkillDetail.tsx                 P8
│   │   └── SkillDependencyGraph.tsx        P8
│   ├── prompts/
│   │   ├── PromptList.tsx                  P10
│   │   └── PromptDetail.tsx                P10
│   ├── context/
│   │   ├── ContextBar.tsx                  P11
│   │   ├── LayerBreakdown.tsx              P11
│   │   ├── CompactionHistory.tsx           P11
│   │   └── CompactionDiff.tsx              P11
│   └── right-panel/
│       ├── TerminalPanel.tsx               P12  (replaces ToolCallsPanel)
│       ├── VegaChart.tsx                   P13
│       ├── DataTable.tsx                   P13
│       └── ArtifactCard.tsx               P13
├── sections/
│   ├── ChatSection.tsx                     P7
│   ├── AgentsSection.tsx                   P9
│   ├── SkillsSection.tsx                   P8
│   ├── PromptsSection.tsx                  P10
│   ├── ContextSection.tsx                  P11
│   ├── DevtoolsSection.tsx                 P7
│   └── SettingsSection.tsx                 P7
└── lib/
    ├── api-skills-detail.ts                P8
    ├── api-prompts.ts                      P10
    └── api-context.ts                      P11
```

---

## Definition of Done

- [ ] App shows icon rail; clicking each icon loads the correct section
- [ ] Skills section: 3-level hierarchy, Python source viewable in CodeBlock, dependency arrows shown
- [ ] Prompts section: all system/skill/injector/tool prompts listed with token count and layer info
- [ ] Context section: stacked bar chart showing L1/L2/conversation/tool breakdown; compaction diff view works
- [ ] Monitoring section: agent cards with status badges; live token counter on RUNNING agents
- [ ] Terminal panel: animated tool entries with Python stdout; live timer on in-flight calls
- [ ] Artifacts panel: Vega-Lite charts render inline; tables sortable
- [ ] `docs/gap-analysis.md` written and committed
- [ ] `pnpm build` — 0 TS errors
- [ ] `pytest backend/` — no regressions
