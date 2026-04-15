# task_plan.md — claude-code-agent

**Created:** 2026-04-14  
**Source plan v1:** docs/progressive_plan.md (P0–P6 complete)  
**Source plan v2:** docs/progressive_plan_v2.md (P7–P14 — new)  
**Status:** v2 planning — ready to execute

---

## Goal
Bring claude-code-agent to its full target state per docs/progressive_plan.md:
fix test infrastructure, wire frontend tabs, right panel, streaming, A2A, and evals.

---

## Phase Status

### v1 Phases (complete)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P0 | Fix 36 skill test collection errors | **complete** |
| P1-A | Frontend: Agents tab + Skills tab | **complete** |
| P1-B | Frontend: Right panel (artifacts, scratchpad, tool calls) | **complete** |
| P1-C | Frontend: Per-agent monitoring page `/monitor/:id` | **complete** |
| P2-A | Backend: DuckDB session integration + sandbox globals | **complete** |
| P2-B | Backend: AgentLoop → SSE streaming | **complete** |
| P3 | Frontend: Wire SSE stream to right panel + chat | **complete** |
| P4 | Backend: A2A delegation (`delegate_subagent`) | **complete** |
| P5 | Frontend: A2A visualization | **complete** |
| P6 | Eval: run all 5 levels, document results | **complete** |

### v2 Phases (see docs/progressive_plan_v2.md)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P7 | OS-platform layout: icon rail + section router | **PARTIAL** — components built, App.tsx not updated |
| P8 | Skills Explorer: hierarchy + Python source + dep graph | **PARTIAL** — section + backend endpoints exist |
| P9 | Monitoring Dashboard: agent cards grid, live status | **MOSTLY DONE** |
| P10 | Prompts Registry: all prompts with layer/token metadata | **PARTIAL** |
| P11 | Context Inspector: L1/L2 breakdown + compaction diff | **MOSTLY DONE** |
| P12 | Terminal Progress Panel (Analytical-chatbot quality) | **PARTIAL** — TerminalPanel.tsx exists |
| P13 | Chart/Artifact rendering (Vega-Lite embed) | **PARTIAL** — ArtifactsPanel exists, VegaChart unclear |
| P14 | Gap analysis document vs Analytical-agent + CC-main | **DONE** (gap-analysis-v2.md supersedes) |

### v3 Phases (new — see docs/progressive_plan_v3.md)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P15 | **CRITICAL**: Wire full harness to chat_api.py | **pending** |
| P16 | Connect OS platform routing in App.tsx | **pending** |
| P17 | Proactive MicroCompact in agent loop | **pending** |
| P18 | Structured session memory (cross-session continuity) | **pending** |
| P19 | In-session task tracking | **pending** |
| P20 | Full SKILL.md loading (load_skill tool) | **pending** |
| P21 | Token budget awareness in system prompt | **pending** |
| P22 | Plan Mode gate | **pending** |

---

## P0 Fix Plan

**Root cause 1 (35 errors): `ModuleNotFoundError: No module named 'tests.test_*'`**

`app/skills/<name>/` has no `__init__.py`, but `tests/` subdirs do have `__init__.py`.
pytest prepend mode prepends `app/skills/<name>/` to sys.path, then tries to import
`tests.test_X` as a top-level package → fails.

**Fix:** Add `addopts = "--import-mode=importlib"` to `[tool.pytest.ini_options]`
in `backend/pyproject.toml`. importlib mode doesn't manipulate sys.path.

**Root cause 2 (1 error): `ValueError: Plugin already registered` for data_profiler**

`backend/conftest.py` registers `app.skills.data_profiler.tests.fixtures.conftest`
via `pytest_plugins`. But pytest also auto-discovers `conftest.py` when traversing
`app/skills/data_profiler/tests/fixtures/` → registered twice.

**Fix:** Remove `app.skills.data_profiler.tests.fixtures.conftest` from
`pytest_plugins` in `backend/conftest.py`. pytest auto-discovers conftest.py files
within testpaths, so fixtures will still be available to data_profiler tests.

**Files to change:**
- `backend/pyproject.toml` — add `addopts = "--import-mode=importlib"`
- `backend/conftest.py` — remove duplicate data_profiler fixtures plugin

---

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| — | — | — |
