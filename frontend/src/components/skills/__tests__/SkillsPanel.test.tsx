import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SkillsPanel } from '../SkillsPanel'
import { useSkillsStore, aggregateUsage, countToday } from '@/lib/skills-store'

function seed(partial: Partial<ReturnType<typeof useSkillsStore.getState>>) {
  useSkillsStore.setState({
    loading: false,
    error: null,
    events: [],
    ...partial,
  })
}

beforeEach(() => {
  global.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ ok: true, count: 0, events: [] }), {
      status: 200,
    }),
  ) as typeof fetch
  seed({})
})

describe('SkillsPanel', () => {
  it('returns null when closed', () => {
    const { container } = render(<SkillsPanel open={false} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders empty state when no events', () => {
    render(<SkillsPanel open onClose={() => {}} />)
    expect(screen.getByText(/no skill invocations yet/i)).toBeInTheDocument()
  })

  it('aggregates and renders rows most-used first', () => {
    seed({
      events: [
        {
          timestamp: '2026-04-18T12:00:00Z',
          actor: 'skill:foo',
          duration_ms: 1,
          outcome: 'ok',
        },
        {
          timestamp: '2026-04-18T12:00:05Z',
          actor: 'skill:foo',
          duration_ms: 2,
          outcome: 'ok',
        },
        {
          timestamp: '2026-04-18T12:01:00Z',
          actor: 'skill:bar',
          duration_ms: 3,
          outcome: 'error',
        },
      ],
    })
    render(<SkillsPanel open onClose={() => {}} />)
    const rows = screen.getAllByTestId('skills-row')
    expect(rows).toHaveLength(2)
    // foo has 2, bar has 1 — foo first
    expect(rows[0]).toHaveTextContent('foo')
    expect(rows[0]).toHaveTextContent('2 invocations')
    expect(rows[1]).toHaveTextContent('bar')
    expect(rows[1]).toHaveTextContent('1 invocations')
  })
})

describe('skills-store helpers', () => {
  it('aggregateUsage sorts by count and tracks latest outcome', () => {
    const usage = aggregateUsage([
      {
        timestamp: '2026-04-18T10:00:00Z',
        actor: 'skill:foo',
        duration_ms: 1,
        outcome: 'ok',
      },
      {
        timestamp: '2026-04-18T11:00:00Z',
        actor: 'skill:foo',
        duration_ms: 2,
        outcome: 'error',
      },
      {
        timestamp: '2026-04-18T12:00:00Z',
        actor: 'skill:bar',
        duration_ms: 3,
        outcome: 'ok',
      },
    ])
    expect(usage[0].name).toBe('foo')
    expect(usage[0].count).toBe(2)
    expect(usage[0].lastOutcome).toBe('error')
    expect(usage[0].lastTimestamp).toBe('2026-04-18T11:00:00Z')
  })

  it('countToday matches the UTC date prefix', () => {
    const today = new Date().toISOString().slice(0, 10)
    const n = countToday([
      {
        timestamp: `${today}T10:00:00Z`,
        actor: 'skill:foo',
        duration_ms: 1,
        outcome: 'ok',
      },
      {
        timestamp: '1999-01-01T10:00:00Z',
        actor: 'skill:bar',
        duration_ms: 1,
        outcome: 'ok',
      },
    ])
    expect(n).toBe(1)
  })

  it('refresh fetches telemetry and stores events', async () => {
    global.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          ok: true,
          count: 1,
          events: [
            {
              timestamp: '2026-04-18T10:00:00Z',
              actor: 'skill:foo',
              duration_ms: 1,
              outcome: 'ok',
            },
          ],
        }),
        { status: 200 },
      ),
    ) as typeof fetch
    await useSkillsStore.getState().refresh()
    expect(useSkillsStore.getState().events).toHaveLength(1)
    expect(useSkillsStore.getState().events[0].actor).toBe('skill:foo')
  })
})
