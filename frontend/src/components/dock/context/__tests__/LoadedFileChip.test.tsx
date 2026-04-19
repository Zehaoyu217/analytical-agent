import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LoadedFileChip } from '../LoadedFileChip'

describe('LoadedFileChip', () => {
  it('renders kind, name, size; onUnload fires on × click', () => {
    const onUnload = vi.fn()
    render(
      <LoadedFileChip
        file={{ id: 'a', name: 'iris.csv', size: 4096, kind: 'csv' }}
        onUnload={onUnload}
      />,
    )
    expect(screen.getByText('csv')).toBeInTheDocument()
    expect(screen.getByText('iris.csv')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /unload/i }))
    expect(onUnload).toHaveBeenCalledWith('a')
  })
})
