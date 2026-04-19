import { useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { Composer } from '@/components/chat/composer/Composer'

export function ChatMain() {
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const createConversation = useChatStore((s) => s.createConversation)
  const createConversationRemote = useChatStore((s) => s.createConversationRemote)

  useEffect(() => {
    if (conversations.length === 0) {
      createConversationRemote('New Conversation').catch(() => {
        createConversation()
      })
    } else if (
      !activeConversationId ||
      !conversations.some((c) => c.id === activeConversationId)
    ) {
      useChatStore.getState().setActiveConversation(conversations[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!activeConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-[11px] font-mono text-surface-700 tracking-widest uppercase">
          initializing session…
        </span>
      </div>
    )
  }

  return (
    <>
      <ChatWindow conversationId={activeConversationId} />
      <Composer conversationId={activeConversationId} />
      <div className="cockpit-shortcuts" aria-hidden="true">
        <span>⌘L focus</span>
        <span>⌘K palette</span>
        <span>⌘P session</span>
        <span>⌘\ trace tab</span>
      </div>
    </>
  )
}
