import { nanoid } from 'nanoid'
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { DEFAULT_MODEL } from './constants'
import { extractTextContent } from './utils'
import type { ContentBlock } from './types'
import { backend, type Conversation as BackendConversation } from './api-backend'

export type TodoStatus = 'pending' | 'in_progress' | 'completed'

export interface TodoItem {
  id: string
  content: string
  status: TodoStatus
}

export interface Artifact {
  id: string
  type: 'chart' | 'table' | 'diagram' | 'profile' | 'analysis' | 'file'
  title: string
  content: string  // JSON string for vega-lite/table-json, raw HTML for html, mermaid code for mermaid, raw text for csv/text
  format: 'vega-lite' | 'mermaid' | 'table-json' | 'html' | 'csv' | 'text'
  session_id: string
  created_at: number
  metadata: Record<string, unknown>
}

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

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string | ContentBlock[]
  timestamp: number
  status: 'complete' | 'sending' | 'streaming' | 'error'
  traceId?: string
  artifactIds?: string[]
}

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
  context?: ContextShape
  pinned?: boolean
  // Epoch milliseconds. Presence = frozen (immutable checkpoint). One-way.
  frozenAt?: number | null
}

export type SidebarTab = 'chats' | 'agents' | 'skills' | 'history' | 'files' | 'devtools' | 'settings'
export type RightPanelTab = 'artifacts' | 'scratchpad' | 'tools'
export type SectionId =
  | 'chat'
  | 'agents'
  | 'skills'
  | 'prompts'
  | 'context'
  | 'health'
  | 'graph'
  | 'digest'
  | 'ingest'
  | 'settings'

export interface Settings {
  model: string
}

export type ToolCallStatus = 'pending' | 'ok' | 'error' | 'blocked'

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
  messageId?: string
  rows?: string
}

// DevTools content is dense — widen sidebar on first switch if it's too narrow.
const DEVTOOLS_MIN_WIDTH = 500
const DEVTOOLS_TARGET_WIDTH = 520

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  sidebarOpen: boolean
  sidebarWidth: number
  sidebarTab: SidebarTab
  settings: Settings
  draftInput: string
  rightPanelOpen: boolean
  rightPanelTab: RightPanelTab
  toolCallLog: ToolCallEntry[]
  scratchpad: string
  todos: TodoItem[]
  artifacts: Artifact[]
  activeSection: SectionId
  // Plan mode gates dangerous tools (execute_python, save_artifact, ...) and
  // injects a plan-only instruction into the system prompt. Backend enforces
  // the gate; this flag only controls the UI affordance + request payload.
  planMode: boolean
  searchPanelOpen: boolean

  createConversation: () => string
  setActiveConversation: (id: string) => void
  clearActiveConversation: () => void
  updateConversationModel: (id: string, modelId: string) => void
  setConversationExtendedThinking: (id: string, enabled: boolean) => void
  addAttachedFile: (conversationId: string, file: AttachedFile) => void
  removeAttachedFile: (conversationId: string, fileId: string) => void
  clearAttachedFiles: (conversationId: string) => void
  updateConversationTitle: (id: string, title: string) => void
  forkConversation: (conversationId: string, throughMessageId?: string) => string
  deleteConversation: (id: string) => void
  addMessage: (conversationId: string, msg: Omit<Message, 'id' | 'timestamp'>) => string
  updateMessage: (conversationId: string, messageId: string, patch: Partial<Message>) => void
  setConversationSessionId: (conversationId: string, sessionId: string) => void
  setConversationContext: (conversationId: string, context: ContextShape) => void
  unloadFile: (conversationId: string, fileId: string) => void
  loadConversation: (id: string) => Promise<void>
  createConversationRemote: (title: string) => Promise<string>
  refreshConversations: () => Promise<void>
  setConversationPinned: (id: string, pinned: boolean) => Promise<void>
  freezeConversation: (id: string) => Promise<void>
  duplicateConversation: (id: string) => Promise<string>
  renameConversation: (id: string, title: string) => Promise<void>
  deleteConversationRemote: (id: string) => Promise<void>
  toggleSidebar: () => void
  setSidebarWidth: (w: number) => void
  setSidebarTab: (t: SidebarTab) => void
  focusDevTools: () => void
  toggleRightPanel: () => void
  setRightPanelTab: (t: RightPanelTab) => void
  pushToolCall: (entry: Omit<ToolCallEntry, 'id'>) => string
  updateToolCallById: (id: string, patch: Partial<ToolCallEntry>) => void
  clearToolCallLog: () => void
  setScratchpad: (content: string) => void
  clearScratchpad: () => void
  setTodos: (todos: TodoItem[]) => void
  clearTodos: () => void
  setDraftInput: (s: string) => void
  deleteMessage: (conversationId: string, messageId: string) => void
  updateSettings: (patch: Partial<Settings>) => void
  openSettings: () => void
  openSearch: () => void
  closeSearch: () => void
  setActiveSection: (section: SectionId) => void
  addArtifact: (artifact: Artifact) => void
  clearArtifacts: () => void
  setPlanMode: (enabled: boolean) => void
  togglePlanMode: () => void
}

