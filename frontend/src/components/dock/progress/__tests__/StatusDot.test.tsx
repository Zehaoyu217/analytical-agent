import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusDot } from '../StatusDot'

describe('StatusDot', () => {
  it.each(['queued', 'running', 'ok', 'err'] as const)(
    'renders with data-status=%s',
    (status) => {
      const { container } = render(<StatusDot status={status} />)
      const el = container.querySelector('[data-status]')
      expect(el).not.toBeNull()
      expect(el!.getAttribute('data-status')).toBe(status)
    },
  )
})
