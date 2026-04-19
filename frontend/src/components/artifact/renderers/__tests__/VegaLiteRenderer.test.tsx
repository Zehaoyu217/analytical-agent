import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { VegaLiteRenderer } from '../VegaLiteRenderer'

describe('VegaLiteRenderer', () => {
  it('shows loading placeholder before dynamic import resolves', () => {
    const { container } = render(<VegaLiteRenderer content='{"$schema":"vega-lite"}' />)
    expect(container.textContent).toMatch(/loading/i)
  })
})
