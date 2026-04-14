import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface TraceSummary {
  session_id: string
  level: number
  level_label: string
  outcome: string
  turn_count: number
  duration_ms: number
  started_at: string
}

interface TraceResponse {
  summary: TraceSummary
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; data: TraceSummary }

const OUTCOME_STYLES: Record<string, string> = {
  success: 'text-emerald-400 border-emerald-800 bg-emerald-950/40',
  error: 'text-red-400 border-red-800 bg-red-950/40',
  cancelled: 'text-amber-400 border-amber-800 bg-amber-950/40',
}

function OutcomeBadge({ outcome }: { outcome: string }): React.ReactElement {
  const style = OUTCOME_STYLES[outcome.toLowerCase()] ?? 'text-surface-400 border-surface-700 bg-surface-900'
  return (
    <span className={cn('px-1.5 py-0.5 text-[10px] font-mono border rounded uppercase tracking-wider', style)}>
      {outcome}
    </span>
  )
}

interface SessionHeaderProps {
  sessionId: string
}

export function SessionHeader({ sessionId }: SessionHeaderProps): React.ReactElement {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })

    fetch(`/api/trace/traces/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<TraceResponse>
      })
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'ok', data: data.summary })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: 'error', message: 'Failed to load session' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [sessionId])

  if (state.status === 'loading') {
    return (
      <div className="flex items-center gap-4 px-4 h-full">
        <div className="h-3 w-32 animate-pulse bg-surface-800 rounded" />
        <div className="h-3 w-24 animate-pulse bg-surface-800 rounded" />
        <div className="h-3 w-16 animate-pulse bg-surface-800 rounded" />
        <div className="h-3 w-20 animate-pulse bg-surface-800 rounded" />
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="flex items-center px-4 h-full">
        <span className="text-red-400 font-mono text-[11px]">{state.message}</span>
      </div>
    )
  }

  const { data } = state
  const shortId = data.session_id.slice(0, 12)

  return (
    <div className="flex items-center gap-3 px-4 h-full font-mono text-[11px] text-surface-400 overflow-x-auto whitespace-nowrap">
      <span>
        <span className="text-surface-500 uppercase tracking-widest text-[9px] mr-1.5">Session</span>
        <span className="text-surface-200">{shortId}</span>
      </span>

      <span className="text-surface-700">|</span>

      <span>
        <span className="text-surface-500 uppercase tracking-widest text-[9px] mr-1.5">Level</span>
        <span className="text-surface-200">{data.level}</span>
        <span className="text-surface-600 mx-1">—</span>
        <span className="text-surface-300">{data.level_label}</span>
      </span>

      <span className="text-surface-700">|</span>

      <OutcomeBadge outcome={data.outcome} />

      <span className="text-surface-700">|</span>

      <span>
        <span className="text-surface-200">{data.turn_count}</span>
        <span className="text-surface-500 uppercase tracking-widest text-[9px] ml-1">Turns</span>
      </span>

      <span className="text-surface-700">|</span>

      <span>
        <span className="text-surface-200">{data.duration_ms.toLocaleString()}</span>
        <span className="text-surface-500 text-[9px] ml-0.5">ms</span>
      </span>

      <span className="text-surface-700">|</span>

      <span className="text-surface-400">{data.started_at}</span>
    </div>
  )
}
