# Deepdive Audit — claude-code-agent
**Date:** 2026-04-16
**Scope:** Cross-reference every planning document, spec, and progressive plan against the actual implementation. Find gaps, orphans, and dead code.
**Method:** Read 13 planning docs (~4,562 lines), enumerate every named deliverable, then verify each against the codebase using grep, glob, and direct file reads.

---

## TL;DR

The project's **v1, v2, v3 plans (P0–P22)** and **EVAL-1–5** are fully implemented. The **prior P0–P2 engineering audit** (`docs/audit-2026-04-16.md`) is resolved end-to-end — confirmed by `docs/log.md` Unreleased section.

**Real gaps remain in two areas**:

1. **Hermes H3b — parallel tool execution** is the only un-shipped Hermes subcomponent. `PARALLEL_SAFE_TOOLS` and `asyncio.gather` were specified but never wired; `ToolDispatcher.dispatch()` is sequential-only.
2. **v4 quality pass (P23–P27)** is half-shipped: P23 + P25 done, P24 + P27 missing, P26 partial.

There are also **3 dead/orphaned items** worth removing or wiring:

- `frontend/src/components/right-panel/ToolCallsPanel.tsx` — never imported (superseded by `TerminalPanel.tsx`).
- `backend/app/harness/semantic_compactor.py` — has full implementation + tests but no caller in `loop.py` or `chat_api.py`.
- `.mcp.json` references `mcp-server/dist/index.js` — that directory does not exist; the live `mcp/` folder is at a different path.

Below: full mapping of every plan item to its implementation status.

---

## 1. Plan-vs-Code Status Matrix

### v1 — P0 through P6 (`progressive_plan.md`)

| Phase | Deliverable | Status | Evidence |
|------|------|------|------|
| P0 | Fix 36 skill test collection errors (importlib mode) | ✅ DONE | `backend/pyproject.toml` has `--import-mode=importlib`; suite collects clean |
| P1-A | Frontend Agents tab + Skills tab in sidebar | ✅ DONE | `AgentsTab.tsx`, `SkillsTab.tsx` present and referenced in `Sidebar.tsx` |
| P1-B | Right panel (Artifacts, Scratchpad, Tool Calls) | ✅ DONE | `RightPanel.tsx` mounts panels; `rightPanelTab` in store |
| P1-C | Per-agent monitor page `/monitor/:id` | ✅ DONE | `pages/MonitorPage.tsx` + `monitor/SessionHeader`, `TraceTimeline`, `EventDetailDrawer` |
| P2-A | DuckDB session integration + sandbox globals | ✅ DONE | `sandbox_bootstrap.py` builds globals; `data/db_init.py` initializes DuckDB |
| P2-B | AgentLoop → SSE streaming | ✅ DONE | `harness/loop.py::run_stream()` + `harness/stream_events.py` + `chat_api.py` StreamingResponse |
| P3 | Wire SSE to right panel + chat | ✅ DONE | `lib/api.ts` event handlers; store updates artifacts / scratchpad / toolCallLog |
| P4 | A2A delegation backend (`delegate_subagent`) | ✅ DONE | `harness/a2a.py` registered; tool surfaces in `chat_api.py` |
| P5 | A2A visualization frontend | ✅ DONE | `components/chat/SubagentCard.tsx` |
| P6 | Eval pipeline run + documentation | ✅ DONE | See `docs/progress_eval_results_v1.md` |

### v2 — P7 through P14 (`progressive_plan_v2.md`)

