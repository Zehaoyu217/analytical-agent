import './digest.css'

interface DigestHeaderProps {
  date: string
  unread: number
  onMarkRead: () => void
  onClose: () => void
}

export function DigestHeader({ date, unread, onMarkRead, onClose }: DigestHeaderProps) {
  return (
    <div className="digest-header">
      <div>
        <div className="digest-header__title">DIGEST</div>
        <div className="digest-header__meta">
          {date || '—'} · {unread} unread
        </div>
      </div>
      <div className="digest-header__actions">
        <button type="button" onClick={onMarkRead}>
          mark read
        </button>
        <button
          type="button"
          className="digest-header__close"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>
    </div>
  )
}
