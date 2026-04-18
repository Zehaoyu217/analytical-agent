import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import {
  useIngestStore,
  shortPath,
  formatAgo,
} from '@/lib/ingest-store'
import './ingest.css'

interface IngestPanelProps {
  open: boolean
  onClose: () => void
  embedded?: boolean
}

type Mode = 'file' | 'url'

export function IngestPanel({ open, onClose, embedded = false }: IngestPanelProps) {
  const recent = useIngestStore((s) => s.recent)
  const submitting = useIngestStore((s) => s.submitting)
  const submit = useIngestStore((s) => s.submit)
  const submitFile = useIngestStore((s) => s.submitFile)

  const [mode, setMode] = useState<Mode>('file')
  const [url, setUrl] = useState<string>('')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  if (!open) return null

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) {
      setMode('file')
      setPendingFile(file)
      return
    }
    const text =
      e.dataTransfer.getData('text/uri-list') ||
      e.dataTransfer.getData('text/plain')
    if (text) {
      setMode('url')
      setUrl(text.trim())
    }
  }

  const handleFilePick = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setPendingFile(f)
    e.target.value = ''
  }

  const handleSubmit = async () => {
    if (mode === 'file') {
      if (!pendingFile) return
      await submitFile(pendingFile)
      setPendingFile(null)
    } else {
      const trimmed = url.trim()
      if (!trimmed) return
      await submit(trimmed)
      setUrl('')
    }
  }

  const canSubmit =
    !submitting &&
    (mode === 'file' ? pendingFile !== null : url.trim().length > 0)

  return (
    <aside
      className={
        'ingest-panel' + (embedded ? ' ingest-panel--embedded' : '')
      }
      aria-label="Second-brain ingest panel"
    >
      {!embedded && (
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
      )}

      <div
        className="ingest-panel__tabs"
        role="tablist"
        aria-label="ingest source"
      >
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'file'}
          data-active={mode === 'file' ? 'true' : 'false'}
          className="ingest-panel__tab"
          onClick={() => setMode('file')}
          data-testid="ingest-mode-file"
        >
          FILE
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'url'}
          data-active={mode === 'url' ? 'true' : 'false'}
          className="ingest-panel__tab"
          onClick={() => setMode('url')}
          data-testid="ingest-mode-url"
        >
          URL
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
        {mode === 'file' ? 'DROP FILE OR CLICK LOAD' : 'PASTE OR DROP URL'}
        <span className="ingest-panel__dropzone-hint">
          {mode === 'file'
            ? 'any file — stored to a staging dir before ingest'
            : 'http(s)://…, gh:owner/repo, or file:// URL'}
        </span>
      </div>

      {mode === 'file' ? (
        <div className="ingest-panel__form">
          <input
            ref={fileInputRef}
            type="file"
            className="ingest-panel__file-hidden"
            onChange={handleFilePick}
            aria-label="ingest file"
            data-testid="ingest-file-input"
          />
          <div className="ingest-panel__file-row">
            <button
              type="button"
              className="ingest-panel__load"
              onClick={() => fileInputRef.current?.click()}
              data-testid="ingest-load"
            >
              LOAD FILE
            </button>
            <span
              className="ingest-panel__file-name"
              data-testid="ingest-file-name"
              title={pendingFile?.name ?? ''}
            >
              {pendingFile ? pendingFile.name : 'no file selected'}
            </span>
          </div>
          <button
            type="button"
            className="ingest-panel__submit"
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
            data-testid="ingest-submit"
          >
            {submitting ? '…' : 'INGEST'}
          </button>
        </div>
      ) : (
        <div className="ingest-panel__form">
          <input
            type="text"
            className="ingest-panel__input"
            placeholder="https://… or gh:owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleSubmit()
            }}
            aria-label="ingest url"
            data-testid="ingest-input"
          />
          <button
            type="button"
            className="ingest-panel__submit"
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
            data-testid="ingest-submit"
          >
            {submitting ? '…' : 'INGEST'}
          </button>
        </div>
      )}

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
