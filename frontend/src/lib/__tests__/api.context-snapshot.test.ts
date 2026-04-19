import { describe, it, expect } from 'vitest'
import type { ChatStreamEvent } from '@/lib/api'

describe('ChatStreamEvent', () => {
  it('includes context_snapshot variant with layer + file + budget fields', () => {
    const ev: ChatStreamEvent = {
      type: 'context_snapshot',
      layers: [{ id: 'sys', label: 'system', tokens: 8_000, max_tokens: 16_000 }],
      loaded_files: [{ id: 'f1', name: 'data.csv', size: 2048, kind: 'csv' }],
      total_tokens: 42_000,
      budget_tokens: 200_000,
    }
    expect(ev.type).toBe('context_snapshot')
    expect(ev.layers?.[0].label).toBe('system')
    expect(ev.loaded_files?.[0].kind).toBe('csv')
  })
})
