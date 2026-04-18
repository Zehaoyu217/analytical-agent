import { useEffect, useState } from 'react'
import { useDigestStore } from '@/lib/digest-store'
import { DigestEntry } from './DigestEntry'
import { DigestHeader } from './DigestHeader'
import './digest.css'

interface DigestPanelProps {
  open: boolean
  onClose: () => void
  embedded?: boolean
}

type Tab = 'today' | 'pending'

const REFRESH_INTERVAL_MS = 10_000

export function DigestPanel({ open, onClose, embedded = false }: DigestPanelProps) {
  const date = useDigestStore((s) => s.date)
  const entries = useDigestStore((s) => s.entries)
  const unread = useDigestStore((s) => s.unread)
  const error = useDigestStore((s) => s.error)
  const refresh = useDigestStore((s) => s.refresh)
  const apply = useDigestStore((s) => s.apply)
  const skip = useDigestStore((s) => s.skip)
  const markRead = useDigestStore((s) => s.markRead)
  const pending = useDigestStore((s) => s.pending)
  const refreshPending = useDigestStore((s) => s.refreshPending)
  const triggerBuild = useDigestStore((s) => s.triggerBuild)

  const [tab, setTab] = useState<Tab>('today')

  useEffect(() => {
    if (!open) return
    if (tab === 'today') {
      void refresh()
      const t = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS)
      return () => window.clearInterval(t)
    }
    void refreshPending()
    const t = window.setInterval(() => void refreshPending(), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [open, tab, refresh, refreshPending])

  if (!open) return null

  const sections = Array.from(new Set(entries.map((e) => e.section)))
  const pendingCount = pending.length

  const handleBuild = async () => {
    await triggerBuild()
    await refreshPending()
    await refresh()
  }

  return (
    <aside
      className={'digest-panel' + (embedded ? ' digest-panel--embedded' : '')}
      aria-label="Second-brain digest"
    >
      {!embedded && (
        <DigestHeader
          date={date}
          unread={unread}
          onMarkRead={() => void markRead()}
          onClose={onClose}
        />
      )}
      <div className="digest-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className="digest-tabs__btn"
          data-active={tab === 'today' ? 'true' : 'false'}
          onClick={() => setTab('today')}
        >
          TODAY
        </button>
        <button
          type="button"
          role="tab"
          className="digest-tabs__btn"
          data-active={tab === 'pending' ? 'true' : 'false'}
          onClick={() => setTab('pending')}
        >
          PENDING{pendingCount > 0 ? ` (${pendingCount})` : ''}
        </button>
      </div>
      {error && <div className="digest-panel__error">{error}</div>}
      {tab === 'today' ? (
        entries.length === 0 ? (
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
        )
      ) : (
        <div>
          <div className="digest-pending__actions">
            <button
              type="button"
              className="digest-pending__build"
              onClick={() => void handleBuild()}
            >
              BUILD NOW
            </button>
          </div>
          {pending.length === 0 ? (
            <div className="digest-panel__empty">no pending proposals</div>
          ) : (
            pending.map((p) => (
              <div
                key={p.id}
                data-testid="digest-pending-entry"
                className="digest-entry"
              >
                <span className="digest-entry__id">[{p.id}]</span>
                <span className="digest-entry__line">
                  <span className="digest-pending__section">{p.section}</span>{' '}
                  {p.line}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </aside>
  )
}
