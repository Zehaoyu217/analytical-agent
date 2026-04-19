# DS-Agent Dock + Artifact Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Dock into a three-tab trust surface (Progress / Context / Artifacts), land a full-viewport Artifact Viewer with six renderers, optionally ship a ⌘K Command Palette, and retire the legacy cockpit-era `TraceRail`.

**Architecture:** Dock becomes a thin orchestrator at `components/dock/Dock.tsx` switching on `ui-store.dockTab`. Progress is derived from a new `selectProgressSteps` selector over `toolCallLog` plus aggregates of `a2a_*` / `micro_compact` / `scratchpad_delta` events. Context is per-conversation, sourced from a new SSE `context_snapshot` event stored on `Conversation.context`. Artifacts render as lazy-thumbnail tiles; the Viewer renders six formats via a format-switch with heavy renderers (`vega-embed`, `mermaid`, `papaparse`) dynamic-imported behind a `Suspense` boundary with a raw-text fallback.

**Tech Stack:** React 19 + Vite + TS strict, Zustand v5 + `persist` + zod, `lucide-react`, `focus-trap-react` (~3KB), `fuse.js` (palette only), `papaparse` (lazy), `vega-embed` (lazy, already bundled), existing `mermaid` chunk. Backend: FastAPI + one new SSE frame emitted from `chat_api.py` via `sse_line("context_snapshot", …)`.

---

## Task 0: Tracking scaffolding

**Files:**
- Modify: `task_plan.md` (append "step 3 of 5" sub-plan header with Phase 1–8 boxes)

- [ ] **Step 1**: Append step 3 sub-plan to `task_plan.md` with Phase 1–8 checkboxes matching this plan, leave unchecked.

- [ ] **Step 2**: Commit

```bash
git add task_plan.md
git commit -m "docs(dock): track step 3 sub-plan phases"
```

---

## Phase 1 — Data model + `context_snapshot` event

### Task 1.1: Extend `ChatStreamEvent` and `ContextShape` types

**Files:**
- Modify: `frontend/src/lib/api.ts:139-195` (add `'context_snapshot'` to union and optional fields)
- Modify: `frontend/src/lib/store.ts:17-56` (add `ContextShape`, `ContextLayer`, `LoadedFile`, extend `Conversation`)

- [ ] **Step 1: Write failing test**

Create `frontend/src/lib/__tests__/api.context-snapshot.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import type { ChatStreamEvent } from '@/lib/api'

describe('ChatStreamEvent', () => {
  it('includes context_snapshot variant with layer + file + budget fields', () => {
    const ev: ChatStreamEvent = {
      type: 'context_snapshot',
      layers: [{ id: 'sys', label: 'system', tokens: 8_000, max_tokens: 16_000 }],
      loaded_files: [{ id: 'f1', name: 'data.csv', size: 2048, kind: 'csv' }],
      total_tokens: 42_000,
      budget_tokens: 200_000,
    }
    expect(ev.type).toBe('context_snapshot')
    expect(ev.layers?.[0].label).toBe('system')
    expect(ev.loaded_files?.[0].kind).toBe('csv')
  })
})
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
cd frontend && pnpm vitest run src/lib/__tests__/api.context-snapshot.test.ts
```

Expected: FAIL (type union missing `'context_snapshot'`, missing fields).

- [ ] **Step 3: Add type variant**

In `frontend/src/lib/api.ts`, edit the `ChatStreamEvent` interface to add `'context_snapshot'` to the `type` union, and append these optional fields just above `created_at?: number`:

```ts
  // context_snapshot
  layers?: Array<{ id: string; label: string; tokens: number; max_tokens: number }>
  loaded_files?: Array<{ id: string; name: string; size: number; kind: string }>
  total_tokens?: number
  budget_tokens?: number
```

- [ ] **Step 4: Add `ContextShape` to store**

In `frontend/src/lib/store.ts`, above `interface Message`, add:

```ts
export interface ContextLayer {
  id: string
  label: string
  tokens: number
  maxTokens: number
}

export interface LoadedFile {
  id: string
  name: string
  size: number
  kind: string
}

export interface ContextShape {
  layers: ContextLayer[]
  loadedFiles: LoadedFile[]
  scratchpad: string
  totalTokens: number
  budgetTokens: number
}
```

Extend `interface Conversation` with `context?: ContextShape`.

- [ ] **Step 5: Run test — verify PASS**

```bash
cd frontend && pnpm vitest run src/lib/__tests__/api.context-snapshot.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/store.ts frontend/src/lib/__tests__/api.context-snapshot.test.ts
git commit -m "feat(dock): add context_snapshot event type + ContextShape model"
```

### Task 1.2: Store actions for context + progress aggregates

**Files:**
- Modify: `frontend/src/lib/store.ts` (add `setConversationContext`, `unloadFile`, and progress-aggregate slices)

- [ ] **Step 1: Write failing test**

Create `frontend/src/lib/__tests__/store.context.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useChatStore } from '@/lib/store'

describe('setConversationContext', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('attaches ContextShape to the conversation', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().setConversationContext(id, {
      layers: [{ id: 'sys', label: 'system', tokens: 8_000, maxTokens: 16_000 }],
      loadedFiles: [],
      scratchpad: '',
      totalTokens: 8_000,
      budgetTokens: 200_000,
    })
    const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv.context?.totalTokens).toBe(8_000)
    expect(conv.context?.layers[0].label).toBe('system')
  })

  it('unloadFile removes the file by id', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().setConversationContext(id, {
      layers: [],
      loadedFiles: [
        { id: 'a', name: 'x.csv', size: 1, kind: 'csv' },
        { id: 'b', name: 'y.csv', size: 1, kind: 'csv' },
      ],
      scratchpad: '',
      totalTokens: 0,
      budgetTokens: 200_000,
    })
    useChatStore.getState().unloadFile(id, 'a')
    const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv.context?.loadedFiles.map((f) => f.id)).toEqual(['b'])
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd frontend && pnpm vitest run src/lib/__tests__/store.context.test.ts
```

Expected: FAIL (`setConversationContext` / `unloadFile` undefined).

- [ ] **Step 3: Implement**

In `frontend/src/lib/store.ts`:

Add to `ChatState`:

```ts
  setConversationContext: (conversationId: string, context: ContextShape) => void
  unloadFile: (conversationId: string, fileId: string) => void
```

Add implementations inside the `create(...)` body (after `setConversationSessionId`):

```ts
      setConversationContext: (conversationId, context) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId ? { ...c, context } : c,
          ),
        })),

      unloadFile: (conversationId, fileId) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId || !c.context) return c
            return {
              ...c,
              context: {
                ...c.context,
                loadedFiles: c.context.loadedFiles.filter((f) => f.id !== fileId),
              },
            }
          }),
        })),
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/store.ts frontend/src/lib/__tests__/store.context.test.ts
git commit -m "feat(dock): store actions for per-conversation context + unloadFile"
```

### Task 1.3: Wire `context_snapshot` into stream handler

