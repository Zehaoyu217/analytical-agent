import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PlanToggle } from '../PlanToggle'

describe('PlanToggle', () => {
  it('renders Plan label', () => {
    render(<PlanToggle enabled={false} onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: /plan mode/i })).toBeInTheDocument()
  })

  it('applies active styling when enabled', () => {
    render(<PlanToggle enabled={true} onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: /plan mode/i })).toHaveAttribute('data-active', 'true')
  })

  it('fires onToggle on click', () => {
    const spy = vi.fn()
    render(<PlanToggle enabled={false} onToggle={spy} />)
    fireEvent.click(screen.getByRole('button', { name: /plan mode/i }))
    expect(spy).toHaveBeenCalled()
  })
})