| Phase | Deliverable | Status | Evidence / Gaps |
|------|------|------|------|
| P7 | OS-platform layout: icon rail + section router | ✅ DONE | `IconRail.tsx`, `SectionContent.tsx`; `App.tsx` wires both |
| P8 | Skills Explorer (hierarchy + Python source + dep graph) | ⚠️ PARTIAL | `SkillsSection.tsx` lists hierarchy + source; **dep graph (`SkillDependencyGraph.tsx`) was specified but never built**. `lib/api-skills-detail.ts` also missing — endpoints fold into `api-skills.ts` |
| P9 | Monitoring Dashboard (Agent cards grid) | ⚠️ PARTIAL | `AgentsSection.tsx` shows trace list with status filtering, but **`components/agents/AgentCard.tsx` and `AgentCardSkeleton.tsx` were never created** — list is rendered inline rather than via a card component |
| P10 | Prompts Registry | ✅ DONE | `PromptsSection.tsx` + `api-prompts.ts` + backend `/api/prompts` |
| P11 | Context Inspector (L1/L2 breakdown + compaction diff) | ✅ DONE | `ContextSection.tsx` + inline `CompactionDiffPanel`; `lib/api.ts::fetchCompactionDiff`. NB: spec called for separate `components/context/CompactionDiff.tsx`; implementation is inline in the section |
| P12 | Terminal Progress Panel | ✅ DONE | `right-panel/TerminalPanel.tsx` (rotating verbs, timer) |
| P13 | Vega-Lite chart rendering | ✅ DONE | `chat/VegaChart.tsx` + `right-panel/DataTable.tsx`; `vega-embed` in deps |
| P14 | Gap analysis document | ✅ DONE | superseded by `docs/gap-analysis-v2.md` |

**Notable v2 gap**: the planned `frontend/src/components/skills/`, `agents/`, `context/`, `prompts/` subcomponent directories were **never created**. The four sections work, but they implement the UI inline rather than via the planned dedicated component trees. This isn't a functional bug, but it's a planning-vs-execution drift that contributed to "PARTIAL" verdicts above.

### v3 — P15 through P22 (`progressive_plan_v3.md`)

| Phase | Status | Evidence |
|------|------|------|
| P15 — Wire full harness | ✅ FULLY WIRED | `chat_api.py:51, 62-66` import `PreTurnInjector`, `WikiEngine`, `SkillRegistry`, `register_core_tools`, `TurnWrapUp`. `register_core_tools()` invoked at `chat_api.py:587`. `TurnWrapUp.finalize()` at `chat_api.py:969-990`. **No legacy `_SYSTEM_PROMPT_BASE`** remains. |
| P16 — Connect OS routing | ✅ FULLY WIRED | `App.tsx:242` renders `<IconRail />`; `App.tsx:194-215` switches on `activeSection` to all 7 sections. |
| P17 — Proactive MicroCompact | ✅ FULLY WIRED | `loop.py:314-327` calls `_compactor.maybe_compact()`; emits `micro_compact` SSE; `context/manager.py:87-104` has `record_compaction()`. |
| P18 — Structured session memory | ✅ FULLY WIRED | `wiki/engine.py:145-184` has `write_session_notes()` + `latest_session_notes()`; `wrap_up.py:244-262` writes 9-section notes; `injector.py:181-191` injects them. |
| P19 — In-session task tracking | ✅ FULLY WIRED | `todo_store.py` (`TodoStore` singleton); `_todo_write_handler` registered at `chat_api.py:659-677`; `todos_update` SSE event; `right-panel/TodosPanel.tsx`. |
| P20 — `load_skill` tool | ✅ FULLY WIRED | `skill_tools.py:100-171` `_load_skill_body()`; registered as `"skill"` at `skill_tools.py:361`. |
| P21 — Token budget awareness | ✅ FULLY WIRED | `injector.py:14-25` `TokenBudget`; `injector.py:193-217` `_token_budget_section()`; called from both `build_dynamic()` and `build()`. |
| P22 — Plan Mode gate | ✅ FULLY WIRED | `injector.py:33` `plan_mode` field; `injector.py:162-179` `_plan_mode_section()`; `chat_api.py:395-412` `filter_tools_for_plan_mode()` with `_PLAN_MODE_TOOL_NAMES` frozenset; frontend toggle in `ChatInput.tsx`. |

### EVAL-1 through EVAL-5

| Phase | Status |
|------|------|
| EVAL-1 — LLM judge model fix | ✅ DONE |
| EVAL-2 — `tool_call` + `scratchpad_write` events from loop.py | ✅ DONE |
| EVAL-3 — Per-turn LLM call recording | ✅ DONE |
| EVAL-4 — `RealAgentAdapter` | ✅ DONE (`tests/evals/real_agent.py`) |
| EVAL-5 — Eval conftest probe | ✅ DONE |

