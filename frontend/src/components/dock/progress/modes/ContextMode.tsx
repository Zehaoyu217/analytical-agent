import { useChatStore } from '@/lib/store'
import { extractTextContent } from '@/lib/utils'

function formatTime(ts: number): string {
  return new Date(ts).toTimeString().slice(0, 8)
}

export function ContextMode() {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === activeId),
  )
  const toolCallLog = useChatStore((s) => s.toolCallLog)

  if (!conversation) {
    return (
      <div className="cockpit-trace__body">
        <div className="cockpit-trace__empty">no session</div>
      </div>
    )
  }

  const messages = conversation.messages.slice(-6)

  return (
    <div className="cockpit-context">
      {messages.length === 0 && (
        <div className="cockpit-trace__empty">no turns yet</div>
      )}
      {messages.map((m) => {
        const text = extractTextContent(m.content).slice(0, 180)
        return (
          <div key={m.id}>
            <div className="cockpit-context__turn-role">
              {m.role} · {formatTime(m.timestamp)}
            </div>
            <div className="cockpit-context__turn-body">
              {text || '[no text]'}
            </div>
          </div>
        )
      })}
      {toolCallLog.length > 0 && (
        <div className="cockpit-context__tools">
          <div className="cockpit-context__tools-head">
            tool calls ({toolCallLog.length})
          </div>
          {toolCallLog.slice(-8).map((t) => (
            <div key={t.id} className="cockpit-trace__row">
              <span className="cockpit-trace__row-kind">{t.name}</span>
              <span className="cockpit-hud__dim">{t.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
