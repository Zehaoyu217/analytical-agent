import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Composer } from '../Composer'
import { useChatStore } from '@/lib/store'

vi.mock('@/lib/api-chat', () => ({
  streamChatMessage: async function* () {
    yield { type: 'turn_end', final_text: 'ok' }
  },
}))

vi.mock('@/lib/api-backend', () => ({
  backend: {
    conversations: { appendTurn: vi.fn().mockResolvedValue({}) },
    slash: { list: vi.fn().mockResolvedValue([]) },
    models: { list: vi.fn().mockResolvedValue({ groups: [] }) },
  },
}))

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

  it('renders model picker, extended toggle, and icon row', () => {
    const id = useChatStore.getState().createConversation()
    render(<Composer conversationId={id} />)
    expect(screen.getByRole('button', { name: /model/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /extended/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /attach/i })).toBeInTheDocument()
  })

  it('renders frozen banner instead of textarea when conversation frozen', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.setState((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, frozenAt: Date.now() } : c,
      ),
    }))
    render(<Composer conversationId={id} />)
    expect(screen.queryByPlaceholderText(/ask the agent/i)).not.toBeInTheDocument()
    expect(screen.getByText(/this conversation is frozen/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /duplicate/i })).toBeInTheDocument()
  })
})
