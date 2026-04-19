import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ModelPicker } from '../ModelPicker'
import { useChatStore } from '@/lib/store'

vi.mock('@/lib/api-backend', () => ({
  backend: {
    models: {
      list: vi.fn().mockResolvedValue({
        groups: [
          {
            provider: 'anthropic',
            label: 'Anthropic',
            available: true,
            note: '',
            models: [
              { id: 'anthropic/claude-sonnet-4-6', label: 'Sonnet 4.6', description: '' },
              { id: 'anthropic/claude-opus-4-7', label: 'Opus 4.7', description: '' },
            ],
          },
        ],
      }),
    },
  },
}))

describe('ModelPicker', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('renders label of active model', async () => {
    const id = useChatStore.getState().createConversation()
    useChatStore.getState().updateConversationModel(id, 'anthropic/claude-opus-4-7')
    render(<ModelPicker conversationId={id} />)
    await waitFor(() => expect(screen.getByText('Opus 4.7')).toBeInTheDocument())
  })

  it('opens popover and persists selection', async () => {
    const id = useChatStore.getState().createConversation()
    render(<ModelPicker conversationId={id} />)
    fireEvent.click(screen.getByRole('button', { name: /model/i }))
    await waitFor(() => expect(screen.getByText('Opus 4.7')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Opus 4.7'))
    const conv = useChatStore.getState().conversations.find((c) => c.id === id)!
    expect(conv.model).toBe('anthropic/claude-opus-4-7')
  })
})
