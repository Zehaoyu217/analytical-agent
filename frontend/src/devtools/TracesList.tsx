import { useEffect, useState } from 'react'
import { listTraces, type TraceListItem } from '../lib/api'
import { useDevtoolsStore } from '../stores/devtools'

const POLL_INTERVAL_MS = 2000

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString(undefined, { hour12: false })
}

function outcomeColor(outcome: string): string {
  if (outcome === 'ok') return '#4ade80'
  if (outcome === 'error') return '#f87171'
  return '#94a3b8'
}

export function TracesList() {
  const selectedTraceId = useDevtoolsStore((s) => s.selectedTraceId)
  const setSelectedTrace = useDevtoolsStore((s) => s.setSelectedTrace)

  const [traces, setTraces] = useState<TraceListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const next = await listTraces()
        if (cancelled) return
        next.sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
        setTraces(next)
        setError(null)
      } catch (err: unknown) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'listTraces failed')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    poll()
    const handle = window.setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(handle)
    }
  }, [])

  if (loading && traces.length === 0) {
    return (
      <div style={{ padding: 16, color: '#4a4a5a', fontSize: 11 }}>Loading traces…</div>
    )
  }

  if (error && traces.length === 0) {
    return (
      <div style={{ padding: 16, color: '#f87171', fontSize: 11, fontFamily: 'monospace' }}>
        {error}
      </div>
    )
  }

  if (traces.length === 0) {
    return (
      <div style={{ padding: 16, color: '#4a4a5a', fontSize: 11 }}>
        No traces yet. Send a chat message to produce one.
      </div>
    )
  }

  return (
    <div style={{ padding: 8 }}>
      {error && (
        <div
          style={{
            color: '#f59e0b',
            fontSize: 10,
            fontFamily: 'monospace',
            padding: '4px 8px',
            marginBottom: 4,
          }}
        >
          polling error: {error}
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ color: '#64748b', textAlign: 'left' }}>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>time</th>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>session</th>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>level</th>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>llm</th>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>tokens</th>
            <th style={{ padding: '4px 8px', fontWeight: 500 }}>outcome</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((trace) => {
            const isSelected = trace.session_id === selectedTraceId
            return (
              <tr
                key={trace.session_id}
                onClick={() => setSelectedTrace(trace.session_id)}
                style={{
                  background: isSelected ? '#1e1b4b' : 'transparent',
                  color: isSelected ? '#e0e0e8' : '#94a3b8',
                  cursor: 'pointer',
                  fontFamily: 'monospace',
                }}
              >
                <td style={{ padding: '4px 8px' }}>{formatTime(trace.started_at)}</td>
                <td style={{ padding: '4px 8px' }}>{trace.session_id}</td>
                <td style={{ padding: '4px 8px' }}>{trace.level_label}</td>
                <td style={{ padding: '4px 8px' }}>{trace.llm_call_count}</td>
                <td style={{ padding: '4px 8px' }}>
                  {trace.total_input_tokens}/{trace.total_output_tokens}
                </td>
                <td style={{ padding: '4px 8px', color: outcomeColor(trace.outcome) }}>
                  {trace.outcome}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