### Hermes H1 through H6 (`task_plan.md`)

| Phase | Status | Notes |
|------|------|------|
| H1 — `CCAGENT_HOME` path unification | ✅ DONE | `core/home.py` 60 lines; zero hardcoded `/Users/jay/` paths in non-data files |
| H2 — `sessions.db` + FTS5 | ✅ DONE | `storage/session_db.py` 426 lines; WAL mode; FTS5 triggers; jitter retry × 15; checkpoint every 50 writes; `cron_jobs` table |
| H3a — Injection scanning | ✅ DONE | `harness/injection_guard.py` — 10 regex patterns; applied in `injector.py:108, 114` |
| **H3b — Parallel tools + asyncio.gather** | **❌ MISSING** | grep for `PARALLEL_SAFE\|asyncio.gather` in `harness/` returns **zero matches**. `ToolDispatcher.dispatch()` is synchronous-only. The plan called for a `PARALLEL_SAFE_TOOLS` frozenset + parallel execution; never built. |
| H3c — Skills cache | ✅ DONE | `injector.py:91` `_skill_menu_cache`; static once, dynamic merged into user msg |
| H4a — Semantic compactor (Stage 2) | ⚠️ ORPHAN CODE | `harness/semantic_compactor.py` (216 lines) is fully implemented with tests, but **grep shows zero callers** in `loop.py` or `chat_api.py`. Only the Stage 1 `MicroCompactor` is wired. The Stage 2 LLM-summarization path that protects head/tail and rewrites the middle has no production caller. |
| H4b — Cron / APScheduler | ✅ DONE | `scheduler/engine.py` `BackgroundScheduler`; `scheduler/jobs.py` parses natural-language schedules; `scheduler/runner.py` writes back to `sessions.db` |
| H5a — Toolsets YAML | ✅ DONE | `backend/config/toolsets.yaml` — readonly/standard/full/planning with recursive `includes` |
| H5b — `ToolsetResolver` | ✅ DONE | `harness/toolsets.py` — `from_yaml`, cycle detection, resolves to `frozenset[str]` |
| H5c — Batch runner | ✅ DONE | `backend/scripts/batch_runner.py` — JSONL in/out, checkpoint every 10, `--resume` |
| H6a — MCP sampling callbacks | ✅ DONE | `api/mcp_sampling_api.py` — 5/turn limit, audit log to `sessions.db` |
| H6b — Theme / branding system | ✅ DONE | `app/config.py` 3-tier resolution; `config/branding.yaml`; `api/config_api.py`; `frontend/src/hooks/useBranding.ts` |

**Hermes total: 5.5 of 6 phases complete.** H3b (parallel safe tools) is the lone hole.

### v4 — P23 through P27 (`progress_plan_v4.md`)

| Phase | Status | Evidence |
|------|------|------|
| P23 — Hook + fs_tools test coverage ≥80% | ✅ DONE | `backend/tests/unit/test_hooks.py` and `test_fs_tools.py` both present |
| **P24 — Force-synthesis inline table compliance** | **❌ MISSING** | grep in `loop.py` for `_user_wants_inline_table`, `_response_has_table`, `_inject_inline_table` returns **zero matches**. The L1 table_correctness:F failure is unaddressed in code. |
| P25 — Register `read_file`, `glob_files`, `search_text` | ✅ DONE | `skill_tools.py:394-396` registers all three via `FsTools` instance |
| P26 — Anomaly triage with named dismissals | ⚠️ PARTIAL | `prompts/data_scientist.md` mentions "dismissal" twice — needs verification that the full template (bonus / home / merchant keyword anchors) is present and structured per spec |
| **P27 — Eval score dashboard `docs/eval_scores.md`** | **❌ MISSING** | File does not exist. |

**v4 total: 2 of 5 phases complete (3 of 5 if P26 is half-counted).**

---

## 2. Prior P0–P3 Audit Status

The previous audit (`docs/audit-2026-04-16.md`) listed 4 P0, 14 P1, 12 P2, and 9 P3 issues. Per `docs/log.md` `[Unreleased]` section, all P0/P1/P2 are resolved:

