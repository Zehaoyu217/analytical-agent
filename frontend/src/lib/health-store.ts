import { create } from 'zustand'

export interface HealthSummary {
  score: number
  grade?: string
  components?: Record<string, number>
  breakdown?: Record<string, number>
}

export interface DigestBuildSummary {
  duration_ms: number
  outcome: string
  entries: number
  emitted: boolean
}

interface DigestCostsResponse {
  ok: boolean
  record: {
    duration_ms?: number
    outcome?: string
    detail?: { entries?: number; emitted?: boolean }
  } | null
}

interface HealthState {
  loading: boolean
  error: string | null
  stats: Record<string, unknown> | null
  health: HealthSummary | null
  todayCost: DigestBuildSummary | null
  refresh: () => Promise<void>
}

export const useHealthStore = create<HealthState>((set) => ({
  loading: false,
  error: null,
  stats: null,
  health: null,
  todayCost: null,

  async refresh() {
    set({ loading: true, error: null })
    try {
      const [statsRes, costsRes] = await Promise.all([
        fetch('/api/sb/stats'),
        fetch('/api/sb/digest/costs'),
      ])

      if (statsRes.status === 404) {
        set({ loading: false, stats: null, health: null, todayCost: null })
        return
      }
      if (!statsRes.ok) {
        throw new Error(`stats ${statsRes.status}`)
      }
      const data = (await statsRes.json()) as {
        stats?: Record<string, unknown>
        health?: HealthSummary
      }

      let todayCost: DigestBuildSummary | null = null
      if (costsRes.ok) {
        const body = (await costsRes.json()) as DigestCostsResponse
        const rec = body.record
        if (rec && typeof rec.duration_ms === 'number') {
          todayCost = {
            duration_ms: rec.duration_ms,
            outcome: rec.outcome ?? 'unknown',
            entries: rec.detail?.entries ?? 0,
            emitted: Boolean(rec.detail?.emitted),
          }
        }
      }

      set({
        loading: false,
        stats: data.stats ?? null,
        health: data.health ?? null,
        todayCost,
      })
    } catch (err: unknown) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Unexpected error',
      })
    }
  },
}))
