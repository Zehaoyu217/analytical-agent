import type { SlashCommand } from '@/lib/api-backend'

interface SlashMenuProps {
  commands: SlashCommand[]
  highlight: number
  onPick: (cmd: SlashCommand) => void
  onHover: (index: number) => void
}

export function SlashMenu({ commands, highlight, onPick, onHover }: SlashMenuProps) {
  if (commands.length === 0) return null
  return (
    <div
      role="listbox"
      className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-[10px] border shadow"
      style={{
        borderColor: 'var(--line)',
        background: 'var(--bg-1)',
        boxShadow: 'var(--shadow-2)',
      }}
    >
      {commands.map((c, i) => {
        const active = i === highlight
        return (
          <div
            key={c.id}
            role="option"
            aria-selected={active}
            onMouseEnter={() => onHover(i)}
            onClick={() => onPick(c)}
            className="flex cursor-pointer gap-[10px] px-3 py-2 text-[13px]"
            style={{
              color: 'var(--fg-1)',
              background: active ? 'var(--bg-2)' : 'transparent',
            }}
          >
            <span className="mono w-[72px] text-[12px]" style={{ color: 'var(--acc)' }}>
              /{c.id}
            </span>
            <span style={{ color: 'var(--fg-2)' }}>{c.description || c.label}</span>
          </div>
        )
      })}
    </div>
  )
}
