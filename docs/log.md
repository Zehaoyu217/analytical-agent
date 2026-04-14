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

Milestone in progress: **M1 — Agent Capability Upgrade** (branch `feat/agent-capability-upgrade`).
Goal: ship a data-scientist-grade agent with a skills runtime, composition skills (plan → analysis → report/dashboard), unified charting theme, and a guardrailed LangGraph harness.

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

### Fixed

- Append-turn lost-update race — per-conversation `threading.Lock` serializes read-modify-write on `/api/conversations/{id}/turns`. (`backend/app/api/conversations_api.py`)
- Cold-start conversation now persists to the backend so the happy-path first message isn't dropped by the 404 guard on `/turns`. (`frontend/src/components/chat/ChatLayout.tsx`)

### Fixed

- Harness composition tool lambdas now accept a positional dict (dispatcher calls `handler(dict(call.arguments))`); previously raised `TypeError` at runtime on `report.build`, `analysis_plan.plan`, and `dashboard.build`. Regression test added. (`harness/skill_tools.py`, `harness/tests/test_composition_tools.py`) — `ea0b227`
- Sandbox bootstrap now imports composition callables from their submodules directly — `from pkg import build` was binding the submodule, not the function. (`harness/sandbox_bootstrap.py`) — `ea0b227`
- `report_builder/pkg/__init__.py` imports `build` submodule so the name in `__all__` actually resolves. (`skills/report_builder/`) — `ea0b227`
- `report.build` registration binds the function rather than the submodule. (`harness/skill_tools.py`) — `5d83aee`
- `analysis_plan/pkg/__init__.py` no longer shadows the `plan` submodule. (`skills/analysis_plan/`) — `707bc67`
- `distribution_fit` fit accepts `t` tying `norm` on normal data — BIC gate enforces parsimony. (`skills/distribution_fit/`) — `a332bbb`

### Changed

- Ollama client `warmup()` replaces silent `except Exception: pass` with `logger.warning(..., exc_info=True)` so infra failures surface. (`harness/clients/ollama_client.py`) — `ea0b227`

### Removed

- Empty `app/skills/tests/__init__.py` that caused pytest namespace-package collisions. (`skills/`) — `32f682c`

---

<!-- Add new milestone sections above this marker, newest first -->
