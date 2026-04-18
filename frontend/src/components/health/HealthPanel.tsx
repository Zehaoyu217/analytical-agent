import { useEffect } from 'react'
import { useHealthStore } from '@/lib/health-store'
import './health.css'

interface HealthPanelProps {
  open: boolean
  onClose: () => void
}

const REFRESH_INTERVAL_MS = 15_000

function formatValue(v: unknown): string {
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : v.toFixed(2)
  }
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export function HealthPanel({ open, onClose }: HealthPanelProps) {
  const stats = useHealthStore((s) => s.stats)
  const health = useHealthStore((s) => s.health)
  const error = useHealthStore((s) => s.error)
  const refresh = useHealthStore((s) => s.refresh)

  useEffect(() => {
    if (!open) return
    void refresh()
    const t = window.setInterval(() => {
      void refresh()
    }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [open, refresh])

  if (!open) return null

  const isEmpty = stats === null && health === null
  const components = health?.components ?? health?.breakdown ?? undefined

  return (
    <aside className="health-panel" aria-label="Second-brain health">
      <div className="health-panel__header">
        <div className="health-panel__title">HEALTH</div>
        <button
          type="button"
          className="health-panel__close"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>
      {error && <div className="health-panel__empty">{error}</div>}
      {isEmpty ? (
        <div className="health-panel__empty">knowledge base disabled</div>
      ) : (
        <>
          {health && (
            <div className="health-panel__score">
              <span className="health-panel__score-num">{health.score}</span>
              {health.grade && (
                <span className="health-panel__score-grade">{health.grade}</span>
              )}
            </div>
          )}
          {components && Object.keys(components).length > 0 && (
            <>
              <div className="health-panel__section-title">Components</div>
              {Object.entries(components).map(([k, v]) => (
                <div key={k} className="health-panel__row">
                  <span className="health-panel__row-key">{k}</span>
                  <span className="health-panel__row-val">{formatValue(v)}</span>
                </div>
              ))}
            </>
          )}
          {stats && Object.keys(stats).length > 0 && (
            <>
              <div className="health-panel__section-title">Stats</div>
              {Object.entries(stats).map(([k, v]) => (
                <div key={k} className="health-panel__row">
                  <span className="health-panel__row-key">{k}</span>
                  <span className="health-panel__row-val">{formatValue(v)}</span>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </aside>
  )
}
