import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { TopHUD } from '../TopHUD'
import { useRightRailStore } from '@/lib/right-rail-store'
import { useChatStore } from '@/lib/store'

describe('TopHUD', () => {
  beforeEach(() => {
    localStorage.clear()
    useRightRailStore.setState({ mode: 'trace', traceTab: 'timeline' })
    useChatStore.setState({ conversations: [], activeConversationId: null })
  })

  it('renders the session chip and chip row', () => {
    render(<TopHUD />)
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /SESSION/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'GRAPH' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'DIGEST' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'INGEST' })).toBeInTheDocument()
  })

  it('toggles rail mode via the GRAPH chip via store', () => {
    render(<TopHUD />)
    const chip = screen.getByRole('button', { name: 'GRAPH' })
    expect(chip.getAttribute('data-active')).toBe('false')

    act(() => {
      useRightRailStore.getState().toggleMode('graph')
    })

    expect(useRightRailStore.getState().mode).toBe('graph')
  })
})
