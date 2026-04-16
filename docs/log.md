# Changelog

All notable changes to **claude-code-agent** are recorded here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning is by milestone (agent capability tiers) rather than strict SemVer — each milestone produces a merge candidate against `main`.

## How to update this file

**Every main update must land an entry here — no exception.** A "main update" is anything one of:

- A feature commit (`feat:`) that touches user-visible behavior or adds a capability
- A breaking change to a public interface (skill signature, tool registration, API schema, config schema)
- A migration, rename, or removal that affects existing callers
- A security, correctness, or data-loss fix on a critical path

Policy:

1. Add the entry under `[Unreleased]` in the section that matches the change (Added / Changed / Fixed / Removed / Security).
2. Use past tense, one line, ≤120 chars. Link the short commit SHA(s).
3. Reference the affected module in parens: `harness/`, `skills/<name>/`, `frontend/`, `mcp/`, `infra/`.
4. When cutting a milestone, rename `[Unreleased]` to the milestone tag with an ISO date, and open a fresh `[Unreleased]` header above it.
5. Pure refactors, test-only changes, and doc-only commits do NOT need an entry unless they change observable behavior.

Entry shape:

```
- Short imperative past-tense summary. (`module/`) — `abc1234`
```

---

## [Unreleased]

### Added

- **`statistical_gotchas` level-1 skill**: moved 14-entry gotcha catalog from always-injected system prompt to an on-demand skill. Saves ~250 tokens per turn; agent loads it explicitly when needed. (`skills/statistical_gotchas/`) — prompt cleanup
- **Session file auto-cleanup**: `WikiEngine.write_session_notes` now prunes session files older than 3 days automatically, preventing unbounded accumulation in `knowledge/wiki/sessions/`. (`wiki/engine.py`)
- **`log.md` 100 MB cap**: `WikiEngine.append_log` trims the oldest entries when the log exceeds 100 MB, preserving the header and newest lines. (`wiki/engine.py`)
- **`_SingleToolResult` dataclass**: new internal return type from `AgentLoop._dispatch_single_call` — carries all per-tool data (`status`, `tool_message`, `artifact_ids`, `scratchpad_update`, `todo_update`, a2a fields, `dispatch_ms`) so streaming events can be emitted without re-inspecting state. (`harness/loop.py`)
- **`_get_cached_preamble(registry)`**: module-level preamble cache in `sandbox_bootstrap` — static import lines generated once per registry instance instead of on every sandbox execution. (`harness/sandbox_bootstrap.py`)

### Changed

- **`PreTurnInjector._static()` cached**: base prompt (`data_scientist.md`) is read from disk once per process lifetime instead of on every turn. (`harness/injector.py`)
- **`PreTurnInjector._skill_menu()` cached**: rendered skill-menu string computed once and reused — `list_top_level()` no longer called on every turn. (`harness/injector.py`)
- **`_trim_log_to_size` O(n) rewrite**: replaced `while body: body.pop(0)` (O(n²)) with a single forward scan + slice (O(n)); also short-circuits when content already fits. (`wiki/engine.py`)
- **`cleanup_old_sessions` throttled**: `write_session_notes` only scans the sessions directory if ≥ 1 hour has elapsed since the last cleanup, avoiding redundant `glob` I/O on every turn. (`wiki/engine.py`)
- **`AgentLoop._dispatch_single_call` extracted**: ~90 lines of duplicated tool-dispatch + guardrail + state-update logic collapsed into a single shared method; `run()` and `run_stream()` both delegate to it, eliminating the maintenance risk of silent divergence. (`harness/loop.py`)
- **`_SYNTHESIS_SYSTEM` enforces three-section format**: the synthesis fallback prompt now mandates the Headline / Executive Summary / Evidence / Assumptions & Caveats structure so turns that trigger the silent-response fallback still produce output matching the expected frontend format. (`harness/loop.py`)
- **`build_sandbox_bootstrap` removed**: deprecated function deleted; callers use `build_duckdb_globals(registry=...)` directly. (`harness/sandbox_bootstrap.py`)
- **`data_scientist.md` prompt rewrite**: removed stale `# Statistical Gotchas` section, three duplicated rules (print-before-save, no-inline-numbers, always-write-final-response), vague filler line, and `append to log.md` step (auto-managed). 156 → 101 lines, every sentence executable. (`prompts/data_scientist.md`)
- **Empty wiki-header guard**: `## Operational State` is no longer injected when `working.md` / `index.md` contain only auto-generated headers or `_(no pages yet)_` placeholders — no content, no section. (`harness/injector.py`)
- **ContextManager "Tool Results" / "Assistant Turns" items now accumulate**: devtools inspector shows the full tool history per turn instead of only the last tool call. (`api/chat_api.py`)
- **`_SYSTEM_PROMPT` eager-build removed**: the module-level constant that triggered a full singleton init (skill-tree walk, wiki reads) at import time has been removed. `prompts_api` now calls `_build_system_prompt()` directly. (`api/chat_api.py`, `api/prompts_api.py`)
- **`GotchaIndex` removed from `PreTurnInjector` and `wiring.py`**: no longer needed as an injector dependency after gotchas became a skill. (`harness/wiring.py`, `harness/injector.py`)

