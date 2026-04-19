import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ForkButton } from '../ForkButton'
import { useChatStore } from '@/lib/store'

describe('ForkButton', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('creates fork and adds a conversation', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().addMessage(id, { role: 'user', content: 'a', status: 'complete' })
    render(<ForkButton conversationId={id} />)
    fireEvent.click(screen.getByRole('button', { name: /fork/i }))
    expect(useChatStore.getState().conversations.length).toBe(2)
  })
})
