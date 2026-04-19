import { describe, expect, it, beforeEach } from 'vitest'
import { useChatStore } from '@/lib/store'

describe('ToolCallLogEntry.messageId/rows', () => {
  beforeEach(() => {
    useChatStore.setState({ toolCallLog: [] })
  })

  it('stores messageId on pushToolCall', () => {
    const id = useChatStore.getState().pushToolCall({
      step: 0,
      name: 'read_file',
      inputPreview: 'q3.parquet',
      status: 'pending',
      startedAt: 0,
      messageId: 'msg-abc',
      rows: '248,913 × 42',
    })
    const entry = useChatStore.getState().toolCallLog.find((e) => e.id === id)
    expect(entry?.messageId).toBe('msg-abc')
    expect(entry?.rows).toBe('248,913 × 42')
  })
})
