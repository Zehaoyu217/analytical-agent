import { useEffect, useMemo } from 'react'
import { useSkillsStore, aggregateUsage } from '@/lib/skills-store'
import './skills.css'

interface SkillsPanelProps {
  open: boolean
  onClose: () => void
}

const REFRESH_INTERVAL_MS = 15_000

function formatRelative(ts: string): string {
  const then = Date.parse(ts)
  if (Number.isNaN(then)) return '—'
  const delta = Math.max(0, Date.now() - then)
  const sec = Math.round(delta / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.round(hr / 24)
  return `${day}d ago`
}

export function SkillsPanel({ open, onClose }: SkillsPanelProps) {
  const events = useSkillsStore((s) => s.events)
  const error = useSkillsStore((s) => s.error)
  const refresh = useSkillsStore((s) => s.refresh)

  useEffect(() => {
    if (!open) return
    void refresh()
    const t = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [open, refresh])

  const usage = useMemo(() => aggregateUsage(events), [events])

  if (!open) return null

  return (
    <aside className="skills-panel" aria-label="Skills usage telemetry">
      <div className="skills-panel__header">
        <div>
          <div className="skills-panel__title">SKILLS</div>
          <div className="skills-panel__meta">
            {events.length} events · {usage.length} distinct
          </div>
        </div>
        <button
          type="button"
          className="skills-panel__close"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>
      {error && <div className="skills-panel__empty">{error}</div>}
      <div className="skills-panel__section-title">Most used</div>
      {usage.length === 0 ? (
        <div className="skills-panel__empty">no skill invocations yet</div>
      ) : (
        usage.map((u) => (
          <div key={u.name} className="skills-panel__row" data-testid="skills-row">
            <span className="skills-panel__row-name">{u.name}</span>
            <span
              className="skills-panel__row-meta"
              data-outcome={u.lastOutcome}
            >
              {u.count} invocations · last: {formatRelative(u.lastTimestamp)}
            </span>
          </div>
        ))
      )}
    </aside>
  )
}
