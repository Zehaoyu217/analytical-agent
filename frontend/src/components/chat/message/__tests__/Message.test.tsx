import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Message } from '../Message'
import { useChatStore } from '@/lib/store'
import type { Message as MessageRecord } from '@/lib/store'

describe('Message', () => {
  beforeEach(() => {
    useChatStore.setState({
      toolCallLog: [],
      artifacts: [],
      conversations: [],
      activeConversationId: null,
    })
  })

  it('renders user avatar + text + attached chip', () => {
    const msg: MessageRecord = {
      id: 'm1',
      role: 'user',
      content: 'hello',
      status: 'complete',
      timestamp: 1745000000000,
    }
    render(<Message message={msg} attachedNames={['q3-brief.md']} />)
    expect(screen.getByLabelText('user avatar')).toBeInTheDocument()
    expect(screen.getByText('hello')).toBeInTheDocument()
    expect(screen.getByText('q3-brief.md')).toBeInTheDocument()
  })

  it('renders assistant avatar + callout + tool chips + artifact pills', () => {
    useChatStore.getState().pushToolCall({
      step: 0,
      name: 'read_file',
      inputPreview: 'q.parquet',
      status: 'ok',
      messageId: 'm2',
      startedAt: 0,
      finishedAt: 100,
    })
    useChatStore.getState().addArtifact({
      id: 'art1',
      type: 'chart',
      title: 'residuals.png',
      content: '',
      format: 'vega-lite',
      session_id: '',
      created_at: 0,
      metadata: {},
    })
    const msg: MessageRecord = {
      id: 'm2',
      role: 'assistant',
      status: 'complete',
      timestamp: 1745000000000,
      content: [
        { type: 'callout', kind: 'warn', label: 'data quality', text: '31% nulls' },
        { type: 'text', text: 'baseline MAE 142.3' },
      ],
      artifactIds: ['art1'],
    }
    render(<Message message={msg} />)
    expect(screen.getByLabelText('assistant avatar')).toBeInTheDocument()
    expect(screen.getByText('data quality')).toBeInTheDocument()
    // Completed assistant messages collapse tool chips into a summary pill.
    expect(
      screen.getByRole('button', { name: /show 1 tool call/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('residuals.png')).toBeInTheDocument()
  })
})
