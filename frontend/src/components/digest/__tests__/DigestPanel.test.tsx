import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DigestPanel } from '../DigestPanel'
import { useDigestStore } from '@/lib/digest-store'

function seedStore(partial: Partial<ReturnType<typeof useDigestStore.getState>>) {
  useDigestStore.setState({
    date: '2026-04-18',
    entries: [],
    unread: 0,
    loading: false,
    error: null,
    ...partial,
  })
}

beforeEach(() => {
  // Panel calls refresh() via useEffect; stub fetch so it doesn't reach network.
  global.fetch = vi.fn(async () =>
    new Response(
      JSON.stringify({ ok: true, date: '2026-04-18', entries: [], unread: 0 }),
      { status: 200 },
    ),
  ) as typeof fetch
  seedStore({})
})

describe('DigestPanel', () => {
  it('returns null when closed', () => {
    const { container } = render(<DigestPanel open={false} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders entries grouped by section', () => {
    seedStore({
      date: '2026-04-18',
      unread: 2,
      entries: [
        {
          id: 'r01',
          section: 'Reconciliation',
          line: 'a',
          action: 'keep',
          applied: false,
        },
        {
          id: 't01',
          section: 'Taxonomy',
          line: 'b',
          action: 'keep',
          applied: false,
        },
      ],
    })
    render(<DigestPanel open onClose={() => {}} />)
    expect(screen.getByText('Reconciliation')).toBeInTheDocument()
    expect(screen.getByText('Taxonomy')).toBeInTheDocument()
    expect(screen.getAllByTestId('digest-entry')).toHaveLength(2)
  })

  it('renders empty state when no entries', () => {
    seedStore({ entries: [], unread: 0 })
    render(<DigestPanel open onClose={() => {}} />)
    expect(screen.getByText(/no pending/i)).toBeInTheDocument()
  })

  it('renders DIGEST title and unread count in header', () => {
    seedStore({ date: '2026-04-18', unread: 3 })
    render(<DigestPanel open onClose={() => {}} />)
    expect(screen.getByText('DIGEST')).toBeInTheDocument()
    expect(screen.getByText(/3 unread/)).toBeInTheDocument()
  })
})