- **`save_artifact` sandbox function**: rewrote from disk-writer LLM tool to a marker-emitting Python function. Agent calls `save_artifact(df, 'Title')` directly in sandbox — handles DataFrames (`table-json`), Altair charts (`vega-lite`), dicts/lists (`json`), and plain text. Emits `__SAVED_ARTIFACT__…__END_SAVED_ARTIFACT__` markers parsed by `_execute_python`. Returns a confirmation string the model reads. (`harness/sandbox_bootstrap.py`, `api/chat_api.py`)
- **`data_scientist.md` persona rewrite**: new identity + audience framing, explicit Working Loop, print-then-save discipline for DataFrames, three-section Final Response Format (headline → executive summary → evidence + caveats), non-negotiables as hard list. Designed for non-technical audience reads. (`prompts/data_scientist.md`)
- **`data_profiler` SKILL.md**: added full 21-entry risk taxonomy table with typical severity per kind. (`skills/data_profiler/SKILL.md`)

### Added (continued)

- **Progressive Skill Exposure**: skill system restructured from flat catalog to hierarchical tree. `SkillRegistry` discovers skills recursively and maintains `_roots` (Level-1 for system prompt) and `_index` (flat lookup). System prompt now shows only Level-1 skills with `[N sub-skills]` annotations; loading a skill auto-appends its sub-skill catalog (~65% per-turn token reduction). New `SkillNode` dataclass carries depth, parent, children, and breadcrumb. Hub skills (`statistical_analysis`, `charting`, `reporting`) collapse leaf skills under a shared entry point. (`skills/registry.py`, `harness/injector.py`, `harness/skill_tools.py`) — `9331ae8`…`0443799`
- **`skill-new` sub-skill scaffolding**: `make skill-new name=X parent=Y` creates nested skill with hub `__init__.py`; `type=reference` variant skips `pkg/` and prefixes description with `[Reference]`. (`Makefile`, `docs/skill-creation.md`) — `ffd36b1`
- **Dynamic sandbox bootstrap imports** generated from registry tree via `SkillRegistry.generate_bootstrap_imports()` — new skills auto-appear in sandbox without manual edits to `_SKILL_IMPORTS`. (`harness/sandbox_bootstrap.py`) — `4f521af`
- **Agent loop synthesis injection**: after completing tool calls, injects a synthesis prompt and strips tools so the model is forced to write a response. First-step `tool_choice=required` ensures the agent always starts by calling a tool. (`harness/loop.py`) — `e438b30`
- **`tool_choice` field** on `CompletionRequest`; `OpenRouterClient` propagates it and gracefully retries without it on 400/422 (some models reject it). (`harness/clients/`) — `e438b30`
- **H1 CCAGENT_HOME**: single `$CCAGENT_HOME` env var (default `~/.ccagent`) unifies all runtime data paths; `home.py` exports 7 derived path helpers (`sessions_db_path`, `artifacts_db_path`, etc.); `wiring.py` singletons use lazy accessors so no directories are created at import time. (`core/home.py`, `harness/wiring.py`) — H1
- **H2 SessionDB**: SQLite + FTS5 full-text search replaces YAML-only trace storage; WAL mode, jitter-retry on lock, WAL checkpoint every 50 writes; `TraceRecorder` dual-writes to YAML (backward compat) and DB; `GET /api/sessions` list/search/detail API added; `session_search` tool available to the agent; `scripts/migrate_traces_to_db.py` for one-time backfill. (`storage/session_db.py`, `trace/recorder.py`, `api/session_search_api.py`) — H2
- **H3 Injection guard**: `injection_guard.py` scans wiki / session-notes content against 10 regex patterns before injection; on match, the block is silently skipped and a warning is logged. (`harness/injection_guard.py`, `harness/injector.py`) — H3
- **H3 Cache-preservation split**: `PreTurnInjector` gains `build_static()` (base prompt + skills + gotchas, called once per session) and `build_dynamic()` (wiki state + profile + budget, merged into user message each turn); `AgentLoop.run()` / `run_stream()` accept optional `injector` + `injector_inputs` to drive the split automatically. (`harness/injector.py`, `harness/loop.py`) — H3
- **H3 Parallel tool dispatch**: `PARALLEL_SAFE_TOOLS` and `NEVER_PARALLEL_TOOLS` frozensets define the policy; `_should_parallelize()` heuristic; when all calls in a batch are safe, `AgentLoop` dispatches them via `ThreadPoolExecutor`. (`harness/loop.py`) — H3
- **H4 Semantic compactor**: LLM-based stage-2 compaction triggers at 80 % of `model_context_limit` after `MicroCompactor` runs; protects head (first 2 turns) and tail (last 3 turns); emits `semantic_compact` SSE event with token deltas and summary preview. (`harness/semantic_compactor.py`, `harness/loop.py`) — H4
- **H5 Toolset composition**: `ToolsetResolver` loads named toolset groups from `config/toolsets.yaml` with recursive `includes` flattening and cycle detection; 4 built-in toolsets (`readonly`, `standard`, `full`, `planning`); wired as wiring singleton; `SubagentDispatcher.dispatch()` gains `toolset` param (default `"readonly"`); `filter_tools_for_plan_mode()` reads from resolver (falls back to hardcoded set). (`harness/toolsets.py`, `config/toolsets.yaml`, `harness/a2a.py`, `api/chat_api.py`) — H5
- **H5 Batch runner**: `scripts/batch_runner.py` CLI runs a JSONL prompt file through the agent, writes per-result JSONL output, checkpoints every 10 completions, sessions stored with `source="batch"`. (`scripts/batch_runner.py`) — H5
- **H6 MCP sampling API**: `POST /api/mcp/sample` endpoint with per-session rate limiting (5 calls/turn); `TurnState` gains `sampling_calls` counter and `record_sampling_call()` with `SamplingRateLimitError`; module-level `_session_sampling_counts` dict (thread-safe, ephemeral) enforces limit at the API layer. (`api/mcp_sampling_api.py`, `harness/turn_state.py`) — H6
- **H6 Branding / theme system**: `BrandingConfig` Pydantic model with 3-tier YAML resolution (`$CCAGENT_HOME/config/branding.yaml` → repo-default `backend/config/branding.yaml` → hardcoded defaults); `GET /api/config/branding` endpoint; `PreTurnInjector` accepts optional `agent_persona` string prepended before base system prompt; wiring singleton passes persona from branding config. (`config.py`, `api/config_api.py`, `harness/injector.py`, `harness/wiring.py`, `config/branding.yaml`) — H6
- **H6 Frontend branding hook**: `useBranding()` hook with module-level cache + listener pattern (zero re-fetch across components); `prefetchBranding()` called at module scope in `App.tsx`; `document.title`, Sidebar header, and ChatWindow empty state wired to `ui_title` from branding API. (`frontend/src/hooks/useBranding.ts`, `App.tsx`, `Sidebar.tsx`, `ChatWindow.tsx`) — H6
- **H4 APScheduler cron engine**: in-process `BackgroundScheduler` for recurring agent jobs; `CronEngine` + `CronJobRecord` + `parse_schedule` (natural-language aliases + regex "every N hours/minutes"); jobs persisted in `sessions.db`; job runs create sessions with `source="cron"`; REST API at `GET/POST /api/scheduler/jobs`, `GET/PUT/DELETE /api/scheduler/jobs/{id}`, `POST /api/scheduler/jobs/{id}/run`; engine starts/stops via FastAPI lifespan. (`scheduler/`, `api/scheduler_api.py`, `main.py`, `storage/session_db.py`) — H4

