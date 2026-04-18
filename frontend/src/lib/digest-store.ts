import { create } from 'zustand'

export interface DigestEntry {
  id: string
  section: string
  line: string
  action: string
  applied: boolean
}

interface DigestState {
  date: string
  entries: DigestEntry[]
  unread: number
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  apply: (ids: string[]) => Promise<void>
  skip: (id: string, ttlDays?: number) => Promise<void>
  markRead: () => Promise<void>
}

export const useDigestStore = create<DigestState>((set, get) => ({
  date: '',
  entries: [],
  unread: 0,
  loading: false,
  error: null,

  async refresh() {
    set({ loading: true, error: null })
    try {
      const response = await fetch('/api/sb/digest/today')
      if (response.status === 404) {
        // Second-brain disabled — present as empty state.
        set({ date: '', entries: [], unread: 0, loading: false })
        return
      }
      const body = (await response.json()) as {
        date?: string
        entries?: DigestEntry[]
        unread?: number
      }
      set({
        date: body.date ?? '',
        entries: body.entries ?? [],
        unread: body.unread ?? 0,
        loading: false,
      })
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Unexpected error',
        loading: false,
      })
    }
  },

  async apply(ids) {
    try {
      await fetch('/api/sb/digest/apply', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ids }),
      })
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : 'Unexpected error' })
    }
    await get().refresh()
  },

  async skip(id, ttlDays = 30) {
    try {
      await fetch('/api/sb/digest/skip', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id, ttl_days: ttlDays }),
      })
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : 'Unexpected error' })
    }
    await get().refresh()
  },

  async markRead() {
    const { date } = get()
    if (!date) return
    try {
      await fetch('/api/sb/digest/read', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ date }),
      })
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : 'Unexpected error' })
    }
  },
}))
