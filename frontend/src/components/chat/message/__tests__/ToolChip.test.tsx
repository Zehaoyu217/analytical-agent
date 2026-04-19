import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ToolChip } from '../ToolChip'

describe('ToolChip', () => {
  it('renders name + args + ms', () => {
    render(
      <ToolChip
        entry={{
          id: '1',
          step: 0,
          name: 'read_file',
          inputPreview: 'q3.parquet',
          status: 'ok',
          startedAt: 0,
          finishedAt: 1240,
        }}
      />,
    )
    expect(screen.getByText('read_file')).toBeInTheDocument()
    expect(screen.getByText('q3.parquet')).toBeInTheDocument()
    expect(screen.getByText(/1240ms/)).toBeInTheDocument()
  })

  it('renders rows when present', () => {
    render(
      <ToolChip
        entry={{
          id: '1',
          step: 0,
          name: 'x',
          inputPreview: 'y',
          status: 'ok',
          startedAt: 0,
          finishedAt: 1,
          rows: '100 × 5',
        }}
      />,
    )
    expect(screen.getByText(/100 × 5/)).toBeInTheDocument()
  })

  it('dispatches scrollToTrace event on click', () => {
    const spy = vi.fn()
    window.addEventListener('scrollToTrace', spy)
    render(
      <ToolChip
        entry={{ id: 'entry-1', step: 0, name: 'x', inputPreview: 'y', status: 'ok' }}
      />,
    )
    fireEvent.click(screen.getByRole('button'))
    expect(spy).toHaveBeenCalled()
    window.removeEventListener('scrollToTrace', spy)
  })
})
