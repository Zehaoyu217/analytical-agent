# DS-Agent Dock + Artifact Viewer — Design Spec (step 3 of 5)

**Status:** approved
**Started:** 2026-04-19
**Author:** main Claude session
**Source handoff:** `design_handoff_ds_agent/` (`progress.jsx`, `panels.jsx`, `shell.jsx`)
**Precedes:** writing-plans → implementation plan

## Goal

Turn the Dock (currently shell-scaffolded with a stubbed Context/Artifacts tab and a repurposed `TraceRail` Progress tab) into a real "trust surface." The user — an MLE / data scientist / quant — needs to see at a glance **what the agent is doing right now, what it knows, and what it has produced**. Step 3 lands three cohesive panels (Progress / Context / Artifacts), a full-viewport Artifact Viewer modal that renders all six artifact formats, and — as a deferrable final phase — a ⌘K Command Palette.

## Scope

### In scope
- Dock Progress panel (replaces `TraceRail`, step-card driven, per-step expandable Raw/Context/Timeline detail).
- Dock Context panel (per-conversation: budget bar, layer bars, loaded files, attached files, todos, scratchpad preview).
- Dock Artifacts panel (responsive tile grid + list toggle; tiles render lazy thumbnails per format).
- Artifact Viewer modal — full-viewport; renders all six formats (`vega-lite`, `mermaid`, `table-json`, `html`, `csv`, `text`). Keyboard nav (←/→/ESC/⌘C/⌘S), focus trap, copy/download/open-in-new.
- Data-model additions (derived `ProgressStep[]` selector + `ContextShape` on `Conversation`).
- One new backend stream event: `context_snapshot` (on `turn_start` + after each `micro_compact`).
- Command Palette — `⌘K` modal, deferrable final phase (may slip into step 4 without blocking the dock).
- Retire `TraceRail`; move its three modes into per-step expand-row detail.

### Out of scope
- Full sections (Activity, Knowledge, Memory, Skills, Context, Graph, Digest, Ingest) — land in later steps.
- Tweaks panel (experimental handoff surface).
- Backend refactors beyond the single `context_snapshot` event.
- Artifact history across conversations (viewer limited to current session).

## Design decisions (brainstorm outcomes)

1. **Scope = Dock + Viewer + Palette**, Palette deferrable as final phase.
2. **Progress data flow** = replace `TraceRail`; the three modes (Raw/Context/Timeline) collapse into per-step expand-row detail so Progress is the single "what is the agent doing" surface.
3. **Context data flow** = per-conversation current state, not per-trace history. Per-trace context remains accessible via Progress expand-row.
4. **Artifact format coverage** = all six formats, with heavy renderers (vega-lite, mermaid) dynamic-imported on first use; light renderers (table/csv/html/text) ship synchronously.
5. **Toggles and icons** = real lucide-react icons only. No emoji, no Unicode box symbols in shipped UI.

## Architecture

```
  ┌────────────────────────────────────────────────────────┐
  │                         Dock                           │
  │  ┌───────────┬───────────┬───────────┐                 │
  │  │ Progress  │  Context  │ Artifacts │ ←tab strip      │
  │  ├───────────┴───────────┴───────────┤                 │
  │  │                                   │                 │
  │  │  <DockProgress | DockContext |    │                 │
  │  │   DockArtifacts> by ui-store tab  │                 │
  │  │                                   │                 │
  │  └───────────────────────────────────┘                 │
  └────────────────────────────────────────────────────────┘

  Click artifact tile / pill → dispatches focusArtifact event
                                       │
                                       ▼
  ┌────────────────────────────────────────────────────────┐
  │  <ArtifactViewer> portal — full-viewport modal         │
  │    renderer switch on artifact.format                  │
  └────────────────────────────────────────────────────────┘

  ⌘K (palette phase) → <CommandPalette> portal — 560px modal
                        sources: CommandRegistry + conversations
```

### File layout

