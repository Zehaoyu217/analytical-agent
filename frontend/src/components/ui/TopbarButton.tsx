import './topbar-button.css'

interface TopbarButtonProps {
  label: string
  count?: number
  active?: boolean
  unread?: boolean
  onClick: () => void
  ariaLabel?: string
  /** vertical order 0..N; 0 = topmost */
  slot: number
}

export function TopbarButton({
  label,
  count,
  active,
  unread,
  onClick,
  ariaLabel,
  slot,
}: TopbarButtonProps) {
  const showCount = typeof count === 'number' && count > 0
  return (
    <button
      type="button"
      className="topbar-btn"
      data-active={active ? 'true' : 'false'}
      data-unread={unread ? 'true' : 'false'}
      style={{ top: 10 + slot * 32 }}
      onClick={onClick}
      aria-label={ariaLabel ?? label}
    >
      {label}
      {showCount ? ` · ${count}` : ''}
    </button>
  )
}
