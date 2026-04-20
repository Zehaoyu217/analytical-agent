# Pipeline Bar Implementation Plan

**Goal:** Three-button execution footer on the Knowledge page (Ingest / Digest / Maintain), backed by new `/api/sb/pipeline/status` + `/api/sb/maintain/run` routes and a shared `.state/pipeline.json` ledger.

**Architecture:** Per-phase endpoints write their outcome to a single state file; status endpoint aggregates. Frontend store polls after each action + on mount. Drawers open contextually on completion only.

**Tech Stack:** FastAPI + Pydantic (backend), Zustand + Vitest + React (frontend), existing design tokens.

---

## Phase 1 — Backend state helpers

### Task 1: Pipeline state reader/writer
**Files:**
- Create `backend/app/tools/sb_pipeline_state.py`
- Test `backend/tests/app/tools/test_sb_pipeline_state.py`

Implementation: a single module with `read_state(cfg)` and `write_phase(cfg, phase, result)` functions backed by JSON. Never raises on write failure (returns bool). File path: `cfg.sb_dir / ".state" / "pipeline.json"`.

### Task 2: Maintain-run wrapper
**Files:**
- Modify `backend/app/tools/sb_pipeline_state.py`
- Test `backend/tests/app/tools/test_sb_pipeline_state.py`

Add `run_maintain(cfg)` that constructs `MaintainRunner(cfg)`, calls `.run(build_digest=False)`, converts `MaintainReport` to a JSON-safe dict, writes to state, returns the dict.

## Phase 2 — Backend routes

### Task 3: New pipeline router
**Files:**
- Create `backend/app/api/sb_pipeline.py`
- Test `backend/tests/api/test_sb_pipeline.py`

Two routes:
- `GET /api/sb/pipeline/status` → reads state file via helper, returns `{ok: true, ingest, digest, maintain}`
- `POST /api/sb/maintain/run` → invokes `run_maintain(cfg)`, returns `{ok: true, result: {...}}`; on exception returns 500 with `{ok: false, error}`.

Both gated by `_require_enabled()` mirroring `sb_api.py`.

### Task 4: Wire router into app
**Files:**
- Modify `backend/app/main.py` (or wherever FastAPI app is constructed)

Locate the existing `sb_api.router` registration and add `sb_pipeline.router` alongside.

### Task 5: Hook state writes into existing ingest + digest routes
**Files:**
- Modify `backend/app/api/sb_api.py`
- Test `backend/tests/api/test_sb_api.py` (extend existing)

On success in `sb_ingest_route` / `sb_ingest_upload`: call `write_phase(cfg, "ingest", {"sources_added": 1, "source_id": ...})`.

On success in `digest_build`: compute pending count, call `write_phase(cfg, "digest", {"entries": N, "emitted": bool, "pending": M})`.

Failures in state-write are swallowed — must not break the underlying route.

## Phase 3 — Frontend store

### Task 6: Pipeline store
**Files:**
- Create `frontend/src/lib/pipeline-store.ts`
- Test `frontend/src/lib/__tests__/pipeline-store.test.ts`

Zustand store per spec. Actions `refreshStatus`, `runIngest(payload)`, `runDigest`, `runMaintain`. Each action sets `running` → fetches → sets `done`/`error` → schedules a 2s revert to `idle`. Uses `fetch` against existing endpoints.

## Phase 4 — Frontend components

### Task 7: PipelineAction component
**Files:**
- Create `frontend/src/components/pipeline/PipelineAction.tsx`
- Test `frontend/src/components/pipeline/__tests__/PipelineAction.test.tsx`

Single button component. Props: `phase`, `label`, `icon`, `status` (from store), `onClick`, `kbd`. Renders icon + label + status line. Reads `aria-busy`, disabled state from `status.status === 'running'`.

### Task 8: PipelineBar container
**Files:**
- Create `frontend/src/components/pipeline/PipelineBar.tsx`
- Test `frontend/src/components/pipeline/__tests__/PipelineBar.test.tsx`

Footer `<nav>` with three `PipelineAction` children. Pulls state from `pipeline-store`. Triggers `refreshStatus` on mount.

### Task 9: Wire Knowledge page
**Files:**
- Modify `frontend/src/sections/KnowledgeSurface.tsx`
- Modify `frontend/src/lib/surfaces-store.ts`

Remove Ingest + Digest from toolbar. Keep Graph toggle. Add `<PipelineBar />` as a footer below the wiki tree+article grid. On ingest click, toggle `ingest` drawer (existing panel). On digest completion with `entries > 0`, auto-open digest drawer.

### Task 10: Keyboard shortcuts
**Files:**
- Modify `frontend/src/lib/shortcuts.ts`

Register `g i`, `g d`, `g m` → corresponding pipeline-store action.

## Phase 5 — Verification

### Task 11: Backend tests pass
Run: `cd backend && .venv/bin/pytest tests/app/tools/test_sb_pipeline_state.py tests/api/test_sb_pipeline.py -v`

### Task 12: Frontend tests + build
Run: `cd frontend && pnpm test --run pipeline` and `pnpm tsc -b` and `pnpm build`

### Task 13: Manual smoke
Run `make dev`, navigate to Knowledge page, click each of the three buttons against the running backend; verify state transitions + drawer behavior.

### Task 14: Changelog
Append entry under `[Unreleased]` in `docs/log.md` summarizing the new pipeline surface.

---

## Notes on scope discipline

- Do **not** remove the existing `IngestPanel` / `DigestPanel` drawer components — they're re-used.
- Do **not** add SSE or auto-apply in this plan; they're deferred per spec.
- When `MaintainReport` has a field not documented in the spec, include it in the JSON response anyway (frontend only reads named fields).
- Keep per-file size under 200 lines; split if needed.
