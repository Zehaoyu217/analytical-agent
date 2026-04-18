import { create } from 'zustand'

export interface IngestEvent {
  timestamp: number
  path: string
  outcome: 'ok' | 'error'
  detail?: string
}

interface IngestResponse {
  ok: boolean
  source_id?: string
  folder?: string
  error?: string
}

interface IngestState {
  recent: IngestEvent[]
  submitting: boolean
  error: string | null
  submit: (path: string) => Promise<IngestEvent>
  clear: () => void
}

const MAX_RECENT = 10

export const useIngestStore = create<IngestState>((set) => ({
  recent: [],
  submitting: false,
  error: null,

  async submit(path) {
    const trimmed = path.trim()
    if (!trimmed) {
      const ev: IngestEvent = {
        timestamp: Date.now(),
        path,
        outcome: 'error',
        detail: 'empty path',
      }
      set((s) => ({ recent: [ev, ...s.recent].slice(0, MAX_RECENT) }))
      return ev
    }
    set({ submitting: true, error: null })
    let ev: IngestEvent
    try {
      const res = await fetch('/api/sb/ingest', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ path: trimmed }),
      })
      if (res.status === 404) {
        ev = {
          timestamp: Date.now(),
          path: trimmed,
          outcome: 'error',
          detail: 'knowledge base disabled',
        }
      } else {
        const body = (await res.json()) as IngestResponse
        ev = body.ok
          ? {
              timestamp: Date.now(),
              path: trimmed,
              outcome: 'ok',
              detail: body.source_id,
            }
          : {
              timestamp: Date.now(),
              path: trimmed,
              outcome: 'error',
              detail: body.error ?? 'unknown error',
            }
      }
    } catch (err: unknown) {
      ev = {
        timestamp: Date.now(),
        path: trimmed,
        outcome: 'error',
        detail: err instanceof Error ? err.message : 'Unexpected error',
      }
      set({ error: ev.detail ?? null })
    }
    set((s) => ({
      submitting: false,
      recent: [ev, ...s.recent].slice(0, MAX_RECENT),
    }))
    return ev
  },

  clear() {
    set({ recent: [] })
  },
}))

/** Count of error ingests recorded in the last `withinMs` ms. */
export function countRecentFailures(
  recent: IngestEvent[],
  withinMs = 60_000,
  now: number = Date.now(),
): number {
  return recent.filter(
    (e) => e.outcome === 'error' && now - e.timestamp <= withinMs,
  ).length
}

/** Shorten a filesystem path or URL to the last segment(s). */
export function shortPath(p: string, max = 40): string {
  if (p.length <= max) return p
  const parts = p.split(/[\\/]/)
  const tail = parts.slice(-2).join('/')
  return tail.length <= max ? `…/${tail}` : `…${tail.slice(-max + 1)}`
}

/** Relative-time string (e.g. "12s ago"). */
export function formatAgo(ts: number, now: number = Date.now()): string {
  const sec = Math.max(0, Math.round((now - ts) / 1000))
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.round(hr / 24)}d ago`
}
