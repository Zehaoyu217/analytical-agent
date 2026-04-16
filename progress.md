# progress.md — claude-code-agent

---

## Session: 2026-04-14

### Context Restored
- Read `docs/progressive_plan.md` — 10-phase plan (P0–P6)
- Confirmed: no previous planning files existed (fresh session)
- Ran `git log`: most recent work is around lint fixes and eval skip logic

### Current State Assessment
- P0 (test imports): **36 collection errors** — not yet fixed
- P1-A (Agents/Skills tabs): sidebar has only 3 real tabs (Files, History, Settings) — P1-A not done
- P1-B (right panel): no `right-panel/` component directory exists — not done
- P1-C (monitor page): no `MonitorPage.tsx` — not done
- P2-A/B, P3, P4, P5, P6: not started

### Diagnosis Completed (P0)
- **Problem 1**: 35 errors = `importmode=prepend` + `tests/__init__.py` + no skill-level `__init__.py`
  → pytest prepends `app/skills/<name>/` and tries `tests.test_X` import → fails
- **Problem 2**: 1 error = `data_profiler/tests/fixtures/conftest.py` registered twice
  (once via `pytest_plugins` in `backend/conftest.py`, once by auto-discovery)

### Actions Taken
- [x] Apply P0 fix to pyproject.toml and backend/conftest.py
- [x] Rename data_profiler fixtures/conftest.py → fixtures.py; remove duplicate pytest_plugins from 6 test files
- [x] Verified 0 collection errors (503 collected)
- [x] 497 pass, 1 skip, 0 errors (non-eval run). Eval failure = Ollama not running, not a logic bug.
- [x] Committed: `fix(tests): resolve 36 skill test collection errors — P0 complete`

### Next: P1-A (Agents tab + Skills tab in sidebar)

## P1-A/B/C — Complete (same session)
- [x] store.ts: SidebarTab extended to 7 tabs, RightPanelTab + rightPanel state added
- [x] P1-A: AgentsTab, SkillsTab, api-agents.ts, api-skills.ts, Sidebar.tsx updated
- [x] P1-A BE: GET /api/skills/manifest — skills_api.py + main.py registered
- [x] P1-B: RightPanel + 3 sub-panels (Artifacts, Scratchpad, ToolCalls), ChatLayout updated
- [x] P1-C: hash router in App.tsx, MonitorPage, SessionHeader, TraceTimeline, EventDetailDrawer
- [x] pnpm build: passes, 0 TS errors
- [x] Backend unit tests: 293 pass
- [x] Committed: `feat(frontend): P1-A/B/C — Agents tab, Skills tab, right panel, monitor page` (e012d9a)

### Next: P2-A (DuckDB session integration) + P2-B (AgentLoop SSE streaming) — parallel BE work

---

## Session: 2026-04-14 (v2 planning — OS platform + context + skills + prompts)

### Context Restored
- Read task_plan.md: all v1 phases (P0–P6) marked complete
- Read progressive_plan.md: confirmed P0 + P1-A/B/C verified; P2-P6 assumed complete from task_plan
- Read reference projects: openfang (Rust TUI), Analytical-chatbot (React), claude-code-main (TS/Ink)

### Research Completed
- openfang: icon-rail + section-per-screen pattern; Skills screen (Installed/ClawHub/MCP sub-tabs); Agents screen (grouped by role, status badges); theme design decisions
- Analytical-chatbot: ProgressPanel (animated terminal, tool verb maps, live timer, framer-motion); ArtifactsPanel (VegaChart, DataTable, HTML iframe); SSE lib; design tokens (amber accent, navy surfaces)
- claude-code-agent context: ContextManager tracks ContextLayer objects, compaction history; currently global not per-session; L1/L2 not explicitly tagged; context_api.py has single GET /api/context
- claude-code-main: file-based memory, no in-process compaction tracking, hook system, planning mode, task management, per-tool prompt.ts files, full filesystem tools