const DEFAULT_CONVERSATION_TITLE = 'New Conversation'

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      sidebarOpen: true,
      sidebarWidth: 280,
      sidebarTab: 'chats',
      settings: { model: DEFAULT_MODEL },
      draftInput: '',
      rightPanelOpen: false,
      rightPanelTab: 'tools' as RightPanelTab,
      toolCallLog: [] as ToolCallEntry[],
      scratchpad: '',
      todos: [] as TodoItem[],
      artifacts: [] as Artifact[],
      activeSection: 'chat' as SectionId,
      planMode: false,
      searchPanelOpen: false,

      createConversation: () => {
        const id = nanoid()
        const now = Date.now()
        const conversation: Conversation = {
          id,
          title: DEFAULT_CONVERSATION_TITLE,
          messages: [],
          createdAt: now,
          updatedAt: now,
        }
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          activeConversationId: id,
        }))
        return id
      },

      setActiveConversation: (id) => set({ activeConversationId: id }),

      updateConversationModel: (id, modelId) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, model: modelId, updatedAt: Date.now() } : c,
          ),
        })),

      setConversationExtendedThinking: (id, enabled) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, extendedThinking: enabled, updatedAt: Date.now() } : c,
          ),
        })),

      addAttachedFile: (conversationId, file) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId
              ? { ...c, attachedFiles: [...(c.attachedFiles ?? []), file], updatedAt: Date.now() }
              : c,
          ),
        })),

      removeAttachedFile: (conversationId, fileId) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId
              ? {
                  ...c,
                  attachedFiles: (c.attachedFiles ?? []).filter((f) => f.id !== fileId),
                  updatedAt: Date.now(),
                }
              : c,
          ),
        })),

      clearAttachedFiles: (conversationId) =>
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId ? { ...c, attachedFiles: [], updatedAt: Date.now() } : c,
          ),
        })),

      updateConversationTitle: (id, title) =>
        set((state) => {
          const trimmed = title.trim().slice(0, 200)
          if (!trimmed) return state
          return {
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, title: trimmed, updatedAt: Date.now() } : c,
            ),
          }
        }),

      forkConversation: (conversationId, throughMessageId) => {
        const src = get().conversations.find((c) => c.id === conversationId)
        if (!src) return ''
        const cutIndex = throughMessageId
          ? src.messages.findIndex((m) => m.id === throughMessageId)
          : src.messages.length - 1
        const copied =
          cutIndex >= 0 ? src.messages.slice(0, cutIndex + 1).map((m) => ({ ...m })) : []
        const newId = nanoid()
        set((state) => ({
          conversations: [
            ...state.conversations,
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

      deleteConversation: (id) =>
        set((state) => ({
          conversations: state.conversations.filter((c) => c.id !== id),
          activeConversationId:
            state.activeConversationId === id ? null : state.activeConversationId,
        })),

      clearActiveConversation: () =>
        set((state) => {
          const id = state.activeConversationId
          if (!id) return {}
          return {
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, messages: [], updatedAt: Date.now() } : c,
            ),
          }
        }),

      addMessage: (conversationId, msg) => {
        const id = nanoid()
        const now = Date.now()
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c
            const nextMessages = [...c.messages, { ...msg, id, timestamp: now }]
            // Auto-title from the first user message (works for both string and ContentBlock[] shapes)
            const preview = extractTextContent(msg.content)
            const nextTitle =
              c.title === DEFAULT_CONVERSATION_TITLE &&
              msg.role === 'user' &&
              preview
                ? preview.slice(0, 60)
                : c.title
            return {
              ...c,
              messages: nextMessages,
              title: nextTitle,
              updatedAt: now,
            }
          }),
        }))
        return id
      },

      updateMessage: (conversationId, messageId, patch) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, ...patch } : m,
              ),
              updatedAt: Date.now(),
            }
          }),
        }))
      },

      setConversationSessionId: (conversationId, sessionId) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId ? { ...c, sessionId } : c,
          ),
        }))
      },

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

      loadConversation: async (id: string) => {
        const conv = await backend.conversations.get(id)
        const hydrated = backendConversationToStore(conv)
        set((state) => {
          const existing = state.conversations.find((c) => c.id === hydrated.id)
          const nextConversations = existing
            ? state.conversations.map((c) =>
                c.id === hydrated.id ? { ...c, ...hydrated } : c,
              )
            : [hydrated, ...state.conversations]
          return {
            conversations: nextConversations,
            activeConversationId: hydrated.id,
          }
        })
      },

      createConversationRemote: async (title: string) => {
        const conv = await backend.conversations.create(title)
        const hydrated = backendConversationToStore(conv)
        set((state) => ({
          conversations: [hydrated, ...state.conversations],
          activeConversationId: hydrated.id,
        }))
        return hydrated.id
      },

      refreshConversations: async () => {
        const list = await backend.conversations.list()
        set((state) => {
          const byId = new Map(state.conversations.map((c) => [c.id, c]))
          for (const s of list) {
            const existing = byId.get(s.id)
            if (existing) {
              byId.set(s.id, {
                ...existing,
                title: s.title,
                createdAt: Math.round(s.created_at * 1000),
                updatedAt: Math.round(s.updated_at * 1000),
                pinned: s.pinned ?? false,
                frozenAt:
                  typeof s.frozen_at === 'number' ? Math.round(s.frozen_at * 1000) : null,
              })
            } else {
              byId.set(s.id, {
                id: s.id,
                title: s.title,
                messages: [],
                createdAt: Math.round(s.created_at * 1000),
                updatedAt: Math.round(s.updated_at * 1000),
                pinned: s.pinned ?? false,
                frozenAt:
                  typeof s.frozen_at === 'number' ? Math.round(s.frozen_at * 1000) : null,
              })
            }
          }
          return { conversations: Array.from(byId.values()) }
        })
      },

      setConversationPinned: async (id, pinned) => {
        // Optimistic update; revert on error.
        const prev = get().conversations.find((c) => c.id === id)?.pinned ?? false
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, pinned } : c,
          ),
        }))
        try {
          await backend.conversations.patch(id, { pinned })
        } catch (err) {
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, pinned: prev } : c,
            ),
          }))
          throw err
        }
      },

      freezeConversation: async (id) => {
        const nowSec = Date.now() / 1000
        const prev = get().conversations.find((c) => c.id === id)?.frozenAt ?? null
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, frozenAt: Math.round(nowSec * 1000) } : c,
          ),
        }))
        try {
          await backend.conversations.patch(id, { frozen_at: nowSec })
        } catch (err) {
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, frozenAt: prev } : c,
            ),
          }))
          throw err
        }
      },

      renameConversation: async (id, title) => {
        const prev = get().conversations.find((c) => c.id === id)?.title ?? ''
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title } : c,
          ),
        }))
        try {
          await backend.conversations.patch(id, { title })
        } catch (err) {
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === id ? { ...c, title: prev } : c,
            ),
          }))
          throw err
        }
      },

      deleteConversationRemote: async (id) => {
        await backend.conversations.delete(id)
        set((state) => {
          const remaining = state.conversations.filter((c) => c.id !== id)
          return {
            conversations: remaining,
            activeConversationId:
              state.activeConversationId === id ? null : state.activeConversationId,
          }
        })
      },

      duplicateConversation: async (id) => {
        const source = get().conversations.find((c) => c.id === id)
        if (!source) throw new Error('conversation not found')
        const copy = await backend.conversations.create(`${source.title} (copy)`)
        // Replay messages into the new conversation server-side.
        for (const m of source.messages) {
          if (m.role !== 'user' && m.role !== 'assistant') continue
          const text = typeof m.content === 'string' ? m.content : ''
          if (!text) continue
          await backend.conversations.appendTurn(copy.id, m.role, text)
        }
        const fresh = await backend.conversations.get(copy.id)
        const hydrated = backendConversationToStore(fresh)
        set((state) => ({
          conversations: [hydrated, ...state.conversations],
          activeConversationId: hydrated.id,
        }))
        return hydrated.id
      },

      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      setSidebarWidth: (w) => set({ sidebarWidth: w }),

      setSidebarTab: (t) =>
        set((state) => {
          // DevTools needs more horizontal room than the default sidebar width.
          if (t === 'devtools' && state.sidebarWidth < DEVTOOLS_MIN_WIDTH) {
            return {
              sidebarTab: t,
              sidebarWidth: Math.max(state.sidebarWidth, DEVTOOLS_TARGET_WIDTH),
            }
          }
          return { sidebarTab: t }
        }),

      focusDevTools: () =>
        set((state) => {
          const widen =
            state.sidebarWidth < DEVTOOLS_MIN_WIDTH
              ? Math.max(state.sidebarWidth, DEVTOOLS_TARGET_WIDTH)
              : state.sidebarWidth
          return {
            sidebarTab: 'devtools' as SidebarTab,
            sidebarOpen: true,
            sidebarWidth: widen,
          }
        }),

      toggleRightPanel: () => set((state) => ({ rightPanelOpen: !state.rightPanelOpen })),

      setRightPanelTab: (t) => set({ rightPanelTab: t, rightPanelOpen: true }),

      pushToolCall: (entry) => {
        const id = nanoid()
        set((state) => ({ toolCallLog: [...state.toolCallLog, { ...entry, id }] }))
        return id
      },

      updateToolCallById: (id, patch) =>
        set((state) => ({
          toolCallLog: state.toolCallLog.map((e) =>
            e.id === id ? { ...e, ...patch } : e,
          ),
        })),

      clearToolCallLog: () => set({ toolCallLog: [] }),
      setScratchpad: (content) => set({ scratchpad: content }),
      clearScratchpad: () => set({ scratchpad: '' }),
      setTodos: (todos) => set({ todos }),
      clearTodos: () => set({ todos: [] }),

      setDraftInput: (s) => set({ draftInput: s }),

      deleteMessage: (conversationId, messageId) =>
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c
            return { ...c, messages: c.messages.filter((m) => m.id !== messageId) }
          }),
        })),

      updateSettings: (patch) =>
        set((state) => ({ settings: { ...state.settings, ...patch } })),

      openSettings: () => {
        set({ activeSection: 'settings' })
      },

      openSearch: () => set({ searchPanelOpen: true }),
      closeSearch: () => set({ searchPanelOpen: false }),

      setActiveSection: (section) => set({ activeSection: section }),

      addArtifact: (artifact) =>
        set((state) => {
          // Upsert: update if already exists
          const existingIdx = state.artifacts.findIndex((a) => a.id === artifact.id)
          if (existingIdx >= 0) {
            const updated = [...state.artifacts]
            updated[existingIdx] = artifact
            return { artifacts: updated }
          }
          return { artifacts: [...state.artifacts, artifact] }
        }),

      clearArtifacts: () => set({ artifacts: [] }),

      setPlanMode: (enabled) => set({ planMode: enabled }),
      togglePlanMode: () => set((state) => ({ planMode: !state.planMode })),
    }),
    {
      name: 'chat-store-v2',
      version: 2,
      storage: createJSONStorage(() => localStorage),
      // v1 used a narrower Message.content type (string-only). Rather than
      // translate in place, drop old state entirely — this data is client-only
      // dev state with no production users, so a clean slate is safe.
      migrate: (_persistedState, _version) => ({
        conversations: [],
        activeConversationId: null,
        sidebarOpen: true,
        sidebarWidth: 280,
        sidebarTab: 'chats' as SidebarTab,
        settings: { model: DEFAULT_MODEL },
      }),
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
        sidebarOpen: state.sidebarOpen,
        sidebarWidth: state.sidebarWidth,
        sidebarTab: state.sidebarTab,
        settings: state.settings,
        planMode: state.planMode,
      }),
    },
  ),
)

/**
 * Convert a backend Conversation (unix seconds, `turns` as {role, content,
 * timestamp}) into the store's Conversation shape (millisecond `Date.now()`
 * timestamps, `messages` with nanoid ids + status). Backend turns are always
 * complete by definition, so status is 'complete'.
 */
function backendConversationToStore(conv: BackendConversation): Conversation {
  const messages: Message[] = conv.turns
    .filter((t) => t.role !== 'system')
    .map((t) => ({
      id: nanoid(),
      role: t.role as 'user' | 'assistant',
      content: t.content,
      timestamp: Math.round(t.timestamp * 1000),
      status: 'complete' as const,
    }))
  return {
    id: conv.id,
    title: conv.title,
    messages,
    createdAt: Math.round(conv.created_at * 1000),
    updatedAt: Math.round(conv.updated_at * 1000),
    pinned: conv.pinned ?? false,
    frozenAt:
      typeof conv.frozen_at === 'number' ? Math.round(conv.frozen_at * 1000) : null,
  }
}
