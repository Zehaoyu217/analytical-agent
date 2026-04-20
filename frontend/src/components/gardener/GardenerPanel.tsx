import { useCallback, useEffect, useRef, useState } from 'react'
import { usePipelineStore } from '@/lib/pipeline-store'
import { cn } from '@/lib/utils'

interface GardenerPanelProps {
  open: boolean
  onClose: () => void
  embedded?: boolean
}

type Mode = 'proposal' | 'autonomous'
type Tier = 'cheap' | 'default' | 'deep'

interface Habits {
  mode: Mode
  models: Record<string, string>
  passes: Record<string, boolean>
  max_cost_usd_per_run: number
  max_tokens_per_source: number
  dry_run: boolean
}

interface StatusPayload {
  ok: boolean
  habits: Habits
  enabled_passes: string[]
}

interface EstimatePayload {
  ok: boolean
  passes: Record<string, { tokens: number; cost_usd: number }>
  total_tokens: number
  total_cost_usd: number
}

interface LogRow {
  ts: string
  pass?: string
  event?: string
  [k: string]: unknown
}

const ALL_PASSES: ReadonlyArray<{ name: string; tier: Tier; desc: string }> = [
  { name: 'extract', tier: 'cheap', desc: 'Promote unprocessed sources to claims' },
  { name: 're_abstract', tier: 'default', desc: 'Rewrite stale claim abstracts' },
  { name: 'semantic_link', tier: 'default', desc: 'Link claims to wiki + peers' },
  { name: 'dedupe', tier: 'default', desc: 'Cluster + merge duplicate claims' },
  { name: 'contradict', tier: 'deep', desc: 'Flag contradicting claim pairs' },
  { name: 'taxonomy_curate', tier: 'deep', desc: 'Restructure claim taxonomy' },
  { name: 'wiki_summarize', tier: 'default', desc: 'Compact long findings' },
]

const TIER_SUGGESTIONS: Record<Tier, ReadonlyArray<string>> = {
  cheap: [
    'anthropic/claude-haiku-4-5',
    'openai/gpt-4o-mini',
    'deepseek/deepseek-chat',
  ],
  default: [
    'anthropic/claude-sonnet-4-6',
    'openai/gpt-4o',
  ],
  deep: [
    'anthropic/claude-opus-4-7',
  ],
}

