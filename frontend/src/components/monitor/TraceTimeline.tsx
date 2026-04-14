import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface TurnLayers {
  input: number
  tool_calls: number
}

interface TimelineTurn {
  turn: number
  layers: TurnLayers
}

interface TimelineEvent {
  turn: number
  kind: string
  detail: string
}

interface TimelineResponse {
  turns: TimelineTurn[]
  events: TimelineEvent[]
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; data: TimelineResponse }

function TurnBlock({ turn, events }: { turn: TimelineTurn; events: TimelineEvent[] }): React.ReactElement {
  const turnEvents = events.filter((e) => e.turn === turn.turn)
  const toolCount = turn.layers.tool_calls
  const inputTokens = turn.layers.input

  return (
    <div className="flex flex-col gap-1 min-w-[120px] max-w-[180px] shrink-0">
      {/* Turn header */}
      <div className="flex items-center justify-between px-2 py-1 border border-surface-800 rounded-t bg-surface-900">
        <span className="font-mono text-[9px] text-surface-500 uppercase tracking-widest">
          T{turn.turn}
        </span>
        {toolCount > 0 && (
          <span className="font-mono text-[9px] text-violet-400">
            {toolCount} tool{toolCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Token bar */}
      <div className="px-2 py-1.5 bg-surface-900/60 border border-t-0 border-surface-800 rounded-b flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[9px] text-surface-600 uppercase w-8 shrink-0">In</span>
          <div className="flex-1 h-1 bg-surface-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-600/70 rounded-full"
              style={{ width: inputTokens > 0 ? `${Math.min(100, (inputTokens / 8192) * 100)}%` : '0%' }}
            />
          </div>
          <span className="font-mono text-[9px] text-surface-500 w-10 text-right shrink-0">
            {inputTokens > 0 ? `${(inputTokens / 1000).toFixed(1)}k` : '—'}
          </span>
        </div>

        {/* Inline events for this turn */}
        {turnEvents.map((ev, i) => (
          <div
            key={i}
            className={cn(
              'px-1.5 py-0.5 rounded text-[9px] font-mono truncate',
              ev.kind === 'compaction'
                ? 'bg-amber-950/50 text-amber-400 border border-amber-900'
                : 'bg-surface-800 text-surface-400 border border-surface-700',
            )}
            title={ev.detail}
          >
            {ev.kind === 'compaction' ? '⌃ compact' : ev.kind}
          </div>
        ))}
      </div>
    </div>
  )
}

interface TraceTimelineProps {
  sessionId: string
}

export function TraceTimeline({ sessionId }: TraceTimelineProps): React.ReactElement {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })

    fetch(`/api/trace/traces/${sessionId}/timeline`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<TimelineResponse>
      })
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'ok', data })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: 'error', message: 'Failed to load timeline' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [sessionId])

  return (
    <div className="flex flex-col h-full">
      {/* Section label */}
      <div className="flex items-center gap-3 px-4 pt-3 pb-2 border-b border-surface-800 shrink-0">
        <span className="font-mono text-[10px] text-surface-500 uppercase tracking-widest">
          Trace Timeline
        </span>
        {state.status === 'ok' && state.data.turns.length > 0 && (
          <span className="font-mono text-[10px] text-surface-600">
            {state.data.turns.length} turns
          </span>
        )}
      </div>

      {/* Scrollable turn track */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden">
        {state.status === 'loading' && (
          <div className="flex items-center gap-3 px-4 py-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="min-w-[120px] h-16 animate-pulse bg-surface-800 rounded" />
            ))}
          </div>
        )}

        {state.status === 'error' && (
          <div className="flex items-center px-4 py-6">
            <span className="font-mono text-[11px] text-red-400">{state.message}</span>
          </div>
        )}

        {state.status === 'ok' && state.data.turns.length === 0 && (
          <div className="px-4 py-6">
            <p className="font-mono text-[11px] text-surface-600 uppercase tracking-widest">
              No trace data available for this session.
            </p>
            <div className="mt-1 w-24 h-px bg-surface-800" />
          </div>
        )}

        {state.status === 'ok' && state.data.turns.length > 0 && (
          <div className="flex items-start gap-2 px-4 py-4 w-max min-w-full">
            {state.data.turns.map((turn) => (
              <TurnBlock
                key={turn.turn}
                turn={turn}
                events={state.data.events}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
