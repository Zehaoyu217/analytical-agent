import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatPane } from '../ChatPane'
import { useChatStore } from '@/lib/store'
import { CommandRegistryProvider } from '@/hooks/useCommandRegistry'

function renderPane() {
  return render(
    <CommandRegistryProvider>
      <ChatPane />
    </CommandRegistryProvider>,
  )
}

describe('ChatPane', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('renders header + window + composer for active conversation', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().setActiveConversation(id)
    renderPane()
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/ask the agent/i)).toBeInTheDocument()
  })

  it('creates a default conversation when none exists', () => {
    renderPane()
    expect(useChatStore.getState().conversations.length).toBeGreaterThanOrEqual(1)
  })
})
