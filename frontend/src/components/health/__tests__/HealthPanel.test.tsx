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
})
