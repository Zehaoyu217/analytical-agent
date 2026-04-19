import { useEffect, useMemo } from 'react'
import { useChatStore } from '@/lib/store'
import { ChatHeader } from './header/ChatHeader'
import { ChatWindow } from './ChatWindow'
import { Composer } from './composer/Composer'

export function ChatPane() {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversations = useChatStore((s) => s.conversations)
  const createConversation = useChatStore((s) => s.createConversation)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)

  useEffect(() => {
    if (!activeId && conversations.length === 0) {
      createConversation()
    } else if (!activeId && conversations.length > 0) {
      setActiveConversation(conversations[0].id)
    }
  }, [activeId, conversations, createConversation, setActiveConversation])

  const conversationId = useMemo(
    () => activeId ?? conversations[0]?.id ?? '',
    [activeId, conversations],
  )

  if (!conversationId) return null

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <ChatHeader conversationId={conversationId} />
      <div className="flex-1 overflow-auto px-7">
        <div className="mx-auto max-w-[820px]">
          <ChatWindow conversationId={conversationId} />
        </div>
      </div>
      <div className="px-7 pb-[18px] pt-3.5">
        <div className="mx-auto max-w-[820px]">
          <Composer conversationId={conversationId} />
        </div>
      </div>
    </div>
  )
}