export function GardenerPanel({ open, embedded = false }: GardenerPanelProps) {
  const gardener = usePipelineStore((s) => s.gardener)
  const runGardener = usePipelineStore((s) => s.runGardener)

  const [habits, setHabits] = useState<Habits | null>(null)
  const [estimate, setEstimate] = useState<EstimatePayload | null>(null)
  const [log, setLog] = useState<LogRow[]>([])
  const [logFilter, setLogFilter] = useState<string>('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const saveTimer = useRef<number | null>(null)

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
      setHabits(s.habits)
      setEstimate(e)
      setLoadError(null)
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load')
    }
  }, [])

  const reloadLog = useCallback(async () => {
    try {
      const qs = logFilter ? `?n=50&pass_name=${encodeURIComponent(logFilter)}` : '?n=50'
      const res = await fetch(`/api/sb/gardener/log${qs}`)
      if (!res.ok) return
      const body = (await res.json()) as { ok: boolean; rows: LogRow[] }
      setLog(body.rows ?? [])
    } catch {
      /* log is best-effort */
    }
  }, [logFilter])

  useEffect(() => {
    if (!open) return
    void reload()
    void reloadLog()
  }, [open, reload, reloadLog])

  const scheduleSave = useCallback((patch: Partial<Habits>) => {
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(async () => {
      try {
        const res = await fetch('/api/sb/gardener/habits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        })
        if (!res.ok) throw new Error(`habits ${res.status}`)
        setSaveError(null)
        void reload()
      } catch (err: unknown) {
        setSaveError(err instanceof Error ? err.message : 'Save failed')
      }
    }, 350)
  }, [reload])

  const patch = useCallback(
    (update: Partial<Habits>) => {
      if (!habits) return
      setHabits({ ...habits, ...update })
      scheduleSave(update)
    },
    [habits, scheduleSave],
  )

  const patchModel = (tier: Tier, modelId: string) => {
    if (!habits) return
    const models = { ...habits.models, [tier]: modelId }
    setHabits({ ...habits, models })
    scheduleSave({ models: { [tier]: modelId } })
  }

  const patchPass = (name: string, enabled: boolean) => {
    if (!habits) return
    const passes = { ...habits.passes, [name]: enabled }
    setHabits({ ...habits, passes })
    scheduleSave({ passes: { [name]: enabled } })
  }

  if (!open) return null

  const running = gardener.status === 'running'
  const result = gardener.lastResult
  const enabledPassNames = habits
    ? ALL_PASSES.filter((p) => habits.passes[p.name]).map((p) => p.name)
    : []
  const overBudget = estimate && habits
    ? estimate.total_cost_usd > habits.max_cost_usd_per_run
    : false

  const handleRun = async () => {
    if (!habits) return
    await runGardener({ dry_run: habits.dry_run })
    await reload()
    await reloadLog()
  }

  return (
    <aside
      className={cn(
        'flex h-full flex-col overflow-hidden bg-bg-0 text-fg-1',
        embedded ? 'border-0' : 'border border-line',
      )}
      aria-label="Second-brain gardener panel"
    >
      <div className="flex flex-col gap-5 overflow-auto p-4 font-mono text-[12px]">
        {loadError && (
          <div className="border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-400">
            {loadError}
          </div>
        )}
        {saveError && (
          <div className="border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-400">
            save: {saveError}
          </div>
        )}

        {habits && (
          <>
            {/* Model tier picker */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-fg-2">
                Model tiers
              </div>
              <div className="grid grid-cols-[72px_1fr] items-center gap-x-2 gap-y-1.5">
                {(['cheap', 'default', 'deep'] as const).map((tier) => (
                  <TierRow
                    key={tier}
                    tier={tier}
                    value={habits.models[tier] ?? ''}
                    onChange={(v) => patchModel(tier, v)}
                  />
                ))}
              </div>
            </section>

            {/* Pass toggles */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-fg-2">
                Passes
              </div>
              <ul className="space-y-1">
                {ALL_PASSES.map((p) => {
                  const enabled = Boolean(habits.passes[p.name])
                  const est = estimate?.passes[p.name]
                  return (
                    <li
                      key={p.name}
                      className="flex items-center justify-between gap-2 border-b border-line/40 pb-1"
                    >
                      <label className="flex min-w-0 flex-1 items-center gap-2">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => patchPass(p.name, e.target.checked)}
                          className="accent-acc"
                        />
                        <span className="text-fg-0">{p.name}</span>
                        <TierBadge tier={p.tier} />
                      </label>
                      <span className="shrink-0 text-right text-[11px] text-fg-3">
                        {enabled && est
                          ? `${est.tokens} tok · $${est.cost_usd.toFixed(4)}`
                          : p.desc}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </section>

            {/* Budget */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-fg-2">
                Budget
              </div>
              <div className="grid grid-cols-2 gap-2">
                <NumberField
                  label="$ / run"
                  value={habits.max_cost_usd_per_run}
                  step={0.05}
                  min={0}
                  onCommit={(v) => patch({ max_cost_usd_per_run: v })}
                />
                <NumberField
                  label="tok / source"
                  value={habits.max_tokens_per_source}
                  step={500}
                  min={0}
                  onCommit={(v) => patch({ max_tokens_per_source: Math.round(v) })}
                />
              </div>
              {estimate && (
                <div className={cn(
                  'mt-2 border px-3 py-2',
                  overBudget
                    ? 'border-red-500/40 bg-red-500/10 text-red-400'
                    : 'border-line bg-bg-1 text-fg-1',
                )}>
                  Est: {estimate.total_tokens} tokens · $
                  {estimate.total_cost_usd.toFixed(4)}
                  {overBudget && ' — over budget'}
                </div>
              )}
            </section>

            {/* Authority + dry run */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-fg-2">
                Authority
              </div>
              <div className="flex flex-col gap-1.5">
                <ModeRadio
                  name="proposal"
                  label="Proposal"
                  hint="Write to pending.jsonl; you review before applying."
                  checked={habits.mode === 'proposal'}
                  onChange={() => patch({ mode: 'proposal' })}
                />
                <ModeRadio
                  name="autonomous"
                  label="Autonomous"
                  hint="Apply directly; every write still audited."
                  checked={habits.mode === 'autonomous'}
                  onChange={() => patch({ mode: 'autonomous' })}
                />
                <label className="mt-1 flex items-center gap-2 text-fg-1">
                  <input
                    type="checkbox"
                    checked={habits.dry_run}
                    onChange={(e) => patch({ dry_run: e.target.checked })}
                    className="accent-acc"
                  />
                  Dry run (no writes, no LLM calls)
                </label>
              </div>
            </section>

            {/* Run */}
            <section className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleRun}
                disabled={running || enabledPassNames.length === 0}
                className={cn(
                  'h-9 border px-3 text-left font-mono text-[12px] transition-colors focus-ring',
                  running
                    ? 'cursor-wait border-line bg-bg-1 text-fg-2'
                    : 'border-acc-line bg-acc-dim text-acc hover:bg-acc/20',
                  enabledPassNames.length === 0 && 'opacity-50',
                )}
              >
                {running
                  ? 'Tending…'
                  : habits.dry_run
                    ? `Tend (dry run) · ${enabledPassNames.length} pass${enabledPassNames.length === 1 ? '' : 'es'}`
                    : `Tend · ${enabledPassNames.length} pass${enabledPassNames.length === 1 ? '' : 'es'}`}
              </button>
              {gardener.status === 'error' && gardener.errorMessage && (
                <div className="border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-400">
                  {gardener.errorMessage}
                </div>
              )}
            </section>

            {/* Last result */}
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
                  <ul className="mt-2 space-y-0.5 text-red-400">
                    {result.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {/* Activity log */}
            <section>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-[0.08em] text-fg-2">
                  Activity
                </span>
                <select
                  value={logFilter}
                  onChange={(e) => setLogFilter(e.target.value)}
                  className="h-6 border border-line bg-bg-1 px-1 text-[11px] text-fg-1 focus-ring"
                  aria-label="Filter activity by pass"
                >
                  <option value="">all passes</option>
                  {ALL_PASSES.map((p) => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              {log.length === 0 ? (
                <div className="text-fg-3">No runs yet.</div>
              ) : (
                <ul className="max-h-64 space-y-0.5 overflow-auto border border-line bg-bg-1 p-2 text-[11px]">
                  {log.map((row, i) => (
                    <LogEntry key={i} row={row} />
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </aside>
  )
}

function TierRow({
  tier,
  value,
  onChange,
}: {
  tier: Tier
  value: string
  onChange: (v: string) => void
}) {
  return (
    <>
      <label htmlFor={`tier-${tier}`} className="text-fg-2">
        {tier}
      </label>
      <input
        id={`tier-${tier}`}
        type="text"
        list={`tier-${tier}-suggest`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 border border-line bg-bg-1 px-2 font-mono text-[12px] text-fg-0 focus-ring"
      />
      <datalist id={`tier-${tier}-suggest`}>
        {TIER_SUGGESTIONS[tier].map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
    </>
  )
}

function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span
      className={cn(
        'shrink-0 border px-1 py-px text-[9px] uppercase tracking-wider',
        tier === 'cheap' && 'border-line bg-bg-1 text-fg-2',
        tier === 'default' && 'border-acc-line/50 bg-acc-dim text-acc',
        tier === 'deep' && 'border-amber-500/40 bg-amber-500/10 text-amber-400',
      )}
    >
      {tier}
    </span>
  )
}

function NumberField({
  label,
  value,
  step,
  min,
  onCommit,
}: {
  label: string
  value: number
  step: number
  min: number
  onCommit: (v: number) => void
}) {
  const [local, setLocal] = useState<string>(String(value))
  useEffect(() => {
    setLocal(String(value))
  }, [value])
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-[0.08em] text-fg-2">
        {label}
      </span>
      <input
        type="number"
        value={local}
        step={step}
        min={min}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          const n = Number(local)
          if (!Number.isFinite(n) || n < min) {
            setLocal(String(value))
            return
          }
          onCommit(n)
        }}
        className="h-7 border border-line bg-bg-1 px-2 font-mono text-[12px] text-fg-0 focus-ring"
      />
    </label>
  )
}

function ModeRadio({
  name,
  label,
  hint,
  checked,
  onChange,
}: {
  name: string
  label: string
  hint: string
  checked: boolean
  onChange: () => void
}) {
  return (
    <label className="flex items-start gap-2">
      <input
        type="radio"
        name="gardener-mode"
        value={name}
        checked={checked}
        onChange={onChange}
        className="mt-0.5 accent-acc"
      />
      <span className="flex flex-col">
        <span className="text-fg-0">{label}</span>
        <span className="text-[11px] text-fg-3">{hint}</span>
      </span>
    </label>
  )
}

function LogEntry({ row }: { row: LogRow }) {
  const ts = typeof row.ts === 'string' ? row.ts.replace('T', ' ').slice(0, 19) : ''
  const pass = typeof row.pass === 'string' ? row.pass : ''
  const event = typeof row.event === 'string' ? row.event : ''
  const cost = typeof row.cost_usd === 'number' ? `$${row.cost_usd.toFixed(4)}` : ''
  return (
    <li className="grid grid-cols-[110px_80px_80px_1fr] gap-2">
      <span className="text-fg-3">{ts}</span>
      <span className="text-fg-1">{pass}</span>
      <span className="text-fg-2">{event}</span>
      <span className="truncate text-fg-3">{cost}</span>
    </li>
  )
}