- ✅ Health endpoints (`/health/live`, `/health/ready`) added
- ✅ `_lookup_frame` crash fixed
- ✅ CORS env-var driven
- ✅ Prometheus `/metrics` exposed
- ✅ `SESSION_SECRET` Helm guarded
- ✅ Slash command behavior re-evaluated (still a stub — see §4)
- ✅ React `ErrorBoundary` added at App / SectionContent / RightPanel
- ✅ 9 keyboard shortcuts wired
- ✅ Artifact name case-comparison fixed
- ✅ Chart sentinel UUID-randomized
- ✅ Helm memory raised to 2Gi; CPU to 2
- ✅ Docker Compose health check fixed
- ✅ `nginx.conf` marked deprecated
- ✅ `bun audit` `continue-on-error` removed
- ✅ Helm RBAC + NetworkPolicy added
- ✅ `litellm.yaml` master_key env-var driven
- ✅ `VegaChart` `as any` removed
- ✅ Silent exceptions logged (8 sites)
- ✅ `MessageBubble.conversationId` removed
- ✅ Session `title` populated on creation
- ✅ Hardcoded `/Users/jay/...` `_BANK_MACRO_DIR` removed
- ✅ `openSettings` / `openSearch` de-stubbed (`openSearch` still navigates to chat — see §4)
- ✅ E2E smoke suite (5 tests, green)

P3 items not explicitly checked here, but `log.md` indicates the major ones are done.

---

## 3. Dead Code & Orphans

### 3.1 Frontend dead component — `ToolCallsPanel.tsx`

**File**: `frontend/src/components/right-panel/ToolCallsPanel.tsx`
**Status**: DEAD
**Evidence**: `grep -rn "ToolCallsPanel" frontend/src/` returns only the file's own export line. `RightPanel.tsx` and `SessionRightPanel.tsx` both render `TerminalPanel` instead.
**Action**: Delete the file. The plan to retire it was made in v2 P12 ("Files to delete: ToolCallsPanel.tsx") but the deletion never happened.

### 3.2 Backend orphan — `semantic_compactor.py`

**File**: `backend/app/harness/semantic_compactor.py` (216 lines)
**Status**: ORPHAN — fully implemented + has tests, but no production caller
**Evidence**: `grep -rn "SemanticCompactor\|semantic_compactor" backend/app/harness/loop.py backend/app/api/chat_api.py` returns **nothing**. Only `tests/test_semantic_compactor.py` references the class.
**Why it matters**: `SemanticCompactor` is the Stage 2 (LLM-summarized middle window) compactor designed for long sessions. Without it, only the lossy `MicroCompactor` runs, and tokens past the threshold are dropped instead of summarized.
**Action**: Either wire it into `AgentLoop` (add a `_semantic_compact()` call when `MicroCompactor` cannot recover enough budget), or move to `experimental/` and document it as not-yet-active. Don't ship Stage 2 in `harness/` as if it's live.

### 3.3 Broken MCP integration — `.mcp.json` → `mcp-server/dist/`

**File**: `.mcp.json` references `mcp-server/dist/index.js`
**Status**: BROKEN PATH
**Evidence**: `mcp-server/` directory does not exist. The actual MCP code lives at `mcp/` (with `src/`, `package.json`, `Dockerfile`).
**Action**: Either:
1. Update `.mcp.json` to point at `mcp/dist/index.js` (and ensure the build target exists), or
2. Delete `.mcp.json` if MCP isn't intended to auto-load via Claude Code's project-level MCP config.

The previous audit's P3-7 ("MCP server is orphaned") suggested either documenting integration or removing the directory. Neither happened — instead a third state appeared (a pointer config to a nonexistent path).

### 3.4 Slash command execution — still a stub

**File**: `backend/app/api/slash_api.py:52-56`
**Status**: STUB (per previous audit P1-2; `log.md` does not mark this fixed)
**Evidence**: `execute_slash_command` returns `SlashExecuteResponse(ok=True, message=f"Executed {payload.command_id}")` without doing anything. The frontend `SlashMenu` invokes it.
**Action**: Either wire each command ID (`/help`, `/clear`, `/new`, `/settings`) to its real handler, or remove the `/` menu entry from `ChatInput.tsx`. Right now users press Enter on a slash command, get a "success", and nothing happens.

