import type { JSX, ReactNode } from 'react'
import { cn } from '@/lib/utils'
import {
  formatAgo,
  type PhaseState,
  type PhaseResultSummary,
  type DigestResultSummary,
  type IngestResultSummary,
  type MaintainResultSummary,
} from '@/lib/pipeline-store'

export type PipelinePhase = 'ingest' | 'digest' | 'maintain' | 'gardener'

interface PipelineActionProps {
  phase: PipelinePhase
  label: string
  icon: ReactNode
  state: PhaseState
  onClick: () => void | Promise<void>
  kbd?: string
}

export function PipelineAction({
  phase,
  label,
  icon,
  state,
  onClick,
  kbd,
}: PipelineActionProps): JSX.Element {
  const running = state.status === 'running'
  const errored = state.status === 'error'
  const done = state.status === 'done'

  const statusLine = running
    ? 'Running…'
    : errored
      ? state.errorMessage || 'Error'
      : buildSummaryLine(phase, state.lastRunAt, state.lastResult)

  const ariaLabel = `${label}, ${statusLine}`

  return (
    <button
      type="button"
      onClick={() => {
        if (!running) void onClick()
      }}
      disabled={running}
      aria-busy={running}
      aria-label={ariaLabel}
      data-phase={phase}
      data-status={state.status}
      className={cn(
        'group flex flex-1 items-center gap-3 border-l border-line px-4 py-2',
        'transition-colors focus-ring text-left',
        'first:border-l-0',
        running && 'opacity-70 cursor-wait',
        done && 'text-acc',
        errored && 'text-red-400',
        !running && !errored && 'hover:bg-bg-2',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line bg-bg-1',
          running && 'animate-pulse',
          done && 'border-acc-line bg-acc-dim text-acc',
          errored && 'border-red-500/40 bg-red-500/10 text-red-400',
        )}
      >
        {icon}
      </span>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.08em] text-fg-0">
          {running ? 'RUNNING…' : label}
          {kbd && !running ? (
            <kbd
              aria-hidden
              className="rounded border border-line bg-bg-1 px-1 py-px font-mono text-[9px] text-fg-2"
            >
              {kbd}
            </kbd>
          ) : null}
        </span>
        <span className="truncate font-mono text-[11px] text-fg-2">
          {statusLine}
        </span>
      </span>
    </button>
  )
}

function buildSummaryLine(
  phase: PipelinePhase,
  lastRunAt: string | null,
  result: PhaseResultSummary | null,
): string {
  const ago = formatAgo(lastRunAt)
  const summary = summarizeResult(phase, result)
  if (summary) return `${ago} · ${summary}`
  return ago
}

function summarizeResult(
  phase: PipelinePhase,
  result: PhaseResultSummary | null,
): string {
  if (!result) return ''
  if (phase === 'ingest') {
    const r = result as IngestResultSummary
    return r.sources_added === 1
      ? '+1 source'
      : `+${r.sources_added} sources`
  }
  if (phase === 'digest') {
    const r = result as DigestResultSummary
    const pending = r.pending > 0 ? `, ${r.pending} pending` : ''
    return `${r.entries} ${r.entries === 1 ? 'entry' : 'entries'}${pending}`
  }
  const r = result as MaintainResultSummary
  if (r.lint_errors > 0) return `${r.lint_errors} err`
  if (r.lint_warnings > 0) return `${r.lint_warnings} warn`
  return 'clean'
}
