import { useEffect, useState } from 'react'
import { useDevtoolsStore } from '../../stores/devtools'
import { fetchPromptAssembly, fetchTraceSummary, type PromptAssembly, type TraceSummary } from './api'

interface Props {
  traceId: string
  stepId: string
}

export function PromptInspector({ traceId, stepId }: Props) {
  const [summary, setSummary] = useState<TraceSummary | null>(null)
  const [assembly, setAssembly] = useState<PromptAssembly | null>(null)
  const [error, setError] = useState<string | null>(null)
  const setSelectedStep = useDevtoolsStore((s) => s.setSelectedStep)

  useEffect(() => {
    fetchTraceSummary(traceId)
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'error'))
  }, [traceId])

  useEffect(() => {
    fetchPromptAssembly(traceId, stepId)
      .then(setAssembly)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'error'))
  }, [traceId, stepId])

  if (error) return <div className="sop-empty">{error}</div>
  if (!summary || !assembly) return <div className="sop-empty">Loading…</div>

  return (
    <div style={{ padding: 12, color: '#e0e0e8', fontFamily: 'monospace', fontSize: 11 }}>
      <div style={{ marginBottom: 12 }}>
        <label>Step: </label>
        <select
          value={stepId}
          onChange={(e) => setSelectedStep(e.target.value)}
          style={{ fontFamily: 'monospace', fontSize: 11 }}
        >
          {summary.step_ids.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </div>
      {assembly.sections.map((section, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <div style={{ color: '#818cf8' }}>{section.source} ({section.lines})</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{section.text}</pre>
        </div>
      ))}
      {assembly.conflicts.length > 0 && (
        <div style={{ marginTop: 16, color: '#f87171' }}>
          <strong>Conflicts:</strong>
          <ul>
            {assembly.conflicts.map((c, i) => (
              <li key={i}>{c.source_a} ↔ {c.source_b} at {c.overlap}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
