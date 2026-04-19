# Task Plan — DS-Agent Shell Foundation (step 1 of 5) ✅ SHIPPED

**Source spec:** `docs/superpowers/specs/2026-04-18-shell-foundation-design.md`
**Canonical plan:** `docs/superpowers/plans/2026-04-18-shell-foundation.md`
**Started:** 2026-04-18
**Owner:** main Claude session

## Goal

Replace the current Cockpit shell with the handoff's four-pane `AppShell` (IconRail + ThreadList + Conversation + Dock) at pixel fidelity, pivot theme default to light (both first-class), port full token system with oklch palette + Inter/JBM fonts, add ui-store + auto-collapse + keyboard resize, and land a green build.

## Phases

### Phase 1 — Tokens & fonts
- [x] Spec approved
- [x] Write full `tokens.css` (light + dark, keyframes, component layer)
- [x] Drop Inter and JBM SemiBold woff2 into `public/fonts/`
- [x] Update `globals.css` (import tokens.css first, add @font-face, alias legacy vars)
- [x] Update `tailwind.config.ts` (darkMode selector, colors, fonts, keyframes, animations)

### Phase 2 — UI state plumbing
- [x] Build `lib/ui-store.ts` with zod schema + Zustand persist
- [x] Build `hooks/useViewportWidth.ts` (rAF-throttled)
- [x] Build `hooks/useAutoCollapse.ts`
- [x] Unit tests for all three

### Phase 3 — Shell components
- [x] Build `components/shell/Resizer.tsx` (drag + keyboard + ARIA)
- [x] Build `components/shell/ThreadList.tsx`
- [x] Build `components/shell/Dock.tsx`
- [x] Build `components/shell/AppShell.tsx`
- [x] `shell.css` for per-component details
- [x] Component tests

### Phase 4 — IconRail rebuild
- [x] Rewrite `components/layout/IconRail.tsx` to handoff spec
- [x] Add `components/layout/icons/Sidebar.tsx` (bespoke SVG pair for step 2 consumption)
- [x] Flyout tooltip sub-component with label + kbd hint
- [x] Wire new section routes (graph/digest/ingest) in store + App.tsx

### Phase 5 — Theme default flip
- [x] `ThemeProvider.tsx` flips default to light + uses `[data-theme="dark"]` attribute
- [x] Migrate legacy `theme` localStorage key to `ds:theme`
- [x] Ensure components reading `--color-*` vars still render via alias block

### Phase 6 — Legacy retirement
- [x] Delete `Cockpit.tsx`, `TopHUD.tsx`, `RightRail.tsx`, `cockpit.css`, `SessionDropdown.tsx`
- [x] Trim `lib/right-rail-store.ts` to `traceTab` (kept for `TraceRail` consumer)
- [x] Update `App.tsx` to render `AppShell` instead of Cockpit-based layout
- [x] Update/delete related tests

### Phase 7 — Shortcuts
- [x] Add `TOGGLE_DOCK` (mod+j) and nine `OPEN_SECTION_*` (mod+shift+1..9)
- [x] Remove `CYCLE_RAIL` (mod+\)
- [x] Update `shortcuts.ts` CMD registry

### Phase 8 — Verification
- [x] `pnpm typecheck` green (`tsc --noEmit` clean)
- [ ] `pnpm lint` — eslint not installed in this workspace; deferred
- [x] `pnpm test` green (41 files / 179 tests)
- [x] Playwright smoke + shell-foundation specs land; DevTools-label and `.light`-class assertions updated to match new shell
- [ ] Visual-regression baselines at 320/768/1100/1440 × light/dark — deferred until CI baseline-image review flow exists
- [x] `pnpm build` succeeds; main `index` bundle is 2.2MB / 670KB gz (pre-existing shiki+cytoscape+wasm weight; not regressed by shell work). Follow-up: route-level code-split for shiki/mermaid/cytoscape to hit the <150KB landing target.
- [x] Update `docs/log.md` [Unreleased] with shell-foundation entry

## Guardrails / decisions (from brainstorm)

- App-wide new shell — every section renders inside the Conversation pane
- Graph/Digest/Ingest promoted to full sections (replace RightRail "summon" modes)
- Full Tailwind-extend styling (not BEM-first)
- Light default (`:root`), dark opt-in (`[data-theme="dark"]`)
- Inter self-hosted + JBM + OS serif (Charter/Iowan-Old-Style)
- 11 rail items + theme toggle + settings
- Persistence key: `ds:ui` (with zod schema v=1); legacy `ds:threadW`/`ds:dockW` read on migrate

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|

## Files created / modified so far

| Path | Action |
|------|--------|
| `docs/superpowers/specs/2026-04-18-shell-foundation-design.md` | created |
| `task_plan.md` | created |
| `findings.md` | created |
| `progress.md` | created |

---

# Task Plan — DS-Agent Chat Surface (step 2 of 5)

**Source spec:** `docs/superpowers/specs/2026-04-18-chat-surface-design.md`
**Canonical plan:** `docs/superpowers/plans/2026-04-18-chat-surface.md`
**Started:** 2026-04-18
**Owner:** main Claude session

## Phases
- [ ] Phase 1 — Store additions
- [ ] Phase 2 — Composer extraction
- [ ] Phase 3 — Composer parity surfaces
- [ ] Phase 4 — Message parity surfaces
- [ ] Phase 5 — Header toolbar
- [ ] Phase 6 — ChatPane integration + retirement
- [ ] Phase 7 — Shortcuts + verification

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|

## Files created / modified so far

| Path | Action |
|------|--------|

