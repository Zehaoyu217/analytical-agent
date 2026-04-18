import { useState } from 'react'
import { useChatStore } from '@/lib/store'
import { countToday, useSkillsStore } from '@/lib/skills-store'
import { useRightRailStore, type RailMode } from '@/lib/right-rail-store'
import { SessionDropdown } from './SessionDropdown'

interface ChipDef {
  id: Exclude<RailMode, 'trace'>
  label: string
}

const CHIPS: ChipDef[] = [
  { id: 'graph', label: 'GRAPH' },
  { id: 'digest', label: 'DIGEST' },
  { id: 'ingest', label: 'INGEST' },
]

function shortModel(model: string): string {
  const trimmed = model.split('/').pop() || model
  return trimmed.replace(/^anthropic\./i, '')
}

export function TopHUD() {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversations = useChatStore((s) => s.conversations)
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const settings = useChatStore((s) => s.settings)
  const skillEvents = useSkillsStore((s) => s.events)
  const skillsToday = countToday(skillEvents)
  const mode = useRightRailStore((s) => s.mode)
  const toggleMode = useRightRailStore((s) => s.toggleMode)

  const active = conversations.find((c) => c.id === activeId)
  const shortId = (active?.sessionId || active?.id || '').slice(0, 7) || '—'
  const lastTool = toolCallLog.length
    ? toolCallLog[toolCallLog.length - 1].name
    : '—'
  const streaming =
    active?.messages.some((m) => m.status === 'streaming') ?? false

  const [dropdownOpen, setDropdownOpen] = useState(false)

  return (
    <header className="cockpit-hud" role="banner" aria-label="Session telemetry">
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          className="cockpit-hud__session"
          onClick={() => setDropdownOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={dropdownOpen}
        >
          SESSION {shortId} ▾
        </button>
        {dropdownOpen && <SessionDropdown onClose={() => setDropdownOpen(false)} />}
      </div>

      <span>·</span>
      <span className="cockpit-hud__value">{shortModel(settings.model)}</span>
      <span>·</span>
      <span className="cockpit-hud__value">$—</span>
      <span className="cockpit-hud__dim">($—/day)</span>
      <span>·</span>
      <span className="cockpit-hud__value">— / 200k</span>
      <span>·</span>
      <span className="cockpit-hud__value">—</span>
      <span>·</span>
      <span className={streaming ? 'cockpit-hud__ok' : 'cockpit-hud__dim'}>●</span>
      <span>{streaming ? 'STREAMING' : 'IDLE'}</span>
      <span>·</span>
      <span>
        SKILLS <span className="cockpit-hud__value">{skillsToday}/0</span>
      </span>
      <span>·</span>
      <span>
        KB <span className="cockpit-hud__ok">OK</span>
      </span>
      <span>·</span>
      <span>
        last: <span className="cockpit-hud__accent-soft">{lastTool}</span>
      </span>

      <div className="cockpit-hud__chips">
        {CHIPS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className="cockpit-hud__chip"
            data-active={mode === chip.id}
            onClick={() => toggleMode(chip.id)}
            aria-pressed={mode === chip.id}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </header>
  )
}
