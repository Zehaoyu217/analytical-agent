import { useEffect } from 'react'
import { useDigestStore } from '@/lib/digest-store'
import { DigestEntry } from './DigestEntry'
import { DigestHeader } from './DigestHeader'
import './digest.css'

interface DigestPanelProps {
  open: boolean
  onClose: () => void
}

const REFRESH_INTERVAL_MS = 10_000

export function DigestPanel({ open, onClose }: DigestPanelProps) {
  const date = useDigestStore((s) => s.date)
  const entries = useDigestStore((s) => s.entries)
  const unread = useDigestStore((s) => s.unread)
  const error = useDigestStore((s) => s.error)
  const refresh = useDigestStore((s) => s.refresh)
  const apply = useDigestStore((s) => s.apply)
  const skip = useDigestStore((s) => s.skip)
  const markRead = useDigestStore((s) => s.markRead)

  useEffect(() => {
    if (!open) return
    void refresh()
    const t = window.setInterval(() => {
      void refresh()
    }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [open, refresh])

  if (!open) return null

  const sections = Array.from(new Set(entries.map((e) => e.section)))

  return (
    <aside className="digest-panel" aria-label="Second-brain digest">
      <DigestHeader
        date={date}
        unread={unread}
        onMarkRead={() => void markRead()}
        onClose={onClose}
      />
      {error && <div className="digest-panel__error">{error}</div>}
      {entries.length === 0 ? (
        <div className="digest-panel__empty">no pending decisions</div>
      ) : (
        sections.map((sec) => (
          <section key={sec} className="digest-section">
            <h3 className="digest-section__title">{sec}</h3>
            {entries
              .filter((e) => e.section === sec)
              .map((e) => (
                <DigestEntry
                  key={e.id}
                  entry={e}
                  onApply={(id) => void apply([id])}
                  onSkip={(id) => void skip(id)}
                />
              ))}
          </section>
        ))
      )}
    </aside>
  )
}
