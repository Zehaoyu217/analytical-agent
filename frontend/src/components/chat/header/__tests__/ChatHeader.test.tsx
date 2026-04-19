import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatHeader } from '../ChatHeader'
import { useChatStore } from '@/lib/store'
import { useUiStore } from '@/lib/ui-store'
import { CommandRegistryProvider } from '@/hooks/useCommandRegistry'

function renderWithCommands(ui: React.ReactNode) {
  return render(<CommandRegistryProvider>{ui}</CommandRegistryProvider>)
}

describe('ChatHeader', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
    useUiStore.setState({ ...useUiStore.getState(), threadsOpen: false, dockOpen: false })
  })

  it('renders sidebar toggle + title + action buttons', () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().updateConversationTitle(id, 'Q3 churn')
    renderWithCommands(<ChatHeader conversationId={id} />)
    expect(screen.getByLabelText(/show threads/i)).toBeInTheDocument()
    expect(screen.getByText('Q3 churn')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /fork/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  })

  it('shows new-chat button only when threadsOpen is false', () => {
    const id = useChatStore.getState().createConversation()
    renderWithCommands(<ChatHeader conversationId={id} />)
    expect(screen.getByLabelText(/new chat/i)).toBeInTheDocument()
  })
})
