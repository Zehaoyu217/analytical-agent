import {
  MessageSquare,
  Monitor,
  Puzzle,
  FileText,
  Layers,
  Code2,
  Settings,
} from 'lucide-react'
import { useChatStore, type SectionId } from '@/lib/store'
import { cn } from '@/lib/utils'

interface SectionDef {
  id: SectionId
  icon: React.ElementType
  label: string
}

const TOP_SECTIONS: SectionDef[] = [
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
  { id: 'agents', icon: Monitor, label: 'Agents' },
  { id: 'skills', icon: Puzzle, label: 'Skills' },
  { id: 'prompts', icon: FileText, label: 'Prompts' },
  { id: 'context', icon: Layers, label: 'Context' },
  { id: 'devtools', icon: Code2, label: 'DevTools' },
]

const BOTTOM_SECTIONS: SectionDef[] = [
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export function IconRail() {
  const activeSection = useChatStore((s) => s.activeSection)
  const setActiveSection = useChatStore((s) => s.setActiveSection)

  function renderButton(def: SectionDef) {
    const isActive = activeSection === def.id
    const Icon = def.icon

    return (
      <button
        key={def.id}
        type="button"
        title={def.label}
        aria-label={def.label}
        aria-current={isActive ? 'page' : undefined}
        onClick={() => setActiveSection(def.id)}
        className={cn(
          'flex items-center justify-center w-12 h-12 rounded-md transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
          isActive
            ? 'text-brand-500'
            : 'text-surface-600 hover:text-surface-300',
        )}
        style={
          isActive
            ? { backgroundColor: 'rgba(139,92,246,0.12)' }
            : undefined
        }
      >
        <Icon
          className="w-5 h-5"
          aria-hidden="true"
        />
      </button>
    )
  }

  return (
    <nav
      aria-label="Main navigation"
      className="flex flex-col items-center w-12 h-full bg-surface-900 border-r border-surface-800 flex-shrink-0 py-2"
    >
      {/* Top section icons */}
      <div className="flex flex-col items-center gap-0.5 flex-1">
        {TOP_SECTIONS.map(renderButton)}
      </div>

      {/* Separator before settings */}
      <div className="w-8 h-px bg-surface-800 my-1" aria-hidden="true" />

      {/* Bottom section icons */}
      <div className="flex flex-col items-center gap-0.5 pb-1">
        {BOTTOM_SECTIONS.map(renderButton)}
      </div>
    </nav>
  )
}
