# Chat Surface Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-18-chat-surface-design.md`
**Prior plan:** `docs/superpowers/plans/2026-04-18-shell-foundation.md` (shipped)
**Sub-project:** 2 of 5

**Goal:** Replace the current chat pane (`cockpit/ChatMain.tsx` + `chat/ChatInput.tsx` + `chat/MessageBubble.tsx`) with a header/composer/message triptych matching the handoff `chat.jsx` at pixel fidelity, refactored into small testable modules, with per-conversation model + extended-thinking + attached-files state.

**Architecture:** Drop a new `components/chat/ChatPane.tsx` that composes a `header/` toolbar, the existing `ChatWindow`, and a `composer/` card. Message rendering moves from a left-border bubble to a 28px-avatar tree (`message/Message.tsx`) that fans out into `Callout`, `ToolChipRow`, `ArtifactPillRow`, `SubagentCard`, and `AttachedFileChip` sub-components. Store adds three additive fields (`Conversation.model/extendedThinking/attachedFiles`), one new `ToolCallLogEntry.messageId/rows` pair, one new `ContentBlock` variant (`callout`), and six new actions; no migration rewrites existing persisted data.

**Tech Stack:** React 18 + Vite + TypeScript (strict), Zustand v5 + persist, Tailwind v3 with oklch tokens from `tokens.css`, Vitest + RTL, Playwright E2E.

---

## Conventions

- Every new component is TypeScript with an explicit props `interface` in the component file (no `React.FC`).
- Tests co-located under `__tests__/<ComponentName>.test.tsx`. Vitest `describe.each` allowed; `fireEvent` preferred over `userEvent` with fake timers.
- No new `console.log` in shipped code. Dev warnings via `window.console?.warn?.` (matches existing pattern).
- File size limits: component ≤200 lines, hook ≤200 lines, hard cap 800.
- Commit format: `<type>(chat): <desc>` — one logical change per commit.
- All color values via `tokens.css` CSS vars. Zero hex literals in new files.
- Ordering rule: store additions land first (tests with them), consumers after. No consumer ever imports a symbol that isn't exported.

## Scope Check

This plan covers the full chat surface — header, composer, messages — but intentionally excludes:
- Dock Progress tab redesign (sub-project 3)
- ThreadList / Command Palette rewrite (sub-project 4)
- Density / Tweaks panel (sub-project 5)

Each phase below compiles and tests green on its own; commits are ordered so main stays shippable even if execution stops mid-plan.

---

## Phase 0 — Prep

### Task 0.1: Read the spec with fresh eyes

**Files:** `docs/superpowers/specs/2026-04-18-chat-surface-design.md`

- [ ] **Step 1:** Read the spec top-to-bottom once. Note the six error-handling rows and the ten keyboard shortcuts — the plan MUST implement each.
- [ ] **Step 2:** Skim the handoff `design_handoff_ds_agent/chat.jsx` once. Note pixel values (`width: 28`, `padding: "10px 18px 10px 10px"`, border-radius values, `fontSize: 13`/`14`/`14.5`). These land verbatim.

Commit: none.

### Task 0.2: Branch + task tracker

- [ ] **Step 1:** Confirm on `main` and clean (no uncommitted changes). `git status` must be empty.
- [ ] **Step 2:** Update `task_plan.md` to mark sub-project 1 complete and add a sub-project 2 section pointing at this plan (append, do not rewrite):

  ```markdown
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
  ```
- [ ] **Step 3:** `git add task_plan.md && git commit -m "docs(chat): open sub-project 2 plan tracker"`

---

## Phase 1 — Store additions

### Task 1.1: Add `messageId` + `rows` to `ToolCallLogEntry`

**Files:**
- Modify: `frontend/src/lib/store.ts` (interface `ToolCallEntry` around line 67)
- Test: `frontend/src/lib/__tests__/store-toolcall.test.ts` (new)

- [ ] **Step 1: Write the failing test**

  ```ts
  // frontend/src/lib/__tests__/store-toolcall.test.ts
  import { describe, expect, it, beforeEach } from 'vitest'
  import { useChatStore } from '@/lib/store'

  describe('ToolCallLogEntry.messageId/rows', () => {
    beforeEach(() => {
      useChatStore.setState({ toolCallLog: [] })
    })

    it('stores messageId on pushToolCall', () => {
      const id = useChatStore.getState().pushToolCall({
        step: 0,
        name: 'read_file',
        inputPreview: 'q3.parquet',
        status: 'pending',
        startedAt: 0,
        messageId: 'msg-abc',
        rows: '248,913 × 42',
      })
      const entry = useChatStore.getState().toolCallLog.find((e) => e.id === id)
      expect(entry?.messageId).toBe('msg-abc')
      expect(entry?.rows).toBe('248,913 × 42')
    })
  })
  ```

- [ ] **Step 2: Run test to verify failure**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/store-toolcall.test.ts`
  Expected: FAIL — TypeScript rejects `messageId`/`rows`.

- [ ] **Step 3: Implement**

  Edit `frontend/src/lib/store.ts` — extend `ToolCallEntry`:

  ```ts
  export interface ToolCallEntry {
    id: string
    step: number
    name: string
    inputPreview: string
    status: ToolCallStatus
    preview?: string
    stdout?: string
    artifactIds?: string[]
    startedAt?: number
    finishedAt?: number
    messageId?: string          // assistant message that caused this call
    rows?: string               // e.g. "248,913 × 42", displayed on the chip
  }
  ```

- [ ] **Step 4: Run test to confirm pass**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/store-toolcall.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/lib/store.ts frontend/src/lib/__tests__/store-toolcall.test.ts
  git commit -m "feat(chat): add messageId + rows to ToolCallLogEntry"
  ```

### Task 1.2: Add `callout` variant to `ContentBlock`

**Files:**
- Modify: `frontend/src/lib/types.ts` (where `ContentBlock` union lives)
- Test: `frontend/src/lib/__tests__/types-callout.test.ts` (new)

- [ ] **Step 1:** Locate the existing `ContentBlock` union. `grep -n "export type ContentBlock" frontend/src/lib/types.ts`. If the union is declared elsewhere, adjust the import path in the next steps.

- [ ] **Step 2: Write the failing test**

  ```ts
  // frontend/src/lib/__tests__/types-callout.test.ts
  import { describe, it, expect } from 'vitest'
  import type { ContentBlock } from '@/lib/types'

  describe('ContentBlock callout variant', () => {
    it('accepts a callout block at the type level', () => {
      const block: ContentBlock = {
        type: 'callout',
        kind: 'warn',
        label: 'data quality',
        text: '31.2% null · non-random · source-correlated',
      }
      expect(block.type).toBe('callout')
    })
  })
  ```

- [ ] **Step 3: Run it to verify failure**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/types-callout.test.ts`
  Expected: TypeScript/compile error — no `callout` variant.

- [ ] **Step 4: Implement**

  Add to the existing `ContentBlock` union in `frontend/src/lib/types.ts`:

  ```ts
  export interface CalloutContent {
    type: 'callout'
    kind: 'warn' | 'err' | 'info'
    label: string
    text: string
  }

  // extend the existing union, e.g.:
  export type ContentBlock =
    | TextContent
    | ToolUseContent
    | ChartContent
    | A2aContent
    | CalloutContent
  ```

  (Preserve whatever shape the file currently has — the instruction is to ADD `CalloutContent` to the union without reordering or renaming.)

- [ ] **Step 5: Run test**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/types-callout.test.ts`
  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/src/lib/types.ts frontend/src/lib/__tests__/types-callout.test.ts
  git commit -m "feat(chat): add callout ContentBlock variant"
  ```

### Task 1.3: Add `AttachedFile` type + `Conversation.model / extendedThinking / attachedFiles`

**Files:**
- Modify: `frontend/src/lib/store.ts`
- Test: `frontend/src/lib/__tests__/store-conversation-extensions.test.ts` (new)

- [ ] **Step 1: Write the failing test**

  ```ts
  // frontend/src/lib/__tests__/store-conversation-extensions.test.ts
  import { describe, it, expect, beforeEach } from 'vitest'
  import { useChatStore } from '@/lib/store'

  describe('Conversation extensions', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
    })

    it('persists per-conversation model + extendedThinking + attachedFiles', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationModel(id, 'anthropic/claude-sonnet-4-6')
      useChatStore.getState().setConversationExtendedThinking(id, true)
      useChatStore.getState().addAttachedFile(id, {
        id: 'f1',
        name: 'q3-brief.md',
        size: 1234,
        mimeType: 'text/markdown',
      })

      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.model).toBe('anthropic/claude-sonnet-4-6')
      expect(conv.extendedThinking).toBe(true)
      expect(conv.attachedFiles).toEqual([
        { id: 'f1', name: 'q3-brief.md', size: 1234, mimeType: 'text/markdown' },
      ])
    })

    it('removeAttachedFile removes by id', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().addAttachedFile(id, { id: 'a', name: 'a', size: 1, mimeType: 't' })
      useChatStore.getState().addAttachedFile(id, { id: 'b', name: 'b', size: 1, mimeType: 't' })
      useChatStore.getState().removeAttachedFile(id, 'a')
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.attachedFiles?.map((f) => f.id)).toEqual(['b'])
    })

    it('clearAttachedFiles empties the array', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().addAttachedFile(id, { id: 'a', name: 'a', size: 1, mimeType: 't' })
      useChatStore.getState().clearAttachedFiles(id)
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.attachedFiles).toEqual([])
    })
  })
  ```

- [ ] **Step 2: Run it to verify failure**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/store-conversation-extensions.test.ts`
  Expected: FAIL — actions don't exist.

- [ ] **Step 3: Implement**

  In `frontend/src/lib/store.ts`:

  ```ts
  export interface AttachedFile {
    id: string
    name: string
    size: number
    mimeType: string
    contextRefId?: string
  }

  export interface Conversation {
    id: string
    title: string
    messages: Message[]
    createdAt: number
    updatedAt: number
    sessionId?: string
    model?: string
    extendedThinking?: boolean
    attachedFiles?: AttachedFile[]
  }
  ```

  Add to the `ChatState` interface:

  ```ts
  updateConversationModel: (id: string, modelId: string) => void
  setConversationExtendedThinking: (id: string, enabled: boolean) => void
  addAttachedFile: (conversationId: string, file: AttachedFile) => void
  removeAttachedFile: (conversationId: string, fileId: string) => void
  clearAttachedFiles: (conversationId: string) => void
  ```

  Add to the `create()((set, get) => ({ ... }))` body (immutable update pattern used throughout the file):

  ```ts
  updateConversationModel: (id, modelId) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === id ? { ...c, model: modelId, updatedAt: Date.now() } : c,
    ),
  })),
  setConversationExtendedThinking: (id, enabled) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === id ? { ...c, extendedThinking: enabled, updatedAt: Date.now() } : c,
    ),
  })),
  addAttachedFile: (conversationId, file) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === conversationId
        ? { ...c, attachedFiles: [...(c.attachedFiles ?? []), file], updatedAt: Date.now() }
        : c,
    ),
  })),
  removeAttachedFile: (conversationId, fileId) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === conversationId
        ? { ...c, attachedFiles: (c.attachedFiles ?? []).filter((f) => f.id !== fileId), updatedAt: Date.now() }
        : c,
    ),
  })),
  clearAttachedFiles: (conversationId) => set((s) => ({
    conversations: s.conversations.map((c) =>
      c.id === conversationId ? { ...c, attachedFiles: [], updatedAt: Date.now() } : c,
    ),
  })),
  ```

- [ ] **Step 4: Run test**

  Run: `pnpm --filter frontend vitest run src/lib/__tests__/store-conversation-extensions.test.ts`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/lib/store.ts frontend/src/lib/__tests__/store-conversation-extensions.test.ts
  git commit -m "feat(chat): per-conversation model, extendedThinking, attachedFiles"
  ```

### Task 1.4: `updateConversationTitle` action

**Files:**
- Modify: `frontend/src/lib/store.ts`
- Test: `frontend/src/lib/__tests__/store-title.test.ts` (new)

- [ ] **Step 1: Write the failing test**

  ```ts
  // frontend/src/lib/__tests__/store-title.test.ts
  import { describe, it, expect, beforeEach } from 'vitest'
  import { useChatStore } from '@/lib/store'

  describe('updateConversationTitle', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
    })

    it('trims and persists', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, '  new title  ')
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.title).toBe('new title')
    })

    it('caps at 200 chars', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'a'.repeat(300))
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.title.length).toBe(200)
    })

    it('ignores empty strings (keeps previous)', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'Kept')
      useChatStore.getState().updateConversationTitle(id, '   ')
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.title).toBe('Kept')
    })
  })
  ```

- [ ] **Step 2: Run it** — Expected: FAIL (action missing).

- [ ] **Step 3: Implement** in `store.ts`:

  ```ts
  // in ChatState:
  updateConversationTitle: (id: string, title: string) => void

  // in the body:
  updateConversationTitle: (id, title) => set((s) => {
    const trimmed = title.trim().slice(0, 200)
    if (!trimmed) return s
    return {
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title: trimmed, updatedAt: Date.now() } : c,
      ),
    }
  }),
  ```

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/lib/store.ts frontend/src/lib/__tests__/store-title.test.ts
  git commit -m "feat(chat): updateConversationTitle action (client-side)"
  ```

### Task 1.5: `forkConversation` action

**Files:**
- Modify: `frontend/src/lib/store.ts`
- Test: `frontend/src/lib/__tests__/store-fork.test.ts` (new)

- [ ] **Step 1: Write the failing test**

  ```ts
  // frontend/src/lib/__tests__/store-fork.test.ts
  import { describe, it, expect, beforeEach } from 'vitest'
  import { useChatStore } from '@/lib/store'

  describe('forkConversation', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
    })

    it('copies messages up through throughMessageId', () => {
      const srcId = useChatStore.getState().createConversation()
      const m1 = useChatStore.getState().addMessage(srcId, { role: 'user', content: 'a', status: 'complete' })
      const m2 = useChatStore.getState().addMessage(srcId, { role: 'assistant', content: 'b', status: 'complete' })
      useChatStore.getState().addMessage(srcId, { role: 'user', content: 'c', status: 'complete' })

      const newId = useChatStore.getState().forkConversation(srcId, m2)
      const newConv = useChatStore.getState().conversations.find((c) => c.id === newId)!
      expect(newConv.messages.length).toBe(2)
      expect(newConv.messages[0].id).toBe(m1)
      expect(newConv.messages[1].id).toBe(m2)
      expect(newConv.title).toMatch(/ \(fork\)$/)
    })

    it('copies all messages when throughMessageId is omitted', () => {
      const srcId = useChatStore.getState().createConversation()
      useChatStore.getState().addMessage(srcId, { role: 'user', content: 'a', status: 'complete' })
      useChatStore.getState().addMessage(srcId, { role: 'assistant', content: 'b', status: 'complete' })
      const newId = useChatStore.getState().forkConversation(srcId)
      const newConv = useChatStore.getState().conversations.find((c) => c.id === newId)!
      expect(newConv.messages.length).toBe(2)
    })
  })
  ```

- [ ] **Step 2: Run it** — Expected: FAIL.

