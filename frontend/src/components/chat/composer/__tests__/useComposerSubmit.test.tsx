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
