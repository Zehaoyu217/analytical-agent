import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DockProgress } from '../DockProgress'
import { useChatStore } from '@/lib/store'

describe('DockProgress', () => {
  beforeEach(() => {
    useChatStore.setState({ toolCallLog: [] } as never)
  })

  it('shows empty state when no tool calls', () => {
    render(<DockProgress />)
    expect(screen.getByText(/no steps yet/i)).toBeInTheDocument()
  })

  it('renders one StepCard per tool call', () => {
    useChatStore.setState({
      toolCallLog: [
        { id: 'a', step: 1, name: 'first', inputPreview: '', status: 'ok', startedAt: 1, finishedAt: 2 },
        { id: 'b', step: 2, name: 'second', inputPreview: '', status: 'pending', startedAt: 3 },
      ],
    } as never)
    render(<DockProgress />)
    expect(screen.getByText('first')).toBeInTheDocument()
    expect(screen.getByText('second')).toBeInTheDocument()
  })
})
