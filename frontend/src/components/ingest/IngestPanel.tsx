import { useState, type DragEvent } from 'react'
import {
  useIngestStore,
  shortPath,
  formatAgo,
} from '@/lib/ingest-store'
import './ingest.css'

interface IngestPanelProps {
  open: boolean
  onClose: () => void
}

export function IngestPanel({ open, onClose }: IngestPanelProps) {
  const recent = useIngestStore((s) => s.recent)
  const submitting = useIngestStore((s) => s.submitting)
  const submit = useIngestStore((s) => s.submit)

  const [path, setPath] = useState<string>('')
  const [dragActive, setDragActive] = useState<boolean>(false)

  if (!open) return null

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      // Browsers don't expose a real filesystem path. Prefill with the
      // file name as a hint — user completes the path manually.
      setPath((curr) => curr || file.name)
      return
    }
    const text = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain')
    if (text) setPath(text.trim())
  }

  const handleSubmit = async () => {
    if (!path.trim()) return
    await submit(path)
    setPath('')
  }

  return (
    <aside className="ingest-panel" aria-label="Second-brain ingest panel">
      <div className="ingest-panel__header">
        <div>
          <div className="ingest-panel__title">INGEST</div>
          <div className="ingest-panel__meta">{recent.length} recent</div>
        </div>
        <button
          type="button"
          className="ingest-panel__close"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>

      <div
        className="ingest-panel__dropzone"
        data-active={dragActive ? 'true' : 'false'}
        data-testid="ingest-dropzone"
        onDragOver={(e) => {
          e.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        DROP FILE OR PASTE URL
        <span className="ingest-panel__dropzone-hint">
          browsers hide real paths — paste an absolute path or URL below
        </span>
      </div>

      <div className="ingest-panel__form">
        <input
          type="text"
          className="ingest-panel__input"
          placeholder="/path/to/file.md or https://…"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void handleSubmit()
          }}
          aria-label="ingest target path or url"
          data-testid="ingest-input"
        />
        <button
          type="button"
          className="ingest-panel__submit"
          onClick={() => void handleSubmit()}
          disabled={submitting || !path.trim()}
          data-testid="ingest-submit"
        >
          {submitting ? '…' : 'INGEST'}
        </button>
      </div>

      <div className="ingest-panel__section-title">Recent</div>
      {recent.length === 0 ? (
        <div className="ingest-panel__empty">no ingests yet</div>
      ) : (
        recent.map((r) => (
          <div
            key={`${r.timestamp}-${r.path}`}
            className="ingest-panel__row"
            data-testid="ingest-recent-row"
          >
            <span
              className="ingest-panel__row-outcome"
              data-outcome={r.outcome}
            >
              {r.outcome === 'ok' ? 'OK' : 'ERR'}
            </span>
            <span className="ingest-panel__row-path" title={r.path}>
              {shortPath(r.path)}
            </span>
            <span className="ingest-panel__row-meta">
              {formatAgo(r.timestamp)}
            </span>
          </div>
        ))
      )}
    </aside>
  )
}
