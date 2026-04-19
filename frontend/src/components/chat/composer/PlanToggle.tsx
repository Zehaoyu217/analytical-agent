import { ClipboardList } from 'lucide-react'

interface PlanToggleProps {
  enabled: boolean
  onToggle: () => void
}

export function PlanToggle({ enabled, onToggle }: PlanToggleProps) {
  return (
    <button
      type="button"
      aria-label="plan mode"
      data-active={enabled}
      onClick={onToggle}
      className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px] transition-colors"
      style={{
        color: enabled ? 'var(--acc)' : 'var(--fg-1)',
        background: enabled ? 'var(--acc-dim)' : 'transparent',
      }}
    >
      <ClipboardList size={12} style={{ color: enabled ? 'var(--acc)' : 'var(--fg-2)' }} />
      Plan
    </button>
  )
}
