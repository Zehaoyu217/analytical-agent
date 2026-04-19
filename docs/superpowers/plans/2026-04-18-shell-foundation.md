# Implementation Plan — DS-Agent Shell Foundation

**Spec:** `docs/superpowers/specs/2026-04-18-shell-foundation-design.md`
**Working plan:** `task_plan.md` + `findings.md` + `progress.md` (project root)

This plan decomposes the approved spec into file-level work, ordered so each commit leaves the build green. TDD where practical: write the test, watch it fail, then make it pass.

## Conventions

- All new components use TypeScript with explicit props interfaces (no `React.FC`).
- Props interfaces live in the component file unless reused across files (then `lib/types/ui.ts`).
- All new components have a Vitest spec under `__tests__/<ComponentName>.test.tsx`.
- CSS: Tailwind utilities for layout; handoff semantic classes (`.surface`, `.kbd`, …) via `@layer components` in globals.css; per-component custom selectors go in `<component>/<name>.css` files if genuinely component-specific (avoid where possible).
- No `console.log` in shipped code. Use the `assert(condition, msg)` dev-only utility.
- File size limit: 800 lines; function limit: 50 lines; nesting: ≤4 levels.
- Commit cadence: one logical change per commit; message format `<type>(shell): <desc>`.

## Phase 1 — Tokens & Fonts

### 1.1 Drop Inter + JBM SemiBold fonts

**Files:**
- `frontend/public/fonts/Inter-Regular.woff2`
- `frontend/public/fonts/Inter-Medium.woff2`
- `frontend/public/fonts/Inter-SemiBold.woff2`
- `frontend/public/fonts/Inter-Bold.woff2`
- `frontend/public/fonts/JetBrainsMono-SemiBold.woff2`
- `frontend/public/fonts/LICENSE-Inter.txt` (OFL notice)
- `frontend/public/fonts/LICENSE-JetBrainsMono.txt` (OFL notice, if not already present)

**How:** Download from the official Inter (`rsms.me/inter`) and JetBrains Mono (`jetbrains.com/mono`) releases. Latin + Latin-Extended subset each woff2 via `pyftsubset` or use pre-subset release.

**Verify:** Each file < 40KB gzipped. Total added font weight < 150KB over the wire.

### 1.2 Write `frontend/src/styles/tokens.css`

**Content:** Full port of `design_handoff_ds_agent/tokens.css` with these edits:

1. `:root` holds the light values verbatim from handoff.
2. `html[data-theme="dark"]` holds dark overrides verbatim.
3. Density variants unchanged.
4. Legacy compat at file end:

   ```css
   :root {
     --color-bg-primary: var(--bg-0);
     --color-bg-secondary: var(--bg-1);
     --color-bg-elevated: var(--bg-2);
     --color-text-primary: var(--fg-0);
     --color-text-secondary: var(--fg-1);
     --color-text-muted: var(--fg-2);
     --color-accent: var(--acc);
     --color-accent-hover: color-mix(in oklab, var(--acc) 92%, black);
     --color-accent-active: color-mix(in oklab, var(--acc) 82%, black);
     --color-accent-foreground: var(--acc-fg);
     --color-border: var(--line-2);
     --color-border-hover: var(--line);
     --color-success: var(--ok);
     --color-warning: var(--warn);
     --color-error: var(--err);
     --color-info: var(--info);
     --color-success-bg: color-mix(in oklab, var(--ok) 12%, transparent);
     --color-warning-bg: color-mix(in oklab, var(--warn) 12%, transparent);
     --color-error-bg: color-mix(in oklab, var(--err) 12%, transparent);
     --color-info-bg: color-mix(in oklab, var(--info) 12%, transparent);
   }
   ```

