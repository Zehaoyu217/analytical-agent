import { create } from 'zustand'

export interface SkillEvent {
  timestamp: string
  actor: string
  duration_ms: number
  outcome: string
  detail?: Record<string, unknown>
}

export interface SkillUsage {
  name: string
  count: number
  lastTimestamp: string
  lastOutcome: string
}

interface SkillsTelemetryResponse {
  ok: boolean
  count: number
  events: SkillEvent[]
}

interface SkillsState {
  loading: boolean
  error: string | null
  events: SkillEvent[]
  refresh: () => Promise<void>
}

export const useSkillsStore = create<SkillsState>((set) => ({
  loading: false,
  error: null,
  events: [],

  async refresh() {
    set({ loading: true, error: null })
    try {
      const res = await fetch('/api/skills/telemetry?limit=200')
      if (!res.ok) {
        throw new Error(`skills ${res.status}`)
      }
      const body = (await res.json()) as SkillsTelemetryResponse
      set({ loading: false, events: body.events ?? [] })
    } catch (err: unknown) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Unexpected error',
      })
    }
  },
}))

/** Group events by skill name, sorted by invocation count desc. */
export function aggregateUsage(events: SkillEvent[]): SkillUsage[] {
  const byName = new Map<string, SkillUsage>()
  for (const ev of events) {
    const name = ev.actor.startsWith('skill:') ? ev.actor.slice(6) : ev.actor
    const existing = byName.get(name)
    if (existing) {
      existing.count += 1
      if (ev.timestamp > existing.lastTimestamp) {
        existing.lastTimestamp = ev.timestamp
        existing.lastOutcome = ev.outcome
      }
    } else {
      byName.set(name, {
        name,
        count: 1,
        lastTimestamp: ev.timestamp,
        lastOutcome: ev.outcome,
      })
    }
  }
  return Array.from(byName.values()).sort((a, b) => b.count - a.count)
}

/** Count of events whose timestamp falls on today's UTC date. */
export function countToday(events: SkillEvent[]): number {
  const today = new Date().toISOString().slice(0, 10)
  return events.filter((e) => e.timestamp.slice(0, 10) === today).length
}