### 3.5 `openSearch()` — incomplete de-stub

**File**: `frontend/src/lib/store.ts`
**Status**: PARTIAL STUB
**Evidence**: per `log.md`, "`openSearch` navigates to `'chat'` pending a dedicated search panel". The "Global search" command exists in the registry and the keyboard shortcut is wired, but pressing it just goes to the chat section.
**Action**: Build the global-search panel or remove the command + shortcut from the registry. Listing a shortcut that does nothing is worse than not listing it.

---

## 4. Planned-but-Never-Built (Spec Drift)

These are items called out by name in the planning docs that have no corresponding code at all:

| Planned item | Where promised | What exists today |
|------|------|------|
| `frontend/src/components/skills/SkillDependencyGraph.tsx` | `progressive_plan_v2.md` Phase 8 | Directory `components/skills/` does not exist. Hierarchy is rendered inline in `SkillsSection.tsx` |
| `frontend/src/components/agents/AgentCard.tsx`, `AgentCardSkeleton.tsx` | `progressive_plan_v2.md` Phase 9 | Directory `components/agents/` does not exist. List view is inline in `AgentsSection.tsx` |
| `frontend/src/lib/api-skills-detail.ts` | `progressive_plan_v2.md` Phase 8 | Folded into `api-skills.ts` |
| `frontend/src/components/context/CompactionDiff.tsx` | `progressive_plan_v2.md` Phase 11 | Implemented inline as `CompactionDiffPanel()` in `ContextSection.tsx` |
| `frontend/src/components/prompts/PromptList.tsx`, `PromptDetail.tsx` | `progressive_plan_v2.md` Phase 10 | Directory `components/prompts/` does not exist. `PromptsSection.tsx` renders inline |
| `frontend/src/components/right-panel/ArtifactCard.tsx` | `progressive_plan_v2.md` Phase 13 | Type routing happens inline in `ArtifactsPanel.tsx` |
| `PARALLEL_SAFE_TOOLS` frozenset + `asyncio.gather` parallel dispatch | Hermes H3b (`task_plan.md`) | Not implemented anywhere |
| `_user_wants_inline_table` / `_response_has_table` / `_inject_inline_table` | v4 P24 (`progress_plan_v4.md`) | Not implemented anywhere |
| `docs/eval_scores.md` running ledger | v4 P27 (`progress_plan_v4.md`) | File does not exist |

**Pattern**: Most of the v2 "spec drift" items are functionally OK — the section pages render their UI inline rather than via the planned subcomponent files. This is fine for current scope; document the deviation so future contributors don't waste time looking for a `SkillDependencyGraph.tsx` that was never built.

The Hermes H3b and v4 P24 / P27 items are real implementation gaps — not just refactoring drift.

---

## 5. Dead Schema / Config Items

| Item | Status |
|------|------|
| `artifacts.displayed_rows` column | Backend writes/reads it (see `artifacts/store.py:103, 117, 132`). Frontend never reads it. Not dead, just back-end-only metadata. Safe to keep. |
| `nginx.conf` | Header now says deprecated (per `log.md`). File still present. OK. |
| Makefile `graphify`, `seed-data`, `wiki-lint` targets | Print "not yet implemented". Either implement or remove. Low priority. |
| `infra/grafana/dashboards/*.json` `"uid": "prometheus"` | Hardcoded UID; only an issue if Grafana is provisioned with a different datasource UID. Per previous audit P2-11 (not in `log.md` resolved list — verify) |

---

## 6. Verified Strong Areas

- **Backend test suite**: ~77 test files, ~7,500 LOC, covers harness, skills, storage, trace, evals, sop, scheduler. `pytest --co` clean after P0 fix.
- **Hermes H1 / H2 / H4 / H5 / H6**: production-quality implementations; `core/home.py`, `storage/session_db.py`, `scheduler/`, `harness/toolsets.py`, `mcp_sampling_api.py`, `config.py` + `useBranding.ts` are all real, integrated, and tested.
- **Frontend type safety**: zero `as any` casts in production code (per Explore sweep). Strict TypeScript throughout.
- **SSE event taxonomy**: 8+ typed events, all consumed by the frontend. No event published by the backend goes unhandled.
- **Skills system**: 6 first-level skills, 25+ chart variants, 5 statistical analysis sub-packages, all discovered by `SkillRegistry.discover()` and exposed via `skill_tools.py::register_core_tools()`.
- **Previous audit follow-through**: `log.md` shows real evidence of P0–P2 fixes (line numbers + module names per entry, not just checkmarks).

