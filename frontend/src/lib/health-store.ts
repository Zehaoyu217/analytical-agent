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

export interface DriftSummary {
  total: number
  orphan_claims: number
  orphan_backlinks: number
  stale_claims: number
  timestamp: string
}

interface DigestCostsResponse {
  ok: boolean
  record: {
    duration_ms?: number
    outcome?: string
    detail?: { entries?: number; emitted?: boolean }
  } | null
}

interface DriftResponse {
  ok: boolean
  report: {
    timestamp?: string
    total?: number
    by_kind?: Record<string, number>
  } | null
}

interface HealthState {
  loading: boolean
  error: string | null
  stats: Record<string, unknown> | null
  health: HealthSummary | null
  todayCost: DigestBuildSummary | null
  drift: DriftSummary | null
  refresh: () => Promise<void>
}

export const useHealthStore = create<HealthState>((set) => ({
  loading: false,
  error: null,
  stats: null,
  health: null,
  todayCost: null,
  drift: null,

  async refresh() {
    set({ loading: true, error: null })
    try {
      const [statsRes, costsRes, driftRes] = await Promise.all([
        fetch('/api/sb/stats'),
        fetch('/api/sb/digest/costs'),
        fetch('/api/sb/drift'),
      ])

      if (statsRes.status === 404) {
        set({
          loading: false,
          stats: null,
          health: null,
          todayCost: null,
          drift: null,
        })
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

      let drift: DriftSummary | null = null
      if (driftRes.ok) {
        const body = (await driftRes.json()) as DriftResponse
        const rep = body.report
        if (rep && typeof rep.total === 'number') {
          const by = rep.by_kind ?? {}
          drift = {
            total: rep.total,
            orphan_claims: by.orphan_claim ?? 0,
            orphan_backlinks: by.orphan_backlink ?? 0,
            stale_claims: by.stale_claim ?? 0,
            timestamp: rep.timestamp ?? '',
          }
        }
      }

      set({
        loading: false,
        stats: data.stats ?? null,
        health: data.health ?? null,
        todayCost,
        drift,
      })
    } catch (err: unknown) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Unexpected error',
      })
    }
  },
}))