```
frontend/src/
├── components/
│   ├── dock/
│   │   ├── Dock.tsx                         (re-lives here, moved from shell/)
│   │   ├── DockProgress.tsx
│   │   ├── DockContext.tsx
│   │   ├── DockArtifacts.tsx
│   │   ├── progress/
│   │   │   ├── StepCard.tsx
│   │   │   ├── StatusDot.tsx
│   │   │   └── modes/
│   │   │       ├── RawMode.tsx              (moved from cockpit/trace/)
│   │   │       ├── ContextMode.tsx          (moved)
│   │   │       └── TimelineMode.tsx         (moved)
│   │   ├── context/
│   │   │   ├── ContextBudgetBar.tsx
│   │   │   ├── LayerBars.tsx
│   │   │   ├── LoadedFileChip.tsx
│   │   │   ├── AttachedFileList.tsx
│   │   │   ├── TodoList.tsx
│   │   │   └── ScratchpadPreview.tsx
│   │   └── artifacts/
│   │       ├── ArtifactTile.tsx
│   │       └── ArtifactContextMenu.tsx
│   ├── artifact/
│   │   ├── ArtifactViewer.tsx
│   │   └── renderers/
│   │       ├── VegaLiteRenderer.tsx         (lazy)
│   │       ├── MermaidRenderer.tsx          (lazy)
│   │       ├── TableRenderer.tsx
│   │       ├── CsvRenderer.tsx              (lazy papaparse)
│   │       ├── HtmlRenderer.tsx
│   │       └── TextRenderer.tsx
│   └── palette/                             (deferrable)
│       ├── CommandPalette.tsx
│       ├── CommandRow.tsx
│       └── CommandGroup.tsx
├── lib/
│   ├── selectors/
│   │   └── progressSteps.ts                 (derived selector)
│   ├── hooks/
│   │   ├── useFilteredCommands.ts           (palette)
│   │   └── useArtifactNav.ts                (viewer ←/→)
│   └── store.ts                             (+ContextShape + unloadFile)
└── routes/
    └── ArtifactPage.tsx                     (/artifact/:id — open-in-new target)
```

## Data model

### New frontend types (`frontend/src/lib/store.ts`)

```ts
export interface ProgressStep {
  id: string
  index: number
  title: string
  kind: 'tool' | 'reason' | 'compact' | 'a2a' | 'turn'
  status: 'queued' | 'running' | 'ok' | 'err'
  startedAt?: number
  finishedAt?: number
  thinkingPreview?: string
  toolCallIds: string[]
  artifactIds: string[]
  children?: ProgressStep[]
}

export interface ContextLayer {
  id: string
  label: string          // e.g. 'system', 'skills', 'history', 'scratchpad'
  tokens: number
  maxTokens: number      // per-layer soft cap
}

export interface LoadedFile {
  id: string
  name: string
  size: number           // bytes
  kind: string           // 'csv' | 'parquet' | 'py' | ...
}

export interface ContextShape {
  layers: ContextLayer[]
  loadedFiles: LoadedFile[]
  scratchpad: string     // latest scratchpad_delta aggregate
  totalTokens: number
  budgetTokens: number   // typically 200_000
}

// added to Conversation:
interface Conversation {
  // …existing fields
  context?: ContextShape
}
```

`ProgressStep[]` is **not stored** — it's derived via `selectProgressSteps(conversationId)(state)` from `toolCallLog` + in-memory aggregates of stream events (`a2a_start`/`a2a_end`, `micro_compact`, `turn_start`/`turn_end`, `scratchpad_delta`). The selector memoizes on `toolCallLog` identity.

### Stream events

New event from backend:

```ts
interface ContextSnapshotEvent {
  type: 'context_snapshot'
  layers: Array<{ id: string; label: string; tokens: number; max_tokens: number }>
  loaded_files: Array<{ id: string; name: string; size: number; kind: string }>
  total_tokens: number
  budget_tokens: number
}
```

Emitted on `turn_start` and after each `micro_compact`. Frontend handler: `setConversationContext(conversationId, shape)`. Backend addition is ~30 lines in `backend/app/api/chat_api.py` + `backend/app/trace/publishers.py` — no new context engine; the context manager already tracks layer sizes.