### Fixed

- **Statistical analysis functions missing from sandbox**: `generate_bootstrap_imports()` only generated `pkg/`-layout imports, silently dropping all stat skills (`correlate`, `compare`, `validate`, `characterize`, `decompose`, `find_anomalies`, `find_changepoints`, `lag_correlate`, `fit`). Added `skill_path` to `SkillNode` and extended the generator to detect direct-layout skills (no `pkg/`, but has `__init__.py` with `__all__`). Hub skills without `__all__` are correctly skipped. (`skills/base.py`, `skills/registry.py`, `harness/sandbox_bootstrap.py`)
- **`altair_charts` SKILL.md stub**: 14 of 20 chart templates were undocumented ("ships in Plan 4"). Rewrote with all 20 templates organized by category with signatures and use cases. (`skills/charting/altair_charts/SKILL.md`)
- **Wrong import paths in stat skill SKILL.md files**: `from app.skills.X import Y` examples would fail at runtime — these are pre-injected sandbox globals; no import needed. Fixed in correlation, time_series, stat_validate, group_compare, distribution_fit. (`skills/statistical_analysis/*/SKILL.md`)
- `skills_api` `/manifest` and `/{name}/detail` crashed with `AttributeError` after `level` was removed from `SkillMetadata` — replaced with `node.depth`. (`api/skills_api.py`) — `b845412`
- Nested skill `skill_dir` resolution used flat path `skills_root/name` — fixed to use `node.package_path.parent` so sub-skills are found at any depth. (`api/skills_api.py`) — `b845412`
- Sandbox bootstrap multi-line import strings caused `IndentationError` when the skills-only filter stripped continuation lines — collapsed to single-line imports. (`harness/sandbox_bootstrap.py`) — `2a0125e`

