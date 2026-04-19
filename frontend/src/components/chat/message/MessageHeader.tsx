import { Copy, MoreHorizontal } from 'lucide-react'

interface MessageHeaderProps {
  name: string
  timestamp: string
  onCopy: () => void
}

export function MessageHeader({ name, timestamp, onCopy }: MessageHeaderProps) {
  return (
    <div className="mb-1 flex items-baseline gap-2">
      <span
        className="text-[13px] font-semibold tracking-[-0.005em]"
        style={{ color: 'var(--fg-0)' }}
      >
        {name}
      </span>
      <span className="mono text-[10.5px]" style={{ color: 'var(--fg-3)' }}>
        {timestamp}
      </span>
      <div className="flex-1" />
      <button
        type="button"
        aria-label="Copy"
        onClick={onCopy}
        className="rounded p-[3px]"
        style={{ color: 'var(--fg-3)' }}
      >
        <Copy size={12} />
      </button>
      <button
        type="button"
        aria-label="More"
        className="rounded p-[3px]"
        style={{ color: 'var(--fg-3)' }}
      >
        <MoreHorizontal size={12} />
      </button>
    </div>
  )
}
