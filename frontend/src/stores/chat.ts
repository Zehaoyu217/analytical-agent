import { create } from 'zustand'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  traceId?: string
  timestamp: number
}

interface ChatState {
  sessionId: string | null
  messages: ChatMessage[]
  sending: boolean
  error: string | null
  setSessionId: (id: string | null) => void
  appendMessage: (msg: ChatMessage) => void
  setSending: (sending: boolean) => void
  setError: (error: string | null) => void
  newSession: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  sending: false,
  error: null,
  setSessionId: (id) => set({ sessionId: id }),
  appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setSending: (sending) => set({ sending }),
  setError: (error) => set({ error }),
  newSession: () => set({ sessionId: null, messages: [], error: null }),
}))
