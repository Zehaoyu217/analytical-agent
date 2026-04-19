import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MessageHeader } from '../MessageHeader'

describe('MessageHeader', () => {
  it('renders name + timestamp', () => {
    render(<MessageHeader name="Martin" timestamp="14:02:11" onCopy={() => {}} />)
    expect(screen.getByText('Martin')).toBeInTheDocument()
    expect(screen.getByText('14:02:11')).toBeInTheDocument()
  })

  it('fires onCopy on copy button click', () => {
    const spy = vi.fn()
    render(<MessageHeader name="x" timestamp="t" onCopy={spy} />)
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(spy).toHaveBeenCalled()
  })
})
