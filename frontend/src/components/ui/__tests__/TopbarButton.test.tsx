import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TopbarButton } from '../TopbarButton'

describe('TopbarButton', () => {
  it('renders label and fires onClick', () => {
    const onClick = vi.fn()
    render(<TopbarButton label="DIGEST" slot={0} onClick={onClick} />)
    const btn = screen.getByRole('button', { name: /DIGEST/i })
    expect(btn).toHaveTextContent('DIGEST')
    fireEvent.click(btn)
    expect(onClick).toHaveBeenCalled()
  })

  it('renders count with separator when count > 0', () => {
    render(<TopbarButton label="HEALTH" slot={1} count={3} onClick={() => {}} />)
    expect(screen.getByRole('button')).toHaveTextContent('HEALTH · 3')
  })

  it('omits count when count is 0 or undefined', () => {
    render(<TopbarButton label="HEALTH" slot={1} count={0} onClick={() => {}} />)
    expect(screen.getByRole('button').textContent).toBe('HEALTH')
  })

  it('sets data attributes for active and unread', () => {
    render(
      <TopbarButton
        label="X"
        slot={2}
        active
        unread
        onClick={() => {}}
      />,
    )
    const btn = screen.getByRole('button')
    expect(btn.getAttribute('data-active')).toBe('true')
    expect(btn.getAttribute('data-unread')).toBe('true')
  })

  it('positions using slot-based top style', () => {
    render(<TopbarButton label="X" slot={2} onClick={() => {}} />)
    const btn = screen.getByRole('button')
    expect(btn.style.top).toBe('74px')
  })

  it('supports a custom aria-label', () => {
    render(
      <TopbarButton label="X" slot={0} onClick={() => {}} ariaLabel="Toggle X panel" />,
    )
    expect(screen.getByRole('button', { name: 'Toggle X panel' })).toBeInTheDocument()
  })
})