---

## [M1 — Agent Capability Upgrade] - 2026-04-15

Shipped on branch `feat/v2-os-platform`. Goal: ship a data-scientist-grade agent with a skills runtime, composition skills (plan → analysis → report/dashboard), unified charting theme, a guardrailed LangGraph harness, and the long-session primitives (MicroCompact, session memory, task tracking, token budget, Plan Mode, OpenRouter 429 fallback).

### Added

- Composition skill **`dashboard_builder`**: contracts, KPI tile with direction semantics, layout span resolver, a2ui JSON emitter, `build()` orchestrator (standalone HTML + a2ui). (`skills/dashboard_builder/`) — `da2a4e3`, `f1b6de7`, `30a585a`, `d2a0f37`, `d1fd8ab`, `b2f37b6`
- Composition skill **`report_builder`**: ReportSpec contracts, Jinja2 templates + editorial.css, Markdown/HTML renderers, weasyprint PDF renderer, `build()` orchestrator. (`skills/report_builder/`) — `dd95a5e`, `8b586e5`, `3c4a7fc`, `2908413`, `0385b67`, `8517e50`
- Composition skill **`analysis_plan`**: step catalogue + `plan()` orchestrator that writes `wiki/working.md`. (`skills/analysis_plan/`) — `7ad69bd`, `65cce66`, `5105dd3`
- Tool registrations for `report.build`, `analysis_plan.plan`, `dashboard.build` in the harness dispatcher. (`harness/`) — `6f631a9`, `9291023`
- End-to-end composition smoke test: plan → chart → report → dashboard. (`harness/tests/`) — `025fec7`
- Harness runtime: `ToolDispatcher`, `SandboxExecutor`, `PreTurnInjector`, `AgentLoop`, `TurnWrapUp`, guardrails (pre/post/end-of-turn), model router with Ollama + Anthropic clients, warmup + cache. (`harness/`) — `91817e4`, `0fa043f`, `0b27e63`, `be1177e`, `38faec1`, `7dadd35`, `6e7dc12`, `050415a`, `a6e9318`, `cca53cb`, `e896f01`
- Sandbox bootstrap script builder that preloads pandas, Altair theme, and all skills. (`harness/sandbox_bootstrap.py`) — `cd6b07c`
- Altair chart template library (20 templates) with unified theme and surface smoke test. (`skills/altair_charts/`) — `61f9b65`, `c259715`, `1d9c772`, `a97af7b`, `2db42c2`, `f5c77ef`, `cf506d0`, `eae39e7`, `ac54515`, `dee1f0a`, `f9289fa`, `b134c1d`, `8e509b7`, `87000b6`, `9409c2c`
- Data-scientist system prompt. (`backend/app/prompts/`) — `2c69dd4`
- BE1 API routers: conversations, settings, files, slash commands. (`backend/app/api/`) — `a8ff766`
- Frontend 3-panel shell with DevTools-in-sidebar and message rendering. (`frontend/`) — `85b856f`
- Frontend P3 command palette, keyboard shortcuts, and a11y pass. (`frontend/`) — `1e56bdb`
- Frontend P4-P7: typed `api-backend` client; sidebar History / Settings / Files tabs wired to BE1; chat input slash menu with `/api/slash` commands; chat turns persisted to `/api/conversations` fire-and-forget. (`frontend/`) — `45831ff`
- **P21** `TokenBudget` section in the system prompt — surfaces `max_tokens`, `compact_threshold`, `char_budget`, and `keep_recent_tool_results` so the model knows the budget alongside the `MicroCompactor`'s enforcement signal. (`harness/injector.py`) — `23c77be`
- **P22** Plan Mode two-layer gate — backend filters execute_python / save_artifact / promote_finding / delegate_subagent from the tool menu and rewrites the system prompt when `plan_mode=true`; frontend surfaces a terminal-aesthetic switch in `<ChatInput/>` with an orange accent badge and threads the flag through `streamChatMessage`. Store flag persists across reloads. (`backend/app/api/chat_api.py`, `backend/app/harness/injector.py`, `frontend/src/components/chat/ChatInput.tsx`, `frontend/src/lib/store.ts`, `frontend/src/lib/api.ts`) — `23c77be`
- **P23** OpenRouter 429 fallback chain — `FallbackModelClient` wraps a primary model with an ordered list from `OPENROUTER_FALLBACK_MODELS`; triggers only on `RateLimitError` so non-rate-limit failures (bad API key, network, malformed payload) surface immediately instead of silently burning fallback quota. Structural `ModelClient` surface preserved so existing trace/logging call sites are unchanged. (`harness/clients/fallback_client.py`, `harness/clients/base.py`, `harness/clients/openrouter_client.py`, `api/chat_api.py`) — `23c77be`

