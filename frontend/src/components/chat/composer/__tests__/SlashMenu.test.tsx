import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SlashMenu } from '../SlashMenu'
import type { SlashCommand } from '@/lib/api-backend'

const list: SlashCommand[] = [
  { id: 'help', label: 'Help', description: 'open help' },
  { id: 'clear', label: 'Clear', description: 'wipe thread' },
]

describe('SlashMenu', () => {
  it('renders each command with / prefix + description', () => {
    render(<SlashMenu commands={list} highlight={0} onPick={() => {}} onHover={() => {}} />)
    expect(screen.getByText('/help')).toBeInTheDocument()
    expect(screen.getByText('open help')).toBeInTheDocument()
  })

  it('fires onPick on click', () => {
    const onPick = vi.fn()
    render(<SlashMenu commands={list} highlight={0} onPick={onPick} onHover={() => {}} />)
    fireEvent.click(screen.getByText('/clear'))
    expect(onPick).toHaveBeenCalledWith(list[1])
  })

  it('applies active styles to highlight index', () => {
    render(<SlashMenu commands={list} highlight={1} onPick={() => {}} onHover={() => {}} />)
    const rows = screen.getAllByRole('option')
    expect(rows[1].getAttribute('aria-selected')).toBe('true')
    expect(rows[0].getAttribute('aria-selected')).toBe('false')
  })
})