5. Reduced-motion override block at file end:

   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 0.01ms !important;
       scroll-behavior: auto !important;
     }
   }
   ```

### 1.3 Update `frontend/src/styles/globals.css`

Changes:
1. Import `./tokens.css` at the top (before Tailwind directives) so custom properties exist during Tailwind's `@layer base` reset.
2. Replace the existing `@layer base :root { … hex tokens … }` block with a short stub (delete the block — legacy names are now aliased in tokens.css).
3. Add `@font-face` blocks for Inter 400/500/600/700 and JBM 400/500/600 with `font-display: swap` and `unicode-range: U+0000-007F, U+00A0-024F` (Latin + Latin-Extended).
4. Add the handoff's semantic classes under `@layer components`:
   - `.surface`, `.surface-raised`, `.mono`, `.serif`, `.label`, `.label-cap`, `.kbd`, `.dot`, `.btn`, `.btn-primary`, `.btn-ghost`, `.row-hover`, `.ants`, `.pulse`, `.pulse-ring`, `.caret`, `.draw-check`, `.scale-in`, `.fade-in`, `.slide-in-r`, `.shimmer`, `.stripe-ph`, `.focus-ring`.
5. Set body base style: `font-family: var(--font-sans); font-size: 13.5px; line-height: 1.5; letter-spacing: -0.003em; font-feature-settings: "cv11","ss01","ss03"; -webkit-font-smoothing: antialiased;`
6. Preload hint is added in `frontend/index.html` for `Inter-Regular.woff2`.

### 1.4 Update `frontend/index.html`

Add inside `<head>`:
```html
<link rel="preload" href="/fonts/Inter-Regular.woff2" as="font" type="font/woff2" crossorigin>
```

### 1.5 Extend `frontend/tailwind.config.ts`

1. Change `darkMode` to `['selector', '[data-theme="dark"]']`.
2. Extend `theme.extend.colors` with the DS tokens (additive; existing palettes stay):
   ```ts
   'bg-0': 'var(--bg-0)', 'bg-1': 'var(--bg-1)', 'bg-2': 'var(--bg-2)', 'bg-3': 'var(--bg-3)',
   'fg-0': 'var(--fg-0)', 'fg-1': 'var(--fg-1)', 'fg-2': 'var(--fg-2)', 'fg-3': 'var(--fg-3)',
   line: 'var(--line)', 'line-2': 'var(--line-2)',
   acc: 'var(--acc)', 'acc-fg': 'var(--acc-fg)', 'acc-dim': 'var(--acc-dim)', 'acc-line': 'var(--acc-line)',
   ok: 'var(--ok)', warn: 'var(--warn)', err: 'var(--err)', info: 'var(--info)',
   ```
3. Replace `fontFamily` with:
   ```ts
   sans: ['Inter', 'ui-sans-serif', '-apple-system', 'BlinkMacSystemFont', 'SF Pro Text', 'Helvetica Neue', 'sans-serif'],
   serif: ['Charter', 'Iowan Old Style', 'Palatino', 'ui-serif', 'serif'],
   mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
   ```
4. Extend `borderRadius` with `xs: 'var(--radius-xs)'`, `DEFAULT: 'var(--radius)'`, `lg: 'var(--radius-lg)'`, `xl: 'var(--radius-xl)'`.
5. Extend `transitionTimingFunction` with `'out-expo'`, `'out-2'`, `'in-out'`, `'spring'` from tokens.
6. Extend `transitionDuration` with `fast: '140ms', base: '220ms', slow: '360ms'`.
7. Extend `keyframes` with `march`, `pulse`, `pulseRing`, `drawCheck`, `scaleIn`, `slideInR`, `sheen` (fadeIn and shimmer already exist; keep but rename to match handoff semantics — or keep both, new keyframes are additive).
8. Extend `animation` with entries referencing the new keyframes (names listed in the spec).
9. Add `safelist` entries for `animate-march`, `animate-pulse-ring`, `animate-draw-check`, `animate-scale-in`, `animate-slide-in-r`, `animate-sheen` so they survive Tailwind purging when applied dynamically.

**Commit:** `feat(shell): port handoff tokens, Inter + JBM fonts, tailwind-extend`

## Phase 2 — UI state plumbing

### 2.1 Build `frontend/src/lib/ui-store.ts`

1. Zod schema:
   ```ts
   const UiPersistedSchema = z.object({
     v: z.literal(1).default(1),
     threadW: z.number().int().min(160).max(360).default(200),
     dockW: z.number().int().min(240).max(480).default(320),
     threadsOpen: z.boolean().default(true),
     dockOpen: z.boolean().default(true),
     dockTab: z.enum(['progress', 'context', 'artifacts']).default('progress'),
     density: z.enum(['compact', 'default', 'cozy']).default('default'),
   })
   ```
2. Transient (not persisted): `threadsOverridden: boolean`, `dockOverridden: boolean`.
3. Actions (listed in spec).
4. Zustand `persist` middleware with custom `storage`:
   - On `getItem('ds:ui')`, parse via `UiPersistedSchema.safeParse`; on failure return null (use defaults).
   - On first run, also read legacy `ds:threadW` / `ds:dockW` and fold into defaults.
5. `partialize` limits persistence to the schema'd fields.
6. Export the typed store hook plus named selectors.

### 2.2 Unit tests — `lib/__tests__/ui-store.test.ts`

- Default hydration returns schema defaults.
- Clamp on setThreadW below 160 returns 160.
- Clamp on setDockW above 480 returns 480.
- Toggle actions set override flags.
- Corrupt JSON in localStorage → defaults applied + no throw.
- Legacy key migration: `ds:threadW='220'` picked up on first load.

### 2.3 Build `frontend/src/hooks/useViewportWidth.ts`

- Returns `window.innerWidth` reactive to resize.
- rAF-throttled — only update React state once per frame during resize storms.
- Handles `resize` and `orientationchange` events.
- Unsubscribes on unmount.

### 2.4 Build `frontend/src/hooks/useAutoCollapse.ts`

Behavior:
- Reads `vw` from `useViewportWidth`.
- On `vw` crossing 1100 (either direction), calls `ui-store.resetThreadsOverride()` then `ui-store.setAutoThreads(vw >= 1100)`.
- Same at 900 for dock.
- Guards with a ref that stores the previous vw so we only trigger on the crossing, not on every update.
- Does NOT call auto-set if the user's override flag is true.

### 2.5 Tests

- `hooks/__tests__/useViewportWidth.test.tsx` — mounts, simulates `window.innerWidth = 500`, fires resize, asserts returned value updates; asserts cleanup on unmount.
- `hooks/__tests__/useAutoCollapse.test.tsx` — simulates vw transitions across boundaries; asserts store actions called.

**Commit:** `feat(shell): ui-store, viewport/auto-collapse hooks`

## Phase 3 — Shell components

### 3.1 `frontend/src/components/shell/Resizer.tsx`

- Props: `axis, min, max, value, onChange, ariaLabel, invert?`.
- Renders a 4px-thick div styled by axis (`cursor-col-resize` or `cursor-row-resize`).
- `pointerdown` captures pointer, registers `pointermove` and `pointerup` on window.
- Drag math: `delta = (e.clientX - startX) * (invert ? -1 : 1)`; `next = clamp(startValue + delta, min, max)`.
- Keyboard: `ArrowLeft`/`ArrowRight` ±10, `ArrowDown`/`ArrowUp` if axis=y, `Home`/`End` snap.
- ARIA: `role="separator"`, `aria-orientation`, `aria-valuenow/min/max`, `aria-label`.
- Focus ring via `.focus-ring` utility.

### 3.2 `frontend/src/components/shell/ThreadList.tsx`

- Header: `Chats` label (`.label-cap`), `+` button (imports existing `createConversationRemote`), close chevron (calls `toggleThreads`).
- Body: scroll container, section groups (Pinned, Today, This week, Older).
- Each section: collapsible? For step 1 — always expanded. Section header `.label-cap` with count (e.g., `TODAY · 4`).
- Each row: left gutter 10px, two-line item (title, preview), right timestamp. Active row `bg-acc-dim` + absolute 2px `acc` left border.
- Footer: archive button ghost-style, 40px tall.
- `ThreadList` reads `conversations` + `activeConversationId` + `setActiveConversation` from `useChatStore`.
- Right edge: `<Resizer axis="x" min={160} max={360} value={threadW} onChange={setThreadW} ariaLabel="Resize thread list" />`.

### 3.3 `frontend/src/components/shell/Dock.tsx`

- Tab bar: three tab buttons. Active tab has 2px `acc` bottom border + accent icon.
- Close chevron (`>`) at far right.
- Tab body switch:
  - `'progress'` → existing `<TraceRail />` wrapped in `.surface` container with scroll.
  - `'context'` → `<DockContextStub />` — an inline component returning `.stripe-ph` box with the handoff-styled placeholder text.
  - `'artifacts'` → `<DockArtifactsStub />` — 3-col grid of `.stripe-ph` boxes with captions.
- Left edge: `<Resizer axis="x" min={240} max={480} value={dockW} onChange={setDockW} invert ariaLabel="Resize dock" />`.

### 3.4 `frontend/src/components/shell/AppShell.tsx`

- Mounts `useAutoCollapse()` once at the top of the component.
- Layout: `flex h-dvh overflow-hidden bg-bg-0 text-fg-0`
- Children slot: the Conversation pane body.
- Conditionally renders ThreadList/Dock — only when `activeSection === 'chat'` AND `threadsOpen` / `dockOpen` are true.
- Renders IconRail always.

### 3.5 `frontend/src/components/shell/shell.css`

Only for things that can't be expressed cleanly in Tailwind utilities — e.g., custom scroll shadows, fine-grained border positioning if needed. Start empty; add only as required.

### 3.6 Tests — `components/shell/__tests__/*`

- `Resizer.test.tsx`: keyboard (`ArrowRight` → onChange called with `value + 10`); pointer drag (synthetic events); clamp at bounds; ARIA attrs correct.
- `ThreadList.test.tsx`: renders sections correctly; click row calls setActiveConversation; renders empty Pinned section hidden.
- `Dock.test.tsx`: tab switching; close button fires onClose.
- `AppShell.test.tsx`: renders without ThreadList/Dock when section != 'chat'.

**Commit:** `feat(shell): Resizer, ThreadList, Dock, AppShell`

## Phase 4 — IconRail rebuild

### 4.1 Bespoke sidebar icons

`frontend/src/components/layout/icons/Sidebar.tsx` — exports `SidebarIcon` and `SidebarOnIcon` (filled-left-pane variant). Both inline SVG, 18×18 viewBox, stroke 1.5 or fill.

### 4.2 Flyout tooltip

`frontend/src/components/layout/FlyoutTooltip.tsx` — small headless-ish component. Props: `label, hint?, side='right'`. Renders on hover + focus-visible, fades in 120ms. Handles focus trapping naturally (no trap needed — it's purely display).

### 4.3 Rewrite `IconRail.tsx`

- 52px wide, full-height, `bg-bg-1 border-r border-line-2`, 10px top padding.
- Define `SECTIONS` array with `{ id, icon, label, hint }` for 9 items; `BOTTOM` array for theme + settings.
- Render each as 36×36 focusable button wrapped in a positioning `<div>` so the 2px active-state left bar can be absolutely positioned.
- Active styling: `text-acc bg-acc-dim` + left bar (abs div, 2px × 22px, `bg-acc`, `rounded-r-full`).
- Hover: `bg-bg-2 text-fg-0`.
- Each item mounts a `<FlyoutTooltip label={label} hint={hint} />`.
- Theme toggle button: shows `Sun` when dark, `Moon` when light; clicks call `setTheme(theme === 'dark' ? 'light' : 'dark')`.
- Custom SVG icons: keep using Lucide where there's a clean match (`Network` for Graph, `ClipboardList` for Digest, `Download` for Ingest). Export `SidebarIcon`/`SidebarOnIcon` for later (chat header in step 2).

### 4.4 Update section union

`frontend/src/lib/store.ts` — extend `SectionId`: `'graph' | 'digest' | 'ingest'` added.
`App.tsx` — `SectionContent` adds three cases:
```tsx
case 'graph':   return <GraphPanel open onClose={noop} embedded={false} />
case 'digest':  return <DigestPanel open onClose={noop} embedded={false} />
case 'ingest':  return <IngestPanel open onClose={noop} embedded={false} />
```
Where `noop` is a safe placeholder — these new sections don't have a close affordance because they're full sections now. Review `GraphPanel`/`DigestPanel`/`IngestPanel` implementations to see whether they gracefully handle a no-op close; if not, relax the prop type (`onClose?: () => void`) in those components.

### 4.5 Tests

- `IconRail.test.tsx`: 11 section buttons + theme + settings = 13 buttons total. Click each sets activeSection. Theme toggle toggles. Active state reflects activeSection.
- `FlyoutTooltip.test.tsx`: appears on focus/hover; contains label + hint; proper ARIA.

**Commit:** `feat(shell): IconRail v2 with handoff visuals, flyout tooltips, section-expansion`

## Phase 5 — Theme default flip

### 5.1 Update `frontend/src/components/layout/ThemeProvider.tsx`

Change:
- Initial theme resolution order:
  1. Read `ds:theme` from localStorage.
  2. If absent, read legacy `theme` key; if present, migrate to `ds:theme` + remove legacy.
  3. If still absent, check `prefers-color-scheme` media query; default `light` if no preference.
- Apply via `document.documentElement.dataset.theme = 'dark'` (when dark) or delete (when light).
- **Remove** all use of the `.light` class path.
- `setTheme(theme)` writes to `ds:theme`.

### 5.2 Tests

- `ThemeProvider.test.tsx`: initial render without localStorage → theme='light', no data-theme attr; with `ds:theme='dark'` → data-theme='dark'; `setTheme('dark')` flips attr and writes storage.

### 5.3 Wire legacy key cleanup in `App.tsx`

On mount, run the migration once. `ThemeProvider` owns this — no App.tsx change required if it runs in `useEffect`.

**Commit:** `refactor(shell): theme default light, [data-theme] attribute, migrate legacy key`

## Phase 6 — Legacy retirement + App.tsx wiring

### 6.1 Replace Cockpit with AppShell in `App.tsx`

```tsx
return (
  <ErrorBoundary name="App">
    <ThemeProvider>
      <AnnouncerProvider>
        <CommandRegistryProvider>
          <SkipToContent />
          <ShortcutWiring />
          <AppShell>
            <ErrorBoundary name="SectionContent">
              <SectionContent />
            </ErrorBoundary>
          </AppShell>
          <CommandPalette />
          <GlobalSearchPanel />
          <ShortcutsHelp />
        </CommandRegistryProvider>
      </AnnouncerProvider>
    </ThemeProvider>
  </ErrorBoundary>
)
```

`SectionContent` stays the same switch, now returning `<ChatMain />` directly for the chat case (not wrapped in `<Cockpit/>`).

### 6.2 Delete files

```
frontend/src/components/cockpit/Cockpit.tsx
frontend/src/components/cockpit/TopHUD.tsx
frontend/src/components/cockpit/RightRail.tsx
frontend/src/components/cockpit/SessionDropdown.tsx
frontend/src/components/cockpit/cockpit.css
frontend/src/components/cockpit/__tests__/Cockpit.test.tsx   (if present)
frontend/src/components/cockpit/__tests__/TopHUD.test.tsx    (if present)
frontend/src/components/cockpit/__tests__/RightRail.test.tsx (if present)
frontend/src/components/cockpit/__tests__/SessionDropdown.test.tsx (if present)
frontend/src/lib/right-rail-store.ts
```

### 6.3 Remove remaining consumers

```bash
# Verify no stragglers
rg "from '@/components/cockpit/Cockpit'" frontend/src
rg "from '@/components/cockpit/TopHUD'" frontend/src
rg "from '@/components/cockpit/RightRail'" frontend/src
rg "right-rail-store" frontend/src
rg "useRightRailStore" frontend/src
```

Each match gets updated or deleted.

### 6.4 Update section switching to new shell

- Remove `mod+\` CYCLE_RAIL registration from `App.tsx` (dead code once RightRail is gone).
- `SectionContent` already handles each section's render — just ensure the new sections render.

**Commit:** `refactor(shell): retire Cockpit/TopHUD/RightRail, wire AppShell in App.tsx`

## Phase 7 — Shortcuts

### 7.1 Update `frontend/src/lib/shortcuts.ts`

Add to the `CMD` registry:
```ts
TOGGLE_DOCK: 'toggle-dock',
OPEN_SECTION_CHAT: 'open-section-chat',
OPEN_SECTION_AGENTS: 'open-section-agents',
OPEN_SECTION_SKILLS: 'open-section-skills',
OPEN_SECTION_PROMPTS: 'open-section-prompts',
OPEN_SECTION_CONTEXT: 'open-section-context',
OPEN_SECTION_HEALTH: 'open-section-health',
OPEN_SECTION_GRAPH: 'open-section-graph',
OPEN_SECTION_DIGEST: 'open-section-digest',
OPEN_SECTION_INGEST: 'open-section-ingest',
```

Remove `CYCLE_RAIL` entry and its command registration in `App.tsx`.

### 7.2 Register new commands in `ShortcutWiring`

Nine `OPEN_SECTION_*` commands each bound to `mod+shift+N` (1..9), action = `setActiveSection(sectionId)`. Plus `TOGGLE_DOCK` bound to `mod+j`, action = `ui-store.toggleDock`. Include `icon` and `category: 'Navigation'` so they appear in the command palette.

### 7.3 Tests

- `App.test.tsx` (lightweight smoke): mounts App, fires `mod+shift+2`, asserts `activeSection === 'agents'`. Uses existing test harness convention.

**Commit:** `feat(shell): add TOGGLE_DOCK + OPEN_SECTION_* shortcuts, drop CYCLE_RAIL`

## Phase 8 — Verification

### 8.1 Lint + typecheck

```bash
pnpm -C frontend lint
pnpm -C frontend typecheck
```

Resolve any strict-mode warnings surfaced by the new `SectionId` members (exhaustive switch statements will complain if they don't handle `graph|digest|ingest`).

### 8.2 Unit + integration

```bash
pnpm -C frontend test
```

### 8.3 Playwright visual regression

New file: `frontend/e2e-shell-foundation.cjs` — drives four breakpoints × two themes × three sections = 24 screenshots. Save screenshots into `frontend/e2e-shell-*.png`. Use the existing Playwright harness (`playwright.config.ts`).

Assertions:
- Screenshots match committed baselines (after the first run, commit baselines).
- No layout shift during font load (measure CLS).

### 8.4 Build budget

```bash
pnpm -C frontend build
```

Expected output: no chunk > 300KB gzipped. Landing chat route < 150KB gzipped. If regressed, identify the culprit and split.

### 8.5 Changelog

Append to `docs/log.md` under `[Unreleased] > changed`:

> - **shell:** rebuilt app shell to four-pane (IconRail + ThreadList + Conversation + Dock) matching DS-Agent handoff; theme default flipped to light with dark opt-in; summon modes promoted to sections.

**Commit:** `chore(shell): update changelog for foundation release`

## Cross-cutting checklist

- [ ] Every new file has a test file.
- [ ] No `console.log` / `console.error` in shipped code.
- [ ] All public APIs have explicit types.
- [ ] Zod is used for any external-input validation (localStorage JSON).
- [ ] No mutation (spread for all updates).
- [ ] All interactive elements reachable by keyboard.
- [ ] All interactive elements have `aria-label` or accessible text.
- [ ] `tailwind.config.ts` safelist includes any animation class applied dynamically.
- [ ] `docs/log.md` updated.
- [ ] `task_plan.md` phases marked complete.

## Risk mitigations (from spec)

- **FOUT on font load:** preload Inter-Regular; use `font-display: swap`; add `@font-face` with `size-adjust` / `ascent-override` calibrated to match Inter's metrics (final numbers determined empirically in phase 1).
- **Tailwind purge misses animation classes:** safelist entries added in phase 1.5.
- **Legacy `--color-*` alias drift:** smoke test in `__tests__/tokens.test.ts` that reads computed style of an element referencing `var(--color-accent)` after applying `[data-theme="dark"]` and asserts it matches `var(--acc)`.
- **Keyboard shortcut collision:** `mod+shift+N` is global; `mod+N` stays conversation-scoped — already divergent, no runtime collision.

## Completion definition

The plan is done when all eight phase commits land on `main`, all `task_plan.md` phases show `[x]`, `docs/log.md` entry is written, CI (if configured) is green, and a final demo at the four breakpoints in both themes visually matches the handoff HTML mock within ±2px per pane edge.
