import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Avatar } from '../Avatar'

describe('Avatar', () => {
  it('renders user initial with gradient', () => {
    render(<Avatar role="user" initial="M" />)
    const el = screen.getByLabelText('user avatar')
    expect(el.textContent).toBe('M')
    expect(el.style.background).toMatch(/linear-gradient/)
  })

  it('renders assistant avatar with initial', () => {
    render(<Avatar role="assistant" initial="D" />)
    const el = screen.getByLabelText('assistant avatar')
    expect(el.textContent).toBe('D')
  })
})