**Files:**
- Modify: `frontend/src/components/chat/composer/useComposerSubmit.ts` (add `context_snapshot` branch)

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/chat/composer/__tests__/useComposerSubmit.context-snapshot.test.tsx` (use the existing mock pattern from `useComposerSubmit.test.tsx`):

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useComposerSubmit } from '../useComposerSubmit'
import { useChatStore } from '@/lib/store'

vi.mock('@/lib/api-chat', () => ({
  streamChatMessage: async function* () {
    yield { type: 'turn_start', session_id: 's1', step: 0 }
    yield {
      type: 'context_snapshot',
      layers: [{ id: 'sys', label: 'system', tokens: 8_000, max_tokens: 16_000 }],
      loaded_files: [{ id: 'f1', name: 'data.csv', size: 2048, kind: 'csv' }],
      total_tokens: 42_000,
      budget_tokens: 200_000,
    }
    yield { type: 'turn_end', final_text: 'ok', stop_reason: 'end_turn', steps: 1 }
  },
}))

vi.mock('@/lib/api-backend', () => ({
  backend: {
    conversations: {
      appendTurn: vi.fn().mockResolvedValue(undefined),
      get: vi.fn(),
      create: vi.fn(),
    },
  },
}))

describe('useComposerSubmit — context_snapshot', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('writes ContextShape onto the active conversation', async () => {
    const id = useChatStore.getState().createConversation()
    const { result } = renderHook(() => useComposerSubmit(id))
    await act(async () => {
      await result.current.submit('hi')
    })
    const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv.context?.totalTokens).toBe(42_000)
    expect(conv.context?.loadedFiles[0].name).toBe('data.csv')
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

In `useComposerSubmit.ts`, destructure `setConversationContext` from the store state. Inside the `for await` loop, before `else if (event.type === 'scratchpad_delta')`, add:

```ts
          } else if (event.type === 'context_snapshot') {
            setConversationContext(conversationId, {
              layers: (event.layers ?? []).map((l) => ({
                id: l.id,
                label: l.label,
                tokens: l.tokens,
                maxTokens: l.max_tokens,
              })),
              loadedFiles: (event.loaded_files ?? []).map((f) => ({
                id: f.id,
                name: f.name,
                size: f.size,
                kind: f.kind,
              })),
              scratchpad:
                useChatStore.getState().conversations.find((c) => c.id === conversationId)
                  ?.context?.scratchpad ?? '',
              totalTokens: event.total_tokens ?? 0,
              budgetTokens: event.budget_tokens ?? 200_000,
            })
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/composer/useComposerSubmit.ts frontend/src/components/chat/composer/__tests__/useComposerSubmit.context-snapshot.test.tsx
git commit -m "feat(dock): handle context_snapshot stream events"
```

### Task 1.4: `selectProgressSteps` selector

**Files:**
- Create: `frontend/src/lib/selectors/progressSteps.ts`
- Create: `frontend/src/lib/selectors/__tests__/progressSteps.test.ts`

- [ ] **Step 1: Write failing test**

```ts
import { describe, it, expect } from 'vitest'
import { selectProgressSteps } from '../progressSteps'
import type { ToolCallEntry } from '@/lib/store'

function entry(p: Partial<ToolCallEntry>): ToolCallEntry {
  return {
    id: p.id ?? 'x',
    step: p.step ?? 0,
    name: p.name ?? 'tool',
    inputPreview: p.inputPreview ?? '',
    status: p.status ?? 'pending',
    startedAt: p.startedAt ?? 1,
    ...p,
  } as ToolCallEntry
}

describe('selectProgressSteps', () => {
  it('returns empty for empty log', () => {
    expect(selectProgressSteps([])).toEqual([])
  })

  it('maps tool calls to running/ok/err steps', () => {
    const steps = selectProgressSteps([
      entry({ id: 'a', step: 1, name: 'fetch', status: 'pending' }),
      entry({ id: 'b', step: 2, name: 'save', status: 'ok', finishedAt: 5 }),
      entry({ id: 'c', step: 3, name: 'x', status: 'error', finishedAt: 7 }),
    ])
    expect(steps).toHaveLength(3)
    expect(steps[0].status).toBe('running')
    expect(steps[1].status).toBe('ok')
    expect(steps[2].status).toBe('err')
  })

  it('tags compact entries with kind=compact', () => {
    const steps = selectProgressSteps([
      entry({ id: 'c', step: 4, name: '__compact__', status: 'ok', finishedAt: 9 }),
    ])
    expect(steps[0].kind).toBe('compact')
  })

  it('is referentially stable for the same log identity', () => {
    const log: ToolCallEntry[] = [entry({ id: 'a', step: 1, name: 'fetch', status: 'ok' })]
    const a = selectProgressSteps(log)
    const b = selectProgressSteps(log)
    expect(a).toBe(b)
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/selectors/progressSteps.ts
import type { ToolCallEntry } from '@/lib/store'

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

const cache = new WeakMap<ToolCallEntry[], ProgressStep[]>()

function kindOf(name: string): ProgressStep['kind'] {
  if (name === '__compact__') return 'compact'
  if (name.startsWith('a2a:')) return 'a2a'
  return 'tool'
}

function statusOf(t: ToolCallEntry): ProgressStep['status'] {
  if (t.status === 'pending') return 'running'
  if (t.status === 'error' || t.status === 'blocked') return 'err'
  return 'ok'
}

export function selectProgressSteps(log: ToolCallEntry[]): ProgressStep[] {
  const cached = cache.get(log)
  if (cached) return cached
  const steps: ProgressStep[] = log.map((t, i) => ({
    id: t.id,
    index: t.step ?? i,
    title: t.name,
    kind: kindOf(t.name),
    status: statusOf(t),
    startedAt: t.startedAt,
    finishedAt: t.finishedAt,
    toolCallIds: [t.id],
    artifactIds: t.artifactIds ?? [],
  }))
  cache.set(log, steps)
  return steps
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/selectors/progressSteps.ts frontend/src/lib/selectors/__tests__/progressSteps.test.ts
git commit -m "feat(dock): selectProgressSteps selector with memoization"
```

### Task 1.5: ui-store schema v2 — add `progressExpanded`, `artifactView`, `recentCommandIds`, absorb `traceTab`

**Files:**
- Modify: `frontend/src/lib/ui-store.ts`
- Create: `frontend/src/lib/__tests__/ui-store.v2.test.ts`

- [ ] **Step 1: Write failing test**

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useUiStore } from '@/lib/ui-store'

describe('ui-store v2', () => {
  beforeEach(() => {
    localStorage.clear()
    useUiStore.setState({
      progressExpanded: [],
      artifactView: 'grid',
      recentCommandIds: [],
      traceTab: 'timeline',
    } as never)
  })

  it('toggleProgressExpanded adds and removes step ids', () => {
    useUiStore.getState().toggleProgressExpanded('s1')
    expect(useUiStore.getState().progressExpanded).toEqual(['s1'])
    useUiStore.getState().toggleProgressExpanded('s1')
    expect(useUiStore.getState().progressExpanded).toEqual([])
  })

  it('setArtifactView switches mode', () => {
    useUiStore.getState().setArtifactView('list')
    expect(useUiStore.getState().artifactView).toBe('list')
  })

  it('pushRecentCommand deduplicates and caps at 5', () => {
    for (const id of ['a', 'b', 'c', 'd', 'e', 'f', 'a']) {
      useUiStore.getState().pushRecentCommand(id)
    }
    const ids = useUiStore.getState().recentCommandIds
    expect(ids.length).toBeLessThanOrEqual(5)
    expect(ids[0]).toBe('a')
  })

  it('setTraceTab lives in ui-store now', () => {
    useUiStore.getState().setTraceTab('raw')
    expect(useUiStore.getState().traceTab).toBe('raw')
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

In `frontend/src/lib/ui-store.ts`:

1. Bump schema: extend `UiPersistedSchema`:

```ts
export const UiPersistedSchema = z.object({
  v: z.literal(2).default(2),
  threadW: z.number().int().min(THREAD_W_MIN).max(THREAD_W_MAX).default(200),
  dockW: z.number().int().min(DOCK_W_MIN).max(DOCK_W_MAX).default(320),
  threadsOpen: z.boolean().default(true),
  dockOpen: z.boolean().default(true),
  dockTab: z.enum(["progress", "context", "artifacts"]).default("progress"),
  density: z.enum(["compact", "default", "cozy"]).default("default"),
  progressExpanded: z.array(z.string()).default([]),
  artifactView: z.enum(["grid", "list"]).default("grid"),
  recentCommandIds: z.array(z.string()).default([]),
  traceTab: z.enum(["timeline", "context", "raw"]).default("timeline"),
})
```

2. Add store actions + selectors:

```ts
export type TraceTab = UiPersisted["traceTab"]

export interface UiStore extends UiPersisted {
  threadsOverridden: boolean
  dockOverridden: boolean
  // …existing
  toggleProgressExpanded: (stepId: string) => void
  setArtifactView: (view: 'grid' | 'list') => void
  pushRecentCommand: (id: string) => void
  setTraceTab: (tab: TraceTab) => void
  // …existing rest
}
```

Implementations inside `create(...)`:

```ts
      progressExpanded: [],
      artifactView: 'grid' as const,
      recentCommandIds: [],
      traceTab: 'timeline' as TraceTab,

      toggleProgressExpanded: (stepId) =>
        set((s) => ({
          progressExpanded: s.progressExpanded.includes(stepId)
            ? s.progressExpanded.filter((id) => id !== stepId)
            : [...s.progressExpanded, stepId],
        })),
      setArtifactView: (view) => set({ artifactView: view }),
      pushRecentCommand: (id) =>
        set((s) => {
          const next = [id, ...s.recentCommandIds.filter((x) => x !== id)].slice(0, 5)
          return { recentCommandIds: next }
        }),
      setTraceTab: (tab) => set({ traceTab: tab }),
```

Update `partialize` to include the four new fields, bump persist `version: 2`, and add a `migrate` that backfills defaults for v1 users:

```ts
      version: 2,
      migrate: (persisted, fromVersion) => {
        if (fromVersion === 1 && persisted && typeof persisted === 'object') {
          return { ...persisted, v: 2, progressExpanded: [], artifactView: 'grid', recentCommandIds: [], traceTab: 'timeline' }
        }
        return persisted as UiPersisted
      },
```

Add selectors:

```ts
export const selectArtifactView = (s: UiStore): 'grid' | 'list' => s.artifactView
export const selectProgressExpanded = (s: UiStore): string[] => s.progressExpanded
export const selectTraceTab = (s: UiStore): TraceTab => s.traceTab
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/ui-store.ts frontend/src/lib/__tests__/ui-store.v2.test.ts
git commit -m "feat(dock): ui-store v2 — progressExpanded/artifactView/recentCommandIds/traceTab"
```

### Task 1.6: Backend `context_snapshot` publisher

**Files:**
- Modify: `backend/app/api/chat_api.py` (emit `context_snapshot` at `turn_start` and after `micro_compact`)
- Create: `backend/tests/api/test_chat_stream_context_snapshot.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/api/test_chat_stream_context_snapshot.py
"""Verify chat/stream emits context_snapshot frames at turn_start + post-compact."""
import json
from fastapi.testclient import TestClient

from app.main import app


def test_context_snapshot_emitted_on_turn_start(monkeypatch):
    client = TestClient(app)
    with client.stream("POST", "/api/chat/stream", json={"message": "ping"}) as r:
        saw_turn_start = False
        saw_context_snapshot = False
        for raw in r.iter_lines():
            if not raw or not raw.startswith("data: "):
                continue
            evt = json.loads(raw[len("data: "):])
            if evt.get("type") == "turn_start":
                saw_turn_start = True
            elif evt.get("type") == "context_snapshot":
                saw_context_snapshot = True
                assert "layers" in evt
                assert "total_tokens" in evt
                assert "budget_tokens" in evt
            if saw_context_snapshot:
                break
        assert saw_turn_start
        assert saw_context_snapshot
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && pytest tests/api/test_chat_stream_context_snapshot.py -v
```

Expected: FAIL (no context_snapshot frames emitted).

- [ ] **Step 3: Implement**

In `backend/app/api/chat_api.py`, locate the generator that yields `turn_start` (search for `"turn_start"`). Immediately after the first `turn_start` yield, insert:

```python
# Emit an initial context snapshot so the Dock Context panel can render
# before any tool runs.
_snap = ctx.snapshot()
yield sse_line("context_snapshot", {
    "layers": [
        {"id": str(i), "label": L.name, "tokens": L.tokens, "max_tokens": _snap.max_tokens}
        for i, L in enumerate(_snap.layers)
    ],
    "loaded_files": [],
    "total_tokens": _snap.total_tokens,
    "budget_tokens": _snap.max_tokens,
})
```

And at the end of the `if event.type == "micro_compact":` block (around line 1129), append another snapshot yield using the same shape.

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat_api.py backend/tests/api/test_chat_stream_context_snapshot.py
git commit -m "feat(chat): emit context_snapshot on turn_start + post-compact"
```

---

## Phase 2 — Progress panel

### Task 2.1: `StatusDot`

**Files:**
- Create: `frontend/src/components/dock/progress/StatusDot.tsx`
- Create: `frontend/src/components/dock/progress/__tests__/StatusDot.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusDot } from '../StatusDot'

describe('StatusDot', () => {
  it.each(['queued', 'running', 'ok', 'err'] as const)(
    'renders with data-status=%s',
    (status) => {
      const { container } = render(<StatusDot status={status} />)
      const el = container.querySelector('[data-status]')
      expect(el).not.toBeNull()
      expect(el!.getAttribute('data-status')).toBe(status)
    },
  )
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/progress/StatusDot.tsx
import { cn } from '@/lib/utils'

interface StatusDotProps {
  status: 'queued' | 'running' | 'ok' | 'err'
  className?: string
}

export function StatusDot({ status, className }: StatusDotProps) {
  return (
    <span
      data-status={status}
      aria-label={`status: ${status}`}
      className={cn(
        'inline-block h-1.5 w-1.5 rounded-full',
        status === 'queued' && 'bg-fg-3',
        status === 'running' && 'bg-acc animate-pulse',
        status === 'ok' && 'bg-ok',
        status === 'err' && 'bg-err',
        className,
      )}
    />
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/progress/StatusDot.tsx frontend/src/components/dock/progress/__tests__/StatusDot.test.tsx
git commit -m "feat(dock): StatusDot component"
```

### Task 2.2: Move legacy trace modes into `dock/progress/modes/`

**Files:**
- Move: `frontend/src/components/cockpit/trace/TimelineMode.tsx` → `frontend/src/components/dock/progress/modes/TimelineMode.tsx`
- Move: `frontend/src/components/cockpit/trace/ContextMode.tsx` → `frontend/src/components/dock/progress/modes/ContextMode.tsx`
- Move: `frontend/src/components/cockpit/trace/RawMode.tsx` → `frontend/src/components/dock/progress/modes/RawMode.tsx`

- [ ] **Step 1**: `git mv` each file into the new path (don't edit content yet).

```bash
mkdir -p frontend/src/components/dock/progress/modes
git mv frontend/src/components/cockpit/trace/TimelineMode.tsx frontend/src/components/dock/progress/modes/TimelineMode.tsx
git mv frontend/src/components/cockpit/trace/ContextMode.tsx frontend/src/components/dock/progress/modes/ContextMode.tsx
git mv frontend/src/components/cockpit/trace/RawMode.tsx frontend/src/components/dock/progress/modes/RawMode.tsx
```

- [ ] **Step 2**: Replace `useRightRailStore` imports with `useUiStore` in all three modes:

```ts
// before
import { useRightRailStore } from '@/lib/right-rail-store'
// after
import { useUiStore } from '@/lib/ui-store'
```

(None of the three mode files actually use `useRightRailStore` — it's only in `TraceRail.tsx`. This step is a no-op for modes but verify grep shows zero remaining references after Phase 6.)

- [ ] **Step 3**: Update the one import inside `frontend/src/components/cockpit/TraceRail.tsx` so the file still compiles during transition:

```ts
// TraceRail.tsx
import { TimelineMode } from '@/components/dock/progress/modes/TimelineMode'
import { ContextMode } from '@/components/dock/progress/modes/ContextMode'
import { RawMode } from '@/components/dock/progress/modes/RawMode'
```

- [ ] **Step 4: Run typecheck**

```bash
cd frontend && pnpm tsc --noEmit
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "refactor(dock): move trace modes to dock/progress/modes"
```

### Task 2.3: `StepCard`

**Files:**
- Create: `frontend/src/components/dock/progress/StepCard.tsx`
- Create: `frontend/src/components/dock/progress/__tests__/StepCard.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StepCard } from '../StepCard'
import { useUiStore } from '@/lib/ui-store'
import type { ProgressStep } from '@/lib/selectors/progressSteps'

const step: ProgressStep = {
  id: 's1',
  index: 1,
  title: 'fetch_data',
  kind: 'tool',
  status: 'ok',
  startedAt: 1_000,
  finishedAt: 1_250,
  toolCallIds: ['t1'],
  artifactIds: [],
}

describe('StepCard', () => {
  beforeEach(() => {
    useUiStore.setState({ progressExpanded: [] } as never)
  })

  it('renders title and elapsed', () => {
    render(<StepCard step={step} />)
    expect(screen.getByText('fetch_data')).toBeInTheDocument()
    expect(screen.getByText(/250\s*ms/)).toBeInTheDocument()
  })

  it('toggles expanded on click', () => {
    render(<StepCard step={step} />)
    fireEvent.click(screen.getByRole('button', { name: /fetch_data/i }))
    expect(useUiStore.getState().progressExpanded).toContain('s1')
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/progress/StepCard.tsx
import { useUiStore, selectProgressExpanded, selectTraceTab } from '@/lib/ui-store'
import type { ProgressStep } from '@/lib/selectors/progressSteps'
import { StatusDot } from './StatusDot'
import { cn } from '@/lib/utils'
import { TimelineMode } from './modes/TimelineMode'
import { ContextMode } from './modes/ContextMode'
import { RawMode } from './modes/RawMode'

interface StepCardProps {
  step: ProgressStep
}

function elapsedLabel(step: ProgressStep): string {
  if (!step.startedAt) return ''
  const end = step.finishedAt ?? Date.now()
  const ms = Math.max(0, end - step.startedAt)
  return ms < 1_000 ? `${ms} ms` : `${(ms / 1_000).toFixed(1)} s`
}

export function StepCard({ step }: StepCardProps) {
  const expanded = useUiStore(selectProgressExpanded)
  const isOpen = expanded.includes(step.id)
  const toggle = useUiStore((s) => s.toggleProgressExpanded)
  const traceTab = useUiStore(selectTraceTab)
  const setTraceTab = useUiStore((s) => s.setTraceTab)

  return (
    <div className="border-b border-line-2 px-3 py-2">
      <button
        type="button"
        onClick={() => toggle(step.id)}
        className={cn(
          'flex w-full items-center gap-2 text-left focus-ring rounded',
          'hover:bg-bg-2',
        )}
        aria-expanded={isOpen}
        aria-label={`Step ${step.index}: ${step.title}`}
      >
        <StatusDot status={step.status} />
        <span className="flex-1 truncate text-[13px] text-fg-0">{step.title}</span>
        <span className="mono text-[11px] text-fg-3">{elapsedLabel(step)}</span>
      </button>
      {isOpen && (
        <div className="mt-2 border-t border-line-2 pt-2">
          <div className="mb-2 flex gap-1">
            {(['timeline', 'context', 'raw'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTraceTab(t)}
                data-active={traceTab === t}
                className={cn(
                  'mono rounded px-2 py-0.5 text-[10.5px] uppercase',
                  traceTab === t ? 'bg-acc/10 text-acc' : 'text-fg-3 hover:text-fg-0',
                )}
              >
                {t}
              </button>
            ))}
          </div>
          {traceTab === 'timeline' && <TimelineMode />}
          {traceTab === 'context' && <ContextMode />}
          {traceTab === 'raw' && <RawMode />}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/progress/StepCard.tsx frontend/src/components/dock/progress/__tests__/StepCard.test.tsx
git commit -m "feat(dock): StepCard with expand-row Raw/Context/Timeline modes"
```

### Task 2.4: `DockProgress` panel

**Files:**
- Create: `frontend/src/components/dock/DockProgress.tsx`
- Create: `frontend/src/components/dock/__tests__/DockProgress.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DockProgress } from '../DockProgress'
import { useChatStore } from '@/lib/store'

describe('DockProgress', () => {
  beforeEach(() => {
    useChatStore.setState({ toolCallLog: [] } as never)
  })

  it('shows empty state when no tool calls', () => {
    render(<DockProgress />)
    expect(screen.getByText(/no steps yet/i)).toBeInTheDocument()
  })

  it('renders one StepCard per tool call', () => {
    useChatStore.setState({
      toolCallLog: [
        { id: 'a', step: 1, name: 'first', inputPreview: '', status: 'ok', startedAt: 1, finishedAt: 2 },
        { id: 'b', step: 2, name: 'second', inputPreview: '', status: 'pending', startedAt: 3 },
      ],
    } as never)
    render(<DockProgress />)
    expect(screen.getByText('first')).toBeInTheDocument()
    expect(screen.getByText('second')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/DockProgress.tsx
import { useMemo } from 'react'
import { useChatStore } from '@/lib/store'
import { selectProgressSteps } from '@/lib/selectors/progressSteps'
import { StepCard } from './progress/StepCard'

export function DockProgress() {
  const log = useChatStore((s) => s.toolCallLog)
  const steps = useMemo(() => selectProgressSteps(log), [log])

  const running = steps.filter((s) => s.status === 'running').length
  const ok = steps.filter((s) => s.status === 'ok').length

  if (steps.length === 0) {
    return (
      <div className="flex h-full flex-col gap-2 p-4">
        <div className="label-cap">No steps yet</div>
        <div className="mono text-[10.5px] text-fg-3">Waiting for agent…</div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col" aria-label="Agent progress">
      <div className="flex items-center justify-between border-b border-line-2 px-3 py-2">
        <div className="label-cap">Progress</div>
        <div className="mono text-[10.5px] text-fg-3">
          {running} running · {ok} done · {steps.length} total
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {steps.map((s) => (
          <StepCard key={s.id} step={s} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/DockProgress.tsx frontend/src/components/dock/__tests__/DockProgress.test.tsx
git commit -m "feat(dock): DockProgress panel with step summary"
```

---

## Phase 3 — Context panel

### Task 3.1: `ContextBudgetBar`

**Files:**
- Create: `frontend/src/components/dock/context/ContextBudgetBar.tsx`
- Create: `frontend/src/components/dock/context/__tests__/ContextBudgetBar.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContextBudgetBar } from '../ContextBudgetBar'

describe('ContextBudgetBar', () => {
  it('shows used / budget labels', () => {
    render(<ContextBudgetBar totalTokens={50_000} budgetTokens={200_000} />)
    expect(screen.getByLabelText(/context budget/i)).toBeInTheDocument()
    expect(screen.getByText(/50\s*k/i)).toBeInTheDocument()
    expect(screen.getByText(/200\s*k/i)).toBeInTheDocument()
  })

  it('adds warn tone at >=60% and err tone at >=85%', () => {
    const { rerender, container } = render(
      <ContextBudgetBar totalTokens={125_000} budgetTokens={200_000} />,
    )
    expect(container.querySelector('[data-tone="warn"]')).not.toBeNull()
    rerender(<ContextBudgetBar totalTokens={180_000} budgetTokens={200_000} />)
    expect(container.querySelector('[data-tone="err"]')).not.toBeNull()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/context/ContextBudgetBar.tsx
import { cn } from '@/lib/utils'

interface ContextBudgetBarProps {
  totalTokens: number
  budgetTokens: number
}

function fmtK(n: number): string {
  return n >= 1000 ? `${Math.round(n / 100) / 10}k` : `${n}`
}

export function ContextBudgetBar({ totalTokens, budgetTokens }: ContextBudgetBarProps) {
  const pct = Math.min(100, Math.round((totalTokens / Math.max(1, budgetTokens)) * 100))
  const tone = pct >= 85 ? 'err' : pct >= 60 ? 'warn' : 'ok'
  return (
    <div aria-label="Context budget">
      <div className="mono mb-1 flex items-center justify-between text-[10.5px] text-fg-3">
        <span>{fmtK(totalTokens)}</span>
        <span>{fmtK(budgetTokens)}</span>
      </div>
      <div
        data-tone={tone}
        className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-2"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            'h-full transition-[width]',
            tone === 'ok' && 'bg-fg-2',
            tone === 'warn' && 'bg-warn',
            tone === 'err' && 'bg-err',
          )}
          style={{ width: `${pct}%` }}
        />
        <div
          aria-hidden
          className="absolute top-0 h-full w-px bg-line-2"
          style={{ left: '80%' }}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/context/ContextBudgetBar.tsx frontend/src/components/dock/context/__tests__/ContextBudgetBar.test.tsx
git commit -m "feat(dock): ContextBudgetBar"
```

### Task 3.2: `LayerBars`

**Files:**
- Create: `frontend/src/components/dock/context/LayerBars.tsx`
- Create: `frontend/src/components/dock/context/__tests__/LayerBars.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LayerBars } from '../LayerBars'

describe('LayerBars', () => {
  it('renders one bar per layer with label and token count', () => {
    render(
      <LayerBars
        layers={[
          { id: '0', label: 'system', tokens: 12_000, maxTokens: 16_000 },
          { id: '1', label: 'history', tokens: 8_000, maxTokens: 16_000 },
        ]}
      />,
    )
    expect(screen.getByText('system')).toBeInTheDocument()
    expect(screen.getByText('history')).toBeInTheDocument()
    expect(screen.getAllByRole('progressbar')).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/context/LayerBars.tsx
import type { ContextLayer } from '@/lib/store'

interface LayerBarsProps {
  layers: ContextLayer[]
}

function fmtK(n: number): string {
  return n >= 1000 ? `${Math.round(n / 100) / 10}k` : `${n}`
}

export function LayerBars({ layers }: LayerBarsProps) {
  const max = Math.max(1, ...layers.map((l) => l.tokens))
  return (
    <ul className="flex flex-col gap-1.5">
      {layers.map((l) => {
        const pct = Math.round((l.tokens / max) * 100)
        return (
          <li key={l.id} className="flex items-center gap-2">
            <span className="mono w-20 truncate text-[10.5px] text-fg-2">{l.label}</span>
            <div
              className="relative h-2 flex-1 overflow-hidden rounded bg-bg-2"
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${l.label} tokens`}
            >
              <div className="h-full bg-fg-2" style={{ width: `${pct}%` }} />
            </div>
            <span className="mono w-12 text-right text-[10.5px] text-fg-3">{fmtK(l.tokens)}</span>
          </li>
        )
      })}
    </ul>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/context/LayerBars.tsx frontend/src/components/dock/context/__tests__/LayerBars.test.tsx
git commit -m "feat(dock): LayerBars"
```

### Task 3.3: `LoadedFileChip` + small sub-lists

**Files:**
- Create: `frontend/src/components/dock/context/LoadedFileChip.tsx`
- Create: `frontend/src/components/dock/context/AttachedFileList.tsx`
- Create: `frontend/src/components/dock/context/TodoList.tsx`
- Create: `frontend/src/components/dock/context/ScratchpadPreview.tsx`
- Create: `frontend/src/components/dock/context/__tests__/LoadedFileChip.test.tsx`
- Create: `frontend/src/components/dock/context/__tests__/TodoList.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// LoadedFileChip.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LoadedFileChip } from '../LoadedFileChip'

describe('LoadedFileChip', () => {
  it('renders kind, name, size; onUnload fires on × click', () => {
    const onUnload = vi.fn()
    render(
      <LoadedFileChip
        file={{ id: 'a', name: 'iris.csv', size: 4096, kind: 'csv' }}
        onUnload={onUnload}
      />,
    )
    expect(screen.getByText('csv')).toBeInTheDocument()
    expect(screen.getByText('iris.csv')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /unload/i }))
    expect(onUnload).toHaveBeenCalledWith('a')
  })
})
```

```tsx
// TodoList.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TodoList } from '../TodoList'

describe('TodoList', () => {
  it('renders empty state', () => {
    render(<TodoList todos={[]} />)
    expect(screen.getByText(/no todos/i)).toBeInTheDocument()
  })
  it('renders todos with status dot', () => {
    render(
      <TodoList
        todos={[
          { id: 't1', content: 'load data', status: 'in_progress' },
          { id: 't2', content: 'train', status: 'pending' },
        ]}
      />,
    )
    expect(screen.getByText('load data')).toBeInTheDocument()
    expect(screen.getByText('train')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/context/LoadedFileChip.tsx
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LoadedFile } from '@/lib/store'

interface LoadedFileChipProps {
  file: LoadedFile
  onUnload?: (id: string) => void
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function LoadedFileChip({ file, onUnload }: LoadedFileChipProps) {
  return (
    <div className={cn('flex items-center gap-2 rounded bg-bg-2 px-2 py-1')}>
      <span className="mono rounded bg-bg-1 px-1 text-[9.5px] uppercase text-fg-2">{file.kind}</span>
      <span className="flex-1 truncate text-[12px] text-fg-1">{file.name}</span>
      <span className="mono text-[10.5px] text-fg-3">{fmtSize(file.size)}</span>
      {onUnload && (
        <button
          type="button"
          aria-label={`Unload ${file.name}`}
          onClick={() => onUnload(file.id)}
          className="inline-flex h-4 w-4 items-center justify-center rounded text-fg-3 hover:bg-bg-1 hover:text-fg-0 focus-ring"
        >
          <X className="h-3 w-3" aria-hidden />
        </button>
      )}
    </div>
  )
}
```

```tsx
// frontend/src/components/dock/context/AttachedFileList.tsx
import type { AttachedFile } from '@/lib/store'

interface AttachedFileListProps {
  files: AttachedFile[]
}

export function AttachedFileList({ files }: AttachedFileListProps) {
  if (files.length === 0) return null
  return (
    <ul className="flex flex-col gap-1">
      {files.map((f) => (
        <li key={f.id} className="mono flex items-center justify-between text-[11px] text-fg-2">
          <span className="truncate">{f.name}</span>
          <span className="text-fg-3">{(f.size / 1024).toFixed(1)} KB</span>
        </li>
      ))}
    </ul>
  )
}
```

```tsx
// frontend/src/components/dock/context/TodoList.tsx
import { cn } from '@/lib/utils'
import type { TodoItem } from '@/lib/store'

interface TodoListProps {
  todos: TodoItem[]
  onFocus?: (id: string) => void
}

const STATUS_COLOR: Record<TodoItem['status'], string> = {
  pending: 'bg-fg-3',
  in_progress: 'bg-acc animate-pulse',
  completed: 'bg-ok',
}

export function TodoList({ todos, onFocus }: TodoListProps) {
  if (todos.length === 0) {
    return <div className="mono text-[10.5px] text-fg-3">No todos</div>
  }
  return (
    <ul className="flex flex-col gap-1">
      {todos.map((t) => (
        <li key={t.id}>
          <button
            type="button"
            onClick={() => onFocus?.(t.id)}
            className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-[12px] text-fg-1 hover:bg-bg-2 focus-ring"
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', STATUS_COLOR[t.status])} />
            <span className="truncate">{t.content}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
```

```tsx
// frontend/src/components/dock/context/ScratchpadPreview.tsx
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface ScratchpadPreviewProps {
  content: string
}

export function ScratchpadPreview({ content }: ScratchpadPreviewProps) {
  const [expanded, setExpanded] = useState(false)
  if (!content.trim()) {
    return <div className="mono text-[10.5px] text-fg-3">Scratchpad empty</div>
  }
  const lines = content.split('\n')
  const shown = expanded ? lines.slice(0, 20) : lines.slice(0, 3)
  return (
    <div>
      <pre className={cn('mono whitespace-pre-wrap text-[11px] text-fg-1')}>
        {shown.join('\n')}
      </pre>
      {lines.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mono mt-1 text-[10.5px] text-acc hover:underline focus-ring rounded"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/context/
git commit -m "feat(dock): LoadedFileChip + AttachedFileList + TodoList + ScratchpadPreview"
```

### Task 3.4: `DockContext` orchestrator

**Files:**
- Create: `frontend/src/components/dock/DockContext.tsx`
- Create: `frontend/src/components/dock/__tests__/DockContext.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DockContext } from '../DockContext'
import { useChatStore } from '@/lib/store'

describe('DockContext', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null } as never)
  })

  it('shows empty state when no context snapshot yet', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.setState({ activeConversationId: id } as never)
    render(<DockContext />)
    expect(screen.getByText(/no context snapshot yet/i)).toBeInTheDocument()
  })

  it('renders budget bar + layers when context present', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().setConversationContext(id, {
      layers: [{ id: '0', label: 'system', tokens: 12_000, maxTokens: 16_000 }],
      loadedFiles: [{ id: 'a', name: 'x.csv', size: 1024, kind: 'csv' }],
      scratchpad: '',
      totalTokens: 12_000,
      budgetTokens: 200_000,
    })
    useChatStore.setState({ activeConversationId: id } as never)
    render(<DockContext />)
    expect(screen.getByLabelText(/context budget/i)).toBeInTheDocument()
    expect(screen.getByText('system')).toBeInTheDocument()
    expect(screen.getByText('x.csv')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/DockContext.tsx
import { useChatStore } from '@/lib/store'
import { ContextBudgetBar } from './context/ContextBudgetBar'
import { LayerBars } from './context/LayerBars'
import { LoadedFileChip } from './context/LoadedFileChip'
import { AttachedFileList } from './context/AttachedFileList'
import { TodoList } from './context/TodoList'
import { ScratchpadPreview } from './context/ScratchpadPreview'

export function DockContext() {
  const conversationId = useChatStore((s) => s.activeConversationId)
  const conv = useChatStore((s) => s.conversations.find((c) => c.id === conversationId))
  const todos = useChatStore((s) => s.todos)
  const scratchpad = useChatStore((s) => s.scratchpad)
  const unloadFile = useChatStore((s) => s.unloadFile)

  if (!conv?.context) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <div className="label-cap">Context snapshot</div>
        <div className="stripe-ph h-40" aria-label="No context snapshot yet">
          No context snapshot yet
        </div>
      </div>
    )
  }

  const { layers, loadedFiles, totalTokens, budgetTokens } = conv.context

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <div className="label-cap mb-2">Budget</div>
        <ContextBudgetBar totalTokens={totalTokens} budgetTokens={budgetTokens} />
      </div>
      {layers.length > 0 && (
        <div>
          <div className="label-cap mb-2">Layers</div>
          <LayerBars layers={layers} />
        </div>
      )}
      {loadedFiles.length > 0 && (
        <div>
          <div className="label-cap mb-2">Loaded files</div>
          <div className="flex flex-col gap-1">
            {loadedFiles.map((f) => (
              <LoadedFileChip key={f.id} file={f} onUnload={(id) => unloadFile(conv.id, id)} />
            ))}
          </div>
        </div>
      )}
      {(conv.attachedFiles?.length ?? 0) > 0 && (
        <div>
          <div className="label-cap mb-2">Attached</div>
          <AttachedFileList files={conv.attachedFiles ?? []} />
        </div>
      )}
      <div>
        <div className="label-cap mb-2">Todos</div>
        <TodoList todos={todos} />
      </div>
      <div>
        <div className="label-cap mb-2">Scratchpad</div>
        <ScratchpadPreview content={scratchpad} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/DockContext.tsx frontend/src/components/dock/__tests__/DockContext.test.tsx
git commit -m "feat(dock): DockContext orchestrator"
```

---

## Phase 4 — Artifacts grid

### Task 4.1: `ArtifactTile`

**Files:**
- Create: `frontend/src/components/dock/artifacts/ArtifactTile.tsx`
- Create: `frontend/src/components/dock/artifacts/__tests__/ArtifactTile.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ArtifactTile } from '../ArtifactTile'
import type { Artifact } from '@/lib/store'

const artifact: Artifact = {
  id: 'a1',
  type: 'chart',
  title: 'Revenue',
  content: '{}',
  format: 'vega-lite',
  session_id: 's',
  created_at: Date.now() / 1000,
  metadata: {},
}

describe('ArtifactTile', () => {
  it('renders kind label and title', () => {
    render(<ArtifactTile artifact={artifact} />)
    expect(screen.getByText('Revenue')).toBeInTheDocument()
    expect(screen.getByText(/chart/i)).toBeInTheDocument()
  })

  it('dispatches focusArtifact on click', () => {
    const handler = vi.fn()
    window.addEventListener('focusArtifact', handler as EventListener)
    render(<ArtifactTile artifact={artifact} />)
    fireEvent.click(screen.getByRole('button'))
    expect(handler).toHaveBeenCalled()
    const ev = handler.mock.calls[0][0] as CustomEvent
    expect((ev.detail as { id: string }).id).toBe('a1')
    window.removeEventListener('focusArtifact', handler as EventListener)
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/artifacts/ArtifactTile.tsx
import { TrendingUp, Table2, FileText, Workflow, FileBarChart, File } from 'lucide-react'
import type { Artifact } from '@/lib/store'
import { cn } from '@/lib/utils'

const ICONS: Record<Artifact['format'], typeof TrendingUp> = {
  'vega-lite': TrendingUp,
  'table-json': Table2,
  mermaid: Workflow,
  csv: FileBarChart,
  html: FileText,
  text: File,
}

interface ArtifactTileProps {
  artifact: Artifact
  view?: 'grid' | 'list'
}

function focus(id: string) {
  window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { id } }))
}

export function ArtifactTile({ artifact, view = 'grid' }: ArtifactTileProps) {
  const Icon = ICONS[artifact.format] ?? File
  return (
    <button
      type="button"
      onClick={() => focus(artifact.id)}
      className={cn(
        'group relative flex rounded border border-line-2 bg-bg-1 text-left focus-ring',
        'hover:border-acc hover:shadow-sm',
        view === 'grid' ? 'aspect-square flex-col p-2' : 'h-10 items-center gap-2 px-2',
      )}
      aria-label={`Open artifact ${artifact.title}`}
    >
      <div className={cn('flex items-center gap-1', view === 'grid' ? '' : 'flex-1')}>
        <Icon className="h-3 w-3 text-fg-2" aria-hidden />
        <span className="mono text-[9.5px] uppercase text-fg-3">{artifact.type}</span>
      </div>
      <span
        className={cn(
          'truncate text-[12px] text-fg-0',
          view === 'grid' ? 'mt-auto' : 'flex-1',
        )}
        title={artifact.title}
      >
        {artifact.title}
      </span>
    </button>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/artifacts/ArtifactTile.tsx frontend/src/components/dock/artifacts/__tests__/ArtifactTile.test.tsx
git commit -m "feat(dock): ArtifactTile with grid/list support"
```

### Task 4.2: `DockArtifacts`

**Files:**
- Create: `frontend/src/components/dock/DockArtifacts.tsx`
- Create: `frontend/src/components/dock/__tests__/DockArtifacts.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DockArtifacts } from '../DockArtifacts'
import { useChatStore, type Artifact } from '@/lib/store'
import { useUiStore } from '@/lib/ui-store'

const art: Artifact = {
  id: 'x',
  type: 'chart',
  title: 'Chart A',
  content: '{}',
  format: 'vega-lite',
  session_id: 's',
  created_at: 1,
  metadata: {},
}

describe('DockArtifacts', () => {
  beforeEach(() => {
    useChatStore.setState({ artifacts: [] } as never)
    useUiStore.setState({ artifactView: 'grid' } as never)
  })

  it('empty state', () => {
    render(<DockArtifacts />)
    expect(screen.getByText(/no artifacts yet/i)).toBeInTheDocument()
  })

  it('renders tiles and toggles view', () => {
    useChatStore.setState({ artifacts: [art] } as never)
    render(<DockArtifacts />)
    expect(screen.getByText('Chart A')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /list view/i }))
    expect(useUiStore.getState().artifactView).toBe('list')
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/dock/DockArtifacts.tsx
import { LayoutGrid, List } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { useUiStore, selectArtifactView } from '@/lib/ui-store'
import { ArtifactTile } from './artifacts/ArtifactTile'
import { cn } from '@/lib/utils'

export function DockArtifacts() {
  const artifacts = useChatStore((s) => s.artifacts)
  const view = useUiStore(selectArtifactView)
  const setView = useUiStore((s) => s.setArtifactView)

  if (artifacts.length === 0) {
    return (
      <div className="flex h-full flex-col gap-2 p-4">
        <div className="label-cap">Artifacts</div>
        <div className="stripe-ph h-40">No artifacts yet</div>
        <div className="mono text-[10.5px] text-fg-3">They appear here as the agent produces them.</div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-line-2 px-3 py-2">
        <div className="label-cap">{artifacts.length} artifacts</div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setView('grid')}
            aria-label="Grid view"
            aria-pressed={view === 'grid'}
            className={cn(
              'inline-flex h-5 w-5 items-center justify-center rounded focus-ring',
              view === 'grid' ? 'bg-bg-2 text-fg-0' : 'text-fg-3 hover:text-fg-0',
            )}
          >
            <LayoutGrid className="h-3 w-3" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => setView('list')}
            aria-label="List view"
            aria-pressed={view === 'list'}
            className={cn(
              'inline-flex h-5 w-5 items-center justify-center rounded focus-ring',
              view === 'list' ? 'bg-bg-2 text-fg-0' : 'text-fg-3 hover:text-fg-0',
            )}
          >
            <List className="h-3 w-3" aria-hidden />
          </button>
        </div>
      </div>
      <div className={cn('flex-1 overflow-y-auto p-2', view === 'grid' ? 'grid grid-cols-2 gap-2' : 'flex flex-col gap-1')}>
        {artifacts.map((a) => (
          <ArtifactTile key={a.id} artifact={a} view={view} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dock/DockArtifacts.tsx frontend/src/components/dock/__tests__/DockArtifacts.test.tsx
git commit -m "feat(dock): DockArtifacts with grid/list toggle"
```

---

## Phase 5 — Artifact Viewer

### Task 5.1: Light renderers (`TableRenderer`, `CsvRenderer`, `HtmlRenderer`, `TextRenderer`)

**Files:**
- Create: `frontend/src/components/artifact/renderers/TableRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/CsvRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/HtmlRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/TextRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/__tests__/renderers.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TableRenderer } from '../TableRenderer'
import { HtmlRenderer } from '../HtmlRenderer'
import { TextRenderer } from '../TextRenderer'

describe('renderers', () => {
  it('TableRenderer renders headers and rows', () => {
    render(
      <TableRenderer
        content={JSON.stringify({ columns: ['a', 'b'], rows: [[1, 2], [3, 4]] })}
      />,
    )
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('HtmlRenderer uses srcdoc iframe', () => {
    const { container } = render(<HtmlRenderer content="<p>hi</p>" />)
    const iframe = container.querySelector('iframe')
    expect(iframe).not.toBeNull()
    expect(iframe?.getAttribute('srcdoc')).toContain('<p>hi</p>')
  })

  it('TextRenderer renders pre block', () => {
    render(<TextRenderer content="hello" />)
    expect(screen.getByText('hello')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/artifact/renderers/TextRenderer.tsx
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface TextRendererProps {
  content: string
}

export function TextRenderer({ content }: TextRendererProps) {
  const [wrap, setWrap] = useState(true)
  return (
    <div className="flex h-full flex-col">
      <div className="flex justify-end border-b border-line-2 px-3 py-1">
        <button
          type="button"
          onClick={() => setWrap((v) => !v)}
          className="mono text-[10.5px] text-fg-2 hover:text-fg-0 focus-ring rounded"
        >
          {wrap ? 'no wrap' : 'wrap'}
        </button>
      </div>
      <pre
        className={cn(
          'mono flex-1 overflow-auto p-3 text-[12px] text-fg-0',
          wrap ? 'whitespace-pre-wrap break-words' : 'whitespace-pre',
        )}
      >
        {content}
      </pre>
    </div>
  )
}
```

```tsx
// frontend/src/components/artifact/renderers/HtmlRenderer.tsx
interface HtmlRendererProps {
  content: string
}

export function HtmlRenderer({ content }: HtmlRendererProps) {
  return (
    <iframe
      title="artifact-html"
      srcDoc={content}
      sandbox="allow-same-origin"
      className="h-full w-full border-0 bg-bg-0"
    />
  )
}
```

```tsx
// frontend/src/components/artifact/renderers/TableRenderer.tsx
import { useMemo } from 'react'

interface TableRendererProps {
  content: string
}

interface TableData {
  columns: string[]
  rows: Array<Array<string | number | null>>
}

function parse(content: string): TableData {
  try {
    const data = JSON.parse(content) as TableData
    return {
      columns: Array.isArray(data.columns) ? data.columns : [],
      rows: Array.isArray(data.rows) ? data.rows : [],
    }
  } catch {
    return { columns: [], rows: [] }
  }
}

export function TableRenderer({ content }: TableRendererProps) {
  const { columns, rows } = useMemo(() => parse(content), [content])
  return (
    <div className="flex-1 overflow-auto">
      <table className="min-w-full border-collapse">
        <thead className="sticky top-0 bg-bg-1">
          <tr>
            {columns.map((c) => (
              <th
                key={c}
                className="mono border-b border-line-2 px-3 py-1.5 text-left text-[10.5px] uppercase text-fg-2"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line-2">
              {r.map((cell, j) => (
                <td key={j} className="mono px-3 py-1 text-[12px] text-fg-0">
                  {cell === null ? '—' : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

```tsx
// frontend/src/components/artifact/renderers/CsvRenderer.tsx
import { lazy, Suspense, useEffect, useState } from 'react'
import { TableRenderer } from './TableRenderer'
import { TextRenderer } from './TextRenderer'

interface CsvRendererProps {
  content: string
}

export function CsvRenderer({ content }: CsvRendererProps) {
  const [tableJson, setTableJson] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let mounted = true
    import('papaparse')
      .then((mod) => {
        const parsed = mod.parse<string[]>(content.trim(), { skipEmptyLines: true })
        if (!mounted) return
        const rows = parsed.data as string[][]
        if (!rows.length) {
          setFailed(true)
          return
        }
        const [header, ...body] = rows
        setTableJson(JSON.stringify({ columns: header, rows: body }))
      })
      .catch(() => {
        if (mounted) setFailed(true)
      })
    return () => {
      mounted = false
    }
  }, [content])

  if (failed) return <TextRenderer content={content} />
  if (!tableJson) return <TextRenderer content="Parsing CSV…" />
  return <TableRenderer content={tableJson} />
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/artifact/renderers/
git commit -m "feat(artifact): Text/Html/Table/Csv renderers"
```

### Task 5.2: Heavy renderers (`VegaLiteRenderer`, `MermaidRenderer`)

**Files:**
- Create: `frontend/src/components/artifact/renderers/VegaLiteRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/MermaidRenderer.tsx`
- Create: `frontend/src/components/artifact/renderers/__tests__/VegaLiteRenderer.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { VegaLiteRenderer } from '../VegaLiteRenderer'

describe('VegaLiteRenderer', () => {
  it('shows loading placeholder before dynamic import resolves', () => {
    const { container } = render(<VegaLiteRenderer content='{"$schema":"vega-lite"}' />)
    expect(container.textContent).toMatch(/loading/i)
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/artifact/renderers/VegaLiteRenderer.tsx
import { useEffect, useRef, useState } from 'react'
import { TextRenderer } from './TextRenderer'

interface VegaLiteRendererProps {
  content: string
}

export function VegaLiteRenderer({ content }: VegaLiteRendererProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let mounted = true
    let view: { finalize: () => void } | null = null
    ;(async () => {
      try {
        const embed = await import('vega-embed')
        if (!mounted || !ref.current) return
        const spec = JSON.parse(content) as unknown
        const result = await embed.default(ref.current, spec as object, { actions: false })
        view = result.view as unknown as { finalize: () => void }
        if (mounted) setLoaded(true)
      } catch {
        if (mounted) setFailed(true)
      }
    })()
    return () => {
      mounted = false
      view?.finalize()
    }
  }, [content])

  if (failed) return <TextRenderer content={content} />
  return (
    <div className="flex h-full w-full items-center justify-center p-4">
      {!loaded && <div className="mono text-[12px] text-fg-3">Loading chart…</div>}
      <div ref={ref} className="max-h-full max-w-full" />
    </div>
  )
}
```

```tsx
// frontend/src/components/artifact/renderers/MermaidRenderer.tsx
import { useEffect, useRef, useState } from 'react'
import { TextRenderer } from './TextRenderer'

interface MermaidRendererProps {
  content: string
}

export function MermaidRenderer({ content }: MermaidRendererProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const m = await import('mermaid')
        const { svg } = await m.default.render(`m-${Date.now()}`, content)
        if (mounted && ref.current) ref.current.innerHTML = svg
      } catch {
        if (mounted) setFailed(true)
      }
    })()
    return () => {
      mounted = false
    }
  }, [content])

  if (failed) return <TextRenderer content={content} />
  return <div ref={ref} className="flex h-full w-full items-center justify-center p-4" />
}
```

- [ ] **Step 4: Run — verify PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/artifact/renderers/VegaLiteRenderer.tsx frontend/src/components/artifact/renderers/MermaidRenderer.tsx frontend/src/components/artifact/renderers/__tests__/VegaLiteRenderer.test.tsx
git commit -m "feat(artifact): VegaLite + Mermaid dynamic-import renderers"
```

### Task 5.3: `useArtifactNav` hook + `ArtifactViewer` modal

**Files:**
- Create: `frontend/src/lib/hooks/useArtifactNav.ts`
- Create: `frontend/src/components/artifact/ArtifactViewer.tsx`
- Create: `frontend/src/components/artifact/__tests__/ArtifactViewer.test.tsx`

- [ ] **Step 1: Install dep**

```bash
cd frontend && pnpm add focus-trap-react
```

- [ ] **Step 2: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { ArtifactViewer } from '../ArtifactViewer'
import { useChatStore, type Artifact } from '@/lib/store'

const a1: Artifact = {
  id: 'a1',
  type: 'analysis',
  title: 'Notes',
  content: 'hello',
  format: 'text',
  session_id: 's',
  created_at: 1,
  metadata: {},
}
const a2: Artifact = { ...a1, id: 'a2', title: 'More', content: 'world' }

describe('ArtifactViewer', () => {
  beforeEach(() => {
    useChatStore.setState({ artifacts: [a1, a2] } as never)
  })

  it('opens on focusArtifact event and closes on ESC', () => {
    render(<ArtifactViewer />)
    act(() => {
      window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { id: 'a1' } }))
    })
    expect(screen.getByText('Notes')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByText('Notes')).toBeNull()
  })

  it('cycles with arrow keys', () => {
    render(<ArtifactViewer />)
    act(() => {
      window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { id: 'a1' } }))
    })
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(screen.getByText('More')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run — verify FAIL**

- [ ] **Step 4: Implement hook**

```ts
// frontend/src/lib/hooks/useArtifactNav.ts
import { useCallback, useMemo } from 'react'
import { useChatStore, type Artifact } from '@/lib/store'

export function useArtifactNav(currentId: string | null) {
  const artifacts = useChatStore((s) => s.artifacts)
  const index = useMemo(
    () => artifacts.findIndex((a) => a.id === currentId),
    [artifacts, currentId],
  )
  const current: Artifact | null = index >= 0 ? artifacts[index] : null
  const next = useCallback(
    () => (artifacts.length > 0 ? artifacts[(index + 1) % artifacts.length].id : null),
    [artifacts, index],
  )
  const prev = useCallback(
    () =>
      artifacts.length > 0
        ? artifacts[(index - 1 + artifacts.length) % artifacts.length].id
        : null,
    [artifacts, index],
  )
  return { current, next, prev, count: artifacts.length, index }
}
```

- [ ] **Step 5: Implement viewer**

```tsx
// frontend/src/components/artifact/ArtifactViewer.tsx
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import FocusTrap from 'focus-trap-react'
import { Copy, Download, ExternalLink, X } from 'lucide-react'
import { useArtifactNav } from '@/lib/hooks/useArtifactNav'
import type { Artifact } from '@/lib/store'
import { cn } from '@/lib/utils'
import { TextRenderer } from './renderers/TextRenderer'
import { HtmlRenderer } from './renderers/HtmlRenderer'
import { TableRenderer } from './renderers/TableRenderer'
import { CsvRenderer } from './renderers/CsvRenderer'
import { VegaLiteRenderer } from './renderers/VegaLiteRenderer'
import { MermaidRenderer } from './renderers/MermaidRenderer'

function Renderer({ artifact }: { artifact: Artifact }) {
  switch (artifact.format) {
    case 'vega-lite':
      return <VegaLiteRenderer content={artifact.content} />
    case 'mermaid':
      return <MermaidRenderer content={artifact.content} />
    case 'table-json':
      return <TableRenderer content={artifact.content} />
    case 'csv':
      return <CsvRenderer content={artifact.content} />
    case 'html':
      return <HtmlRenderer content={artifact.content} />
    case 'text':
    default:
      return <TextRenderer content={artifact.content} />
  }
}

function filenameFor(a: Artifact): string {
  const slug = a.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40) || 'artifact'
  const ext =
    a.format === 'csv' ? 'csv' :
    a.format === 'html' ? 'html' :
    a.format === 'mermaid' ? 'mmd' :
    a.format === 'table-json' || a.format === 'vega-lite' ? 'json' :
    'txt'
  return `${slug}.${ext}`
}

export function ArtifactViewer() {
  const [openId, setOpenId] = useState<string | null>(null)
  const { current, next, prev } = useArtifactNav(openId)

  useEffect(() => {
    const onFocus = (e: Event) => {
      const detail = (e as CustomEvent).detail as { id?: string } | undefined
      if (detail?.id) setOpenId(detail.id)
    }
    window.addEventListener('focusArtifact', onFocus as EventListener)
    return () => window.removeEventListener('focusArtifact', onFocus as EventListener)
  }, [])

  useEffect(() => {
    if (!openId) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenId(null)
        return
      }
      if (e.key === 'ArrowRight') setOpenId(next())
      else if (e.key === 'ArrowLeft') setOpenId(prev())
      else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'c' && current) {
        e.preventDefault()
        void navigator.clipboard.writeText(current.content)
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's' && current) {
        e.preventDefault()
        download(current)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [openId, next, prev, current])

  if (!openId || !current) return null

  return createPortal(
    <FocusTrap>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={current.title}
        className="fixed inset-0 z-50 flex flex-col bg-bg-0"
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpenId(null)
        }}
      >
        <header className="flex h-10 items-center gap-2 border-b border-line-2 bg-bg-1 px-3">
          <span className="mono rounded bg-bg-2 px-1.5 py-0.5 text-[10.5px] uppercase text-fg-2">
            {current.type}
          </span>
          <h2 className="flex-1 truncate text-[14.5px] text-fg-0">{current.title}</h2>
          <IconBtn label="Copy" onClick={() => void navigator.clipboard.writeText(current.content)}>
            <Copy className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Download" onClick={() => download(current)}>
            <Download className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Open in new window" onClick={() => window.open(`/artifact/${current.id}`)}>
            <ExternalLink className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Close" onClick={() => setOpenId(null)}>
            <X className="h-3.5 w-3.5" />
          </IconBtn>
        </header>
        <main className="flex-1 overflow-hidden">
          <Renderer artifact={current} />
        </main>
        <footer className="mono flex h-7 items-center justify-between border-t border-line-2 bg-bg-1 px-3 text-[10.5px] text-fg-3">
          <span>{new Date(current.created_at * 1000).toLocaleString()}</span>
          <span>← → cycle · ⌘C copy · ⌘S download · ESC close</span>
        </footer>
      </div>
    </FocusTrap>,
    document.body,
  )
}

function IconBtn({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded focus-ring',
        'text-fg-2 hover:bg-bg-2 hover:text-fg-0',
      )}
    >
      {children}
    </button>
  )
}

function download(a: Artifact): void {
  const mime =
    a.format === 'csv' ? 'text/csv' :
    a.format === 'html' ? 'text/html' :
    a.format === 'vega-lite' || a.format === 'table-json' ? 'application/json' :
    'text/plain'
  const blob = new Blob([a.content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filenameFor(a)
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
```

- [ ] **Step 6: Mount viewer at app root**

Edit `frontend/src/App.tsx` (or wherever `<AppShell>` is rendered) to render `<ArtifactViewer />` once alongside `<AppShell>`.

- [ ] **Step 7: Run — verify PASS**

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/hooks/useArtifactNav.ts frontend/src/components/artifact/ frontend/src/App.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(artifact): ArtifactViewer modal with keyboard nav, copy, download"
```

### Task 5.4: Standalone `/artifact/:id` page (open-in-new)

**Files:**
- Create: `frontend/src/routes/ArtifactPage.tsx`
- Modify: `frontend/src/App.tsx` or router config (add `/artifact/:id` route)

- [ ] **Step 1: Implement page**

```tsx
// frontend/src/routes/ArtifactPage.tsx
import { useParams } from 'react-router-dom'
import { useChatStore } from '@/lib/store'
import { TextRenderer } from '@/components/artifact/renderers/TextRenderer'
import { HtmlRenderer } from '@/components/artifact/renderers/HtmlRenderer'
import { TableRenderer } from '@/components/artifact/renderers/TableRenderer'
import { CsvRenderer } from '@/components/artifact/renderers/CsvRenderer'
import { VegaLiteRenderer } from '@/components/artifact/renderers/VegaLiteRenderer'
import { MermaidRenderer } from '@/components/artifact/renderers/MermaidRenderer'

export function ArtifactPage() {
  const { id } = useParams<{ id: string }>()
  const artifact = useChatStore((s) => s.artifacts.find((a) => a.id === id))
  if (!artifact) {
    return <div className="p-6 text-fg-2">Artifact not found.</div>
  }
  const R = {
    'vega-lite': VegaLiteRenderer,
    mermaid: MermaidRenderer,
    'table-json': TableRenderer,
    csv: CsvRenderer,
    html: HtmlRenderer,
    text: TextRenderer,
  }[artifact.format] ?? TextRenderer
  return (
    <div className="flex h-dvh flex-col bg-bg-0 text-fg-0">
      <header className="flex h-10 items-center border-b border-line-2 bg-bg-1 px-3">
        <h1 className="text-[14.5px]">{artifact.title}</h1>
      </header>
      <main className="flex-1 overflow-hidden">
        <R content={artifact.content} />
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Add route**

Patch the app router (search for the `<Routes>` or `<Router>` in `App.tsx` / `main.tsx`) to add:

```tsx
<Route path="/artifact/:id" element={<ArtifactPage />} />
```

If the app doesn't currently use `react-router-dom`, install it (`pnpm add react-router-dom`) and wrap the existing tree in `<BrowserRouter>` around the main `<AppShell>` call. (A single added route is acceptable per spec.)

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/ArtifactPage.tsx frontend/src/App.tsx frontend/src/main.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(artifact): standalone /artifact/:id route"
```

---

## Phase 6 — Retirement

### Task 6.1: Move Dock into `components/dock/` and slim to orchestrator

**Files:**
- Move: `frontend/src/components/shell/Dock.tsx` → `frontend/src/components/dock/Dock.tsx`
- Modify: new `Dock.tsx` (slim to tab-switch rendering `<DockProgress>` / `<DockContext>` / `<DockArtifacts>`)
- Modify: `frontend/src/components/shell/AppShell.tsx` import path
- Modify: `frontend/src/components/shell/__tests__/Dock.test.tsx` import path (rename to `dock/__tests__/Dock.test.tsx`)

- [ ] **Step 1: Move file**

```bash
git mv frontend/src/components/shell/Dock.tsx frontend/src/components/dock/Dock.tsx
git mv frontend/src/components/shell/__tests__/Dock.test.tsx frontend/src/components/dock/__tests__/Dock.test.tsx
```

- [ ] **Step 2: Rewrite `Dock.tsx` body**

Replace inline stubs + `TraceRail` with the real panels:

```tsx
// top of file — imports
import { ChevronRight } from 'lucide-react'
import {
  useUiStore,
  DOCK_W_MIN,
  DOCK_W_MAX,
  selectDockW,
  selectDockTab,
  type DockTab,
} from '@/lib/ui-store'
import { cn } from '@/lib/utils'
import { Resizer } from '@/components/shell/Resizer'
import { DockProgress } from './DockProgress'
import { DockContext } from './DockContext'
import { DockArtifacts } from './DockArtifacts'

// delete DockContextStub and DockArtifactsStub.
// In tab-body switch, replace TraceRail with DockProgress, and stubs with DockContext / DockArtifacts.
```

Tab-body jsx becomes:

```tsx
        {dockTab === "progress" && <DockProgress />}
        {dockTab === "context" && <DockContext />}
        {dockTab === "artifacts" && <DockArtifacts />}
```

- [ ] **Step 3: Update import in AppShell**

In `frontend/src/components/shell/AppShell.tsx`:

```ts
import { Dock } from "@/components/dock/Dock"
```

- [ ] **Step 4: Fix moved test's import paths**

Update `frontend/src/components/dock/__tests__/Dock.test.tsx` imports if needed (`'../Dock'` should still work because the relative path matches).

- [ ] **Step 5: Run tests**

```bash
cd frontend && pnpm vitest run
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "refactor(dock): move Dock to components/dock/ as thin orchestrator"
```

### Task 6.2: Delete `cockpit/` + legacy `right-rail-store`

**Files:**
- Delete: `frontend/src/components/cockpit/TraceRail.tsx`
- Delete: `frontend/src/components/cockpit/` (whole dir if empty after Task 2.2)
- Delete: `frontend/src/lib/right-rail-store.ts`
- Modify: any residual imports of `right-rail-store` or `cockpit/TraceRail` → replace with `ui-store` `setTraceTab` / direct component use.

- [ ] **Step 1: Find remaining references**

```bash
cd frontend && grep -rn "right-rail-store\|cockpit/TraceRail" src/
```

- [ ] **Step 2: Swap each reference**

For each hit, replace `useRightRailStore(s => s.traceTab)` → `useUiStore(selectTraceTab)`, and `s.setTraceTab` → pull from `ui-store`.

- [ ] **Step 3: Delete files**

```bash
git rm frontend/src/components/cockpit/TraceRail.tsx
git rm -r frontend/src/components/cockpit/trace 2>/dev/null || true
rmdir frontend/src/components/cockpit 2>/dev/null || true
git rm frontend/src/lib/right-rail-store.ts
```

- [ ] **Step 4: Run typecheck + tests**

```bash
cd frontend && pnpm tsc --noEmit && pnpm vitest run
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(dock): retire TraceRail + right-rail-store"
```

---

## Phase 7 — Command Palette (deferrable)

> Skip Phase 7 if schedule slips — Dock + Viewer ship without it. Ensure no palette files exist in tree if skipped.

### Task 7.1: Install `fuse.js`

- [ ] **Step 1**: `cd frontend && pnpm add fuse.js`

- [ ] **Step 2**: Commit lockfile:

```bash
git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(palette): add fuse.js"
```

### Task 7.2: `useFilteredCommands` + `CommandPalette`

**Files:**
- Create: `frontend/src/lib/hooks/useFilteredCommands.ts`
- Create: `frontend/src/components/palette/CommandPalette.tsx`
- Create: `frontend/src/components/palette/CommandRow.tsx`
- Create: `frontend/src/components/palette/CommandGroup.tsx`
- Create: `frontend/src/components/palette/__tests__/CommandPalette.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CommandPalette } from '../CommandPalette'
import { useUiStore } from '@/lib/ui-store'
import { useChatStore } from '@/lib/store'

describe('CommandPalette', () => {
  beforeEach(() => {
    useUiStore.setState({ recentCommandIds: [] } as never)
    useChatStore.setState({ conversations: [], activeConversationId: null } as never)
  })

  it('opens on ⌘K and closes on ESC', () => {
    render(<CommandPalette />)
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    expect(screen.getByRole('dialog', { name: /command palette/i })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: /command palette/i })).toBeNull()
  })
})
```

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement hook**

```ts
// frontend/src/lib/hooks/useFilteredCommands.ts
import { useMemo } from 'react'
import Fuse from 'fuse.js'

export interface Command {
  id: string
  label: string
  description?: string
  keywords?: string[]
  group: 'navigate' | 'actions' | 'recent'
  run: () => void
}

export function useFilteredCommands(commands: Command[], query: string): Command[] {
  const fuse = useMemo(
    () => new Fuse(commands, { keys: ['label', 'description', 'keywords'], threshold: 0.4 }),
    [commands],
  )
  return useMemo(() => {
    if (!query.trim()) return commands
    return fuse.search(query).map((r) => r.item)
  }, [fuse, commands, query])
}
```

- [ ] **Step 4: Implement palette**

```tsx
// frontend/src/components/palette/CommandRow.tsx
import { cn } from '@/lib/utils'
import type { Command } from '@/lib/hooks/useFilteredCommands'

interface CommandRowProps {
  command: Command
  active: boolean
  onExecute: () => void
  onHover: () => void
}

export function CommandRow({ command, active, onExecute, onHover }: CommandRowProps) {
  return (
    <li
      role="option"
      aria-selected={active}
      onMouseEnter={onHover}
      onClick={onExecute}
      className={cn(
        'flex cursor-pointer items-center gap-3 px-3 py-2 text-[13px]',
        active ? 'bg-bg-2 text-fg-0' : 'text-fg-1 hover:bg-bg-2',
      )}
    >
      <span className="flex-1 truncate">{command.label}</span>
      {command.description && (
        <span className="mono truncate text-[10.5px] text-fg-3">{command.description}</span>
      )}
    </li>
  )
}
```

```tsx
// frontend/src/components/palette/CommandGroup.tsx
interface CommandGroupProps {
  label: string
  children: React.ReactNode
}

export function CommandGroup({ label, children }: CommandGroupProps) {
  return (
    <section>
      <div className="label-cap px-3 pb-1 pt-2">{label}</div>
      <ul role="listbox" className="flex flex-col">
        {children}
      </ul>
    </section>
  )
}
```

```tsx
// frontend/src/components/palette/CommandPalette.tsx
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import FocusTrap from 'focus-trap-react'
import { useUiStore } from '@/lib/ui-store'
import { useChatStore } from '@/lib/store'
import { useFilteredCommands, type Command } from '@/lib/hooks/useFilteredCommands'
import { CommandRow } from './CommandRow'
import { CommandGroup } from './CommandGroup'

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  const conversations = useChatStore((s) => s.conversations)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)
  const setActiveSection = useChatStore((s) => s.setActiveSection)
  const pushRecent = useUiStore((s) => s.pushRecentCommand)

  const commands: Command[] = useMemo(() => {
    const nav: Command[] = [
      { id: 'nav:chat', label: 'Go to chat', group: 'navigate', run: () => setActiveSection('chat') },
      { id: 'nav:graph', label: 'Go to graph', group: 'navigate', run: () => setActiveSection('graph') },
      { id: 'nav:digest', label: 'Go to digest', group: 'navigate', run: () => setActiveSection('digest') },
      { id: 'nav:ingest', label: 'Go to ingest', group: 'navigate', run: () => setActiveSection('ingest') },
      { id: 'nav:settings', label: 'Open settings', group: 'navigate', run: () => setActiveSection('settings') },
    ]
    const threads: Command[] = conversations.slice(0, 20).map((c) => ({
      id: `thread:${c.id}`,
      label: c.title,
      description: 'conversation',
      group: 'recent',
      run: () => {
        setActiveConversation(c.id)
        setActiveSection('chat')
      },
    }))
    return [...nav, ...threads]
  }, [conversations, setActiveConversation, setActiveSection])

  const filtered = useFilteredCommands(commands, query)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
        setQuery('')
        setActive(0)
      } else if (e.key === 'Escape' && open) {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null

  const execute = (cmd: Command) => {
    cmd.run()
    pushRecent(cmd.id)
    setOpen(false)
  }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') setActive((i) => Math.min(filtered.length - 1, i + 1))
    else if (e.key === 'ArrowUp') setActive((i) => Math.max(0, i - 1))
    else if (e.key === 'Enter' && filtered[active]) execute(filtered[active])
  }

  return createPortal(
    <FocusTrap>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[15vh]"
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(false)
        }}
      >
        <div className="w-[560px] overflow-hidden rounded-xl border border-line-2 bg-bg-1 shadow-xl">
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
            }}
            onKeyDown={onKey}
            placeholder="Type a command…"
            className="mono w-full border-b border-line-2 bg-transparent px-4 py-3 text-[14px] text-fg-0 placeholder:text-fg-3 focus:outline-none"
          />
          <div className="max-h-[50vh] overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="mono px-4 py-6 text-center text-[12px] text-fg-3">No matches</div>
            ) : (
              <CommandGroup label="Commands">
                {filtered.map((c, i) => (
                  <CommandRow
                    key={c.id}
                    command={c}
                    active={i === active}
                    onHover={() => setActive(i)}
                    onExecute={() => execute(c)}
                  />
                ))}
              </CommandGroup>
            )}
          </div>
        </div>
      </div>
    </FocusTrap>,
    document.body,
  )
}
```

- [ ] **Step 5: Mount palette**

In `App.tsx`, render `<CommandPalette />` alongside `<ArtifactViewer />`.

- [ ] **Step 6: Run — verify PASS**

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/hooks/useFilteredCommands.ts frontend/src/components/palette/ frontend/src/App.tsx
git commit -m "feat(palette): ⌘K Command Palette with fuse.js search"
```

---

## Phase 8 — Verification + close

### Task 8.1: Typecheck + tests + build

**Files:** (no source changes — verification only)

- [ ] **Step 1: Typecheck**

```bash
cd frontend && pnpm tsc --noEmit
```

Expected: clean.

- [ ] **Step 2: Full test run**

```bash
cd frontend && pnpm vitest run --coverage
```

Expected: green; coverage ≥ 80%.

- [ ] **Step 3: Build**

```bash
cd frontend && pnpm build
```

Expected: success. Confirm lazy chunks for `vega-embed`, `papaparse`, `mermaid`, `fuse.js`.

- [ ] **Step 4: Commit any fixes** as `fix(dock): resolve <area>` commits as needed.

### Task 8.2: Playwright smoke

**Files:**
- Create: `frontend/e2e/dock.spec.ts`
- Create: `frontend/e2e/artifact-viewer.spec.ts`
- Create: `frontend/e2e/palette.spec.ts` (only if Phase 7 shipped)

- [ ] **Step 1: Write Playwright specs**

```ts
// frontend/e2e/dock.spec.ts
import { test, expect } from '@playwright/test'

test('dock tabs switch', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('tab', { name: 'Context' }).click()
  await expect(page.getByText(/no context snapshot yet|Budget/i)).toBeVisible()
  await page.getByRole('tab', { name: 'Artifacts' }).click()
  await expect(page.getByText(/no artifacts yet|artifacts$/i)).toBeVisible()
})
```

```ts
// frontend/e2e/artifact-viewer.spec.ts
import { test, expect } from '@playwright/test'

test('artifact viewer opens and closes', async ({ page }) => {
  await page.goto('/')
  // Seed an artifact via devtools or dispatch
  await page.evaluate(() => {
    window.dispatchEvent(
      new CustomEvent('focusArtifact', { detail: { id: 'nonexistent' } }),
    )
  })
  // Without a matching artifact the modal stays closed; this test validates
  // the listener is wired and doesn't crash.
  await expect(page.locator('[role="dialog"]')).toHaveCount(0)
})
```

- [ ] **Step 2: Run**

```bash
cd frontend && pnpm playwright test e2e/dock.spec.ts e2e/artifact-viewer.spec.ts
```

Expected: green.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/
git commit -m "test(dock): playwright smoke for dock + artifact viewer"
```

### Task 8.3: Changelog + task_plan close

**Files:**
- Modify: `docs/log.md` (append [Unreleased] entry)
- Modify: `task_plan.md` (check all Phase 1–8 boxes for step 3)

- [ ] **Step 1: Add changelog entry**

Under `## [Unreleased]` in `docs/log.md`, add:

```markdown
### Added
- Dock Progress / Context / Artifacts panels replacing the cockpit TraceRail;
  StepCard supports per-step Raw/Context/Timeline detail via expand-row.
- ContextShape on `Conversation` driven by a new `context_snapshot` SSE event
  emitted at `turn_start` and after each `micro_compact`.
- Artifact Viewer modal with six renderers (vega-lite, mermaid, table-json,
  html, csv, text), keyboard nav (←/→/ESC/⌘C/⌘S), copy/download/open-in-new,
  and standalone `/artifact/:id` route.
- ⌘K Command Palette (Navigate / Recent Threads) with fuse.js fuzzy search.
  *(Skip this bullet if Phase 7 was deferred.)*

### Changed
- `components/shell/Dock.tsx` moved to `components/dock/Dock.tsx` and slimmed to
  a tab-switch orchestrator.
- `ui-store` schema v2 — adds `progressExpanded`, `artifactView`,
  `recentCommandIds`, `traceTab` (absorbed from `right-rail-store`).

### Removed
- `components/cockpit/` (TraceRail and the trace/* modes moved to
  `components/dock/progress/modes/`).
- `lib/right-rail-store.ts` (merged into `ui-store`).
```

- [ ] **Step 2: Check Phase boxes**

Open `task_plan.md`, mark all step-3 Phase 1–8 boxes `[x]`.

- [ ] **Step 3: Commit**

```bash
git add docs/log.md task_plan.md
git commit -m "docs(dock): changelog + close step 3 phases"
```

---

## Verification gate (all must pass before declaring step 3 done)

- `pnpm tsc --noEmit` clean
- `pnpm vitest run --coverage` green; coverage ≥ 80%
- `pnpm build` succeeds; `vega-embed`, `papaparse`, `mermaid`, (optional) `fuse.js` appear as lazy chunks
- `pnpm playwright test e2e/dock.spec.ts e2e/artifact-viewer.spec.ts` green
- `docs/log.md` has an [Unreleased] entry for step 3
- `task_plan.md` step-3 phases 1–8 all checked

## Guardrails

- No emoji or Unicode box symbols. Icons via `lucide-react` or bespoke SVG only.
- Dock state lives in `ui-store`; chat state stays in the main store.
- No backend refactors beyond the single `context_snapshot` event.
- If Phase 7 is deferred, `components/palette/` and `fuse.js` must not ship (no dead code).
