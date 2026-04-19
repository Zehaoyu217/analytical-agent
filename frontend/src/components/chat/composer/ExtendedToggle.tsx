import { Brain } from 'lucide-react'
import { useChatStore } from '@/lib/store'

interface ExtendedToggleProps {
  conversationId: string
}

export function ExtendedToggle({ conversationId }: ExtendedToggleProps) {
  const enabled = useChatStore(
    (s) => s.conversations.find((c) => c.id === conversationId)?.extendedThinking ?? false,
  )
  const setConversationExtendedThinking = useChatStore(
    (s) => s.setConversationExtendedThinking,
  )

  return (
    <button
      type="button"
      aria-label="extended thinking"
      onClick={() => setConversationExtendedThinking(conversationId, !enabled)}
      data-active={enabled}
      className="flex items-center gap-[5px] rounded-md px-2 py-1 text-[12px]"
      style={{
        color: enabled ? 'var(--acc)' : 'var(--fg-1)',
        background: enabled ? 'var(--acc-dim)' : 'transparent',
      }}
    >
      <Brain size={12} style={{ color: enabled ? 'var(--acc)' : 'var(--fg-2)' }} />
      Extended
    </button>
  )
}
