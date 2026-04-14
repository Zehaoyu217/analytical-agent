import { nanoid } from 'nanoid'
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { DEFAULT_MODEL } from './constants'
import { extractTextContent } from './utils'
import type { ContentBlock } from './types'
import { backend, type Conversation as BackendConversation } from './api-backend'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string | ContentBlock[]
  timestamp: number
  status: 'complete' | 'sending' | 'streaming' | 'error'
  traceId?: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
  sessionId?: string
}

export type SidebarTab = 'chats' | 'agents' | 'skills' | 'history' | 'files' | 'devtools' | 'settings'
export type RightPanelTab = 'artifacts' | 'scratchpad' | 'tools'

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
  artifactIds?: string[]
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

  createConversation: () => string
  setActiveConversation: (id: string) => void
  addMessage: (conversationId: string, msg: Omit<Message, 'id' | 'timestamp'>) => string
  updateMessage: (conversationId: string, messageId: string, patch: Partial<Message>) => void
  setConversationSessionId: (conversationId: string, sessionId: string) => void
  loadConversation: (id: string) => Promise<void>
  createConversationRemote: (title: string) => Promise<string>
  toggleSidebar: () => void
  setSidebarWidth: (w: number) => void
  setSidebarTab: (t: SidebarTab) => void
  focusDevTools: () => void
  toggleRightPanel: () => void
  setRightPanelTab: (t: RightPanelTab) => void
  pushToolCall: (entry: Omit<ToolCallEntry, 'id'>) => string
  updateToolCallById: (id: string, patch: Partial<ToolCallEntry>) => void
  clearToolCallLog: () => void
  setDraftInput: (s: string) => void
  updateSettings: (patch: Partial<Settings>) => void
  openSettings: () => void
  openSearch: () => void
}

const DEFAULT_CONVERSATION_TITLE = 'New Conversation'

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
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

      setDraftInput: (s) => set({ draftInput: s }),

      updateSettings: (patch) =>
        set((state) => ({ settings: { ...state.settings, ...patch } })),

      openSettings: () => {
        // Stub — Settings panel lands in a later phase
      },

      openSearch: () => {
        // Stub — Global search lands in a later phase
      },
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
  }
}