### ui-store additions

```ts
progressExpanded: string[]       // step IDs open in Progress panel (persisted)
artifactView: 'grid' | 'list'    // Artifacts tab view mode (persisted)
recentCommandIds: string[]       // last 5 executed commands (palette)
```

The existing `traceTab: 'raw' | 'context' | 'timeline'` stays — now scopes per-step expand detail.

## Components

### `DockProgress.tsx`
- Header row: "Progress" label-cap + summary `{running} running · {ok} done · {total} elapsed`.
- Renders `ProgressStep[]` from `selectProgressSteps(activeConversationId)`.
- Auto-scrolls to newest running step unless user scrolled up (tracked via `scrollTop + clientHeight < scrollHeight - 20`).
- Empty state: label-cap "No steps yet" + mono "Waiting for agent…".

### `StepCard.tsx`
- Props: `{ step: ProgressStep }`
- Row 1: `<StatusDot />` + title (13px) + right-aligned elapsed (mono, 11px).
- Row 2 (metadata, kind-specific):
  - `tool`: args preview (mono, 11.5px, fg-1, truncated at 60ch).
  - `compact`: `-{dropped} msgs · -{chars_before - chars_after} chars`.
  - `a2a`: sub-agent task preview.
  - `reason`: thinking preview.
  - `turn`: step count.
- Click header → toggles in `ui-store.progressExpanded`.
- Expand detail: `traceTab` segmented control (Raw / Context / Timeline) + one of the three mode components scoped to this step.
- A2A children render indented (+12px) with a thin `--line-2` connector.

### `StatusDot.tsx`
- 6px circle.
- `queued`: fg-3 static.
- `running`: acc with `pulse` animation + `pulseRing` halo pseudo-element.
- `ok`: ok color + `drawCheck` animation (one-shot on entering ok state).
- `err`: err color, no animation.

### `DockContext.tsx`
Composes (top → bottom):
1. `ContextBudgetBar` — full-width 6px bar; fills `totalTokens / budgetTokens`; tick mark at 80% (compaction threshold); color fg-2 → warn at 60% → err at 85%.
2. `LayerBars` — 10px bars, one per layer, max-normalized, mono token count right.
3. `LoadedFileChip` list — bg-2 pill + kind tag + name + size + unload `×`.
4. `AttachedFileList` — re-uses step-2's `AttachedFileChip`, read-only.
5. `TodoList` — 3-state dot + text. Click row → scroll chat to `messageId`.
6. `ScratchpadPreview` — 3 lines + "Expand" → 20-line inline view (no modal).

Empty conversation → single `stripe-ph` "No context snapshot yet".

### `DockArtifacts.tsx`
- Header: `{count} artifacts` + view-mode toggle (`<LayoutGrid />` / `<List />` lucide icons).
- Grid mode: `grid-cols-3` (dock ≥360px), `grid-cols-2` (<360px). Tile is 100×100 / 88×88.
- List mode: 40px rows with type pill + title + created-at + right-aligned copy/download/open buttons.
- Empty: "No artifacts yet" + mono hint.

### `ArtifactTile.tsx`
- Top-left: kind lucide icon (`TrendingUp` / `Table2` / `FileText` / `Workflow` / `FileBarChart` / `File`) + kind label.
- Body: lazy thumbnail:
  - `vega-lite`: 80px scaled render via dynamic vega-embed.
  - `table-json`: 3-row CSS grid preview.
  - `mermaid`: SVG compile in an offscreen canvas.
  - `html`: sandboxed `<iframe srcdoc>`, `pointer-events: none`.
  - `csv`: first-line mono.
  - `text`: first 2 lines mono.
- Hover: lift + `--shadow-2`; border → `--acc-line`.
- Click → `dispatchEvent(new CustomEvent('focusArtifact', { detail: { id } }))`.
- Right-click → `ArtifactContextMenu` (Copy / Download / Remove).

### `ArtifactViewer.tsx`
Renders via `createPortal(..., document.body)`.