### Plan Created
- [x] findings.md updated with v2 research (Findings 5–11)
- [x] docs/progressive_plan_v2.md created (P7–P14, 8 phases)
- [x] task_plan.md updated with v2 phase status table
- [x] progress.md updated (this entry)

### Key Decisions
- P7 FIRST: OS-platform layout restructure is a prerequisite — all section pages depend on it
- P8/P9/P10 can run in parallel after P7 (independent section implementations)
- P11 (Context Inspector) requires backend changes to context/manager.py, injector.py, loop.py BEFORE frontend work
- P12/P13 can run in parallel after P7 (right panel work, independent)
- P14 (gap analysis doc) can run anytime — no code dependency

### Architecture Decisions
- Session-scoped ContextManager: store in dict keyed by session_id in context_api.py (simple approach, no DB needed)
- L1/L2 tagging: PreTurnInjector calls add_layer() with explicit names (system_prompt, skill_{name})
- Chart rendering: vega-embed library (same as Analytical-chatbot's approach)
- Icon rail: 48px wide, SVG icons from lucide-react, active section = purple fill (#8b5cf6)
- Prompts registry: read-time assembly (filesystem reads + injector introspection) — no persistent store needed

### Next: Start P7 (OS layout) or P14 (gap doc — fast win)

---

## Session: 2026-04-15 (V3 gap analysis + planning)

### Context Restored
- Read task_plan.md: v1 complete, v2 partially complete (P7-P14)
- Read progress.md: previous sessions documented
- Read findings.md: Findings 1-11

### Deep Research Completed (cross-project comparison)
- Re-examined claude-code-main: DreamTask, SessionMemory (9-section template), 4 compaction strategies (compact/microCompact/apiMicrocompact/sessionMemoryCompact), hook system, plan mode, task management tools
- Examined deer-flow: persistent memory with facts/user-context/history, LangGraph checkpointing, memory CRUD API
- Examined Analytical-chatbot: ProgressPanel (animated verbs, live timers), VegaChart, full component library
- Re-examined claude-code-agent: CRITICAL finding — chat_api.py uses 2 tools + legacy prompt, NOT the full harness

### Critical Finding
**Harness-API Disconnect (P15):** The sophisticated backend (PreTurnInjector, 13 skills, WikiEngine, real SandboxExecutor) is built but NOT wired to chat_api.py. The running endpoint uses `_SYSTEM_PROMPT_BASE` ("financial analyst, AT MOST ONCE") with only execute_python + write_working. All v1/v2 work on the harness is invisible to the user.

**Frontend Routing Disconnect (P16):** App.tsx still renders SessionLayout. IconRail, all 7 sections (ChatSection, AgentsSection, ContextSection, etc.) are built but unreachable.

### Also Confirmed
- The older "85% design, 15% implementation" assessment is outdated — project is now ~75% complete
- CLAUDE.md updated: accent color changed from purple (#8b5cf6) to orange (#e0733a)
- V2 P9 (AgentsSection) and P11 (ContextSection) are mostly complete
- Per-session context endpoints exist in context_api.py
- session_registry (per-session ContextManager) is implemented but wiring in chat_api.py unclear

### Documents Created
- [x] docs/gap-analysis-v2.md — comprehensive state assessment with historical context
- [x] docs/progressive_plan_v3.md — V3 spec plan (P15-P22)
- [x] task_plan.md updated with v2 status + v3 phases
- [x] progress.md updated (this entry)
- [x] findings.md to be updated

### Next: P15 (wire full harness to chat_api.py) — the single highest-impact change

---

## Session: 2026-04-15 (Hermes migration — design + planning)

### Context Restored
- Read task_plan.md: v1/v2/v3 all complete (P0–P22, EVAL-1–5)
- Read progress.md: 3 prior sessions documented

### Work Completed

#### Gap Analysis
- Cloned NousResearch/hermes-agent to /Users/jay/Developer/hermes-agent
- Deep architectural exploration of both codebases (parallel agents)
- Produced 12-candidate gap analysis document

#### Brainstorming → Spec
- Decisions: mega-plan, sessions.db replaces YAML, in-process APScheduler, main model for compression, Telegram excluded, CCAGENT_HOME
- Sequenced into 6 phases (H1–H6) with strict dependency ordering
- Self-review fixed 3 issues: consecutive user-role bug (P3c), AgentFactory clarification, config_api.py new file note
- Spec committed: `docs/superpowers/specs/2026-04-15-hermes-migration-design.md`

#### Planning (this session)
- [x] task_plan.md: Added H1–H6 with granular numbered tasks (74 tasks + 23 test tasks total)
- [x] findings.md: Added Findings 18–21 (migration candidates, schema decisions, cache-preservation pattern, parallel safety rules)
- [x] progress.md: Updated (this entry)

### Phase Status
All H1–H6 phases: **pending** — ready to execute

### Key Architectural Decisions to Remember
1. Dynamic context merges INTO current user message, not prepended as separate message
2. `cron_jobs` table defined at H2 time (in sessions.db schema), not H4 — avoids migration later
3. `AgentFactory` lives in `wiring.py` — thin helper to build AgentLoop with correct deps
4. `config_api.py` is a NEW file (not an existing one to modify)
5. Batch runner is a standalone CLI script (`scripts/batch_runner.py`), not in FastAPI

### Next: Execute H1 (CCAGENT_HOME) — lowest risk, pure path resolution, no logic changes

---

## Session: 2026-04-16 (Deepdive audit + Gap-Closure Phase 1)

### Context Restored
- Read prior planning files; reconciled stale task_plan.md (which still had H1–H6 pending) with the truth from `docs/deepdive-audit-2026-04-16.md` (5.5/6 Hermes phases shipped)
- Audit identified gaps: H3b orphan (no parallel dispatch), SemanticCompactor orphan, broken `.mcp.json`, slash command stub that sent `/help` as chat, dead `ToolCallsPanel.tsx`, missing v4 P24/P27, v2 spec drift

### Phase 1 — Cleanup (complete)
- Deleted `frontend/src/components/right-panel/ToolCallsPanel.tsx` (dead — superseded by `TerminalPanel`)
- Fixed `.mcp.json` MCP server path (`mcp-server/dist/index.js` → `mcp/dist/index.js`)
- Refactored slash commands to client-side dispatch:
  - `frontend/src/lib/store.ts`: added `clearActiveConversation`
  - `frontend/src/components/chat/ChatInput.tsx`: imports `useCommandRegistry`; `pickSlashCommand` switches on `cmd.id` and invokes `openHelp / clearActiveConversation / createConversation / setActiveSection`
  - Removed `backend.slash.execute` from `frontend/src/lib/api-backend.ts` and the `POST /api/slash/execute` endpoint from `backend/app/api/slash_api.py`
- Test rewrites: `SlashMenu.test.tsx` (5 behavioral tests), `test_slash_api.py` (added `test_execute_endpoint_removed` 404 assertion), `api-backend.test.ts` (dropped slash.execute case)
- Verification: vitest 16/16 green, pytest 2/2 green, `tsc --noEmit` clean

### Next: Phase 2 — wire `SemanticCompactor` into `loop.py` (two-stage MicroCompact → SemanticCompact)

### Phase 2 — Wire SemanticCompactor (complete)
- `AgentLoop.__init__` extended with `semantic_compactor` + `context_token_budget`
- New `_maybe_semantic_compact()` helper runs as stage-2 after MicroCompact; emits `semantic_compact` SSE event in `run_stream`
- `wiring.get_semantic_compactor()` singleton wired into both `chat_api.py` AgentLoop construction sites
- Tests: 4 new cases in `test_loop_semantic_compaction.py`; pytest 21/21 green

### Phase 3 — Hermes H3b parallel-safe dispatch (complete)
- `loop.py`: `PARALLEL_SAFE_TOOLS` (7 read-only), `NEVER_PARALLEL_TOOLS` (8 mutators/recursive/sandbox), `_should_parallelize()` predicate, `_dispatch_calls()` ThreadPoolExecutor batcher (max 8 workers), `_emit_post_dispatch_events()` helper to keep serial+parallel SSE order identical
- `run_stream` parallel branch: emits all `tool_call` previews up front, then `tool_result` events in submission order (not completion order)
- Serial fallback intact for `delegate_subagent` / `write_working` / `execute_python` etc; `a2a_start` ordering preserved
- Tests: 11 new in `test_parallel_tools.py`; harness suite 156/156 green; semantic compaction 4/4 still green
- Deviation logged: `sandbox.run` is NEVER-parallel (shared session globals would race) vs Hermes spec which whitelisted it

### Phase 4 — v4 P24 inline-table synthesis (complete)
- `loop.py`: `_user_wants_inline_table()` regex predicate + `_response_has_table()` markdown detector + `_INLINE_TABLE_SYSTEM` prompt + `_build_inline_table_messages()` helper that pulls the last 3 tool-result payloads as the data source
- `AgentLoop._maybe_inject_inline_table()` re-synthesises only when `stop_reason ∈ {end_turn, max_steps}` AND user asked AND response lacks a table; never adopts a rewrite that still lacks a table; never crashes on provider errors
- `run_stream` emits new `inline_table` SSE event (`step`, `reason="user_requested_table_not_in_response"`) on injection
- Tests: 14 cases in `test_inline_table_injection.py`; harness suite 174/174 green
- No frontend changes required — `MessageBubble` already renders markdown tables

### Phase 5 — v4 P27 eval scores ledger (complete)
- `docs/eval_scores.md` created — running ledger seeded with two historical rows (2026-04-15 baseline + post-v3 fixes), with "How to add a row" workflow, "How to interpret a row" guidance, and a "Persistent failures to watch" subtable that already cites P24 as the fix for `L1 table_correctness`
- Cross-linked from existing eval docs and `log.md`
- Documentation-only (no code) — matches v4 P27 spec

### Phase 6 — v2 spec drift reconciliation (complete)
- Audited frontend tree: `components/skills/`, `components/agents/`, `components/prompts/`, `components/context/` directories were never created — planned subcomponents (`SkillDependencyGraph.tsx`, `AgentCard.tsx`, `PromptList.tsx`/`PromptDetail.tsx`, `LayerBreakdown.tsx`/`CompactionHistory.tsx`/`CompactionDiff.tsx`) are inlined inside `sections/<Area>Section.tsx`
- `components/right-panel/`: `VegaChart.tsx` and `ArtifactCard.tsx` not created (inlined in `ArtifactsPanel.tsx`); `DataTable.tsx` and `TerminalPanel.tsx` were extracted as planned
- `components/layout/`: `SectionRouter.tsx` not created (routing inlined in `App.tsx`); `IconRail.tsx` and `ContextBar.tsx` extracted as planned
- Edited `docs/progressive_plan_v2.md`: added "Spec Drift Note (2026-04-16)" callouts under Phases 7, 8, 9, 10, 11, 13 explaining the inline-collapse decision, and added a header note above the "Frontend New Files Summary" pointing future contributors to those callouts
- Documentation-only (no code) — closes audit recommendation #9

### Phase 7 — verify + cut v0.1.0 (in progress)
- Backend test suite green: `pytest app/harness/tests/ tests/ -q` → 579 passed, 10 skipped
- `docs/log.md` cut: prior `[Unreleased]` block renamed to `## [v0.1.0] - 2026-04-16` with release-note paragraph; fresh empty `[Unreleased]` header opened above
- Added Phase 5 + Phase 6 entries (`Eval scores ledger`, `v2 spec-drift notes`) to the v0.1.0 block

### Awaiting user confirmation
Working tree has 50+ modified files spanning Phases 1–6. Two durable state-changing steps remain to actually cut v0.1.0:
1. **Commit** the gap-closure work (one logical commit per phase, or one combined commit?)
2. **Tag** the resulting commit as `v0.1.0`

Both visible to other contributors / pushable; pausing here for user direction.
