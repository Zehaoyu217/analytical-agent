import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '@/lib/store'
import { backend } from '@/lib/api-backend'
import { GlobalSearchPanel } from '../GlobalSearchPanel'

const FAKE_RESULTS = [
  {
    session_id: 'sess-001',
    message_id: 'msg-001',
    snippet: 'how do I forecast the SP500 returns',
    role: 'user',
    timestamp: 1_700_000_000,
  },
  {
    session_id: 'sess-001',
    message_id: 'msg-002',
    snippet: 'forecast horizon of 5 days using ARIMA',
    role: 'assistant',
    timestamp: 1_700_000_010,
  },
  {
    session_id: 'sess-002',
    message_id: 'msg-003',
    snippet: 'forecast volatility with GARCH',
    role: 'user',
    timestamp: 1_700_001_000,
  },
]

async function openPanelAndType(query: string): Promise<HTMLInputElement> {
  act(() => {
    useChatStore.getState().openSearch()
  })

  // Wait for the dialog to mount + auto-focus.
  await waitFor(() => {
    const el = document.querySelector<HTMLInputElement>('#global-search-input')
    expect(el).not.toBeNull()
  })

  const input = document.querySelector<HTMLInputElement>('#global-search-input')!
  act(() => {
    fireEvent.change(input, { target: { value: query } })
  })
  return input
}

describe('<GlobalSearchPanel>', () => {
  beforeEach(() => {
    useChatStore.setState({ searchPanelOpen: false })
    window.location.hash = ''
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not render dialog content when closed', () => {
    render(<GlobalSearchPanel />)
    expect(document.querySelector('#global-search-input')).toBeNull()
  })

  it('opens, debounces query, and groups results by session', async () => {
    const searchSpy = vi
      .spyOn(backend.sessions, 'search')
      .mockResolvedValue(FAKE_RESULTS)

    render(<GlobalSearchPanel />)
    await openPanelAndType('forecast')

    await waitFor(() => expect(searchSpy).toHaveBeenCalledTimes(1))
    expect(searchSpy).toHaveBeenCalledWith('forecast', 20)

    await waitFor(() => {
      expect(document.body.textContent).toContain('how do I forecast the SP500 returns')
    })
    expect(document.body.textContent).toContain('forecast volatility with GARCH')
    // Both messages from sess-001 shown under one group header.
    expect(document.body.textContent).toContain('sess-001')
    expect(document.body.textContent).toContain('sess-002')
  })

  it('shows empty state when query has no matches', async () => {
    vi.spyOn(backend.sessions, 'search').mockResolvedValue([])
    render(<GlobalSearchPanel />)
    await openPanelAndType('nope')

    await waitFor(() => {
      expect(document.body.textContent).toContain('No matches')
    })
  })

  it('navigates to monitor page on Enter and closes panel', async () => {
    vi.spyOn(backend.sessions, 'search').mockResolvedValue(FAKE_RESULTS)
    render(<GlobalSearchPanel />)
    const input = await openPanelAndType('forecast')

    await waitFor(() => {
      expect(document.body.textContent).toContain('how do I forecast the SP500 returns')
    })

    act(() => {
      fireEvent.keyDown(input, { key: 'Enter' })
    })

    expect(window.location.hash).toBe('#/monitor/sess-001')
    expect(useChatStore.getState().searchPanelOpen).toBe(false)
  })

  it('surfaces error state on backend failure', async () => {
    vi.spyOn(backend.sessions, 'search').mockRejectedValue(
      new Error('FTS index unavailable'),
    )
    render(<GlobalSearchPanel />)
    await openPanelAndType('boom')

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('FTS index unavailable')
    })
  })
})
