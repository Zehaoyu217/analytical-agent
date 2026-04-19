import { GitBranch } from 'lucide-react'
import { useChatStore } from '@/lib/store'

interface ForkButtonProps {
  conversationId: string
}

export function ForkButton({ conversationId }: ForkButtonProps) {
  const fork = useChatStore((s) => s.forkConversation)
  return (
    <button
      type="button"
      aria-label="Fork"
      onClick={() => fork(conversationId)}
      className="flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px]"
      style={{ borderColor: 'var(--line-2)', color: 'var(--fg-1)' }}
    >
      <GitBranch size={12} /> Fork
    </button>
  )
}
