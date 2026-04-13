import { useCallback, useEffect, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { Message } from '@/lib/store'
import { extractTextContent } from '@/lib/utils'
import { MessageBubble } from './MessageBubble'

/**
 * Estimated heights used for initial layout. The virtualizer measures actual
 * heights after render and updates scroll positions accordingly.
 */
const ESTIMATED_HEIGHT = {
  short: 80, // typical user message
  medium: 160, // short assistant reply
  tall: 320, // code blocks / long replies
} as const

function estimateMessageHeight(message: Message): number {
  const text = extractTextContent(message.content)
  if (text.length < 100) return ESTIMATED_HEIGHT.short
  if (text.length < 500 || text.includes('```')) return ESTIMATED_HEIGHT.medium
  return ESTIMATED_HEIGHT.tall
}

export interface VirtualMessageListProps {
  messages: Message[]
  /**
   * Whether streaming is in progress — suppresses smooth-scroll so autoscroll
   * keeps up with incoming tokens. P2 has no streaming; the flag is kept for
   * forward-compat.
   */
  isStreaming: boolean
  conversationId?: string
  /**
   * Called whenever the user's proximity to the bottom of the scroll region
   * crosses the threshold. The second arg is a callable that performs a
   * smooth scroll to bottom, exposed up so `ScrollToBottom` can fire it.
   */
  onScrollStateChange?: (isAtBottom: boolean, scrollToBottom: () => void) => void
}

export function VirtualMessageList({
  messages,
  isStreaming,
  conversationId,
  onScrollStateChange,
}: VirtualMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => estimateMessageHeight(messages[index]),
    overscan: 4,
  })

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const atBottom = distanceFromBottom < 80
    if (atBottom !== isAtBottomRef.current) {
      isAtBottomRef.current = atBottom
      onScrollStateChange?.(atBottom, scrollToBottom)
    }
  }, [onScrollStateChange, scrollToBottom])

  // Auto-scroll when new messages arrive, only if the user was already at bottom.
  useEffect(() => {
    if (!isAtBottomRef.current) return
    const el = scrollRef.current
    if (!el) return
    if (isStreaming) {
      el.scrollTop = el.scrollHeight
    } else {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }, [messages.length, isStreaming])

  // Also scroll whenever streaming content changes (token-by-token updates).
  useEffect(() => {
    if (!isStreaming || !isAtBottomRef.current) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  })

  const items = virtualizer.getVirtualItems()

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto" onScroll={handleScroll}>
      {/* Spacer that gives the virtualizer its total height */}
      <div
        style={{ height: virtualizer.getTotalSize(), position: 'relative' }}
        className="max-w-3xl mx-auto px-4 py-6"
      >
        {items.map((virtualItem) => {
          const message = messages[virtualItem.index]
          return (
            <div
              key={virtualItem.key}
              data-index={virtualItem.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                transform: `translateY(${virtualItem.start}px)`,
              }}
              className="pb-6"
            >
              <MessageBubble message={message} conversationId={conversationId} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
