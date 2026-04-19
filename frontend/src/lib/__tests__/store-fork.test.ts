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