Header row (40px, bg-1, border-b line-2):
- Kind icon + title (14.5px fg-0).
- Type pill (11px bg-2 fg-2).
- Right group: `<Copy />` / `<Download />` / `<ExternalLink />` / `<X />` icon buttons.

Body: one of six renderers, selected by `artifact.format` switch.

Footer row (30px): created-at + size + mono hint `← → cycle · ⌘C copy · ⌘S download · ESC close`.

Behavior:
- Mount triggered by `focusArtifact` event or tile click.
- ESC, backdrop click, × close.
- ←/→: `useArtifactNav` cycles through session artifacts.
- ⌘C: format-aware copy (table → TSV, vega-lite → JSON, html → rendered text, etc.).
- ⌘S: format-aware download with correct filename + MIME (vega-lite → PNG via `view.toCanvas()`).
- Focus trap via `focus-trap-react` (~3KB).
- Open-in-new: routes to `/artifact/:id` via `react-router` push in a new window (`window.open('/artifact/' + id)`); `ArtifactPage.tsx` reuses the viewer inside a standalone shell.

### Renderers

- `TableRenderer` — sticky header, mono numeric columns, `@tanstack/virtual` if rows > 500.
- `CsvRenderer` — lazy PapaParse, delegates to `TableRenderer`.
- `HtmlRenderer` — `<iframe srcdoc>` with `sandbox="allow-same-origin"` only (no scripts).
- `TextRenderer` — `<pre>` + JBM Mono + soft-wrap toggle.
- `VegaLiteRenderer` — dynamic vega-embed; respects `prefers-reduced-motion`.
- `MermaidRenderer` — dynamic import of existing mermaid chunk.

Loading failures fall back to `<TextRenderer artifact.content>` behind a "Show raw" toggle.

### `CommandPalette.tsx` (deferrable)
- Modal (560px, centered, bg-1, 12px radius, `--shadow`).
- Sources merged into groups:
  - **Navigate** — conversation switches + section routes (from `CMD.OPEN_SECTION_*`).
  - **Actions** — toggles and ops from `CommandRegistry`.
  - **Recent Threads** — synthetic entries per conversation (title → `setActiveConversation`).
- Fuzzy search: `fuse.js` over `label + description + keywords`; score-sorted.
- Empty query: top 3 per group.
- Keyboard: auto-focus input, ↑/↓ navigates, Home/End jumps, Enter executes + closes, ESC closes.
- Recent execution tracking in `ui-store.recentCommandIds[0..4]`.
- Import-boundary deferral: if phase slips, ⌘K falls back to focusing the chat-header search button (current step-2 behavior) with no palette mount.

## Backend additions

**Minimal** — `backend/app/trace/publishers.py`:

```python
def publish_context_snapshot(session_id: str, context: ContextShape) -> None:
    bus.publish(session_id, {
        "type": "context_snapshot",
        "layers": [...],
        "loaded_files": [...],
        "total_tokens": context.total_tokens,
        "budget_tokens": context.budget_tokens,
    })
```

`chat_api.py` calls this at `turn_start` and after `micro_compact`. No other backend changes.

## Data flow

```
  backend chat_api.py
        │
        │  SSE events: tool_call / tool_result / context_snapshot /
        │              scratchpad_delta / artifact / micro_compact / a2a_*
        ▼
  frontend streamChat handler (lib/api.ts)
        │
        ├─ tool_call / tool_result → pushToolCall / updateToolCallById
        ├─ context_snapshot        → setConversationContext
        ├─ scratchpad_delta        → appendScratchpad (within context)
        ├─ todos_update            → setTodos
        ├─ artifact                → addArtifact
        └─ micro_compact / a2a_*   → aggregated in-memory for ProgressStep derive
        ▼
  zustand store (store.ts)
        │
        ├─ selectProgressSteps() → ProgressStep[]  → DockProgress
        ├─ conversation.context                    → DockContext
        ├─ artifacts filter by session             → DockArtifacts
        └─ artifact by id                          → ArtifactViewer
```

