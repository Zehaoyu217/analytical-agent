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
