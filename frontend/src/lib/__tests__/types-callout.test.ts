import { describe, it, expect } from 'vitest'
import type { ContentBlock } from '@/lib/types'

describe('ContentBlock callout variant', () => {
  it('accepts a callout block at the type level', () => {
    const block: ContentBlock = {
      type: 'callout',
      kind: 'warn',
      label: 'data quality',
      text: '31.2% null · non-random · source-correlated',
    }
    expect(block.type).toBe('callout')
  })
})
