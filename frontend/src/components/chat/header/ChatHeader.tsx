import { useCallback, useState } from 'react'
import { Plus } from 'lucide-react'
import { SidebarIcon, SidebarOnIcon } from '@/components/layout/icons/Sidebar'
import { useUiStore } from '@/lib/ui-store'
import { useChatStore } from '@/lib/store'
import { TitleEditor } from './TitleEditor'
import { HeaderActions } from './HeaderActions'

interface ChatHeaderProps {
  conversationId: string
}

export function ChatHeader({ conversationId }: ChatHeaderProps) {
  const threadsOpen = useUiStore((s) => s.threadsOpen)
  const setThreadsOpen = useUiStore((s) => s.setThreadsOpen)
  const createConversation = useChatStore((s) => s.createConversation)
  const [renameSignal, setRenameSignal] = useState(0)

  const triggerRename = useCallback(() => {
    setRenameSignal((n) => n + 1)
  }, [])

  return (
    <div
      className="flex items-center gap-2 border-b py-2.5 pl-2.5 pr-[18px]"
      style={{ borderColor: 'var(--line-2)' }}
    >
      <button
        type="button"
        aria-label={threadsOpen ? 'Hide threads' : 'Show threads'}
        onClick={() => setThreadsOpen(!threadsOpen)}
        className="flex h-[30px] w-[30px] items-center justify-center rounded-md transition-colors"
        style={{
          color: threadsOpen ? 'var(--acc)' : 'var(--fg-2)',
          background: threadsOpen ? 'var(--acc-dim)' : 'transparent',
        }}
      >
        {threadsOpen ? <SidebarOnIcon size={14} /> : <SidebarIcon size={14} />}
      </button>
      {!threadsOpen && (
        <button
          type="button"
          aria-label="New chat"
          title="New chat · ⌘N"
          onClick={() => createConversation()}
          className="fade-in flex h-[30px] w-[30px] items-center justify-center rounded-md"
          style={{ color: 'var(--acc)' }}
        >
          <Plus size={15} />
        </button>
      )}
      <div className="mx-1 h-[18px] w-px" style={{ background: 'var(--line-2)' }} />
      <TitleEditor conversationId={conversationId} triggerSignal={renameSignal} />
      <div className="flex-1" />
      <HeaderActions conversationId={conversationId} onRename={triggerRename} />
    </div>
  )
}
