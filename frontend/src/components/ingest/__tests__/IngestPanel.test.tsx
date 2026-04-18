import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IngestPanel } from '../IngestPanel'
import {
  useIngestStore,
  countRecentFailures,
  shortPath,
} from '@/lib/ingest-store'

function seed(partial: Partial<ReturnType<typeof useIngestStore.getState>>) {
  useIngestStore.setState({
    recent: [],
    submitting: false,
    error: null,
    ...partial,
  })
}

beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(
      JSON.stringify({ ok: true, source_id: 'src_ok', folder: '/tmp/x' }),
      { status: 200 },
    ),
  ) as typeof fetch
  seed({})
})

describe('IngestPanel', () => {
  it('returns null when closed', () => {
    const { container } = render(
      <IngestPanel open={false} onClose={() => {}} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders dropzone and empty recent', () => {
    render(<IngestPanel open onClose={() => {}} />)
    expect(screen.getByTestId('ingest-dropzone')).toBeInTheDocument()
    expect(screen.getByText(/no ingests yet/i)).toBeInTheDocument()
  })

  it('submit posts to /api/sb/ingest and records recent event', async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(
        JSON.stringify({ ok: true, source_id: 'src_abc', folder: '/tmp/abc' }),
        { status: 200 },
      ),
    ) as typeof fetch
    global.fetch = fetchSpy

    render(<IngestPanel open onClose={() => {}} />)
    const input = screen.getByTestId('ingest-input') as HTMLInputElement
    fireEvent.change(input, { target: { value: '/tmp/demo.md' } })
    fireEvent.click(screen.getByTestId('ingest-submit'))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/sb/ingest',
        expect.objectContaining({ method: 'POST' }),
      )
    })
    await waitFor(() => {
      expect(
        screen.getAllByTestId('ingest-recent-row').length,
      ).toBeGreaterThan(0)
    })
    const row = screen.getAllByTestId('ingest-recent-row')[0]
    expect(row).toHaveTextContent('OK')
  })

  it('records failure when api returns 404', async () => {
    global.fetch = vi.fn(async () =>
      new Response('x', { status: 404 }),
    ) as typeof fetch
    render(<IngestPanel open onClose={() => {}} />)
    const input = screen.getByTestId('ingest-input') as HTMLInputElement
    fireEvent.change(input, { target: { value: '/tmp/x' } })
    fireEvent.click(screen.getByTestId('ingest-submit'))
    await waitFor(() => {
      expect(useIngestStore.getState().recent).toHaveLength(1)
    })
    expect(useIngestStore.getState().recent[0].outcome).toBe('error')
  })
})

describe('ingest-store helpers', () => {
  it('countRecentFailures only counts recent errors', () => {
    const now = 1_000_000
    const events = [
      { timestamp: now - 5_000, path: 'a', outcome: 'error' as const },
      { timestamp: now - 5_000, path: 'b', outcome: 'ok' as const },
      { timestamp: now - 120_000, path: 'c', outcome: 'error' as const },
    ]
    expect(countRecentFailures(events, 60_000, now)).toBe(1)
  })

  it('shortPath abbreviates long paths to trailing segments', () => {
    const p = '/some/really/long/nested/directory/tree/file.md'
    expect(shortPath(p, 20).length).toBeLessThanOrEqual(24)
  })
})
