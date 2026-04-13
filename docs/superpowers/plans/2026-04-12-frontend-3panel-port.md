# Frontend 3-Panel UI Port — Implementation Plan

**Goal:** Port the polished Claude Code web UI from `reference/web/` into `frontend/src/`, wired to our FastAPI backend (`/api/chat`, `/api/trace/traces`, etc.). Keep all existing trace/eval functionality.

**Architecture:** Single-page React+Vite app with Tailwind + shadcn/ui + radix. 3-column layout: left sidebar (conversations + DevTools tabs), center (Header + ChatWindow + ChatInput), right panel (optional tool/file inspector — added in P4+). Zustand stores for chat, devtools, theme, settings.

**Tech Stack:** React 18, Vite 5, TypeScript, Tailwind 3, shadcn/ui (radix primitives), framer-motion, lucide-react, react-markdown + remark-gfm, shiki, nanoid, @tanstack/react-virtual.

**Approved decisions (from 2026-04-12 conversation):**
1. Ship P1–P3 first so the UI is usable immediately.
2. UI for unbacked features (P4–P9) ships with "not connected" empty-state stubs so the UI looks complete.
3. DevTools (TracesList, SessionReplay, JudgeVariance, PromptInspector, CompactionTimeline) moves into the new UI's right/left sidebar, replacing the bottom-dock `DevToolsPanel`.
4. After P1–P3 lands, build the backend surface (BE1) before continuing to P4–P9.

---

## Phase summary

| Phase | Task ID | Deliverable | Backend needed |
|------:|--------:|-------------|----------------|
| P1 | 85 | Deps + Tailwind + path alias + layout shell wired to `/api/chat` | none |
| P2 | 86 | MessageBubble + markdown + code blocks (shiki) + virtual list | none |
| P3 | 87 | Command palette + theme + shortcuts + a11y announcer | none |
| P3b | 88 | DevTools moved to new UI sidebar | none |
| BE1 | 89 | APIs: conversations, settings, files, slash, PTY | backend build |
| P4–P9 | 90 | Conversation sidebar, settings, file explorer, slash menu, terminal, mobile, notifications, search, share | uses BE1 |

---

## P1 — Layout shell

**Dependencies to add (frontend):**
- runtime: `@radix-ui/react-{dialog,dropdown-menu,scroll-area,separator,slot,tabs,tooltip,switch,collapsible}`, `class-variance-authority`, `clsx`, `tailwind-merge`, `framer-motion`, `lucide-react`, `react-markdown`, `remark-gfm`, `shiki`, `nanoid`, `@tanstack/react-virtual`
- dev: `tailwindcss`, `postcss`, `autoprefixer`

**Files to create/modify:**
- `frontend/tailwind.config.ts` (copy/adapt from `reference/web/tailwind.config.ts`)
- `frontend/postcss.config.js`
- `frontend/src/styles/globals.css` (Tailwind directives + CSS vars from reference)
- `frontend/tsconfig.json` — add `"baseUrl": "."`, `"paths": { "@/*": ["src/*"] }`
- `frontend/vite.config.ts` — add path alias
- `frontend/src/lib/utils.ts` (cn helper)
- `frontend/src/lib/constants.ts` (MODELS, etc.)
- `frontend/src/lib/store.ts` (Zustand store adapted for our backend — conversations stubbed, active chat wired to `/api/chat`)
- `frontend/src/components/layout/{Sidebar,Header,ThemeProvider}.tsx` (ported, stubbed where needed)
- `frontend/src/components/chat/{ChatLayout,ChatWindow,ChatInput}.tsx` (ported)
- `frontend/src/components/ui/*.tsx` (shadcn primitives used by the above)
- `frontend/src/main.tsx` — import `./styles/globals.css`
- `frontend/src/App.tsx` — render `<ChatLayout>`
- Delete/archive: `frontend/src/panels/ChatPanel.tsx`, `frontend/src/devtools/DevToolsPanel.tsx` (after P3b)

**Backend contract used:** `POST /api/chat` → `{ session_id, response }`, `GET /api/trace/traces`.

---

## P2 — Message rendering

Port `components/chat/{MessageBubble,MarkdownContent,CodeBlock,ThinkingBlock,VirtualMessageList,ScrollToBottom,SuggestedPrompts,FileAttachment}.tsx`. Wire shiki for code highlighting. Virtual scroll for long conversations.

---

## P3 — Command palette + theme + shortcuts + a11y

Port `components/command-palette/`, `components/shortcuts/`, `components/search/GlobalSearch`, `hooks/useCommandRegistry`, `hooks/useKeyboardShortcuts`, `components/a11y/{SkipToContent,Announcer}`, `lib/theme`, `lib/shortcuts`, `components/ui/kbd`.

---

## P3b — DevTools in sidebar

Sidebar gains a "DevTools" section with tabs: Traces, Sessions, Judge, Prompt, Timeline. Each renders existing components from `frontend/src/devtools/`. Cmd+Shift+D toggles sidebar focus/visibility instead of the old bottom-dock panel. Delete `DevToolsPanel.tsx` once fully migrated.

---

## BE1 — Backend API build

New FastAPI routers:
- `/api/conversations` — list, create, append turn, get, delete (persist to sqlite or JSON files for now)
- `/api/settings` — GET/PUT user preferences (theme, model, etc.)
- `/api/files` — tree listing and file read within a safe root
- Slash-command registry — GET list, POST execute
- PTY — websocket terminal passthrough (big; may split)

---

## P4–P9 — Wire feature panels

Port each reference feature dir in order, connect to BE1 endpoints, replace empty-state stubs with real views.

---

## Execution handoff

Use subagent-driven-development where each phase is one subagent dispatch with spec+quality review. Do NOT merge phases — ship P1, verify with user, commit, then P2, etc. If context resets, pick up from latest incomplete task in `TaskList` and continue.
