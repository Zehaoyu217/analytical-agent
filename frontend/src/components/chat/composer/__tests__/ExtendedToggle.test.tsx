import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ExtendedToggle } from '../ExtendedToggle'
import { useChatStore } from '@/lib/store'

describe('ExtendedToggle', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('flips extendedThinking on click', () => {
    const id = useChatStore.getState().createConversation()
    render(<ExtendedToggle conversationId={id} />)
    fireEvent.click(screen.getByRole('button', { name: /extended/i }))
    const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv.extendedThinking).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: /extended/i }))
    const conv2 = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv2.extendedThinking).toBe(false)
  })
})
