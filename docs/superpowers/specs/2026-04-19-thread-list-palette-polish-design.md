# Thread List + Command Palette Polish — Design Spec

**Date:** 2026-04-19
**Sub-project:** 4 of 5 (DS-Agent shell rebuild)
**Status:** Approved (auto-approved by user)

## Goal

Make the left thread list and command palette feel like a power-user tool. Add **freeze checkpoints** so a conversation can be locked as an immutable reference and forked from instead of edited further. Backend persists pin and freeze state so they survive reloads and reach across devices.

## Decisions (from brainstorm)

1. **Scope:** Spec + meaningful list ergonomics (filter, pin, freeze, MoreMenu, Checkpoints section) + palette wiring. No drag/reorder, no bulk select.
2. **Persistence:** Backend-persisted via `pinned: bool` and `frozen_at: float | None` on the `Conversation` model.
3. **Freeze semantics:** **One-way**. Once frozen, the conversation rejects new turns (HTTP 409). To continue work, user duplicates (forks) and works in the copy.
4. **Checkpoints UI:** Separate **Checkpoints** section in the thread list, hidden when empty. Frozen conversations leave the active sections (today/week/older) and live there only.
5. **Filter:** Title-only substring filter input at the top of the list. No content search.
6. **Palette:** Two new groups — **Conversations** (jump-to, max 50, recency-sorted, excluding frozen) and **This conversation** (Pin/Unpin, Freeze, Rename, Duplicate, Delete, Export).

## Architecture

```
Frontend                                          Backend
─────────                                         ───────
ThreadList ──────► useChatStore ──► api-backend ──► PATCH /api/conversations/:id
  ├─ Filter input       │                              { pinned?, frozen_at? }
  ├─ Pinned section     │                          ──► POST /api/conversations/:id/turns
  ├─ Today/Week/Older   │                              → 409 if frozen
  ├─ Checkpoints        │
  └─ MoreMenu (per row) │
                        ▼
CommandPalette ───► registered commands
  ├─ Conversations group (jump-to)
  └─ This conversation group (mutating)
```

Pin and freeze state live on the `Conversation` model itself — no auxiliary tables, no client-only state.

## Backend changes

**File:** `backend/app/api/conversations_api.py`

- Add fields to `Conversation` (Pydantic, frozen=True):
  - `pinned: bool = False`
  - `frozen_at: float | None = None` (epoch seconds; presence = frozen)
- Add `PATCH /api/conversations/{conv_id}` accepting `ConversationPatch { pinned?: bool, frozen_at?: float | None, title?: str }`. Uses the per-conversation lock; replaces fields on the frozen model via `model_copy`.
- Modify `POST /api/conversations/{conv_id}/turns`: if `conv.frozen_at is not None`, return HTTP 409 with `{ detail: "conversation is frozen" }`.
- All writes go through the existing atomic-write + per-conversation lock path.

**Tests** (`backend/tests/test_conversations_api.py`):
- PATCH sets pinned and persists across reload.
- PATCH sets frozen_at and persists.
- POST turns returns 409 when frozen.
- PATCH with `frozen_at: null` is rejected (one-way) — explicit guard in handler.

## Frontend changes

### Store (`frontend/src/lib/store.ts`)

- Extend `Conversation` interface: `pinned?: boolean; frozenAt?: number | null`.
- Add actions:
  - `setPinned(id: string, value: boolean): Promise<void>` — calls `api.conversations.patch`, updates local state.
  - `freezeConversation(id: string): Promise<void>` — calls patch with `frozen_at: Date.now()/1000`, updates local state.
- `loadConversation` and list hydration must read both new fields.

### API client (`frontend/src/lib/api-backend.ts`)

- Add `patch(id, payload: { pinned?: boolean; frozen_at?: number | null; title?: string })` to the `conversations` client.

### ThreadList (`frontend/src/components/shell/ThreadList.tsx`)

- Drop the in-memory `useState<PinnedMap>`; read pinned/frozenAt from conversations.
- Add a title-filter input at the top (controlled, debounced 100 ms, case-insensitive substring on title).
- Sections (in order, each hidden when empty):
  1. **Pinned** — pinned and not frozen.
  2. **Today / Week / Older** — not pinned, not frozen, bucketed by `updatedAt`.
  3. **Checkpoints** — frozen, sorted by `frozen_at` desc.
- Per-row **MoreMenu** (lucide MoreHorizontal trigger):
  - Pin / Unpin
  - Freeze (with confirm: "Freeze this conversation? You won't be able to add new turns. To continue, duplicate it.")
  - Rename
  - Duplicate (creates a new conversation by copying turns; new conversation is unfrozen, unpinned)
  - Delete
  - Export (JSON download)
- Frozen rows render with a `Snowflake`/lock icon and a muted style; click still opens (read-only).

### Composer gating (`frontend/src/components/chat/ChatPane.tsx` or composer)

- When the active conversation has `frozenAt`, disable the input and show inline notice: "This conversation is frozen. Duplicate it to continue."
- Provide a "Duplicate" button in the notice that triggers the same Duplicate action as the MoreMenu.

### Command palette (`frontend/src/components/command-palette/CommandPalette.tsx`)

- Add **Conversations** group: dynamic items for jump-to. Up to 50 most recently updated, **excluding frozen**. Item label = title; subtitle = relative timestamp.
- Add **This conversation** group: Pin/Unpin (label flips by state), Freeze (hidden when already frozen), Rename, Duplicate, Delete, Export. Items are gated on having an active conversation.

## Error handling

- API failures: toast + revert local optimistic state.
- 409 from append: surface as the freeze notice (refresh the conversation if state is stale).
- Duplicate: shows a toast on success and routes to the new conversation.

## Testing

- Backend: pytest cases listed above.
- Frontend unit (vitest): ThreadList sectioning + filter, MoreMenu actions, palette new groups, composer freeze gating, store actions hitting mocked API.
- Coverage target: ≥80% for touched files.

## Out of scope

- Drag-to-reorder, bulk select, content search, tags/labels, multi-pin order.
- Unfreezing (one-way by design — fork to continue).
- Sync/realtime fanout (single-user assumption).
