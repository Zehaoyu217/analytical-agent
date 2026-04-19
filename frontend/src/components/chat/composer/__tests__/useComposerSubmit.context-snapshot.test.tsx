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
    useChatStore.setState({ conversations: [], activeConversationId: null, toolCallLog: [] })
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
    expect(conv.context?.layers[0].maxTokens).toBe(16_000)
  })
})