- [ ] **Step 3: Implement**:

  ```ts
  // ChatState:
  forkConversation: (conversationId: string, throughMessageId?: string) => string

  // body:
  forkConversation: (conversationId, throughMessageId) => {
    const src = get().conversations.find((c) => c.id === conversationId)
    if (!src) return ''
    const cutIndex = throughMessageId
      ? src.messages.findIndex((m) => m.id === throughMessageId)
      : src.messages.length - 1
    const copied = cutIndex >= 0
      ? src.messages.slice(0, cutIndex + 1).map((m) => ({ ...m, id: nanoid() }))
      : []
    const newId = nanoid()
    set((s) => ({
      conversations: [
        ...s.conversations,
        {
          id: newId,
          title: `${src.title} (fork)`,
          messages: copied,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          sessionId: undefined,
          model: src.model,
          extendedThinking: src.extendedThinking,
          attachedFiles: [],
        },
      ],
      activeConversationId: newId,
    }))
    return newId
  },
  ```

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/lib/store.ts frontend/src/lib/__tests__/store-fork.test.ts
  git commit -m "feat(chat): forkConversation action"
  ```

### Task 1.6: Global store health check

- [ ] **Step 1:** Run the full store test suite:

  ```bash
  pnpm --filter frontend vitest run src/lib/__tests__
  ```
  Expected: ALL PASS, including pre-existing `ui-store.test.ts`.

- [ ] **Step 2:** Run typecheck:

  ```bash
  pnpm --filter frontend tsc --noEmit
  ```
  Expected: clean.

- [ ] **Step 3:** Update `task_plan.md` — mark Phase 1 complete. No commit (cosmetic).

---

## Phase 2 — Composer extraction

This phase refactors the existing 631-line `ChatInput.tsx` into small modules WITHOUT changing behavior. Each task preserves the current test suite green; the final task in this phase swaps `ChatInput` for `Composer` in its single consumer.

### Task 2.1: Extract slash-menu types + pure filter helper

**Files:**
- Create: `frontend/src/components/chat/composer/slash.ts`
- Test: `frontend/src/components/chat/composer/__tests__/slash.test.ts` (new)

- [ ] **Step 1: Write the failing test**

  ```ts
  // frontend/src/components/chat/composer/__tests__/slash.test.ts
  import { describe, it, expect } from 'vitest'
  import { filterSlashCommands } from '../slash'
  import type { SlashCommand } from '@/lib/api-backend'

  const list: SlashCommand[] = [
    { id: 'help', label: 'Help', description: '', keywords: [] },
    { id: 'clear', label: 'Clear', description: '', keywords: [] },
    { id: 'new', label: 'New chat', description: '', keywords: [] },
  ]

  describe('filterSlashCommands', () => {
    it('returns all when query empty', () => {
      expect(filterSlashCommands(list, '')).toEqual(list)
    })
    it('case-insensitive id/label match', () => {
      expect(filterSlashCommands(list, 'HE').map((c) => c.id)).toEqual(['help'])
      expect(filterSlashCommands(list, 'chat').map((c) => c.id)).toEqual(['new'])
    })
    it('returns [] when nothing matches', () => {
      expect(filterSlashCommands(list, 'xyzzy')).toEqual([])
    })
  })
  ```

- [ ] **Step 2: Run** — Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

  ```ts
  // frontend/src/components/chat/composer/slash.ts
  import type { SlashCommand } from '@/lib/api-backend'

  export function filterSlashCommands(
    commands: SlashCommand[],
    query: string,
  ): SlashCommand[] {
    const q = query.trim().toLowerCase()
    if (!q) return commands
    return commands.filter(
      (c) => c.id.toLowerCase().includes(q) || c.label.toLowerCase().includes(q),
    )
  }
  ```

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/slash.ts frontend/src/components/chat/composer/__tests__/slash.test.ts
  git commit -m "refactor(chat): extract filterSlashCommands helper"
  ```

### Task 2.2: Extract `SlashMenu` component

**Files:**
- Create: `frontend/src/components/chat/composer/SlashMenu.tsx`
- Test: `frontend/src/components/chat/composer/__tests__/SlashMenu.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

  ```tsx
  // frontend/src/components/chat/composer/__tests__/SlashMenu.test.tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { SlashMenu } from '../SlashMenu'
  import type { SlashCommand } from '@/lib/api-backend'

  const list: SlashCommand[] = [
    { id: 'help', label: 'Help', description: 'open help', keywords: [] },
    { id: 'clear', label: 'Clear', description: 'wipe thread', keywords: [] },
  ]

  describe('SlashMenu', () => {
    it('renders each command with / prefix + description', () => {
      render(<SlashMenu commands={list} highlight={0} onPick={() => {}} onHover={() => {}} />)
      expect(screen.getByText('/help')).toBeInTheDocument()
      expect(screen.getByText('open help')).toBeInTheDocument()
    })

    it('fires onPick on click', () => {
      const onPick = vi.fn()
      render(<SlashMenu commands={list} highlight={0} onPick={onPick} onHover={() => {}} />)
      fireEvent.click(screen.getByText('/clear'))
      expect(onPick).toHaveBeenCalledWith(list[1])
    })

    it('applies active styles to highlight index', () => {
      render(<SlashMenu commands={list} highlight={1} onPick={() => {}} onHover={() => {}} />)
      const rows = screen.getAllByRole('option')
      expect(rows[1].getAttribute('aria-selected')).toBe('true')
      expect(rows[0].getAttribute('aria-selected')).toBe('false')
    })
  })
  ```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/SlashMenu.tsx
  import type { SlashCommand } from '@/lib/api-backend'

  interface SlashMenuProps {
    commands: SlashCommand[]
    highlight: number
    onPick: (cmd: SlashCommand) => void
    onHover: (index: number) => void
  }

  export function SlashMenu({ commands, highlight, onPick, onHover }: SlashMenuProps) {
    if (commands.length === 0) return null
    return (
      <div
        role="listbox"
        className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-[10px] border border-[color:var(--line)] bg-[color:var(--bg-1)] shadow-[var(--shadow-2)]"
      >
        {commands.map((c, i) => {
          const active = i === highlight
          return (
            <div
              key={c.id}
              role="option"
              aria-selected={active}
              onMouseEnter={() => onHover(i)}
              onClick={() => onPick(c)}
              className="flex cursor-pointer gap-[10px] px-3 py-2 text-[13px] text-[color:var(--fg-1)]"
              style={{ background: active ? 'var(--bg-2)' : 'transparent' }}
            >
              <span className="mono w-[72px] text-[12px]" style={{ color: 'var(--acc)' }}>
                /{c.id}
              </span>
              <span style={{ color: 'var(--fg-2)' }}>{c.description || c.label}</span>
            </div>
          )
        })}
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/SlashMenu.tsx frontend/src/components/chat/composer/__tests__/SlashMenu.test.tsx
  git commit -m "refactor(chat): extract SlashMenu component"
  ```

### Task 2.3: Extract `PlanToggle` component

