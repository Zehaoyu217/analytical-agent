import { create } from 'zustand'

export interface HealthSummary {
  score: number
  grade?: string
  components?: Record<string, number>
  breakdown?: Record<string, number>
}

interface HealthState {
  loading: boolean
  error: string | null
  stats: Record<string, unknown> | null
  health: HealthSummary | null
  refresh: () => Promise<void>
}

export const useHealthStore = create<HealthState>((set) => ({
  loading: false,
  error: null,
  stats: null,
  health: null,

  async refresh() {
    set({ loading: true, error: null })
    try {
      const res = await fetch('/api/sb/stats')
      if (res.status === 404) {
        set({ loading: false, stats: null, health: null })
        return
      }
      if (!res.ok) {
        throw new Error(`stats ${res.status}`)
      }
      const data = (await res.json()) as {
        stats?: Record<string, unknown>
        health?: HealthSummary
      }
      set({
        loading: false,
        stats: data.stats ?? null,
        health: data.health ?? null,
      })
    } catch (err: unknown) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : 'Unexpected error',
      })
    }
  },
}))
