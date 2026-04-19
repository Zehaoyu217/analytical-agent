import { useCallback, useEffect, useMemo, useState } from 'react'
import { Cpu, ChevronDown } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { backend, type ModelEntry } from '@/lib/api-backend'

const FALLBACK_MODELS: ModelEntry[] = [
  { id: 'anthropic/claude-sonnet-4-6', label: 'Sonnet 4.6', description: '' },
]

interface ModelPickerProps {
  conversationId: string
}

type CycleFn = (dir: 1 | -1) => void

interface CycleWindow extends Window {
  __dsAgentCycleModel?: CycleFn
}

export function ModelPicker({ conversationId }: ModelPickerProps) {
  const [models, setModels] = useState<ModelEntry[] | null>(null)
  const [open, setOpen] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const updateConversationModel = useChatStore((s) => s.updateConversationModel)

  useEffect(() => {
    let alive = true
    backend.models
      .list()
      .then((res) => {
        if (!alive) return
        const flat = res.groups.flatMap((g) => g.models)
        setModels(flat.length > 0 ? flat : FALLBACK_MODELS)
      })
      .catch(() => {
        if (!alive) return
        setModels(FALLBACK_MODELS)
        setLoadError(true)
      })
    return () => {
      alive = false
    }
  }, [])

  const active = useMemo(() => {
    const source = models ?? FALLBACK_MODELS
    return source.find((m) => m.id === conversation?.model) ?? source[0]
  }, [models, conversation?.model])

  const pick = useCallback(
    (m: ModelEntry) => {
      updateConversationModel(conversationId, m.id)
      setOpen(false)
    },
    [conversationId, updateConversationModel],
  )

  const cycleTo = useCallback<CycleFn>(
    (dir) => {
      const list = models ?? FALLBACK_MODELS
      const idx = list.findIndex((m) => m.id === active?.id)
      const next = list[(idx + dir + list.length) % list.length]
      if (next) updateConversationModel(conversationId, next.id)
    },
    [models, active?.id, conversationId, updateConversationModel],
  )

  useEffect(() => {
    const w = window as CycleWindow
    w.__dsAgentCycleModel = cycleTo
    return () => {
      delete w.__dsAgentCycleModel
    }
  }, [cycleTo])

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="model"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px]"
        style={{ color: 'var(--fg-1)' }}
      >
        <Cpu size={12} style={{ color: 'var(--fg-2)' }} />
        {active?.label ?? 'Model'}
        <ChevronDown size={10} style={{ color: 'var(--fg-3)' }} />
      </button>
      {loadError && (
        <span
          className="ml-1 text-[10.5px]"
          style={{ color: 'var(--warn)' }}
          title="Model list unavailable"
        >
          !
        </span>
      )}
      {open && (
        <div
          role="listbox"
          className="absolute bottom-full left-0 mb-2 min-w-[180px] overflow-hidden rounded-[10px] border shadow-[var(--shadow-2)]"
          style={{ borderColor: 'var(--line)', background: 'var(--bg-1)' }}
        >
          {(models ?? FALLBACK_MODELS).map((m) => (
            <div
              key={m.id}
              role="option"
              aria-selected={m.id === active?.id}
              onClick={() => pick(m)}
              className="cursor-pointer px-3 py-2 text-[12.5px]"
              style={{
                color: 'var(--fg-1)',
                background: m.id === active?.id ? 'var(--bg-2)' : 'transparent',
              }}
            >
              {m.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
