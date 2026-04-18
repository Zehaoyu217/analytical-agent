import { useChatStore } from '@/lib/store'

export function RawMode() {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === activeId),
  )
  const toolCallLog = useChatStore((s) => s.toolCallLog)

  const dump = JSON.stringify(
    {
      sessionId: conversation?.sessionId ?? null,
      conversationId: conversation?.id ?? null,
      messageCount: conversation?.messages.length ?? 0,
      toolCalls: toolCallLog,
    },
    null,
    2,
  )

  return <pre className="cockpit-raw">{dump}</pre>
}
