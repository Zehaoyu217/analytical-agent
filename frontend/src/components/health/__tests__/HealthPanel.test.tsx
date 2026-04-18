import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HealthPanel } from '../HealthPanel'
import { useHealthStore } from '@/lib/health-store'

function seed(partial: Partial<ReturnType<typeof useHealthStore.getState>>) {
  useHealthStore.setState({
    loading: false,
    error: null,
    stats: null,
    health: null,
    todayCost: null,
    drift: null,
    ...partial,
  })
}

beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ ok: true, stats: null, health: null }), {
      status: 200,
    }),
  ) as typeof fetch
  seed({})
})

describe('HealthPanel', () => {
  it('returns null when closed', () => {
    const { container } = render(<HealthPanel open={false} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders empty state when no data', () => {
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText(/knowledge base disabled/i)).toBeInTheDocument()
  })

  it('renders score, grade, and component rows when populated', () => {
    seed({
      stats: { claims: 12 },
      health: { score: 87, grade: 'B', components: { coverage: 0.9 } },
    })
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText('87')).toBeInTheDocument()
    expect(screen.getByText('B')).toBeInTheDocument()
    expect(screen.getByText('coverage')).toBeInTheDocument()
    expect(screen.getByText('claims')).toBeInTheDocument()
  })

  it('shows muted digest build section when no record today', () => {
    seed({ health: { score: 80 } })
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText(/digest build · today/i)).toBeInTheDocument()
    expect(screen.getByText(/no build yet today/i)).toBeInTheDocument()
  })

  it('renders digest build summary when todayCost is present', () => {
    seed({
      health: { score: 80 },
      todayCost: {
        duration_ms: 1234,
        outcome: 'ok',
        entries: 12,
        emitted: true,
      },
    })
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText('1234ms')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('ok')).toBeInTheDocument()
  })

  it('shows muted drift section when no snapshot', () => {
    seed({ health: { score: 80 } })
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText(/drift · today/i)).toBeInTheDocument()
    expect(screen.getByText(/no drift scan yet/i)).toBeInTheDocument()
  })

  it('renders drift counts when snapshot is present', () => {
    seed({
      health: { score: 80 },
      drift: {
        total: 5,
        orphan_claims: 2,
        orphan_backlinks: 1,
        stale_claims: 2,
        timestamp: '2026-04-18T00:00:00Z',
      },
    })
    render(<HealthPanel open onClose={() => {}} />)
    expect(screen.getByText(/orphan claims/i)).toBeInTheDocument()
    expect(screen.getByText(/orphan backlinks/i)).toBeInTheDocument()
    expect(screen.getByText(/stale claims/i)).toBeInTheDocument()
  })
})