## Error handling

- Renderer load failure → fallback to `TextRenderer` with `artifact.content`.
- Missing artifact (viewer receives unknown id) → close viewer + toast "Artifact not found".
- Backend fails to emit `context_snapshot` → `DockContext` shows `stripe-ph` empty state (no broken UI).
- `unloadFile` network failure → re-add optimistically removed chip + inline toast.
- PapaParse / vega-embed lazy import failures → fallback to raw text + "Show raw" toggle.

## Testing

### Unit (vitest)
- `progressSteps.selector.test.ts` — fixtures covering queued/running/ok/err + a2a nesting + compact.
- Per-component tests for every file listed in the layout.
- Renderer tests: one fixture + snapshot per format.
- Selector memoization: same `toolCallLog` identity → same `ProgressStep[]` reference.

### E2E (Playwright)
- `frontend/e2e/dock.spec.ts` — tab switch, step card expand, Context panel render, Artifacts grid render, grid ↔ list toggle persists.
- `frontend/e2e/artifact-viewer.spec.ts` — tile click opens viewer, ESC closes, ←/→ cycles, ⌘C copies, format-specific renderers load.
- `frontend/e2e/palette.spec.ts` (if shipped) — ⌘K opens, typed query filters, Enter executes.

### Coverage target
- 80% minimum — maintained from prior steps.

## Retirement

- `components/cockpit/TraceRail.tsx` — delete.
- `components/cockpit/trace/{Raw,Context,Timeline}Mode.tsx` — move to `components/dock/progress/modes/`.
- `lib/right-rail-store.ts` — merge `traceTab` into `ui-store`, delete file.
- `components/shell/Dock.tsx` — move to `components/dock/Dock.tsx` and slim to a thin tab-switch orchestrator that renders one of `<DockProgress>` / `<DockContext>` / `<DockArtifacts>`. Update `AppShell` import path accordingly.
- Stub panels `DockContextStub` / `DockArtifactsStub` — delete (inlined in the old `shell/Dock.tsx`).
- `components/cockpit/` — delete directory once TraceRail and its modes are gone.

## Verification gate

- `pnpm tsc --noEmit` clean.
- `pnpm vitest run` green; coverage ≥ 80%.
- `pnpm build` succeeds; `vega-embed`, `papaparse`, `fuse.js` (if palette ships) appear as lazy chunks, not in main bundle.
- `pnpm playwright test` — dock + viewer specs green.
- Manual: light + dark theme Dock matches handoff; narrow viewport (<900px) auto-hides; resize persists.
- `docs/log.md` [Unreleased] entry added.
- `task_plan.md` phase boxes for sub-project 3 all checked.

## Phases (for the plan)

1. Data model — `ProgressStep` selector, `ContextShape` on Conversation, ui-store additions, backend `context_snapshot` event.
2. Progress panel — `DockProgress`, `StepCard`, `StatusDot`, mode moves.
3. Context panel — budget bar, layer bars, file chips, todos, scratchpad preview, orchestrator.
4. Artifacts grid — `DockArtifacts`, `ArtifactTile`, context menu, view-mode toggle.
5. Artifact Viewer — modal, six renderers, keyboard nav, copy/download/open-in-new, standalone `/artifact/:id` route.
6. Retirement — delete TraceRail, move modes, slim `Dock.tsx`, merge `right-rail-store` into `ui-store`.
7. Command Palette (deferrable) — `CommandPalette`, rows, fuzzy search, recent tracking.
8. Verification — tests, build, e2e, changelog, task plan close.

## Guardrails / Non-goals

- No emoji or Unicode box symbols in shipped UI. Toggles and icons must use lucide-react or bespoke SVG.
- No new global state store — Dock state lives in `ui-store`; chat state in the main store.
- No reach for `react-router` beyond the standalone `/artifact/:id` route (step 4's navigation work is out of scope here).
- No backend refactors beyond the single `context_snapshot` event.
- Deferral of Command Palette must leave no dead code in the tree — either all of `components/palette/` ships or none does.
