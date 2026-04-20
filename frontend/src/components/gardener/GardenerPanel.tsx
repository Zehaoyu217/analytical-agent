import { useCallback, useEffect, useState } from 'react'
import { usePipelineStore } from '@/lib/pipeline-store'
import { cn } from '@/lib/utils'

interface GardenerPanelProps {
  open: boolean
  onClose: () => void
  embedded?: boolean
}

interface StatusPayload {
  ok: boolean
  habits: {
    mode: 'proposal' | 'autonomous'
    models: Record<string, string>
    passes: Record<string, boolean>
    max_cost_usd_per_run: number
    max_tokens_per_source: number
    dry_run: boolean
  }
  enabled_passes: string[]
}

interface EstimatePayload {
  ok: boolean
  passes: Record<string, { tokens: number; cost_usd: number }>
  total_tokens: number
  total_cost_usd: number
}

export function GardenerPanel({ open, embedded = false }: GardenerPanelProps) {
  const gardener = usePipelineStore((s) => s.gardener)
  const runGardener = usePipelineStore((s) => s.runGardener)

  const [status, setStatus] = useState<StatusPayload | null>(null)
  const [estimate, setEstimate] = useState<EstimatePayload | null>(null)
  const [dryRun, setDryRun] = useState<boolean>(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      const [sRes, eRes] = await Promise.all([
        fetch('/api/sb/gardener/status'),
        fetch('/api/sb/gardener/estimate'),
      ])
      if (!sRes.ok) throw new Error(`status ${sRes.status}`)
      if (!eRes.ok) throw new Error(`estimate ${eRes.status}`)
      const s = (await sRes.json()) as StatusPayload
      const e = (await eRes.json()) as EstimatePayload
      setStatus(s)
      setEstimate(e)
      setDryRun(Boolean(s.habits.dry_run))
      setLoadError(null)
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load')
    }
  }, [])

  useEffect(() => {
    if (!open) return
    void reload()
  }, [open, reload])

  if (!open) return null

  const running = gardener.status === 'running'
  const enabledPasses = status?.enabled_passes ?? []

  const handleRun = async () => {
    await runGardener({ dry_run: dryRun })
    await reload()
  }

  const result = gardener.lastResult

  return (
    <aside
      className={cn(
        'flex h-full flex-col overflow-hidden bg-bg-0 text-fg-1',
        embedded ? 'border-0' : 'border border-line',
      )}
      aria-label="Second-brain gardener panel"
    >
      <div className="flex flex-col gap-4 overflow-auto p-4 font-mono text-[12px]">
        {loadError && (
          <div className="border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-400">
            {loadError}
          </div>
        )}

        <section>
          <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-fg-2">
            Enabled passes
          </div>
          {enabledPasses.length === 0 ? (
            <div className="text-fg-3">No passes enabled.</div>
          ) : (
            <ul className="space-y-1">
              {enabledPasses.map((name) => {
                const tier = status?.habits.models[name] ?? '—'
                const est = estimate?.passes[name]
                return (
                  <li
                    key={name}
                    className="flex items-center justify-between border-b border-line/40 pb-1"
                  >
                    <span className="text-fg-0">{name}</span>
                    <span className="text-fg-2">
                      {tier}
                      {est ? ` · ${est.tokens} tok · $${est.cost_usd.toFixed(4)}` : ''}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        {estimate && (
          <section className="border border-line bg-bg-1 px-3 py-2">
            <div className="text-[10px] uppercase tracking-[0.08em] text-fg-2">
              Estimate
            </div>
            <div className="mt-1 text-fg-0">
              {estimate.total_tokens} tokens · ${estimate.total_cost_usd.toFixed(4)}
            </div>
            {status && (
              <div className="mt-1 text-[11px] text-fg-3">
                Budget: ${status.habits.max_cost_usd_per_run.toFixed(2)} / run ·{' '}
                {status.habits.max_tokens_per_source} tok/source
              </div>
            )}
          </section>
        )}

        <section className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-fg-1">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              disabled={running}
              className="accent-acc"
            />
            Dry run (no writes, no LLM calls)
          </label>
          <button
            type="button"
            onClick={handleRun}
            disabled={running || enabledPasses.length === 0}
            className={cn(
              'h-9 border px-3 text-left font-mono text-[12px] transition-colors focus-ring',
              running
                ? 'cursor-wait border-line bg-bg-1 text-fg-2'
                : 'border-acc-line bg-acc-dim text-acc hover:bg-acc/20',
              enabledPasses.length === 0 && 'opacity-50',
            )}
          >
            {running ? 'Tending…' : dryRun ? 'Tend (dry run)' : 'Tend'}
          </button>
          {gardener.status === 'error' && gardener.errorMessage && (
            <div className="border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-400">
              {gardener.errorMessage}
            </div>
          )}
        </section>

        {result && (
          <section className="border border-line bg-bg-1 px-3 py-2">
            <div className="text-[10px] uppercase tracking-[0.08em] text-fg-2">
              Last result
            </div>
            <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-fg-1">
              <dt className="text-fg-3">passes</dt>
              <dd>{result.passes_run.join(', ') || '—'}</dd>
              <dt className="text-fg-3">proposals</dt>
              <dd>{result.proposals_added}</dd>
              <dt className="text-fg-3">tokens</dt>
              <dd>{result.total_tokens}</dd>
              <dt className="text-fg-3">cost</dt>
              <dd>${result.total_cost_usd.toFixed(4)}</dd>
              <dt className="text-fg-3">duration</dt>
              <dd>{result.duration_ms} ms</dd>
            </dl>
            {result.errors.length > 0 && (
              <div className="mt-2 text-red-400">
                {result.errors.length} error{result.errors.length === 1 ? '' : 's'}
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  )
}