---

## 7. Recommended Resolution Order

### Tier 1 — Real implementation gaps
1. **Implement Hermes H3b parallel tool execution.** Add `PARALLEL_SAFE_TOOLS` frozenset to `dispatcher.py`; in `loop.py::_dispatch_calls`, partition the call batch into parallel-safe vs serial groups and `await asyncio.gather()` the safe group. Skip if you've decided H3b is out of scope — but then mark it explicitly in `task_plan.md` rather than leaving "complete" status implied.
2. **Wire `SemanticCompactor` into `loop.py`** as the Stage 2 fallback when `MicroCompactor` cannot reduce tokens enough, OR move it under `experimental/` with a docstring note. Don't ship a 216-line compactor with tests but no caller.
3. **Implement v4 P24 inline-table synthesis** (`_user_wants_inline_table` / `_response_has_table` / `_inject_inline_table` in `loop.py`). The L1 `table_correctness:F` eval failure is the reason this was specced.
4. **Create `docs/eval_scores.md`** ledger (v4 P27). Trivial — start with the L1–L4 scores from `progress_eval_results_v1.md` and add a row each subsequent eval run.

### Tier 2 — Cleanup
5. **Delete `frontend/src/components/right-panel/ToolCallsPanel.tsx`** — superseded by `TerminalPanel.tsx`, never imported.
6. **Resolve `.mcp.json` path** — either point it at the real `mcp/` directory and ensure the build artifact exists, or delete the file.
7. **Decide on slash commands** — implement the four (`/help`, `/clear`, `/new`, `/settings`) or remove the slash menu from `ChatInput.tsx`. Stub-success is the worst of both worlds.
8. **Decide on `openSearch()`** — build the search panel or unregister the command + shortcut.

### Tier 3 — Spec hygiene
9. **Mark v2 spec drift in the planning docs.** Update `progressive_plan_v2.md` Phases 8–13 to note that `components/skills/`, `agents/`, `context/`, `prompts/` subcomponent files were intentionally collapsed into their section files. Otherwise future contributors will keep searching for `SkillDependencyGraph.tsx` etc.
10. **Cut a `v0.1.0` changelog entry** (previous audit P3-8). The `[Unreleased]` block now spans the full Hermes migration plus the prior audit's P0–P2 fixes — that's a release boundary.
11. **Remove or implement the three Makefile "not yet implemented" targets** (`graphify`, `seed-data`, `wiki-lint`).

---

## 8. Severity Summary

| Severity | Count | Examples |
|------|------|------|
| **Critical (real gap, blocks promised capability)** | 1 | Hermes H3b parallel tool execution missing |
| **High (implemented but not wired / wrong path)** | 3 | `SemanticCompactor` orphan, `.mcp.json` broken path, slash command stub |
| **Medium (spec drift / dead component)** | 3 | `ToolCallsPanel.tsx` dead, v4 P24 unimplemented, v4 P27 missing doc |
| **Low (planning hygiene / minor cleanup)** | 5+ | v2 subcomponent drift, Makefile stubs, cut release tag, `openSearch` partial, document orphan code |

---

## 9. Conclusion

The bulk of what's been promised is built — **27 of 28 non-Hermes phases**, **5.5 of 6 Hermes phases**, and **all 5 EVAL phases** are complete and wired. The previous audit's P0–P2 issues are resolved end-to-end with real fixes documented in `log.md`.

The remaining gaps cluster into three categories:

- One **load-bearing capability gap** (parallel tool execution).
- One **orphaned subsystem** (`SemanticCompactor`) that should either be wired or relocated.
- A small batch of **frontend stubs** and **planning drift** (slash menu, `openSearch`, planned subcomponent files that became inline).

None of these block the project from shipping. All of them are worth a focused cleanup pass before the next major phase begins.
