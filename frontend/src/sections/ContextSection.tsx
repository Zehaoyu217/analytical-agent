import { useCallback, useEffect, useState } from 'react'
import { Layers } from 'lucide-react'
import { fetchContext, type ContextSnapshot } from '@/lib/api'
import { cn } from '@/lib/utils'

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const isHigh = pct >= 80
  const isMed = pct >= 60

  return (
    <div
      className="h-1.5 w-full rounded-full bg-surface-800 overflow-hidden"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemax={max}
      aria-label={`Context utilization: ${pct.toFixed(1)}%`}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all duration-300',
          isHigh
            ? 'bg-red-500'
            : isMed
              ? 'bg-amber-500'
              : 'bg-brand-500',
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function ContextSection() {
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const data = await fetchContext()
      setSnapshot(data)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load context'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
    const interval = setInterval(() => void fetchData(), 10_000)
    return () => clearInterval(interval)
  }, [fetchData])

  const pct = snapshot
    ? Math.min(100, (snapshot.total_tokens / snapshot.max_tokens) * 100)
    : 0

  return (
    <div className="flex flex-col h-full bg-surface-950 text-surface-100 overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-surface-800 flex-shrink-0">
        <Layers className="w-4 h-4 text-surface-500" aria-hidden />
        <h1 className="font-mono text-xs font-semibold text-surface-300 uppercase tracking-widest">
          CONTEXT
        </h1>
        {snapshot && (
          <span className="ml-auto font-mono text-[10px] text-surface-600">
            {pct.toFixed(1)}% utilized
          </span>
        )}
      </header>

      <main className="flex-1 min-h-0 overflow-y-auto px-6 py-6 space-y-6">
        {loading && (
          <p className="text-xs font-mono text-surface-500 text-center py-12">
            Loading context snapshot…
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

        {!loading && !error && snapshot && (
          <>
            {/* Token utilization bar */}
            <section className="space-y-3">
              <div className="flex items-baseline justify-between">
                <h2 className="font-mono text-[10px] text-surface-500 uppercase tracking-widest">
                  Token Budget
                </h2>
                <span className="font-mono text-xs text-surface-300">
                  {snapshot.total_tokens.toLocaleString()} / {snapshot.max_tokens.toLocaleString()}
                </span>
              </div>
              <ProgressBar value={snapshot.total_tokens} max={snapshot.max_tokens} />
              {snapshot.compaction_needed && (
                <p className="text-[10px] font-mono text-amber-400">
                  ⚠ Compaction recommended
                </p>
              )}
            </section>

            {/* Layers */}
            {snapshot.layers.length > 0 && (
              <section className="space-y-2">
                <h2 className="font-mono text-[10px] text-surface-500 uppercase tracking-widest">
                  Layers
                </h2>
                <div className="space-y-px rounded-md border border-surface-800 overflow-hidden">
                  {snapshot.layers.map((layer) => (
                    <div
                      key={layer.name}
                      className="flex items-center justify-between px-3 py-2 bg-surface-900 hover:bg-surface-850 transition-colors"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            'w-1.5 h-1.5 rounded-full flex-shrink-0',
                            layer.compactable ? 'bg-amber-500/70' : 'bg-surface-700',
                          )}
                          aria-hidden
                        />
                        <span className="font-mono text-xs text-surface-300 truncate">
                          {layer.name}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] text-surface-500 flex-shrink-0 ml-3">
                        {layer.tokens.toLocaleString()} tok
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Raw JSON snapshot */}
            <section className="space-y-2">
              <h2 className="font-mono text-[10px] text-surface-500 uppercase tracking-widest">
                Raw Snapshot
              </h2>
              <pre className="rounded-md border border-surface-800 bg-surface-900 p-4 text-[11px] font-mono text-surface-400 overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(snapshot, null, 2)}
              </pre>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