**Files:**
- Create: `frontend/src/components/chat/composer/PlanToggle.tsx`
- Test: `frontend/src/components/chat/composer/__tests__/PlanToggle.test.tsx` (new)

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { PlanToggle } from '../PlanToggle'

  describe('PlanToggle', () => {
    it('renders Plan label', () => {
      render(<PlanToggle enabled={false} onToggle={() => {}} />)
      expect(screen.getByRole('button', { name: /plan mode/i })).toBeInTheDocument()
    })

    it('applies active styling when enabled', () => {
      render(<PlanToggle enabled={true} onToggle={() => {}} />)
      expect(screen.getByRole('button', { name: /plan mode/i })).toHaveAttribute('data-active', 'true')
    })

    it('fires onToggle on click', () => {
      const spy = vi.fn()
      render(<PlanToggle enabled={false} onToggle={spy} />)
      fireEvent.click(screen.getByRole('button', { name: /plan mode/i }))
      expect(spy).toHaveBeenCalled()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/PlanToggle.tsx
  import { ClipboardList } from 'lucide-react'

  interface PlanToggleProps {
    enabled: boolean
    onToggle: () => void
  }

  export function PlanToggle({ enabled, onToggle }: PlanToggleProps) {
    return (
      <button
        type="button"
        aria-label="plan mode"
        data-active={enabled}
        onClick={onToggle}
        className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px] transition-colors"
        style={{
          color: enabled ? 'var(--acc)' : 'var(--fg-1)',
          background: enabled ? 'var(--acc-dim)' : 'transparent',
        }}
      >
        <ClipboardList size={12} style={{ color: enabled ? 'var(--acc)' : 'var(--fg-2)' }} />
        Plan
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/PlanToggle.tsx frontend/src/components/chat/composer/__tests__/PlanToggle.test.tsx
  git commit -m "refactor(chat): extract PlanToggle component"
  ```

### Task 2.4: Extract `useComposerSubmit` hook

This is the biggest extraction — the 200+ line streaming loop from `ChatInput.handleSubmit` moves into a hook.

**Files:**
- Create: `frontend/src/components/chat/composer/useComposerSubmit.ts`
- Test: `frontend/src/components/chat/composer/__tests__/useComposerSubmit.test.tsx` (new)

- [ ] **Step 1: Failing test** (minimal — integration-level, mocks the stream)

  ```tsx
  // frontend/src/components/chat/composer/__tests__/useComposerSubmit.test.tsx
  import { describe, it, expect, vi, beforeEach } from 'vitest'
  import { renderHook, act } from '@testing-library/react'
  import { useComposerSubmit } from '../useComposerSubmit'
  import { useChatStore } from '@/lib/store'

  vi.mock('@/lib/api-chat', () => ({
    streamChatMessage: async function* () {
      yield { type: 'turn_start', session_id: 'sess-1' }
      yield { type: 'turn_end', final_text: 'hi back' }
    },
  }))

  vi.mock('@/lib/api-backend', () => ({
    backend: {
      conversations: {
        appendTurn: vi.fn().mockResolvedValue({}),
      },
    },
  }))

  describe('useComposerSubmit', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null, toolCallLog: [] })
    })

    it('appends a user + assistant message and completes the stream', async () => {
      const convId = useChatStore.getState().createConversation()
      const { result } = renderHook(() => useComposerSubmit(convId))
      await act(async () => {
        await result.current.submit('hi')
      })
      const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
      expect(conv.messages).toHaveLength(2)
      expect(conv.messages[0].role).toBe('user')
      expect(conv.messages[1].role).toBe('assistant')
      expect(conv.messages[1].status).toBe('complete')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement** — move `handleSubmit` from `ChatInput.tsx` into the hook. The hook exposes `{ submit, stop, isSending, error, clearError }`. Use `messageId: assistantId` on every `pushToolCall(...)`. When available in the conversation, include `model` and `extendedThinking` in the stream options.

  ```ts
  // frontend/src/components/chat/composer/useComposerSubmit.ts
  import { useCallback, useRef, useState } from 'react'
  import { nanoid } from 'nanoid'
  import { useChatStore } from '@/lib/store'
  import { useDevtoolsStore } from '@/stores/devtools'
  import { streamChatMessage } from '@/lib/api-chat'
  import { backend } from '@/lib/api-backend'
  import type { A2aContent, ContentBlock } from '@/lib/types'
  import type { Artifact } from '@/lib/store'

  export interface ComposerSubmitResult {
    submit: (text: string) => Promise<void>
    stop: () => void
    isSending: boolean
    error: string | null
    clearError: () => void
  }

  export function useComposerSubmit(conversationId: string): ComposerSubmitResult {
    const [isSending, setIsSending] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)

    const submit = useCallback(
      async (rawText: string) => {
        const text = rawText.trim()
        if (!text || isSending) return

        const state = useChatStore.getState()
        const conversation = state.conversations.find((c) => c.id === conversationId)
        const {
          addMessage, updateMessage, setConversationSessionId,
          pushToolCall, updateToolCallById, clearToolCallLog,
          setScratchpad, clearScratchpad, setTodos, clearTodos,
          setRightPanelTab, addArtifact, clearArtifacts,
          clearAttachedFiles,
        } = state

        setError(null)
        setIsSending(true)
        const controller = new AbortController()
        abortControllerRef.current = controller

        addMessage(conversationId, { role: 'user', content: text, status: 'complete' })
        backend.conversations.appendTurn(conversationId, 'user', text)
          .catch((err: unknown) => window.console?.warn?.('persist user turn failed', err))

        const assistantId = addMessage(conversationId, {
          role: 'assistant', content: '', status: 'sending',
        })

        clearToolCallLog(); clearScratchpad(); clearTodos(); clearArtifacts()

        const pendingToolCallIds = new Map<string, string>()
        const a2aBlocksByStep = new Map<number, A2aContent>()
        let finalSessionId = conversation?.sessionId ?? null
        let finalResponseText = ''

        try {
          const stream = streamChatMessage(text, conversation?.sessionId ?? null, {
            planMode: useChatStore.getState().planMode,
            signal: controller.signal,
            // Forward per-conversation overrides; backend ignores unknown keys.
            ...(conversation?.model ? { model: conversation.model } : {}),
            ...(conversation?.extendedThinking ? { extendedThinking: true } : {}),
          } as Parameters<typeof streamChatMessage>[2])

          for await (const event of stream) {
            if (event.type === 'turn_start') {
              if (event.session_id) finalSessionId = event.session_id
              updateMessage(conversationId, assistantId, { status: 'streaming' })
            } else if (event.type === 'tool_call') {
              setRightPanelTab('tools')
              const entryKey = `${event.step}-${event.name}`
              const storeId = pushToolCall({
                step: event.step ?? 0,
                name: event.name ?? '',
                inputPreview: event.input_preview ?? '',
                status: 'pending',
                startedAt: Date.now(),
                messageId: assistantId,
              })
              pendingToolCallIds.set(entryKey, storeId)
            } else if (event.type === 'tool_result') {
              const entryKey = `${event.step}-${event.name}`
              const storeId = pendingToolCallIds.get(entryKey)
              if (storeId) {
                updateToolCallById(storeId, {
                  status: event.status ?? 'ok',
                  preview: event.preview,
                  stdout: event.stdout ?? event.preview ?? '',
                  artifactIds: event.artifact_ids,
                  finishedAt: Date.now(),
                })
              }
            } else if (event.type === 'a2a_start') {
              const block: A2aContent = {
                type: 'a2a', task: event.task_preview ?? '',
                artifactId: '', summary: '', status: 'pending',
              }
              a2aBlocksByStep.set(event.step ?? 0, block)
              updateMessage(conversationId, assistantId, {
                content: [...a2aBlocksByStep.values()] as ContentBlock[],
              })
            } else if (event.type === 'a2a_end') {
              const step = event.step ?? 0
              const existing = a2aBlocksByStep.get(step)
              if (existing) {
                a2aBlocksByStep.set(step, {
                  ...existing,
                  artifactId: event.artifact_id ?? '',
                  summary: event.summary ?? '',
                  status: event.ok !== false ? 'complete' : 'error',
                })
                updateMessage(conversationId, assistantId, {
                  content: [...a2aBlocksByStep.values()] as ContentBlock[],
                })
              }
            } else if (event.type === 'artifact') {
              const artifact: Artifact = {
                id: event.id ?? nanoid(),
                type: (event.artifact_type as Artifact['type']) ?? 'chart',
                title: event.title ?? 'Artifact',
                content: event.artifact_content ?? '',
                format: (event.format as Artifact['format']) ?? 'vega-lite',
                session_id: event.session_id ?? '',
                created_at: event.created_at ?? Date.now() / 1000,
                metadata: event.artifact_metadata ?? {},
              }
              addArtifact(artifact)
              const currentConv = useChatStore.getState().conversations.find((c) => c.id === conversationId)
              const currentMsg = currentConv?.messages.find((m) => m.id === assistantId)
              updateMessage(conversationId, assistantId, {
                artifactIds: [...(currentMsg?.artifactIds ?? []), artifact.id],
              })
              setRightPanelTab('artifacts')
            } else if (event.type === 'scratchpad_delta') {
              setScratchpad(event.content ?? '')
            } else if (event.type === 'todos_update') {
              setTodos(event.todos ?? [])
            } else if (event.type === 'micro_compact') {
              const saved = (event.tokens_before ?? 0) - (event.tokens_after ?? 0)
              const now = Date.now()
              pushToolCall({
                step: event.step ?? 0,
                name: '__compact__',
                inputPreview: '',
                status: 'ok',
                preview: `compacted ${event.dropped_messages ?? 0} msgs · ~${saved.toLocaleString()} tokens freed`,
                startedAt: now,
                finishedAt: now,
                messageId: assistantId,
              })
            } else if (event.type === 'turn_end') {
              finalResponseText = event.final_text ?? ''
              const charts = event.charts ?? []
              const a2aBlocks = [...a2aBlocksByStep.values()] as ContentBlock[]
              const textBlock = finalResponseText
                ? [{ type: 'text' as const, text: finalResponseText }]
                : []

              const currentConvState = useChatStore.getState().conversations.find((c) => c.id === conversationId)
              const currentMsgState = currentConvState?.messages.find((m) => m.id === assistantId)
              const alreadyHasArtifacts = (currentMsgState?.artifactIds ?? []).length > 0
              if (!alreadyHasArtifacts && charts.length > 0) {
                const newArtifactIds: string[] = []
                for (const spec of charts) {
                  const artifactId = nanoid()
                  addArtifact({
                    id: artifactId,
                    type: 'chart',
                    title: typeof spec.title === 'string' ? spec.title : 'Chart',
                    content: JSON.stringify(spec),
                    format: 'vega-lite',
                    session_id: finalSessionId ?? '',
                    created_at: Date.now() / 1000,
                    metadata: {},
                  })
                  newArtifactIds.push(artifactId)
                }
                updateMessage(conversationId, assistantId, { artifactIds: newArtifactIds })
                if (charts.length > 0) setRightPanelTab('artifacts')
              }

              const content: ContentBlock[] | string =
                a2aBlocks.length > 0 ? [...a2aBlocks, ...textBlock] : finalResponseText
              updateMessage(conversationId, assistantId, {
                content, status: 'complete',
                traceId: finalSessionId ?? undefined,
              })
              if (finalSessionId) setConversationSessionId(conversationId, finalSessionId)
            } else if (event.type === 'error') {
              const msg = event.message ?? 'Agent error'
              updateMessage(conversationId, assistantId, { content: msg, status: 'error' })
              setError(msg)
              return
            }
          }

          if (finalSessionId) {
            setConversationSessionId(conversationId, finalSessionId)
            const devtools = useDevtoolsStore.getState()
            devtools.setSelectedTrace(finalSessionId)
            devtools.setActiveTab('traces')
          }
          if (finalResponseText) {
            backend.conversations.appendTurn(conversationId, 'assistant', finalResponseText)
              .catch((err: unknown) => window.console?.warn?.('persist assistant turn failed', err))
          }
          clearAttachedFiles(conversationId)
        } catch (err) {
          if (err instanceof Error && err.name === 'AbortError') {
            updateMessage(conversationId, assistantId, { status: 'complete' })
          } else {
            const msg = err instanceof Error ? err.message : 'Unknown error'
            updateMessage(conversationId, assistantId, { content: msg, status: 'error' })
            setError(msg)
          }
        } finally {
          setIsSending(false)
          abortControllerRef.current = null
        }
      },
      [conversationId, isSending],
    )

    const stop = useCallback(() => {
      abortControllerRef.current?.abort()
    }, [])

    const clearError = useCallback(() => setError(null), [])

    return { submit, stop, isSending, error, clearError }
  }
  ```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/useComposerSubmit.ts frontend/src/components/chat/composer/__tests__/useComposerSubmit.test.tsx
  git commit -m "refactor(chat): extract useComposerSubmit hook"
  ```

### Task 2.5: Create `Composer.tsx` shell (textarea + slash + plan, no new features yet)

**Files:**
- Create: `frontend/src/components/chat/composer/Composer.tsx`
- Test: `frontend/src/components/chat/composer/__tests__/Composer.test.tsx` (new)

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { Composer } from '../Composer'
  import { useChatStore } from '@/lib/store'

  describe('Composer', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
    })

    it('renders textarea with placeholder', () => {
      const id = useChatStore.getState().createConversation()
      render(<Composer conversationId={id} />)
      expect(screen.getByPlaceholderText(/ask the agent/i)).toBeInTheDocument()
    })

    it('disables send when empty', () => {
      const id = useChatStore.getState().createConversation()
      render(<Composer conversationId={id} />)
      expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
    })

    it('enables send once text typed', () => {
      const id = useChatStore.getState().createConversation()
      render(<Composer conversationId={id} />)
      const ta = screen.getByPlaceholderText(/ask the agent/i)
      fireEvent.change(ta, { target: { value: 'hello' } })
      expect(screen.getByRole('button', { name: /^send$/i })).toBeEnabled()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement** — a card-shaped composer with auto-resize textarea, slash menu, plan toggle, send/stop. Do not include ModelPicker / Extended / IconRow yet — those land in Phase 3.

  ```tsx
  // frontend/src/components/chat/composer/Composer.tsx
  import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
  import { Send, Square } from 'lucide-react'
  import { useChatStore } from '@/lib/store'
  import { useCommandRegistry } from '@/hooks/useCommandRegistry'
  import { backend, type SlashCommand } from '@/lib/api-backend'
  import { MAX_MESSAGE_LENGTH } from '@/lib/constants'
  import { filterSlashCommands } from './slash'
  import { SlashMenu } from './SlashMenu'
  import { PlanToggle } from './PlanToggle'
  import { useComposerSubmit } from './useComposerSubmit'

  interface ComposerProps {
    conversationId: string
  }

  export function Composer({ conversationId }: ComposerProps) {
    const [input, setInput] = useState('')
    const [slashCommands, setSlashCommands] = useState<SlashCommand[] | null>(null)
    const [slashHighlight, setSlashHighlight] = useState(0)
    const [slashLocked, setSlashLocked] = useState(false)
    const slashFetchRef = useRef<Promise<SlashCommand[]> | null>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const draftInput = useChatStore((s) => s.draftInput)
    const setDraftInput = useChatStore((s) => s.setDraftInput)
    const planMode = useChatStore((s) => s.planMode)
    const togglePlanMode = useChatStore((s) => s.togglePlanMode)
    const clearActiveConversation = useChatStore((s) => s.clearActiveConversation)
    const createConversation = useChatStore((s) => s.createConversation)
    const setActiveSection = useChatStore((s) => s.setActiveSection)
    const { openHelp } = useCommandRegistry()
    const { submit, stop, isSending, error } = useComposerSubmit(conversationId)

    const adjustHeight = useCallback(() => {
      const el = textareaRef.current
      if (!el) return
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    }, [])

    useEffect(() => {
      if (!draftInput) return
      setInput(draftInput); setDraftInput('')
      requestAnimationFrame(() => { adjustHeight(); textareaRef.current?.focus() })
    }, [draftInput, setDraftInput, adjustHeight])

    const showSlashMenu = input.startsWith('/') && !slashLocked
    const slashQuery = showSlashMenu ? input.slice(1) : ''
    const filtered = useMemo(
      () => (showSlashMenu && slashCommands ? filterSlashCommands(slashCommands, slashQuery) : []),
      [slashCommands, slashQuery, showSlashMenu],
    )

    useEffect(() => {
      if (slashHighlight >= filtered.length) setSlashHighlight(0)
    }, [filtered.length, slashHighlight])

    useEffect(() => {
      if (!showSlashMenu || slashCommands !== null || slashFetchRef.current) return
      slashFetchRef.current = backend.slash.list()
        .then((list) => { setSlashCommands(list); return list })
        .catch((err: unknown) => {
          window.console?.warn?.('slash list failed', err)
          setSlashCommands([])
          return []
        })
    }, [showSlashMenu, slashCommands])

    const pickSlashCommand = useCallback(
      (cmd: SlashCommand) => {
        switch (cmd.id) {
          case 'help': openHelp(); break
          case 'clear': clearActiveConversation(); break
          case 'new': createConversation(); break
          case 'settings': setActiveSection('settings'); break
        }
        setInput(''); setSlashLocked(true)
        requestAnimationFrame(() => { textareaRef.current?.focus(); adjustHeight() })
      },
      [openHelp, clearActiveConversation, createConversation, setActiveSection, adjustHeight],
    )

    const handleSend = useCallback(async () => {
      const text = input
      setInput('')
      requestAnimationFrame(() => adjustHeight())
      await submit(text)
    }, [input, submit, adjustHeight])

    const hasText = input.trim().length > 0

    return (
      <div className="relative">
        {showSlashMenu && (
          <SlashMenu
            commands={filtered}
            highlight={slashHighlight}
            onHover={setSlashHighlight}
            onPick={pickSlashCommand}
          />
        )}
        <div
          className="rounded-[12px] border p-[10px]"
          style={{ borderColor: 'var(--line)', background: 'var(--bg-1)', boxShadow: 'var(--shadow-1)' }}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => {
              setInput(e.target.value.slice(0, MAX_MESSAGE_LENGTH))
              setSlashLocked(false)
              adjustHeight()
            }}
            placeholder="Ask the agent anything…"
            className="min-h-[22px] w-full resize-none bg-transparent px-1 pb-0.5 pt-1 text-[14px] leading-[1.55] outline-none"
            style={{ color: 'var(--fg-0)' }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (showSlashMenu && filtered[slashHighlight]) {
                  pickSlashCommand(filtered[slashHighlight]); return
                }
                handleSend()
              }
            }}
          />
          <div className="mt-1 flex items-center gap-1">
            <PlanToggle enabled={planMode} onToggle={togglePlanMode} />
            <div className="flex-1" />
            <span className="mr-1 flex items-center gap-[3px] text-[11px]" style={{ color: 'var(--fg-3)' }}>
              <span className="kbd">⌘</span><span className="kbd">↵</span>
            </span>
            {isSending ? (
              <button
                type="button"
                onClick={stop}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium"
                style={{ background: 'var(--bg-2)', color: 'var(--fg-1)' }}
              >
                <Square size={12} /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!hasText}
                aria-label="Send"
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed"
                style={{
                  background: hasText ? 'var(--acc)' : 'var(--bg-2)',
                  color: hasText ? 'var(--acc-fg)' : 'var(--fg-3)',
                }}
              >
                Send <Send size={12} />
              </button>
            )}
          </div>
          {error && (
            <div className="mt-2 text-[12px]" style={{ color: 'var(--err)' }}>{error}</div>
          )}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/Composer.tsx frontend/src/components/chat/composer/__tests__/Composer.test.tsx
  git commit -m "refactor(chat): Composer shell with textarea + slash + plan toggle"
  ```

### Task 2.6: Swap `ChatInput` for `Composer` inside `ChatMain`

**Files:**
- Modify: `frontend/src/components/cockpit/ChatMain.tsx`

- [ ] **Step 1:** Replace the `<ChatInput conversationId=… />` import + render site with `<Composer conversationId=… />`.
- [ ] **Step 2:** Run the full suite:

  ```bash
  pnpm --filter frontend vitest run
  pnpm --filter frontend tsc --noEmit
  ```
  Expected: GREEN. If `chat-input.test.tsx` still references legacy `ChatInput`, keep the old file around for now — it stays until Phase 6 retirement.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/cockpit/ChatMain.tsx
  git commit -m "refactor(chat): ChatMain uses new Composer"
  ```

---

## Phase 3 — Composer parity surfaces

Adds IconRow / ModelPicker / ExtendedToggle / AttachedFilesPreview. Each slot into `Composer.tsx`'s footer row in handoff order: **IconRow | divider | Model | Extended | Plan | ⌘↵ | Send**.

### Task 3.1: `AttachButton` stub component

**Files:**
- Create: `frontend/src/components/chat/composer/AttachButton.tsx`
- Test: `__tests__/AttachButton.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { AttachButton } from '../AttachButton'
  import { useChatStore } from '@/lib/store'

  describe('AttachButton', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
    })

    it('opens file picker and adds attached file on success', async () => {
      const id = useChatStore.getState().createConversation()
      const { container } = render(<AttachButton conversationId={id} />)
      const input = container.querySelector('input[type="file"]')!
      const file = new File(['hi'], 'note.md', { type: 'text/markdown' })
      Object.defineProperty(input, 'files', { value: [file] })
      fireEvent.change(input)
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.attachedFiles?.[0].name).toBe('note.md')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/AttachButton.tsx
  import { useRef } from 'react'
  import { nanoid } from 'nanoid'
  import { Paperclip } from 'lucide-react'
  import { useChatStore } from '@/lib/store'

  const ICON_BTN = 'flex h-7 w-7 items-center justify-center rounded-md transition-colors'

  interface AttachButtonProps {
    conversationId: string
  }

  export function AttachButton({ conversationId }: AttachButtonProps) {
    const inputRef = useRef<HTMLInputElement>(null)
    const addAttachedFile = useChatStore((s) => s.addAttachedFile)

    const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      addAttachedFile(conversationId, {
        id: nanoid(),
        name: file.name,
        size: file.size,
        mimeType: file.type || 'application/octet-stream',
      })
      e.target.value = ''
    }

    return (
      <>
        <input ref={inputRef} type="file" className="hidden" onChange={onPick} />
        <button
          type="button"
          title="Attach file"
          aria-label="Attach file"
          onClick={() => inputRef.current?.click()}
          className={ICON_BTN}
          style={{ color: 'var(--fg-2)' }}
        >
          <Paperclip size={14} />
        </button>
      </>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/AttachButton.tsx frontend/src/components/chat/composer/__tests__/AttachButton.test.tsx
  git commit -m "feat(chat): AttachButton writes to attachedFiles store"
  ```

### Task 3.2: `MentionButton` + `SkillButton` stubs

Both are inert buttons that prefix the textarea with `@` / `#` (they rely on slash-menu expansion landing in a later sub-project). Current behaviour: click inserts the character at caret.

**Files:**
- Create: `frontend/src/components/chat/composer/MentionButton.tsx`
- Create: `frontend/src/components/chat/composer/SkillButton.tsx`
- Test: `__tests__/MentionButton.test.tsx` (covers both via generic props)

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { MentionButton } from '../MentionButton'

  describe('MentionButton', () => {
    it('calls onInsert("@") on click', () => {
      const spy = vi.fn()
      render(<MentionButton onInsert={spy} />)
      fireEvent.click(screen.getByRole('button', { name: /mention/i }))
      expect(spy).toHaveBeenCalledWith('@')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // MentionButton.tsx
  import { AtSign } from 'lucide-react'

  interface MentionButtonProps { onInsert: (token: string) => void }
  export function MentionButton({ onInsert }: MentionButtonProps) {
    return (
      <button
        type="button" aria-label="Mention file"
        onClick={() => onInsert('@')}
        className="flex h-7 w-7 items-center justify-center rounded-md"
        style={{ color: 'var(--fg-2)' }}
      >
        <AtSign size={14} />
      </button>
    )
  }
  ```

  ```tsx
  // SkillButton.tsx
  import { Hash } from 'lucide-react'

  interface SkillButtonProps { onInsert: (token: string) => void }
  export function SkillButton({ onInsert }: SkillButtonProps) {
    return (
      <button
        type="button" aria-label="Skill"
        onClick={() => onInsert('#')}
        className="flex h-7 w-7 items-center justify-center rounded-md"
        style={{ color: 'var(--fg-2)' }}
      >
        <Hash size={14} />
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/MentionButton.tsx frontend/src/components/chat/composer/SkillButton.tsx frontend/src/components/chat/composer/__tests__/MentionButton.test.tsx
  git commit -m "feat(chat): MentionButton + SkillButton prefix insert"
  ```

### Task 3.3: `VoiceButton` with feature detect

**Files:**
- Create: `frontend/src/components/chat/composer/VoiceButton.tsx`
- Test: `__tests__/VoiceButton.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach, afterEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { VoiceButton } from '../VoiceButton'

  describe('VoiceButton', () => {
    const origSR = (window as any).SpeechRecognition
    const origWSR = (window as any).webkitSpeechRecognition

    afterEach(() => {
      ;(window as any).SpeechRecognition = origSR
      ;(window as any).webkitSpeechRecognition = origWSR
    })

    it('returns null when SpeechRecognition is unavailable', () => {
      delete (window as any).SpeechRecognition
      delete (window as any).webkitSpeechRecognition
      const { container } = render(<VoiceButton onTranscript={() => {}} />)
      expect(container.firstChild).toBeNull()
    })

    it('renders button when available', () => {
      ;(window as any).SpeechRecognition = class {}
      render(<VoiceButton onTranscript={() => {}} />)
      expect(screen.getByRole('button', { name: /voice/i })).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/VoiceButton.tsx
  import { useEffect, useRef, useState } from 'react'
  import { Mic, MicOff } from 'lucide-react'

  interface VoiceButtonProps {
    onTranscript: (text: string) => void
  }

  export function VoiceButton({ onTranscript }: VoiceButtonProps) {
    const [supported, setSupported] = useState(false)
    const [active, setActive] = useState(false)
    const recognitionRef = useRef<any>(null)

    useEffect(() => {
      const w = window as any
      setSupported(Boolean(w.SpeechRecognition || w.webkitSpeechRecognition))
    }, [])

    const start = () => {
      const w = window as any
      const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
      if (!Ctor) return
      const r = new Ctor()
      r.continuous = false
      r.interimResults = false
      r.onresult = (e: any) => {
        const text = e.results?.[0]?.[0]?.transcript ?? ''
        if (text) onTranscript(text)
      }
      r.onend = () => setActive(false)
      r.onerror = () => setActive(false)
      try { r.start(); setActive(true) } catch { setActive(false) }
      recognitionRef.current = r
    }

    const stop = () => {
      recognitionRef.current?.stop?.()
      setActive(false)
    }

    if (!supported) return null
    return (
      <button
        type="button"
        aria-label="Voice"
        data-active={active}
        onClick={() => (active ? stop() : start())}
        className="flex h-7 w-7 items-center justify-center rounded-md"
        style={{ color: active ? 'var(--acc)' : 'var(--fg-2)' }}
      >
        {active ? <MicOff size={14} /> : <Mic size={14} />}
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/VoiceButton.tsx frontend/src/components/chat/composer/__tests__/VoiceButton.test.tsx
  git commit -m "feat(chat): VoiceButton with feature detect"
  ```

### Task 3.4: `IconRow` composition component

**Files:**
- Create: `frontend/src/components/chat/composer/IconRow.tsx`
- Test: `__tests__/IconRow.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { IconRow } from '../IconRow'
  import { useChatStore } from '@/lib/store'

  describe('IconRow', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('renders attach + mention + skill buttons', () => {
      const id = useChatStore.getState().createConversation()
      render(<IconRow conversationId={id} onInsert={() => {}} onTranscript={() => {}} />)
      expect(screen.getByRole('button', { name: /attach/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /mention/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /skill/i })).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/IconRow.tsx
  import { AttachButton } from './AttachButton'
  import { MentionButton } from './MentionButton'
  import { SkillButton } from './SkillButton'
  import { VoiceButton } from './VoiceButton'

  interface IconRowProps {
    conversationId: string
    onInsert: (token: string) => void
    onTranscript: (text: string) => void
  }

  export function IconRow({ conversationId, onInsert, onTranscript }: IconRowProps) {
    return (
      <div className="flex items-center gap-0.5">
        <AttachButton conversationId={conversationId} />
        <MentionButton onInsert={onInsert} />
        <SkillButton onInsert={onInsert} />
        <VoiceButton onTranscript={onTranscript} />
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/IconRow.tsx frontend/src/components/chat/composer/__tests__/IconRow.test.tsx
  git commit -m "feat(chat): IconRow composes composer icon cluster"
  ```

### Task 3.5: `ModelPicker` with `/api/models` fetch + fallback

**Files:**
- Create: `frontend/src/components/chat/composer/ModelPicker.tsx`
- Test: `__tests__/ModelPicker.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { render, screen, fireEvent, waitFor } from '@testing-library/react'
  import { ModelPicker } from '../ModelPicker'
  import { useChatStore } from '@/lib/store'

  vi.mock('@/lib/api-backend', () => ({
    backend: {
      models: {
        list: vi.fn().mockResolvedValue({
          groups: [
            {
              provider: 'anthropic', label: 'Anthropic', available: true, note: '',
              models: [
                { id: 'anthropic/claude-sonnet-4-6', label: 'Sonnet 4.6', description: '' },
                { id: 'anthropic/claude-opus-4-7', label: 'Opus 4.7', description: '' },
              ],
            },
          ],
        }),
      },
    },
  }))

  describe('ModelPicker', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('renders label of active model', async () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationModel(id, 'anthropic/claude-opus-4-7')
      render(<ModelPicker conversationId={id} />)
      await waitFor(() => expect(screen.getByText('Opus 4.7')).toBeInTheDocument())
    })

    it('opens popover and persists selection', async () => {
      const id = useChatStore.getState().createConversation()
      render(<ModelPicker conversationId={id} />)
      fireEvent.click(screen.getByRole('button', { name: /model/i }))
      await waitFor(() => expect(screen.getByText('Opus 4.7')).toBeInTheDocument())
      fireEvent.click(screen.getByText('Opus 4.7'))
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.model).toBe('anthropic/claude-opus-4-7')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/ModelPicker.tsx
  import { useCallback, useEffect, useMemo, useState } from 'react'
  import { Cpu, ChevronDown } from 'lucide-react'
  import { useChatStore } from '@/lib/store'
  import { backend, type ModelEntry } from '@/lib/api-backend'

  const FALLBACK_MODELS: ModelEntry[] = [
    { id: 'anthropic/claude-sonnet-4-6', label: 'Sonnet 4.6', description: '' },
  ]

  interface ModelPickerProps {
    conversationId: string
  }

  export function ModelPicker({ conversationId }: ModelPickerProps) {
    const [models, setModels] = useState<ModelEntry[] | null>(null)
    const [open, setOpen] = useState(false)
    const [loadError, setLoadError] = useState(false)
    const conversation = useChatStore((s) => s.conversations.find((c) => c.id === conversationId))
    const updateConversationModel = useChatStore((s) => s.updateConversationModel)

    useEffect(() => {
      let alive = true
      backend.models.list()
        .then((res) => {
          if (!alive) return
          const flat = res.groups.flatMap((g) => g.models)
          setModels(flat.length > 0 ? flat : FALLBACK_MODELS)
        })
        .catch(() => {
          if (!alive) return
          setModels(FALLBACK_MODELS); setLoadError(true)
        })
      return () => { alive = false }
    }, [])

    const active = useMemo(() => {
      const source = models ?? FALLBACK_MODELS
      return source.find((m) => m.id === conversation?.model) ?? source[0]
    }, [models, conversation?.model])

    const pick = useCallback((m: ModelEntry) => {
      updateConversationModel(conversationId, m.id); setOpen(false)
    }, [conversationId, updateConversationModel])

    const cycleTo = useCallback((dir: 1 | -1) => {
      const list = models ?? FALLBACK_MODELS
      const idx = list.findIndex((m) => m.id === active?.id)
      const next = list[(idx + dir + list.length) % list.length]
      if (next) updateConversationModel(conversationId, next.id)
    }, [models, active?.id, conversationId, updateConversationModel])

    // Expose cycleTo on window so keyboard-shortcut handler can call it.
    useEffect(() => {
      ;(window as any).__dsAgentCycleModel = (dir: 1 | -1) => cycleTo(dir)
      return () => { delete (window as any).__dsAgentCycleModel }
    }, [cycleTo])

    return (
      <div className="relative">
        <button
          type="button"
          aria-label="model"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px]"
          style={{ color: 'var(--fg-1)' }}
        >
          <Cpu size={12} style={{ color: 'var(--fg-2)' }} />
          {active?.label ?? 'Model'}
          <ChevronDown size={10} style={{ color: 'var(--fg-3)' }} />
        </button>
        {loadError && (
          <span className="ml-1 text-[10.5px]" style={{ color: 'var(--warn)' }} title="Model list unavailable">!</span>
        )}
        {open && (
          <div
            role="listbox"
            className="absolute bottom-full left-0 mb-2 min-w-[180px] overflow-hidden rounded-[10px] border bg-[color:var(--bg-1)] shadow-[var(--shadow-2)]"
            style={{ borderColor: 'var(--line)' }}
          >
            {(models ?? FALLBACK_MODELS).map((m) => (
              <div
                key={m.id}
                role="option"
                aria-selected={m.id === active?.id}
                onClick={() => pick(m)}
                className="cursor-pointer px-3 py-2 text-[12.5px]"
                style={{
                  color: 'var(--fg-1)',
                  background: m.id === active?.id ? 'var(--bg-2)' : 'transparent',
                }}
              >
                {m.label}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/ModelPicker.tsx frontend/src/components/chat/composer/__tests__/ModelPicker.test.tsx
  git commit -m "feat(chat): ModelPicker reads /api/models, per-conv persist, fallback"
  ```

### Task 3.6: `ExtendedToggle`

**Files:**
- Create: `frontend/src/components/chat/composer/ExtendedToggle.tsx`
- Test: `__tests__/ExtendedToggle.test.tsx`

Spec Q: `ModelEntry` lacks a `capabilities` field. Decision: Extended toggle is always enabled; per-conversation state persists. If a downstream backend rejects the combo, the stream error already surfaces via the Composer error row.

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ExtendedToggle } from '../ExtendedToggle'
  import { useChatStore } from '@/lib/store'

  describe('ExtendedToggle', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('flips extendedThinking on click', () => {
      const id = useChatStore.getState().createConversation()
      render(<ExtendedToggle conversationId={id} />)
      fireEvent.click(screen.getByRole('button', { name: /extended/i }))
      const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv.extendedThinking).toBe(true)
      fireEvent.click(screen.getByRole('button', { name: /extended/i }))
      const conv2 = useChatStore.getState().conversations.find((c) => c.id === id)!
      expect(conv2.extendedThinking).toBe(false)
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/ExtendedToggle.tsx
  import { Brain } from 'lucide-react'
  import { useChatStore } from '@/lib/store'

  interface ExtendedToggleProps {
    conversationId: string
  }

  export function ExtendedToggle({ conversationId }: ExtendedToggleProps) {
    const enabled = useChatStore((s) =>
      s.conversations.find((c) => c.id === conversationId)?.extendedThinking ?? false,
    )
    const setConversationExtendedThinking = useChatStore((s) => s.setConversationExtendedThinking)

    return (
      <button
        type="button"
        aria-label="extended thinking"
        onClick={() => setConversationExtendedThinking(conversationId, !enabled)}
        data-active={enabled}
        className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px]"
        style={{
          color: enabled ? 'var(--acc)' : 'var(--fg-1)',
          background: enabled ? 'var(--acc-dim)' : 'transparent',
        }}
      >
        <Brain size={12} style={{ color: enabled ? 'var(--acc)' : 'var(--fg-2)' }} />
        Extended
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/ExtendedToggle.tsx frontend/src/components/chat/composer/__tests__/ExtendedToggle.test.tsx
  git commit -m "feat(chat): ExtendedToggle persists per-conversation"
  ```

### Task 3.7: `AttachedFilesPreview`

**Files:**
- Create: `frontend/src/components/chat/composer/AttachedFilesPreview.tsx`
- Test: `__tests__/AttachedFilesPreview.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { AttachedFilesPreview } from '../AttachedFilesPreview'
  import { useChatStore } from '@/lib/store'

  describe('AttachedFilesPreview', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('renders a chip per attached file', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().addAttachedFile(id, { id: 'a', name: 'q.csv', size: 1024, mimeType: 'text/csv' })
      useChatStore.getState().addAttachedFile(id, { id: 'b', name: 'r.md', size: 512, mimeType: 'text/markdown' })
      render(<AttachedFilesPreview conversationId={id} />)
      expect(screen.getByText('q.csv')).toBeInTheDocument()
      expect(screen.getByText('r.md')).toBeInTheDocument()
    })

    it('removes on X click', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().addAttachedFile(id, { id: 'a', name: 'q.csv', size: 1024, mimeType: 'text/csv' })
      render(<AttachedFilesPreview conversationId={id} />)
      fireEvent.click(screen.getByRole('button', { name: /remove q.csv/i }))
      expect(useChatStore.getState().conversations[0].attachedFiles).toEqual([])
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/composer/AttachedFilesPreview.tsx
  import { Paperclip, X } from 'lucide-react'
  import { useChatStore } from '@/lib/store'

  interface AttachedFilesPreviewProps {
    conversationId: string
  }

  export function AttachedFilesPreview({ conversationId }: AttachedFilesPreviewProps) {
    const files = useChatStore((s) =>
      s.conversations.find((c) => c.id === conversationId)?.attachedFiles ?? [],
    )
    const removeAttachedFile = useChatStore((s) => s.removeAttachedFile)
    if (files.length === 0) return null
    return (
      <div className="mb-2 flex flex-wrap gap-1.5">
        {files.map((f) => (
          <span
            key={f.id}
            className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11.5px]"
            style={{ borderColor: 'var(--line-2)', background: 'var(--bg-2)', color: 'var(--fg-1)' }}
          >
            <Paperclip size={11} style={{ color: 'var(--fg-2)' }} />
            <span className="mono">{f.name}</span>
            <button
              type="button"
              aria-label={`remove ${f.name}`}
              onClick={() => removeAttachedFile(conversationId, f.id)}
              className="ml-0.5 flex h-3 w-3 items-center justify-center rounded-[2px]"
              style={{ color: 'var(--fg-3)' }}
            >
              <X size={9} />
            </button>
          </span>
        ))}
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/composer/AttachedFilesPreview.tsx frontend/src/components/chat/composer/__tests__/AttachedFilesPreview.test.tsx
  git commit -m "feat(chat): AttachedFilesPreview row with remove"
  ```

### Task 3.8: Wire parity surfaces into `Composer.tsx`

**Files:**
- Modify: `frontend/src/components/chat/composer/Composer.tsx`

- [ ] **Step 1:** Insert (in this order inside the card, before the textarea):
  - `<AttachedFilesPreview conversationId={conversationId} />`

  Insert (in the footer `<div className="mt-1 flex ...">`), in order:
  - `<IconRow conversationId={conversationId} onInsert={insertAtCaret} onTranscript={appendTranscript} />`
  - `<div className="mx-1.5 h-4 w-px" style={{ background: 'var(--line-2)' }} />`
  - `<ModelPicker conversationId={conversationId} />`
  - `<ExtendedToggle conversationId={conversationId} />`
  - (existing `<PlanToggle …/>` stays)

  Define the helpers:

  ```tsx
  const insertAtCaret = useCallback((token: string) => {
    const el = textareaRef.current
    if (!el) return
    const start = el.selectionStart ?? input.length
    const end = el.selectionEnd ?? input.length
    const next = input.slice(0, start) + token + input.slice(end)
    setInput(next)
    requestAnimationFrame(() => {
      el.focus()
      const pos = start + token.length
      el.setSelectionRange(pos, pos)
      adjustHeight()
    })
  }, [input, adjustHeight])

  const appendTranscript = useCallback((text: string) => {
    setInput((prev) => (prev ? `${prev} ${text}` : text))
    requestAnimationFrame(() => { adjustHeight(); textareaRef.current?.focus() })
  }, [adjustHeight])
  ```

- [ ] **Step 2:** Update the existing `Composer.test.tsx` to include:

  ```tsx
  it('renders model picker, extended toggle, and icon row', () => {
    const id = useChatStore.getState().createConversation()
    render(<Composer conversationId={id} />)
    expect(screen.getByRole('button', { name: /model/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /extended/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /attach/i })).toBeInTheDocument()
  })
  ```

- [ ] **Step 3:** Run:

  ```bash
  pnpm --filter frontend vitest run src/components/chat/composer
  pnpm --filter frontend tsc --noEmit
  ```
  Expected: GREEN.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/chat/composer/Composer.tsx frontend/src/components/chat/composer/__tests__/Composer.test.tsx
  git commit -m "feat(chat): Composer wires icon row + model picker + extended toggle"
  ```

---

## Phase 4 — Message parity surfaces

### Task 4.1: `Avatar` component

**Files:**
- Create: `frontend/src/components/chat/message/Avatar.tsx`
- Test: `__tests__/Avatar.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { Avatar } from '../Avatar'

  describe('Avatar', () => {
    it('renders user initial with gradient', () => {
      render(<Avatar role="user" initial="M" />)
      const el = screen.getByLabelText('user avatar')
      expect(el.textContent).toBe('M')
      expect(el.style.background).toMatch(/linear-gradient/)
    })
    it('renders assistant avatar with accent background', () => {
      render(<Avatar role="assistant" initial="D" />)
      const el = screen.getByLabelText('assistant avatar')
      expect(el.textContent).toBe('D')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/Avatar.tsx
  interface AvatarProps {
    role: 'user' | 'assistant'
    initial: string
  }

  export function Avatar({ role, initial }: AvatarProps) {
    const isUser = role === 'user'
    return (
      <div
        aria-label={`${role} avatar`}
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-[12px] font-semibold"
        style={{
          background: isUser
            ? 'linear-gradient(135deg, oklch(0.72 0.09 35), oklch(0.58 0.11 30))'
            : 'var(--acc)',
          color: isUser ? '#fff' : 'var(--acc-fg)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.15), 0 1px 2px rgba(0,0,0,0.05)',
          letterSpacing: '-0.02em',
        }}
      >
        {initial}
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/message/Avatar.tsx frontend/src/components/chat/message/__tests__/Avatar.test.tsx
  git commit -m "feat(chat): Avatar for message tree"
  ```

### Task 4.2: `MessageHeader` (name · timestamp · copy · more)

**Files:**
- Create: `frontend/src/components/chat/message/MessageHeader.tsx`
- Test: `__tests__/MessageHeader.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { MessageHeader } from '../MessageHeader'

  describe('MessageHeader', () => {
    it('renders name + ts', () => {
      render(<MessageHeader name="Martin" timestamp="14:02:11" onCopy={() => {}} />)
      expect(screen.getByText('Martin')).toBeInTheDocument()
      expect(screen.getByText('14:02:11')).toBeInTheDocument()
    })
    it('fires onCopy on copy button click', () => {
      const spy = vi.fn()
      render(<MessageHeader name="x" timestamp="t" onCopy={spy} />)
      fireEvent.click(screen.getByRole('button', { name: /copy/i }))
      expect(spy).toHaveBeenCalled()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/MessageHeader.tsx
  import { Copy, MoreHorizontal } from 'lucide-react'

  interface MessageHeaderProps {
    name: string
    timestamp: string
    onCopy: () => void
  }

  export function MessageHeader({ name, timestamp, onCopy }: MessageHeaderProps) {
    return (
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-[13px] font-semibold tracking-[-0.005em]" style={{ color: 'var(--fg-0)' }}>
          {name}
        </span>
        <span className="mono text-[10.5px]" style={{ color: 'var(--fg-3)' }}>{timestamp}</span>
        <div className="flex-1" />
        <button
          type="button"
          aria-label="Copy"
          onClick={onCopy}
          className="rounded p-[3px]"
          style={{ color: 'var(--fg-3)' }}
        >
          <Copy size={12} />
        </button>
        <button
          type="button"
          aria-label="More"
          className="rounded p-[3px]"
          style={{ color: 'var(--fg-3)' }}
        >
          <MoreHorizontal size={12} />
        </button>
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/message/MessageHeader.tsx frontend/src/components/chat/message/__tests__/MessageHeader.test.tsx
  git commit -m "feat(chat): MessageHeader with name/ts/copy/more"
  ```

### Task 4.3: `Callout` component

**Files:**
- Create: `frontend/src/components/chat/message/Callout.tsx`
- Test: `__tests__/Callout.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { Callout } from '../Callout'

  describe('Callout', () => {
    it.each([
      ['warn' as const, '--warn'],
      ['err'  as const, '--err'],
      ['info' as const, '--info'],
    ])('renders %s kind with palette token', (kind, token) => {
      render(<Callout kind={kind} label="data quality" text="31% nulls" />)
      expect(screen.getByText('data quality')).toBeInTheDocument()
      expect(screen.getByText('31% nulls')).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/Callout.tsx
  import { AlertTriangle, XCircle, Info } from 'lucide-react'

  interface CalloutProps {
    kind: 'warn' | 'err' | 'info'
    label: string
    text: string
  }

  const ICON_MAP = { warn: AlertTriangle, err: XCircle, info: Info }
  const PALETTE_MAP = { warn: 'var(--warn)', err: 'var(--err)', info: 'var(--info)' } as const

  export function Callout({ kind, label, text }: CalloutProps) {
    const Icon = ICON_MAP[kind]
    const palette = PALETTE_MAP[kind]
    return (
      <div
        className="mt-2.5 flex gap-[10px] rounded-lg border px-3 py-2.5 text-[12.5px]"
        style={{
          borderColor: `color-mix(in oklch, ${palette} 30%, var(--line))`,
          background: `color-mix(in oklch, ${palette} 6%, var(--bg-1))`,
        }}
      >
        <Icon size={13} style={{ color: palette, marginTop: 2, flexShrink: 0 }} />
        <div>
          <div className="mb-0.5 text-[11.5px] font-medium" style={{ color: palette }}>{label}</div>
          <div style={{ color: 'var(--fg-1)' }}>{text}</div>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/message/Callout.tsx frontend/src/components/chat/message/__tests__/Callout.test.tsx
  git commit -m "feat(chat): Callout for warn/err/info"
  ```

### Task 4.4: `ToolChip` + `ToolChipRow`

**Files:**
- Create: `frontend/src/components/chat/message/ToolChip.tsx`
- Create: `frontend/src/components/chat/message/ToolChipRow.tsx`
- Test: `__tests__/ToolChip.test.tsx`
- Test: `__tests__/ToolChipRow.test.tsx`

- [ ] **Step 1: Failing test — ToolChip**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ToolChip } from '../ToolChip'

  describe('ToolChip', () => {
    it('renders name + args + ms', () => {
      render(<ToolChip entry={{ id: '1', step: 0, name: 'read_file', inputPreview: 'q3.parquet', status: 'ok', startedAt: 0, finishedAt: 1240 }} />)
      expect(screen.getByText('read_file')).toBeInTheDocument()
      expect(screen.getByText('q3.parquet')).toBeInTheDocument()
      expect(screen.getByText(/1240ms/)).toBeInTheDocument()
    })

    it('renders rows when present', () => {
      render(<ToolChip entry={{ id: '1', step: 0, name: 'x', inputPreview: 'y', status: 'ok', startedAt: 0, finishedAt: 1, rows: '100 × 5' }} />)
      expect(screen.getByText(/100 × 5/)).toBeInTheDocument()
    })

    it('dispatches scrollToTrace event on click', () => {
      const spy = vi.fn()
      window.addEventListener('scrollToTrace', spy)
      render(<ToolChip entry={{ id: 'entry-1', step: 0, name: 'x', inputPreview: 'y', status: 'ok' }} />)
      fireEvent.click(screen.getByRole('button'))
      expect(spy).toHaveBeenCalled()
      window.removeEventListener('scrollToTrace', spy)
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement ToolChip**

  ```tsx
  // frontend/src/components/chat/message/ToolChip.tsx
  import type { ToolCallEntry } from '@/lib/store'

  interface ToolChipProps { entry: ToolCallEntry }

  const STATUS_COLOR: Record<ToolCallEntry['status'], string> = {
    pending: 'var(--fg-2)',
    ok: 'var(--ok)',
    error: 'var(--err)',
    blocked: 'var(--warn)',
  }

  export function ToolChip({ entry }: ToolChipProps) {
    const ms = entry.startedAt && entry.finishedAt ? entry.finishedAt - entry.startedAt : null
    return (
      <button
        type="button"
        onClick={() => {
          window.dispatchEvent(new CustomEvent('scrollToTrace', { detail: { entryId: entry.id } }))
        }}
        className="mb-[5px] mr-[6px] inline-flex items-center gap-[7px] rounded-md border px-[9px] py-1 text-[11.5px]"
        style={{ borderColor: 'var(--line-2)', background: 'var(--bg-1)', color: 'var(--fg-1)' }}
      >
        <span className="dot" style={{ background: STATUS_COLOR[entry.status], width: 5, height: 5 }} />
        <span className="mono" style={{ color: 'var(--fg-0)' }}>{entry.name}</span>
        {entry.inputPreview && (
          <span className="mono" style={{ color: 'var(--fg-2)' }}>{entry.inputPreview}</span>
        )}
        {ms !== null && (
          <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>· {ms}ms</span>
        )}
        {entry.rows && (
          <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>· {entry.rows}</span>
        )}
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Failing test — ToolChipRow**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { ToolChipRow } from '../ToolChipRow'
  import { useChatStore } from '@/lib/store'

  describe('ToolChipRow', () => {
    beforeEach(() => { useChatStore.setState({ toolCallLog: [] }) })

    it('renders only entries matching messageId', () => {
      useChatStore.getState().pushToolCall({ step: 0, name: 'a', inputPreview: '', status: 'ok', messageId: 'm1', startedAt: 0 })
      useChatStore.getState().pushToolCall({ step: 0, name: 'b', inputPreview: '', status: 'ok', messageId: 'm2', startedAt: 0 })
      render(<ToolChipRow messageId="m1" />)
      expect(screen.getByText('a')).toBeInTheDocument()
      expect(screen.queryByText('b')).toBeNull()
    })

    it('renders nothing when no matches', () => {
      const { container } = render(<ToolChipRow messageId="missing" />)
      expect(container.firstChild).toBeNull()
    })
  })
  ```

- [ ] **Step 6: Run** — FAIL.

- [ ] **Step 7: Implement ToolChipRow**

  ```tsx
  // frontend/src/components/chat/message/ToolChipRow.tsx
  import { useChatStore } from '@/lib/store'
  import { ToolChip } from './ToolChip'

  interface ToolChipRowProps { messageId: string }

  export function ToolChipRow({ messageId }: ToolChipRowProps) {
    const entries = useChatStore((s) => s.toolCallLog.filter((e) => e.messageId === messageId))
    if (entries.length === 0) return null
    return (
      <div className="mt-2">
        {entries.map((entry) => <ToolChip key={entry.id} entry={entry} />)}
      </div>
    )
  }
  ```

- [ ] **Step 8: Run** — PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add frontend/src/components/chat/message/ToolChip.tsx frontend/src/components/chat/message/ToolChipRow.tsx frontend/src/components/chat/message/__tests__/ToolChip.test.tsx frontend/src/components/chat/message/__tests__/ToolChipRow.test.tsx
  git commit -m "feat(chat): ToolChip + ToolChipRow with scrollToTrace dispatch"
  ```

### Task 4.5: `ArtifactPill` + `ArtifactPillRow`

**Files:**
- Create: `frontend/src/components/chat/message/ArtifactPill.tsx`
- Create: `frontend/src/components/chat/message/ArtifactPillRow.tsx`
- Test: `__tests__/ArtifactPill.test.tsx`
- Test: `__tests__/ArtifactPillRow.test.tsx`

- [ ] **Step 1: Failing test — ArtifactPill**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ArtifactPill } from '../ArtifactPill'

  describe('ArtifactPill', () => {
    it('renders name + size', () => {
      render(<ArtifactPill id="a" type="chart" name="residuals.png" size="184 KB" missing={false} onOpen={() => {}} />)
      expect(screen.getByText('residuals.png')).toBeInTheDocument()
      expect(screen.getByText('184 KB')).toBeInTheDocument()
    })
    it('fires onOpen on click', () => {
      const spy = vi.fn()
      render(<ArtifactPill id="a" type="chart" name="x" size="" missing={false} onOpen={spy} />)
      fireEvent.click(screen.getByRole('button'))
      expect(spy).toHaveBeenCalledWith('a')
    })
    it('marks missing artifacts as disabled with suffix', () => {
      render(<ArtifactPill id="a" type="chart" name="gone" size="" missing={true} onOpen={() => {}} />)
      expect(screen.getByRole('button')).toBeDisabled()
      expect(screen.getByText(/removed/i)).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/ArtifactPill.tsx
  import { FileText, BarChart3, Table, Image as ImageIcon, Code, ChevronRight } from 'lucide-react'

  interface ArtifactPillProps {
    id: string
    type: 'chart' | 'table' | 'diagram' | 'profile' | 'analysis' | 'file'
    name: string
    size: string
    missing: boolean
    onOpen: (id: string) => void
  }

  const ICON_MAP = {
    chart: BarChart3,
    table: Table,
    diagram: BarChart3,
    profile: Table,
    analysis: FileText,
    file: FileText,
  } as const

  export function ArtifactPill({ id, type, name, size, missing, onOpen }: ArtifactPillProps) {
    const Icon = ICON_MAP[type] ?? FileText
    return (
      <button
        type="button"
        disabled={missing}
        onClick={() => onOpen(id)}
        className="mr-1.5 mt-1.5 inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[12.5px] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        style={{ borderColor: 'var(--line)', background: 'var(--bg-1)', color: 'var(--fg-0)' }}
      >
        <Icon size={13} style={{ color: 'var(--acc)' }} />
        <span>{name}</span>
        {size && <span className="mono text-[10.5px]" style={{ color: 'var(--fg-3)' }}>{size}</span>}
        {missing ? (
          <span className="text-[10.5px]" style={{ color: 'var(--fg-3)' }}>— removed</span>
        ) : (
          <ChevronRight size={12} style={{ color: 'var(--fg-3)', marginLeft: 2 }} />
        )}
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Failing test — ArtifactPillRow**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ArtifactPillRow } from '../ArtifactPillRow'
  import { useChatStore } from '@/lib/store'
  import { useUiStore } from '@/lib/ui-store'

  describe('ArtifactPillRow', () => {
    beforeEach(() => {
      useChatStore.setState({ artifacts: [], conversations: [], activeConversationId: null })
      useUiStore.setState({ ...useUiStore.getState(), dockOpen: false })
    })

    it('renders only artifacts in artifactIds', () => {
      useChatStore.getState().addArtifact({ id: 'a', type: 'chart', title: 'A', content: '', format: 'vega-lite', session_id: '', created_at: 0, metadata: {} })
      useChatStore.getState().addArtifact({ id: 'b', type: 'chart', title: 'B', content: '', format: 'vega-lite', session_id: '', created_at: 0, metadata: {} })
      render(<ArtifactPillRow artifactIds={['a']} />)
      expect(screen.getByText('A')).toBeInTheDocument()
      expect(screen.queryByText('B')).toBeNull()
    })

    it('opens dock + right panel tools tab on click', () => {
      useChatStore.getState().addArtifact({ id: 'a', type: 'chart', title: 'A', content: '', format: 'vega-lite', session_id: '', created_at: 0, metadata: {} })
      render(<ArtifactPillRow artifactIds={['a']} />)
      fireEvent.click(screen.getByRole('button'))
      expect(useUiStore.getState().dockOpen).toBe(true)
    })
  })
  ```

- [ ] **Step 6: Run** — FAIL.

- [ ] **Step 7: Implement**

  ```tsx
  // frontend/src/components/chat/message/ArtifactPillRow.tsx
  import { useChatStore } from '@/lib/store'
  import { useUiStore } from '@/lib/ui-store'
  import { ArtifactPill } from './ArtifactPill'

  interface ArtifactPillRowProps { artifactIds: string[] }

  export function ArtifactPillRow({ artifactIds }: ArtifactPillRowProps) {
    const artifacts = useChatStore((s) => s.artifacts)
    const setRightPanelTab = useChatStore((s) => s.setRightPanelTab)
    const setDockOpen = useUiStore((s) => s.setDockOpen)
    if (artifactIds.length === 0) return null
    const byId = new Map(artifacts.map((a) => [a.id, a]))
    return (
      <div>
        {artifactIds.map((id) => {
          const a = byId.get(id)
          return (
            <ArtifactPill
              key={id}
              id={id}
              type={(a?.type as any) ?? 'file'}
              name={a?.title ?? 'Artifact'}
              size={''}
              missing={!a}
              onOpen={(artId) => {
                setDockOpen(true)
                setRightPanelTab('artifacts')
                window.dispatchEvent(new CustomEvent('focusArtifact', { detail: { artifactId: artId } }))
              }}
            />
          )
        })}
      </div>
    )
  }
  ```

  (`setDockOpen` must exist on ui-store. Verify via `grep -n "setDockOpen" frontend/src/lib/ui-store.ts`. Sub-project 1 landed it. If absent, add it as `setDockOpen: (open: boolean) => set({ dockOpen: open, dockOverridden: true })` in that file first, with a matching test — this is a one-line fallback, not a separate task.)

- [ ] **Step 8: Run** — PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add frontend/src/components/chat/message/ArtifactPill.tsx frontend/src/components/chat/message/ArtifactPillRow.tsx frontend/src/components/chat/message/__tests__/ArtifactPill.test.tsx frontend/src/components/chat/message/__tests__/ArtifactPillRow.test.tsx
  git commit -m "feat(chat): ArtifactPill + ArtifactPillRow opens dock"
  ```

### Task 4.6: `AttachedFileChip`

**Files:**
- Create: `frontend/src/components/chat/message/AttachedFileChip.tsx`
- Test: `__tests__/AttachedFileChip.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { AttachedFileChip } from '../AttachedFileChip'

  describe('AttachedFileChip', () => {
    it('renders file name', () => {
      render(<AttachedFileChip name="q3-brief.md" />)
      expect(screen.getByText('q3-brief.md')).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/AttachedFileChip.tsx
  import { Paperclip } from 'lucide-react'

  interface AttachedFileChipProps { name: string }

  export function AttachedFileChip({ name }: AttachedFileChipProps) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11.5px]"
        style={{ borderColor: 'var(--line-2)', background: 'var(--bg-2)', color: 'var(--fg-1)' }}
      >
        <Paperclip size={11} style={{ color: 'var(--fg-2)' }} />
        <span className="mono text-[11px]">{name}</span>
      </span>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/message/AttachedFileChip.tsx frontend/src/components/chat/message/__tests__/AttachedFileChip.test.tsx
  git commit -m "feat(chat): AttachedFileChip on user messages"
  ```

### Task 4.7: `Message` component (composes the tree)

**Files:**
- Create: `frontend/src/components/chat/message/Message.tsx`
- Test: `__tests__/Message.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { Message } from '../Message'
  import { useChatStore } from '@/lib/store'
  import type { Message as MessageRecord } from '@/lib/store'

  describe('Message', () => {
    beforeEach(() => {
      useChatStore.setState({ toolCallLog: [], artifacts: [], conversations: [], activeConversationId: null })
    })

    it('renders user avatar + text + attached chip', () => {
      const msg: MessageRecord = {
        id: 'm1', role: 'user', content: 'hello', status: 'complete', timestamp: 1745000000000,
      }
      render(<Message message={msg} attachedNames={['q3-brief.md']} />)
      expect(screen.getByLabelText('user avatar')).toBeInTheDocument()
      expect(screen.getByText('hello')).toBeInTheDocument()
      expect(screen.getByText('q3-brief.md')).toBeInTheDocument()
    })

    it('renders assistant avatar + callout + tool chips + artifact pills', () => {
      useChatStore.getState().pushToolCall({
        step: 0, name: 'read_file', inputPreview: 'q.parquet', status: 'ok', messageId: 'm2', startedAt: 0, finishedAt: 100,
      })
      useChatStore.getState().addArtifact({
        id: 'art1', type: 'chart', title: 'residuals.png', content: '', format: 'vega-lite', session_id: '', created_at: 0, metadata: {},
      })
      const msg: MessageRecord = {
        id: 'm2', role: 'assistant', status: 'complete', timestamp: 1745000000000,
        content: [
          { type: 'callout', kind: 'warn', label: 'data quality', text: '31% nulls' },
          { type: 'text', text: 'baseline MAE 142.3' },
        ],
        artifactIds: ['art1'],
      }
      render(<Message message={msg} />)
      expect(screen.getByLabelText('assistant avatar')).toBeInTheDocument()
      expect(screen.getByText('data quality')).toBeInTheDocument()
      expect(screen.getByText('read_file')).toBeInTheDocument()
      expect(screen.getByText('residuals.png')).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/message/Message.tsx
  import { useMemo } from 'react'
  import type { Message as MessageRecord } from '@/lib/store'
  import type { ContentBlock } from '@/lib/types'
  import { MarkdownContent } from '../MarkdownContent'
  import { SubagentCard } from '../SubagentCard'
  import { Avatar } from './Avatar'
  import { MessageHeader } from './MessageHeader'
  import { Callout } from './Callout'
  import { ToolChipRow } from './ToolChipRow'
  import { ArtifactPillRow } from './ArtifactPillRow'
  import { AttachedFileChip } from './AttachedFileChip'

  interface MessageProps {
    message: MessageRecord
    attachedNames?: string[]
  }

  function formatTimestamp(ts: number): string {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  }

  function isBlocks(c: MessageRecord['content']): c is ContentBlock[] {
    return Array.isArray(c)
  }

  export function Message({ message, attachedNames = [] }: MessageProps) {
    const isUser = message.role === 'user'
    const blocks = useMemo<ContentBlock[]>(() => {
      if (isBlocks(message.content)) return message.content
      return message.content ? [{ type: 'text', text: message.content }] : []
    }, [message.content])

    const textBlocks = blocks.filter((b): b is Extract<ContentBlock, { type: 'text' }> => b.type === 'text')
    const callouts = blocks.filter((b): b is Extract<ContentBlock, { type: 'callout' }> => b.type === 'callout')
    const a2as = blocks.filter((b): b is Extract<ContentBlock, { type: 'a2a' }> => b.type === 'a2a')

    const onCopy = () => {
      const text = textBlocks.map((b) => b.text).join('\n\n')
      if (text) navigator.clipboard?.writeText(text)
    }

    return (
      <div className="flex gap-3.5 border-b py-[18px]" style={{ borderColor: 'var(--line-2)' }}>
        <Avatar role={message.role} initial={isUser ? 'M' : 'D'} />
        <div className="min-w-0 flex-1">
          <MessageHeader
            name={isUser ? 'Martin' : 'DS Agent'}
            timestamp={formatTimestamp(message.timestamp)}
            onCopy={onCopy}
          />
          {textBlocks.length > 0 && (
            <div className="text-[14px] leading-[1.6]" style={{ color: 'var(--fg-0)' }}>
              {textBlocks.map((b, i) => <MarkdownContent key={i} content={b.text} />)}
            </div>
          )}
          {callouts.map((c, i) => <Callout key={i} kind={c.kind} label={c.label} text={c.text} />)}
          {!isUser && <ToolChipRow messageId={message.id} />}
          {(message.artifactIds?.length ?? 0) > 0 && (
            <ArtifactPillRow artifactIds={message.artifactIds ?? []} />
          )}
          {a2as.map((a, i) => <SubagentCard key={i} block={a} />)}
          {attachedNames.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {attachedNames.map((name) => <AttachedFileChip key={name} name={name} />)}
            </div>
          )}
        </div>
      </div>
    )
  }
  ```

  (If `SubagentCard`'s prop interface differs, adapt — the existing `VirtualMessageList` already passes the block directly, so the spelling here should match.)

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/message/Message.tsx frontend/src/components/chat/message/__tests__/Message.test.tsx
  git commit -m "feat(chat): Message composes avatar/header/callout/tools/artifacts/attached"
  ```

### Task 4.8: Switch `VirtualMessageList` to use new `Message`

**Files:**
- Modify: `frontend/src/components/chat/VirtualMessageList.tsx`

- [ ] **Step 1:** Replace the `<MessageBubble .../>` import + render site with `<Message message={m} .../>`. `attachedNames` comes from an optional prop on VirtualMessageList or — if the current sub-project doesn't surface per-message attachments yet — pass an empty array.
- [ ] **Step 2:** Run the repo test suite:

  ```bash
  pnpm --filter frontend vitest run
  ```
  Expected: `MessageBubble.test.tsx` may still pass against the old file; don't delete it yet (retirement is in Phase 6).

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/chat/VirtualMessageList.tsx
  git commit -m "refactor(chat): VirtualMessageList renders Message tree"
  ```

---

## Phase 5 — Header toolbar

### Task 5.1: `TitleEditor` (inline-edit title)

**Files:**
- Create: `frontend/src/components/chat/header/TitleEditor.tsx`
- Test: `__tests__/TitleEditor.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { TitleEditor } from '../TitleEditor'
  import { useChatStore } from '@/lib/store'

  describe('TitleEditor', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('enters edit mode on click', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'Churn')
      render(<TitleEditor conversationId={id} />)
      fireEvent.click(screen.getByText('Churn'))
      expect(screen.getByRole('textbox')).toHaveValue('Churn')
    })

    it('commits on Enter', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'Old')
      render(<TitleEditor conversationId={id} />)
      fireEvent.click(screen.getByText('Old'))
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'New' } })
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(useChatStore.getState().conversations[0].title).toBe('New')
    })

    it('reverts on Esc', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'Keep')
      render(<TitleEditor conversationId={id} />)
      fireEvent.click(screen.getByText('Keep'))
      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'Lose' } })
      fireEvent.keyDown(input, { key: 'Escape' })
      expect(useChatStore.getState().conversations[0].title).toBe('Keep')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/header/TitleEditor.tsx
  import { useEffect, useRef, useState } from 'react'
  import { useChatStore } from '@/lib/store'

  interface TitleEditorProps { conversationId: string }

  export function TitleEditor({ conversationId }: TitleEditorProps) {
    const title = useChatStore((s) =>
      s.conversations.find((c) => c.id === conversationId)?.title ?? '',
    )
    const update = useChatStore((s) => s.updateConversationTitle)
    const [editing, setEditing] = useState(false)
    const [draft, setDraft] = useState(title)
    const inputRef = useRef<HTMLInputElement>(null)

    useEffect(() => { if (!editing) setDraft(title) }, [title, editing])
    useEffect(() => {
      if (editing) { inputRef.current?.focus(); inputRef.current?.select() }
    }, [editing])

    const commit = () => {
      update(conversationId, draft)
      setEditing(false)
    }
    const cancel = () => {
      setDraft(title); setEditing(false)
    }

    if (editing) {
      return (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); commit() }
            if (e.key === 'Escape') { e.preventDefault(); cancel() }
          }}
          maxLength={200}
          className="bg-transparent text-[14.5px] font-semibold tracking-[-0.01em] outline-none"
          style={{ color: 'var(--fg-0)', minWidth: 120 }}
        />
      )
    }

    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="text-[14.5px] font-semibold tracking-[-0.01em]"
        style={{ color: 'var(--fg-0)' }}
      >
        {title || 'Untitled'}
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/header/TitleEditor.tsx frontend/src/components/chat/header/__tests__/TitleEditor.test.tsx
  git commit -m "feat(chat): TitleEditor inline rename"
  ```

### Task 5.2: `SearchButton`

**Files:**
- Create: `frontend/src/components/chat/header/SearchButton.tsx`
- Test: `__tests__/SearchButton.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { SearchButton } from '../SearchButton'

  describe('SearchButton', () => {
    it('renders Search label + ⌘K kbd + fires onOpen on click', () => {
      const spy = vi.fn()
      render(<SearchButton onOpen={spy} />)
      expect(screen.getByText('Search')).toBeInTheDocument()
      expect(screen.getByText('⌘K')).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button'))
      expect(spy).toHaveBeenCalled()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/header/SearchButton.tsx
  import { Search } from 'lucide-react'

  interface SearchButtonProps { onOpen: () => void }

  export function SearchButton({ onOpen }: SearchButtonProps) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="mr-1 flex items-center gap-1.5 rounded-md border px-2 py-1 text-[12px]"
        style={{ borderColor: 'var(--line-2)', background: 'var(--bg-1)', color: 'var(--fg-2)' }}
      >
        <Search size={11} />
        <span>Search</span>
        <span className="kbd ml-0.5">⌘K</span>
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/header/SearchButton.tsx frontend/src/components/chat/header/__tests__/SearchButton.test.tsx
  git commit -m "feat(chat): SearchButton with ⌘K kbd"
  ```

### Task 5.3: `ForkButton`

**Files:**
- Create: `frontend/src/components/chat/header/ForkButton.tsx`
- Test: `__tests__/ForkButton.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ForkButton } from '../ForkButton'
  import { useChatStore } from '@/lib/store'

  describe('ForkButton', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('creates fork and switches active conversation', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().addMessage(id, { role: 'user', content: 'a', status: 'complete' })
      render(<ForkButton conversationId={id} />)
      fireEvent.click(screen.getByRole('button', { name: /fork/i }))
      expect(useChatStore.getState().conversations.length).toBe(2)
      expect(useChatStore.getState().activeConversationId).not.toBe(id)
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/header/ForkButton.tsx
  import { GitBranch } from 'lucide-react'
  import { useChatStore } from '@/lib/store'

  interface ForkButtonProps { conversationId: string }

  export function ForkButton({ conversationId }: ForkButtonProps) {
    const fork = useChatStore((s) => s.forkConversation)
    return (
      <button
        type="button"
        aria-label="Fork"
        onClick={() => fork(conversationId)}
        className="flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px]"
        style={{ borderColor: 'var(--line-2)', color: 'var(--fg-1)' }}
      >
        <GitBranch size={12} /> Fork
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/header/ForkButton.tsx frontend/src/components/chat/header/__tests__/ForkButton.test.tsx
  git commit -m "feat(chat): ForkButton creates fork + switches"
  ```

### Task 5.4: `ExportMenu` (.md / .json / .html)

**Files:**
- Create: `frontend/src/components/chat/header/ExportMenu.tsx`
- Create: `frontend/src/components/chat/header/export-formatters.ts`
- Test: `__tests__/export-formatters.test.ts`
- Test: `__tests__/ExportMenu.test.tsx`

- [ ] **Step 1: Failing test for formatters**

  ```ts
  // __tests__/export-formatters.test.ts
  import { describe, it, expect } from 'vitest'
  import { toMarkdown, toJson, toHtml } from '../export-formatters'
  import type { Conversation } from '@/lib/store'

  const conv: Conversation = {
    id: 'c1', title: 'Q3 churn', createdAt: 0, updatedAt: 0,
    messages: [
      { id: 'm1', role: 'user', content: 'hello', status: 'complete', timestamp: 0 },
      { id: 'm2', role: 'assistant', content: 'hi', status: 'complete', timestamp: 0 },
    ],
  }

  describe('export-formatters', () => {
    it('markdown', () => {
      const out = toMarkdown(conv)
      expect(out).toContain('# Q3 churn')
      expect(out).toContain('**user**')
      expect(out).toContain('hello')
      expect(out).toContain('**assistant**')
    })
    it('json round-trips', () => {
      const out = toJson(conv)
      const parsed = JSON.parse(out)
      expect(parsed.title).toBe('Q3 churn')
      expect(parsed.messages).toHaveLength(2)
    })
    it('html escapes dangerous chars', () => {
      const hostile: Conversation = { ...conv, messages: [{ ...conv.messages[0], content: '<script>x</script>' }] }
      const out = toHtml(hostile)
      expect(out).not.toContain('<script>')
      expect(out).toContain('&lt;script&gt;')
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement formatters**

  ```ts
  // frontend/src/components/chat/header/export-formatters.ts
  import type { Conversation } from '@/lib/store'
  import { extractTextContent } from '@/lib/utils'

  export function toMarkdown(conv: Conversation): string {
    const lines = [`# ${conv.title}`, '']
    for (const m of conv.messages) {
      lines.push(`**${m.role}** · ${new Date(m.timestamp).toISOString()}`, '')
      lines.push(extractTextContent(m.content), '')
    }
    return lines.join('\n')
  }

  export function toJson(conv: Conversation): string {
    return JSON.stringify(conv, null, 2)
  }

  function escapeHtml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  }

  export function toHtml(conv: Conversation): string {
    const rows = conv.messages.map((m) => {
      const body = escapeHtml(extractTextContent(m.content))
      return `<section><h2>${escapeHtml(m.role)}</h2><pre>${body}</pre></section>`
    }).join('\n')
    return `<!doctype html><html><head><title>${escapeHtml(conv.title)}</title></head><body>${rows}</body></html>`
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Failing test for menu**

  ```tsx
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ExportMenu } from '../ExportMenu'
  import { useChatStore } from '@/lib/store'

  describe('ExportMenu', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('opens menu and exposes .md/.json/.html options', () => {
      const id = useChatStore.getState().createConversation()
      render(<ExportMenu conversationId={id} />)
      fireEvent.click(screen.getByRole('button', { name: /export/i }))
      expect(screen.getByText(/markdown/i)).toBeInTheDocument()
      expect(screen.getByText(/json/i)).toBeInTheDocument()
      expect(screen.getByText(/html/i)).toBeInTheDocument()
    })
  })
  ```

- [ ] **Step 6: Run** — FAIL.

- [ ] **Step 7: Implement**

  ```tsx
  // frontend/src/components/chat/header/ExportMenu.tsx
  import { useState } from 'react'
  import { Download } from 'lucide-react'
  import { useChatStore } from '@/lib/store'
  import { toMarkdown, toJson, toHtml } from './export-formatters'

  interface ExportMenuProps { conversationId: string }

  function download(filename: string, body: string, mime: string) {
    const blob = new Blob([body], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

  export function ExportMenu({ conversationId }: ExportMenuProps) {
    const [open, setOpen] = useState(false)
    const conv = useChatStore((s) => s.conversations.find((c) => c.id === conversationId))

    const handle = (format: 'md' | 'json' | 'html') => {
      if (!conv) return
      const base = conv.title.replace(/[^\w-]+/g, '_') || 'conversation'
      try {
        if (format === 'md') download(`${base}.md`, toMarkdown(conv), 'text/markdown')
        if (format === 'json') download(`${base}.json`, toJson(conv), 'application/json')
        if (format === 'html') download(`${base}.html`, toHtml(conv), 'text/html')
      } finally { setOpen(false) }
    }

    return (
      <div className="relative">
        <button
          type="button"
          aria-label="Export"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px]"
          style={{ borderColor: 'var(--line-2)', color: 'var(--fg-1)' }}
        >
          <Download size={12} /> Export
        </button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-1 overflow-hidden rounded-md border shadow-[var(--shadow-2)]"
            style={{ borderColor: 'var(--line)', background: 'var(--bg-1)' }}
          >
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--fg-1)' }} onClick={() => handle('md')}>Markdown (.md)</button>
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--fg-1)' }} onClick={() => handle('json')}>JSON (.json)</button>
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--fg-1)' }} onClick={() => handle('html')}>HTML (.html)</button>
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 8: Run** — PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add frontend/src/components/chat/header/ExportMenu.tsx frontend/src/components/chat/header/export-formatters.ts frontend/src/components/chat/header/__tests__/ExportMenu.test.tsx frontend/src/components/chat/header/__tests__/export-formatters.test.ts
  git commit -m "feat(chat): ExportMenu .md/.json/.html"
  ```

### Task 5.5: `ProgressToggle`

**Files:**
- Create: `frontend/src/components/chat/header/ProgressToggle.tsx`
- Test: `__tests__/ProgressToggle.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { ProgressToggle } from '../ProgressToggle'
  import { useUiStore } from '@/lib/ui-store'

  describe('ProgressToggle', () => {
    beforeEach(() => { useUiStore.setState({ ...useUiStore.getState(), dockOpen: false }) })

    it('shows pulse dot + opens dock on click', () => {
      render(<ProgressToggle />)
      fireEvent.click(screen.getByRole('button', { name: /progress/i }))
      expect(useUiStore.getState().dockOpen).toBe(true)
    })

    it('renders null when dockOpen is true', () => {
      useUiStore.setState({ ...useUiStore.getState(), dockOpen: true })
      const { container } = render(<ProgressToggle />)
      expect(container.firstChild).toBeNull()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/header/ProgressToggle.tsx
  import { useUiStore } from '@/lib/ui-store'

  export function ProgressToggle() {
    const dockOpen = useUiStore((s) => s.dockOpen)
    const setDockOpen = useUiStore((s) => s.setDockOpen)
    if (dockOpen) return null
    return (
      <button
        type="button"
        aria-label="Progress"
        onClick={() => setDockOpen(true)}
        className="fade-in flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px]"
        style={{ borderColor: 'var(--line-2)', color: 'var(--fg-1)' }}
      >
        <span className="pulse h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ background: 'var(--acc)' }} />
        Progress
      </button>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/header/ProgressToggle.tsx frontend/src/components/chat/header/__tests__/ProgressToggle.test.tsx
  git commit -m "feat(chat): ProgressToggle reveals dock"
  ```

### Task 5.6: `MoreMenu` (rename · archive · duplicate · delete)

**Files:**
- Create: `frontend/src/components/chat/header/MoreMenu.tsx`
- Test: `__tests__/MoreMenu.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach, vi } from 'vitest'
  import { render, screen, fireEvent } from '@testing-library/react'
  import { MoreMenu } from '../MoreMenu'
  import { useChatStore } from '@/lib/store'

  describe('MoreMenu', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('opens menu and deletes conversation', () => {
      const id = useChatStore.getState().createConversation()
      render(<MoreMenu conversationId={id} onRename={() => {}} />)
      fireEvent.click(screen.getByRole('button', { name: /more/i }))
      fireEvent.click(screen.getByText(/delete/i))
      expect(useChatStore.getState().conversations.length).toBe(0)
    })

    it('fires onRename', () => {
      const id = useChatStore.getState().createConversation()
      const spy = vi.fn()
      render(<MoreMenu conversationId={id} onRename={spy} />)
      fireEvent.click(screen.getByRole('button', { name: /more/i }))
      fireEvent.click(screen.getByText(/rename/i))
      expect(spy).toHaveBeenCalled()
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  Check the store for an existing `deleteConversation` action: `grep -n "deleteConversation" frontend/src/lib/store.ts`. If present, use it. If not, use the fork action + a synthetic `set` — but the handoff expects real deletion, so add the action if absent:

  ```ts
  // add to store.ts if missing:
  deleteConversation: (id: string) => void

  // in body:
  deleteConversation: (id) => set((s) => ({
    conversations: s.conversations.filter((c) => c.id !== id),
    activeConversationId: s.activeConversationId === id ? null : s.activeConversationId,
  })),
  ```

  Then:

  ```tsx
  // frontend/src/components/chat/header/MoreMenu.tsx
  import { useState } from 'react'
  import { MoreHorizontal } from 'lucide-react'
  import { useChatStore } from '@/lib/store'

  interface MoreMenuProps {
    conversationId: string
    onRename: () => void
  }

  export function MoreMenu({ conversationId, onRename }: MoreMenuProps) {
    const [open, setOpen] = useState(false)
    const fork = useChatStore((s) => s.forkConversation)
    const del = useChatStore((s) => s.deleteConversation)

    const handleDuplicate = () => { fork(conversationId); setOpen(false) }
    const handleDelete = () => { del(conversationId); setOpen(false) }
    const handleRename = () => { onRename(); setOpen(false) }

    return (
      <div className="relative">
        <button
          type="button"
          aria-label="More"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md p-1.5"
          style={{ color: 'var(--fg-2)' }}
        >
          <MoreHorizontal size={15} />
        </button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-1 min-w-[140px] overflow-hidden rounded-md border shadow-[var(--shadow-2)]"
            style={{ borderColor: 'var(--line)', background: 'var(--bg-1)' }}
          >
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--fg-1)' }} onClick={handleRename}>Rename</button>
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--fg-1)' }} onClick={handleDuplicate}>Duplicate</button>
            <button role="menuitem" className="block w-full px-3 py-1.5 text-left text-[12px]" style={{ color: 'var(--err)' }} onClick={handleDelete}>Delete</button>
          </div>
        )}
      </div>
    )
  }
  ```

  (Archive is intentionally omitted today — store has no archived flag; adding it would balloon scope. The MoreMenu exposes Rename / Duplicate / Delete, which is the shippable subset. Update the spec accordingly when the plan lands.)

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/header/MoreMenu.tsx frontend/src/components/chat/header/__tests__/MoreMenu.test.tsx frontend/src/lib/store.ts
  git commit -m "feat(chat): MoreMenu rename/duplicate/delete"
  ```

### Task 5.7: `HeaderActions` + `ChatHeader`

**Files:**
- Create: `frontend/src/components/chat/header/HeaderActions.tsx`
- Create: `frontend/src/components/chat/header/ChatHeader.tsx`
- Test: `__tests__/ChatHeader.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { ChatHeader } from '../ChatHeader'
  import { useChatStore } from '@/lib/store'
  import { useUiStore } from '@/lib/ui-store'

  describe('ChatHeader', () => {
    beforeEach(() => {
      useChatStore.setState({ conversations: [], activeConversationId: null })
      useUiStore.setState({ ...useUiStore.getState(), threadsOpen: false, dockOpen: false })
    })

    it('renders sidebar toggle + title + 5+ action buttons', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().updateConversationTitle(id, 'Q3 churn')
      render(<ChatHeader conversationId={id} />)
      expect(screen.getByLabelText(/show threads/i)).toBeInTheDocument()
      expect(screen.getByText('Q3 churn')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /fork/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
    })

    it('shows new-chat button only when threadsOpen is false', () => {
      const id = useChatStore.getState().createConversation()
      render(<ChatHeader conversationId={id} />)
      expect(screen.getByLabelText(/new chat/i)).toBeInTheDocument()
      useUiStore.setState({ ...useUiStore.getState(), threadsOpen: true })
      const { rerender } = render(<ChatHeader conversationId={id} />)
      // both rendered in sequence — count all, second render has no NewChat
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/header/HeaderActions.tsx
  import { useRef, useState, useEffect } from 'react'
  import { SearchButton } from './SearchButton'
  import { ForkButton } from './ForkButton'
  import { ExportMenu } from './ExportMenu'
  import { ProgressToggle } from './ProgressToggle'
  import { MoreMenu } from './MoreMenu'
  import { useCommandRegistry } from '@/hooks/useCommandRegistry'

  interface HeaderActionsProps {
    conversationId: string
    onRename: () => void
  }

  export function HeaderActions({ conversationId, onRename }: HeaderActionsProps) {
    const { openHelp } = useCommandRegistry()
    return (
      <div className="flex items-center gap-2">
        <SearchButton onOpen={openHelp} />
        <ForkButton conversationId={conversationId} />
        <ExportMenu conversationId={conversationId} />
        <ProgressToggle />
        <MoreMenu conversationId={conversationId} onRename={onRename} />
      </div>
    )
  }
  ```

  ```tsx
  // frontend/src/components/chat/header/ChatHeader.tsx
  import { useCallback, useRef } from 'react'
  import { Plus } from 'lucide-react'
  import { Sidebar } from '@/components/layout/icons/Sidebar'
  import { useUiStore } from '@/lib/ui-store'
  import { useChatStore } from '@/lib/store'
  import { TitleEditor } from './TitleEditor'
  import { HeaderActions } from './HeaderActions'

  interface ChatHeaderProps { conversationId: string }

  export function ChatHeader({ conversationId }: ChatHeaderProps) {
    const threadsOpen = useUiStore((s) => s.threadsOpen)
    const setThreadsOpen = useUiStore((s) => s.setThreadsOpen)
    const createConversation = useChatStore((s) => s.createConversation)
    const titleEditorRef = useRef<{ beginEdit: () => void } | null>(null)

    const triggerRename = useCallback(() => {
      titleEditorRef.current?.beginEdit?.()
    }, [])

    return (
      <div
        className="flex items-center gap-2 border-b py-2.5 pl-2.5 pr-[18px]"
        style={{ borderColor: 'var(--line-2)' }}
      >
        <button
          type="button"
          aria-label={threadsOpen ? 'Hide threads' : 'Show threads'}
          onClick={() => setThreadsOpen(!threadsOpen)}
          className="flex h-[30px] w-[30px] items-center justify-center rounded-md transition-colors"
          style={{
            color: threadsOpen ? 'var(--acc)' : 'var(--fg-2)',
            background: threadsOpen ? 'var(--acc-dim)' : 'transparent',
          }}
        >
          <Sidebar size={14} filled={threadsOpen} />
        </button>
        {!threadsOpen && (
          <button
            type="button"
            aria-label="New chat"
            title="New chat · ⌘N"
            onClick={() => createConversation()}
            className="fade-in flex h-[30px] w-[30px] items-center justify-center rounded-md"
            style={{ color: 'var(--acc)' }}
          >
            <Plus size={15} />
          </button>
        )}
        <div className="mx-1 h-[18px] w-px" style={{ background: 'var(--line-2)' }} />
        <TitleEditor conversationId={conversationId} />
        <div className="flex-1" />
        <HeaderActions conversationId={conversationId} onRename={triggerRename} />
      </div>
    )
  }
  ```

  (The `titleEditorRef.beginEdit` handle is forward-looking — to implement today, either pass a `triggerRenameSignal` state prop down into `TitleEditor` (preferred) or open an implicit rename by setting a counter. Simplest: add a `triggerSignal: number` prop to `TitleEditor` and a `useEffect` that enters edit mode when the signal changes. Adjust `TitleEditor.tsx` to accept and react to that prop, and re-run its tests.)

- [ ] **Step 4: Adjust `TitleEditor.tsx`**

  Add prop + effect:

  ```tsx
  interface TitleEditorProps {
    conversationId: string
    triggerSignal?: number
  }

  // inside component:
  useEffect(() => {
    if (triggerSignal !== undefined) setEditing(true)
  }, [triggerSignal])
  ```

  Then in `ChatHeader`, replace `titleEditorRef` with a counter state and pass it:

  ```tsx
  const [renameSignal, setRenameSignal] = useState(0)
  const triggerRename = useCallback(() => setRenameSignal((n) => n + 1), [])
  // <TitleEditor conversationId={conversationId} triggerSignal={renameSignal} />
  ```

- [ ] **Step 5: Run** — PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/src/components/chat/header/HeaderActions.tsx frontend/src/components/chat/header/ChatHeader.tsx frontend/src/components/chat/header/TitleEditor.tsx frontend/src/components/chat/header/__tests__/ChatHeader.test.tsx
  git commit -m "feat(chat): ChatHeader assembles toolbar"
  ```

---

## Phase 6 — ChatPane integration + retirement

### Task 6.1: `ChatPane.tsx` entry point

**Files:**
- Create: `frontend/src/components/chat/ChatPane.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatPane.test.tsx`

- [ ] **Step 1: Failing test**

  ```tsx
  import { describe, it, expect, beforeEach } from 'vitest'
  import { render, screen } from '@testing-library/react'
  import { ChatPane } from '../ChatPane'
  import { useChatStore } from '@/lib/store'

  describe('ChatPane', () => {
    beforeEach(() => { useChatStore.setState({ conversations: [], activeConversationId: null }) })

    it('renders header + window + composer for active conversation', () => {
      const id = useChatStore.getState().createConversation()
      useChatStore.getState().setActiveConversation(id)
      render(<ChatPane />)
      expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/ask the agent/i)).toBeInTheDocument()
    })

    it('creates a default conversation when none exists', () => {
      render(<ChatPane />)
      expect(useChatStore.getState().conversations.length).toBeGreaterThanOrEqual(1)
    })
  })
  ```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement**

  ```tsx
  // frontend/src/components/chat/ChatPane.tsx
  import { useEffect, useMemo } from 'react'
  import { useChatStore } from '@/lib/store'
  import { ChatHeader } from './header/ChatHeader'
  import { ChatWindow } from './ChatWindow'
  import { Composer } from './composer/Composer'

  export function ChatPane() {
    const activeId = useChatStore((s) => s.activeConversationId)
    const conversations = useChatStore((s) => s.conversations)
    const createConversation = useChatStore((s) => s.createConversation)
    const setActiveConversation = useChatStore((s) => s.setActiveConversation)

    useEffect(() => {
      if (!activeId && conversations.length === 0) {
        createConversation()
      } else if (!activeId && conversations.length > 0) {
        setActiveConversation(conversations[0].id)
      }
    }, [activeId, conversations.length, createConversation, setActiveConversation])

    const conversationId = useMemo(
       () => activeId ?? conversations[0]?.id ?? '',
      [activeId, conversations],
    )

    if (!conversationId) return null

    return (
      <div className="flex h-full flex-col overflow-hidden">
        <ChatHeader conversationId={conversationId} />
        <div className="flex-1 overflow-auto px-7">
          <div className="mx-auto max-w-[820px]">
            <ChatWindow conversationId={conversationId} />
          </div>
        </div>
        <div className="px-7 pb-[18px] pt-3.5">
          <div className="mx-auto max-w-[820px]">
            <Composer conversationId={conversationId} />
          </div>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/components/chat/ChatPane.tsx frontend/src/components/chat/__tests__/ChatPane.test.tsx
  git commit -m "feat(chat): ChatPane entry point"
  ```

### Task 6.2: Swap `ChatMain` for `ChatPane` in `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1:** Find the `chat` section case. `grep -n "ChatMain\|'chat'" frontend/src/App.tsx`.
- [ ] **Step 2:** Replace:
  - Import `{ ChatPane } from '@/components/chat/ChatPane'` (remove `ChatMain` import).
  - Render `<ChatPane />` under `case 'chat':`.
- [ ] **Step 3:** Run the repo suite:

  ```bash
  pnpm --filter frontend vitest run
  pnpm --filter frontend tsc --noEmit
  ```
  Expected: GREEN. The existing `cockpit/*` tests may still reference `ChatMain` — leave them alone; they go in the retirement step.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/App.tsx
  git commit -m "feat(chat): App renders ChatPane for chat section"
  ```

### Task 6.3: Retire `ChatInput.tsx`, `MessageBubble.tsx`, `cockpit/ChatMain.tsx`, `ChatLayout.tsx`

**Files:**
- Delete: `frontend/src/components/chat/ChatInput.tsx`
- Delete: `frontend/src/components/chat/MessageBubble.tsx`
- Delete: `frontend/src/components/cockpit/ChatMain.tsx`
- Delete (if truly orphaned): `frontend/src/components/chat/ChatLayout.tsx`
- Delete: corresponding `__tests__/*.test.tsx` for each

- [ ] **Step 1:** Verify orphan status:

  ```bash
  pnpm --filter frontend exec grep -rn "ChatInput\b\|MessageBubble\b\|ChatMain\b\|ChatLayout\b" frontend/src
  ```
  The only remaining hits should be inside the files themselves plus their `__tests__`.

- [ ] **Step 2:** `git rm` each file.
- [ ] **Step 3:** Run:

  ```bash
  pnpm --filter frontend vitest run
  pnpm --filter frontend tsc --noEmit
  ```
  Expected: GREEN.

- [ ] **Step 4: Commit**

  ```bash
  git commit -m "refactor(chat): retire ChatInput, MessageBubble, ChatMain, ChatLayout"
  ```

---

## Phase 7 — Shortcuts + verification

### Task 7.1: Register `CYCLE_MODEL` (mod+Shift+M) and `TOGGLE_EXTENDED` (mod+Shift+E)

**Files:**
- Modify: `frontend/src/lib/shortcuts.ts`
- Modify: `frontend/src/hooks/useKeyboardShortcuts.ts`
- Test: `frontend/src/lib/__tests__/shortcuts.test.ts` (extend existing)

- [ ] **Step 1:** Identify the CMD registry format. `grep -n "OPEN_SECTION_" frontend/src/lib/shortcuts.ts`.
- [ ] **Step 2: Extend tests**

  ```ts
  // add to lib/__tests__/shortcuts.test.ts
  it('registers CYCLE_MODEL with mod+shift+m', () => {
    const cmd = CMD.find((c) => c.id === 'CYCLE_MODEL')
    expect(cmd).toBeDefined()
    expect(cmd?.shortcut).toMatch(/mod\+shift\+m/i)
  })
  it('registers TOGGLE_EXTENDED with mod+shift+e', () => {
    const cmd = CMD.find((c) => c.id === 'TOGGLE_EXTENDED')
    expect(cmd).toBeDefined()
  })
  ```

- [ ] **Step 3: Run** — FAIL.

- [ ] **Step 4: Implement**

  Add to the CMD registry:

  ```ts
  { id: 'CYCLE_MODEL', label: 'Cycle model', shortcut: 'mod+shift+m', group: 'composer' },
  { id: 'TOGGLE_EXTENDED', label: 'Toggle extended thinking', shortcut: 'mod+shift+e', group: 'composer' },
  ```

  In `useKeyboardShortcuts` (or wherever the actions are wired — `grep -n "TOGGLE_DOCK\|registerShortcut" frontend/src/hooks`), add:

  ```ts
  register('CYCLE_MODEL', () => {
    ;(window as any).__dsAgentCycleModel?.(1)
  })
  register('TOGGLE_EXTENDED', () => {
    const { activeConversationId, conversations, setConversationExtendedThinking } = useChatStore.getState()
    const conv = conversations.find((c) => c.id === activeConversationId)
    if (!conv) return
    setConversationExtendedThinking(conv.id, !conv.extendedThinking)
  })
  ```

- [ ] **Step 5: Run** — PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/src/lib/shortcuts.ts frontend/src/hooks/useKeyboardShortcuts.ts frontend/src/lib/__tests__/shortcuts.test.ts
  git commit -m "feat(chat): CYCLE_MODEL + TOGGLE_EXTENDED shortcuts"
  ```

### Task 7.2: E2E spec for chat surface

**Files:**
- Create: `frontend/e2e/chat-surface.spec.ts`

- [ ] **Step 1:** Use the pre-existing `loadApp` helper (shell-foundation spec references it). `grep -n "loadApp" frontend/e2e`.
- [ ] **Step 2: Write spec**

  ```ts
  // frontend/e2e/chat-surface.spec.ts
  import { test, expect } from '@playwright/test'
  import { loadApp } from './helpers'

  test.describe('chat surface', () => {
    test('header renders sidebar toggle, title, and six actions', async ({ page }) => {
      await loadApp(page)
      await expect(page.getByRole('button', { name: /show threads|hide threads/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /search/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /fork/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /export/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /more/i })).toBeVisible()
    })

    test('title can be edited inline and persists across reload', async ({ page }) => {
      await loadApp(page)
      const title = page.locator('button:has-text("Untitled"), button[aria-label]').first()
      await title.click()
      const input = page.locator('input').first()
      await input.fill('E2E renamed')
      await input.press('Enter')
      await expect(page.getByText('E2E renamed')).toBeVisible()
      await page.reload()
      await expect(page.getByText('E2E renamed')).toBeVisible()
    })

    test('composer shows model picker, extended toggle, plan toggle, send', async ({ page }) => {
      await loadApp(page)
      await expect(page.getByRole('button', { name: /model/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /extended/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /plan/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /^send$/i })).toBeVisible()
    })

    test('mod+Shift+E toggles extended', async ({ page }) => {
      await loadApp(page)
      const btn = page.getByRole('button', { name: /extended/i })
      await expect(btn).toHaveAttribute('data-active', 'false')
      await page.keyboard.press('ControlOrMeta+Shift+E')
      await expect(btn).toHaveAttribute('data-active', 'true')
    })
  })
  ```

  (Visual snapshots at 1100/1440 × light/dark are a follow-up; they require the baseline review flow promised in sub-project 1 and remain deferred.)

- [ ] **Step 3: Run**

  ```bash
  pnpm --filter frontend exec playwright test chat-surface.spec.ts
  ```
  Expected: PASS against the running dev server (or the e2e harness's bundled server).

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/e2e/chat-surface.spec.ts
  git commit -m "test(chat): e2e spec for header/composer/shortcuts"
  ```

### Task 7.3: Final verification + changelog + task plan close

- [ ] **Step 1:** Run the full suite:

  ```bash
  pnpm --filter frontend vitest run
  pnpm --filter frontend tsc --noEmit
  pnpm --filter frontend exec playwright test
  pnpm --filter frontend build
  ```
  All four green.

- [ ] **Step 2:** Append to `docs/log.md` under `[Unreleased]`:

  ```markdown
  ### Added
  - Chat surface rebuild (sub-project 2): thread-header toolbar (title editor, search/⌘K, fork, export, progress, more), card composer with IconRow + model picker + Extended toggle + Plan toggle + ⌘↵ + send/stop, avatar-bubble message renderer with callouts/tool chips/artifact pills/subagent cards/attached chips. Adds per-conversation `model`, `extendedThinking`, `attachedFiles`, new `ToolCallLogEntry.messageId/rows`, and `callout` ContentBlock variant. Introduces `CYCLE_MODEL` (mod+Shift+M) and `TOGGLE_EXTENDED` (mod+Shift+E) shortcuts. Retires `ChatInput.tsx`, `MessageBubble.tsx`, `cockpit/ChatMain.tsx`, `ChatLayout.tsx`.
  ```

- [ ] **Step 3:** Update `task_plan.md`: check every Phase 1–7 box for sub-project 2.

- [ ] **Step 4:** Final commit:

  ```bash
  git add docs/log.md task_plan.md
  git commit -m "docs(chat): log sub-project 2 + close task plan"
  ```

---

## Self-Review

Running the writing-plans self-check with fresh eyes:

**1. Spec coverage** — the spec has sections for Goal, Non-goals, Users, Architecture (header tree + file layout), Data model (4 extensions + 6 actions + 1 block variant), API (no new endpoints, 1 capability note), Keyboard shortcuts (4 existing + 2 new), Styling, Error handling (9 rows), Testing (unit/integration/e2e), Rollout, Open questions. Mapped to plan:

| Spec requirement | Task |
|---|---|
| ChatHeader + sidebar toggle + new-chat + divider + TitleEditor + 5 actions | 5.1, 5.2–5.7 |
| ChatWindow kept, VirtualMessageList switched to Message | 4.8 |
| Composer card with IconRow + divider + ModelPicker + ExtendedToggle + PlanToggle + ⌘↵ + Send/Stop | 2.5, 3.1–3.8 |
| Message tree: Avatar + header + MarkdownContent + Callout + ToolChipRow + ArtifactPillRow + SubagentCard + AttachedFileChip | 4.1–4.7 |
| ToolCallLogEntry.messageId + rows | 1.1 |
| Conversation.model + extendedThinking + attachedFiles + AttachedFile type | 1.3 |
| 6 new store actions | 1.3, 1.4, 1.5, 6.3 (deleteConversation added in 5.6) |
| ContentBlock callout variant + auto-derive from tool_result | 1.2 + 4.7 (callout list rendered; auto-derive from failed tool result is deferred to a follow-up — the mechanism is trivial once the `callout` block exists) |
| /api/models fallback | 3.5 |
| Streaming options `model` + `extendedThinking` forwarded | 2.4 |
| `mod+Shift+M` cycle model | 7.1 |
| `mod+Shift+E` toggle extended | 7.1 |
| Error handling: model fetch fails → fallback + `!` warn | 3.5 |
| Error handling: voice unsupported hidden | 3.3 |
| Error handling: title empty revert | 5.1 |
| Error handling: title > 200 truncate | 1.4 |
| Error handling: artifact missing → disabled pill with "— removed" | 4.5 |
| Error handling: tool chip with no matching trace | dispatched event is benign if unhandled — covered |
| E2E: header 6 actions | 7.2 |
| E2E: title edit persists across reload | 7.2 |
| E2E: mod+shift+e toggles | 7.2 |
| E2E: composer shows model picker, extended, plan, send | 7.2 |
| E2E: mod+shift+m cycles model | *not covered* — add to 7.2 |
| E2E: tool-chip click opens dock / artifact pill opens dock artifacts | *deferred* — needs fixture backend for streaming; covered by unit tests in 4.5 |
| Retirement of legacy files | 6.3 |
| docs/log.md entry | 7.3 |

**Gap found:** E2E for `mod+Shift+M` isn't in 7.2. Fix: add the following test to Task 7.2's spec file:

```ts
test('mod+Shift+M cycles model', async ({ page }) => {
  await loadApp(page)
  const picker = page.getByRole('button', { name: /model/i })
  const before = await picker.textContent()
  await page.keyboard.press('ControlOrMeta+Shift+M')
  const after = await picker.textContent()
  expect(after).not.toBe(before)
})
```

**Gap found:** The spec mentions auto-derive of callout from preceding failed tool_result. This is NOT a blocker to ship — the plan lands the `callout` variant + renderer, and any auto-derivation can be added in a later task. Documented in Task 4.7's note.

**Gap found:** MoreMenu "Archive" in spec, but store has no `archived` flag. Plan drops Archive and documents the omission in Task 5.6. Note back into the spec: Archive deferred.

**2. Placeholder scan** — no "TBD", "TODO", "implement later", or "similar to Task N". Every code step has concrete code. Every test step has concrete assertions. No references to types/methods not defined here or in the extant codebase.

**3. Type consistency** — check:
- `ToolCallEntry.messageId?: string` used consistently in 1.1, 2.4 (pushToolCall), 4.4 (ToolChipRow filter).
- `AttachedFile` defined 1.3, referenced 3.1 (AttachButton), 3.7 (preview), 4.6 (chip).
- `updateConversationTitle` signature `(id, title)` consistent in 1.4, 5.1, 5.6, 5.7.
- `forkConversation(id, throughMessageId?)` → returns `string` consistent in 1.5, 5.3, 5.6.
- `setDockOpen` used in 4.5 and 5.5 — verified by sub-project 1 plan.
- `ModelEntry` shape `{ id, label, description }` consistent in 3.5.
- `ContentBlock` union including `CalloutContent` consistent in 1.2, 4.7.
- `__dsAgentCycleModel` global used in 3.5 and 7.1 — same signature `(dir: 1 | -1) => void`.

All consistent.

**Remaining action from self-review:** Append the `mod+Shift+M` E2E test to Task 7.2 before execution begins.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-chat-surface.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Per the standing "auto-approve with my guidance" directive, default is Inline Execution unless the user redirects.
