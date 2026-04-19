import { AlertTriangle, XCircle, Info, type LucideIcon } from 'lucide-react'

interface CalloutProps {
  kind: 'warn' | 'err' | 'info'
  label: string
  text: string
}

const ICON_MAP: Record<CalloutProps['kind'], LucideIcon> = {
  warn: AlertTriangle,
  err: XCircle,
  info: Info,
}

const PALETTE_MAP: Record<CalloutProps['kind'], string> = {
  warn: 'var(--warn)',
  err: 'var(--err)',
  info: 'var(--info)',
}

export function Callout({ kind, label, text }: CalloutProps) {
  const Icon = ICON_MAP[kind]
  const palette = PALETTE_MAP[kind]
  return (
    <div
      className="mt-2.5 flex gap-[10px] rounded-lg border px-3 py-2.5 text-[12.5px]"
      style={{
        borderColor: `color-mix(in oklch, ${palette} 30%, var(--line))`,
        background: `color-mix(in oklch, ${palette} 6%, var(--bg-1))`,
      }}
    >
      <Icon size={13} style={{ color: palette, marginTop: 2, flexShrink: 0 }} />
      <div>
        <div className="mb-0.5 text-[11.5px] font-medium" style={{ color: palette }}>
          {label}
        </div>
        <div style={{ color: 'var(--fg-1)' }}>{text}</div>
      </div>
    </div>
  )
}
