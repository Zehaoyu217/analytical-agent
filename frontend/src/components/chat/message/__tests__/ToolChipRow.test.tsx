import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ToolChipRow } from '../ToolChipRow'
import { useChatStore } from '@/lib/store'

describe('ToolChipRow', () => {
  beforeEach(() => {
    useChatStore.setState({ toolCallLog: [] })
  })

  it('renders only entries matching messageId', () => {
    useChatStore.getState().pushToolCall({
      step: 0,
      name: 'a',
      inputPreview: '',
      status: 'ok',
      messageId: 'm1',
      startedAt: 0,
    })
    useChatStore.getState().pushToolCall({
      step: 0,
      name: 'b',
      inputPreview: '',
      status: 'ok',
      messageId: 'm2',
      startedAt: 0,
    })
    render(<ToolChipRow messageId="m1" />)
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.queryByText('b')).toBeNull()
  })

  it('renders nothing when no matches', () => {
    const { container } = render(<ToolChipRow messageId="missing" />)
    expect(container.firstChild).toBeNull()
  })
})
