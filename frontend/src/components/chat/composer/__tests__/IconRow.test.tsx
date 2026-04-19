import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IconRow } from '../IconRow'
import { useChatStore } from '@/lib/store'

describe('IconRow', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('renders attach + mention + skill buttons', () => {
    const id = useChatStore.getState().createConversation()
    render(
      <IconRow conversationId={id} onInsert={() => {}} onTranscript={() => {}} />,
    )
    expect(screen.getByRole('button', { name: /attach/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /mention/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /skill/i })).toBeInTheDocument()
  })
})
