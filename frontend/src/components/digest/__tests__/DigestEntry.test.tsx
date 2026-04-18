import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DigestEntry } from '../DigestEntry'

describe('DigestEntry', () => {
  it('renders id and line text and fires callbacks on button clicks', () => {
    const onApply = vi.fn()
    const onSkip = vi.fn()
    render(
      <DigestEntry
        entry={{
          id: 'r01',
          section: 'Reconciliation',
          line: 'upgrade foo',
          action: 'upgrade_confidence',
          applied: false,
        }}
        onApply={onApply}
        onSkip={onSkip}
      />,
    )
    expect(screen.getByText('[r01]')).toBeInTheDocument()
    expect(screen.getByText(/upgrade foo/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith('r01')

    fireEvent.click(screen.getByRole('button', { name: /skip/i }))
    expect(onSkip).toHaveBeenCalledWith('r01')
  })

  it('applies the "applied" className and hides action buttons when applied', () => {
    render(
      <DigestEntry
        entry={{
          id: 'r02',
          section: 'Reconciliation',
          line: 'already done',
          action: 'keep',
          applied: true,
        }}
        onApply={() => {}}
        onSkip={() => {}}
      />,
    )
    const node = screen.getByTestId('digest-entry')
    expect(node.className).toMatch(/applied/)
    expect(screen.queryByRole('button', { name: /apply/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /skip/i })).toBeNull()
  })
})
