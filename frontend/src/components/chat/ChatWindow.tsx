import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/lib/store'
import { useBranding } from '@/hooks/useBranding'
import { extractTextContent } from '@/lib/utils'
import { VirtualMessageList } from './VirtualMessageList'
import { ScrollToBottom } from './ScrollToBottom'
import { SuggestedPrompts } from './SuggestedPrompts'

const CHAT_SUBMIT_EVENT = 'chat:submit'

interface ChatWindowProps {
  conversationId: string
}

const ANNOUNCE_PREVIEW_LENGTH = 120

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const setDraftInput = useChatStore((s) => s.setDraftInput)
  const deleteMessage = useChatStore((s) => s.deleteMessage)
  const { ui_title } = useBranding()

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

  const handleRegenerate = useCallback(
    (messageId: string) => {
      const msgs = conversation?.messages ?? []
      const idx = msgs.findIndex((m) => m.id === messageId)
      if (idx < 1) return
      const preceding = msgs[idx - 1]
      if (preceding.role !== 'user') return
      const userText = extractTextContent(preceding.content)
      deleteMessage(conversationId, messageId)
      setDraftInput(userText)
      window.dispatchEvent(new CustomEvent(CHAT_SUBMIT_EVENT))
    },
    [conversation?.messages, conversationId, deleteMessage, setDraftInput],
  )

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
      <div className="flex-1 flex flex-col justify-center px-2">
        <div className="max-w-2xl mx-auto w-full">
          <div className="flex items-center gap-3 mb-6">
            <span className="text-[11px] font-mono tracking-[0.25em] text-surface-500 uppercase">
              {ui_title}
            </span>
            <span className="w-px h-3 bg-surface-700 flex-shrink-0" aria-hidden />
            <span className="text-[11px] font-mono tracking-[0.18em] text-brand-accent/80 uppercase">
              Ready
            </span>
          </div>
          <p className="text-[11px] font-mono text-surface-600 mb-5 leading-relaxed">
            Query datasets, run Python, produce charts and diagnostic reports.
            <br />
            Type <span className="text-surface-400">/</span> for commands, or start with a quick query.
          </p>
          <p className="text-[10px] font-mono tracking-[0.22em] text-surface-600 uppercase mb-3">
            Quick queries
          </p>
          <SuggestedPrompts onSelect={(text) => setDraftInput(text)} />
        </div>
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
        onScrollStateChange={handleScrollStateChange}
        onRegenerate={handleRegenerate}
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