### Fixed

- `/api/chat/stream` now wraps its SSE generator in `TraceSession`, so every streamed turn writes a YAML trace under `TRACE_DIR`. Previously only the non-streaming `/api/chat` endpoint produced traces, which made DevTools' Timeline and Prompt sub-tabs 404 on `/api/trace/traces/{id}/...` for every streamed session (the common case). Regression pinned by integration test. (`backend/app/api/chat_api.py`, `backend/tests/integration/test_stream_trace.py`) — `23c77be`
- Append-turn lost-update race — per-conversation `threading.Lock` serializes read-modify-write on `/api/conversations/{id}/turns`. (`backend/app/api/conversations_api.py`) — `e889f1b`
- Cold-start conversation now persists to the backend so the happy-path first message isn't dropped by the 404 guard on `/turns`. (`frontend/src/components/chat/ChatLayout.tsx`) — `e889f1b`
- Slash menu no longer re-fires on second Enter — picking a command locks the menu closed until the input is edited, so Enter submits the message instead of re-executing. (`frontend/src/components/chat/ChatInput.tsx`) — `5b0cb00`

### Fixed

- Harness composition tool lambdas now accept a positional dict (dispatcher calls `handler(dict(call.arguments))`); previously raised `TypeError` at runtime on `report.build`, `analysis_plan.plan`, and `dashboard.build`. Regression test added. (`harness/skill_tools.py`, `harness/tests/test_composition_tools.py`) — `ea0b227`
- Sandbox bootstrap now imports composition callables from their submodules directly — `from pkg import build` was binding the submodule, not the function. (`harness/sandbox_bootstrap.py`) — `ea0b227`
- `report_builder/pkg/__init__.py` imports `build` submodule so the name in `__all__` actually resolves. (`skills/report_builder/`) — `ea0b227`
- `report.build` registration binds the function rather than the submodule. (`harness/skill_tools.py`) — `5d83aee`
- `analysis_plan/pkg/__init__.py` no longer shadows the `plan` submodule. (`skills/analysis_plan/`) — `707bc67`
- `distribution_fit` fit accepts `t` tying `norm` on normal data — BIC gate enforces parsimony. (`skills/distribution_fit/`) — `a332bbb`

### Changed

- `/api/files/read` omits binary content by default — the UI only renders size + encoding for binary blobs, so shipping up to ~13 MB of base64 was pure waste. Callers that need the bytes can opt in with `?include_binary_content=1`. (`backend/app/api/files_api.py`) — `010493a`
- Ollama client `warmup()` replaces silent `except Exception: pass` with `logger.warning(..., exc_info=True)` so infra failures surface. (`harness/clients/ollama_client.py`) — `ea0b227`

### Removed

- Empty `app/skills/tests/__init__.py` that caused pytest namespace-package collisions. (`skills/`) — `32f682c`

---

<!-- Add new milestone sections above this marker, newest first -->
