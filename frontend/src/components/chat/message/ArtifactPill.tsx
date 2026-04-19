import {
  FileText,
  BarChart3,
  Table,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react'
import type { Artifact } from '@/lib/store'

interface ArtifactPillProps {
  id: string
  type: Artifact['type']
  name: string
  size: string
  missing: boolean
  onOpen: (id: string) => void
}

const ICON_MAP: Record<Artifact['type'], LucideIcon> = {
  chart: BarChart3,
  table: Table,
  diagram: BarChart3,
  profile: Table,
  analysis: FileText,
  file: FileText,
}

export function ArtifactPill({ id, type, name, size, missing, onOpen }: ArtifactPillProps) {
  const Icon = ICON_MAP[type] ?? FileText
  return (
    <button
      type="button"
      disabled={missing}
      onClick={() => onOpen(id)}
      className="mr-1.5 mt-1.5 inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[12.5px] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      style={{
        borderColor: 'var(--line)',
        background: 'var(--bg-1)',
        color: 'var(--fg-0)',
      }}
    >
      <Icon size={13} style={{ color: 'var(--acc)' }} />
      <span>{name}</span>
      {size && (
        <span className="mono text-[10.5px]" style={{ color: 'var(--fg-3)' }}>
          {size}
        </span>
      )}
      {missing ? (
        <span className="text-[10.5px]" style={{ color: 'var(--fg-3)' }}>
          — removed
        </span>
      ) : (
        <ChevronRight size={12} style={{ color: 'var(--fg-3)', marginLeft: 2 }} />
      )}
    </button>
  )
}
