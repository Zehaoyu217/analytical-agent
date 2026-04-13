import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { extractTextContent } from '@/lib/utils'
import { VirtualMessageList } from './VirtualMessageList'
import { ScrollToBottom } from './ScrollToBottom'
import { SuggestedPrompts } from './SuggestedPrompts'

interface ChatWindowProps {
  conversationId: string
}

const ANNOUNCE_PREVIEW_LENGTH = 120

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const setDraftInput = useChatStore((s) => s.setDraftInput)

  const messages = conversation?.messages ?? []
  const isStreaming = messages.some((m) => m.status === 'streaming')

  // Polite live-region announcement for screen readers when an assistant reply finishes.
  const [announcement, setAnnouncement] = useState('')
  const prevLengthRef = useRef(messages.length)

  // Scroll-tracking state for the floating ScrollToBottom button.
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [unreadCount, setUnreadCount] = useState(0)
  const prevMessageCountRef = useRef(messages.length)
  const scrollToBottomFnRef = useRef<(() => void) | null>(null)

  const handleScrollStateChange = useCallback(
    (atBottom: boolean, scrollToBottomFn: () => void) => {
      scrollToBottomFnRef.current = scrollToBottomFn
      setIsAtBottom(atBottom)
      if (atBottom) setUnreadCount(0)
    },
    [],
  )

  // Track new messages arriving while the user is scrolled away from the bottom.
  useEffect(() => {
    const delta = messages.length - prevMessageCountRef.current
    prevMessageCountRef.current = messages.length
    if (delta > 0 && !isAtBottom) {
      setUnreadCount((n) => n + delta)
    }
  }, [messages.length, isAtBottom])

  // Announce the last completed assistant message.
  useEffect(() => {
    const lastMsg = messages[messages.length - 1]
    const shouldAnnounce =
      messages.length > prevLengthRef.current &&
      lastMsg?.role === 'assistant' &&
      lastMsg.status === 'complete'
    prevLengthRef.current = messages.length

    if (!shouldAnnounce) return
    const preview = extractTextContent(lastMsg.content).slice(0, ANNOUNCE_PREVIEW_LENGTH)
    // Clear first so identical text still triggers announcement.
    setAnnouncement('')
    const handle = window.setTimeout(
      () => setAnnouncement(`Assistant replied: ${preview}`),
      50,
    )
    return () => window.clearTimeout(handle)
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-6">
        <div
          className="w-12 h-12 rounded-full bg-brand-600/20 flex items-center justify-center"
          aria-hidden="true"
        >
          <Bot className="w-6 h-6 text-brand-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-surface-100">How can I help?</h2>
          <p className="text-sm text-surface-400 mt-1">
            Send a message to begin chatting with the agent.
          </p>
        </div>
        <SuggestedPrompts onSelect={(text) => setDraftInput(text)} />
      </div>
    )
  }

  return (
    <div className="relative flex-1 min-h-0 flex flex-col">
      {/* Polite live region — announces when the assistant finishes a reply */}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </div>

      <VirtualMessageList
        messages={messages}
        isStreaming={isStreaming}
        conversationId={conversationId}
        onScrollStateChange={handleScrollStateChange}
      />

      {/* Scroll-to-bottom floating button, centred above the input */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 pointer-events-none">
        <div className="pointer-events-auto">
          <ScrollToBottom
            visible={!isAtBottom}
            onClick={() => scrollToBottomFnRef.current?.()}
            unreadCount={unreadCount}
          />
        </div>
      </div>
    </div>
  )
}
