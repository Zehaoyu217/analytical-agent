import { useCallback, useEffect, useState } from 'react'
import { listTraces, type TraceListItem } from '@/lib/api'
import { cn } from '@/lib/utils'

type FilterTab = 'all' | 'done' | 'failed'

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60_000)
  const s = Math.round((ms % 60_000) / 1000)
  return `${m}m ${s}s`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function truncateId(id: string): string {
  if (id.length <= 16) return id
  return `${id.slice(0, 8)}…${id.slice(-6)}`
}

function outcomeToStatus(outcome: string): 'done' | 'failed' {
  if (outcome === 'pass' || outcome === 'ok') return 'done'
  return 'failed'
}

interface AgentCardProps {
  trace: TraceListItem
}

function AgentCard({ trace }: AgentCardProps) {
  const status = outcomeToStatus(trace.outcome)
  const totalTokens = trace.total_input_tokens + trace.total_output_tokens

  function handleClick() {
    window.location.hash = `#/monitor/${trace.session_id}`
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        'flex flex-col gap-3 rounded-md border border-surface-800 bg-surface-900 p-4',
        'text-left hover:border-surface-700 hover:bg-surface-850 transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        'w-full',
      )}
      title={`Session ${trace.session_id}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-xs text-surface-300 truncate min-w-0">
          {truncateId(trace.session_id)}
        </span>
        <span
          className={cn(
            'flex-shrink-0 text-[10px] font-mono font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded',
            status === 'done'
              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/60'
              : 'bg-red-950/60 text-red-400 border border-red-900/60',
          )}
        >
          {status === 'done' ? '✓ DONE' : '✗ FAILED'}
        </span>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 text-[11px] font-mono text-surface-500">
        <span title="Duration">{formatDuration(trace.duration_ms)}</span>
        <span title="Turns" className="flex items-center gap-1">
          <span className="text-surface-600">turns</span>
          {trace.turn_count}
        </span>
        <span title="Tokens" className="flex items-center gap-1">
          <span className="text-surface-600">tok</span>
          {formatTokens(totalTokens)}
        </span>
        {trace.final_grade && (
          <span
            className={cn(
              'font-semibold',
              trace.final_grade === 'A'
                ? 'text-emerald-400'
                : trace.final_grade === 'B'
                  ? 'text-brand-400'
                  : trace.final_grade === 'C'
                    ? 'text-amber-400'
                    : 'text-red-400',
            )}
          >
            {trace.final_grade}
          </span>
        )}
      </div>
    </button>
  )
}

const FILTER_TABS: Array<{ id: FilterTab; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'done', label: 'Done' },
  { id: 'failed', label: 'Failed' },
]

export function AgentsSection() {
  const [traces, setTraces] = useState<TraceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterTab>('all')

  const fetchData = useCallback(async () => {
    try {
      const data = await listTraces()
      setTraces(data)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load traces'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
    const interval = setInterval(() => void fetchData(), 5_000)
    return () => clearInterval(interval)
  }, [fetchData])

  const filtered = traces.filter((t) => {
    if (filter === 'all') return true
    return outcomeToStatus(t.outcome) === filter
  })

  return (
    <div className="flex flex-col h-full bg-surface-950 text-surface-100 overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-4 px-6 py-4 border-b border-surface-800 flex-shrink-0">
        <h1 className="font-mono text-xs font-semibold text-surface-300 uppercase tracking-widest">
          MONITORING
        </h1>

        {/* Filter tabs */}
        <div
          role="tablist"
          aria-label="Filter agent sessions"
          className="flex items-center gap-0.5"
        >
          {FILTER_TABS.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              aria-selected={filter === id}
              type="button"
              onClick={() => setFilter(id)}
              className={cn(
                'px-3 py-1 rounded text-xs font-mono font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500',
                filter === id
                  ? 'bg-surface-800 text-surface-100'
                  : 'text-surface-500 hover:text-surface-300 hover:bg-surface-800/40',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {/* Live indicator */}
        <span className="flex items-center gap-1.5 text-[10px] font-mono text-surface-600">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden />
          LIVE
        </span>
      </header>

      {/* Body */}
      <main className="flex-1 min-h-0 overflow-y-auto px-6 py-6">
        {loading && (
          <p className="text-xs font-mono text-surface-500 text-center py-12">
            Loading agent sessions…
          </p>
        )}

        {!loading && error && (
          <div
            role="alert"
            className="rounded-md border border-red-900/60 bg-red-950/40 px-4 py-3 text-xs font-mono text-red-300"
          >
            {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <p className="text-xs font-mono text-surface-500 text-center py-12">
            {filter === 'all'
              ? 'No agent sessions recorded yet.'
              : `No ${filter} sessions.`}
          </p>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((trace) => (
              <AgentCard key={trace.session_id} trace={trace} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
