import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchButton } from '../SearchButton'

describe('SearchButton', () => {
  it('renders Search label + ⌘K kbd + fires onOpen on click', () => {
    const spy = vi.fn()
    render(<SearchButton onOpen={spy} />)
    expect(screen.getByText('Search')).toBeInTheDocument()
    expect(screen.getByText('⌘K')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button'))
    expect(spy).toHaveBeenCalled()
  })
})
