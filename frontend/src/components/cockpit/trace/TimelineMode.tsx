import { useChatStore } from '@/lib/store'

function formatTime(ts: number | undefined): string {
  if (!ts) return '--:--:--'
  return new Date(ts).toTimeString().slice(0, 8)
}

export function TimelineMode() {
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === activeId),
  )
  const streaming =
    conversation?.messages.some((m) => m.status === 'streaming') ?? false

  if (toolCallLog.length === 0) {
    return (
      <div className="cockpit-trace__body">
        <div className="cockpit-trace__empty">no events yet</div>
        {streaming && (
          <div className="cockpit-trace__streaming">▊ STREAMING</div>
        )}
      </div>
    )
  }

  return (
    <div className="cockpit-trace__body">
      {toolCallLog.map((t) => {
        const dur =
          t.finishedAt && t.startedAt ? `${t.finishedAt - t.startedAt}ms` : ''
        const statusClass =
          t.status === 'error'
            ? ' cockpit-trace__row-status--error'
            : t.status === 'ok'
              ? ' cockpit-trace__row-status--ok'
              : ''
        return (
          <div key={t.id} className="cockpit-trace__row">
            <span className="cockpit-trace__row-time">
              {formatTime(t.startedAt)}
            </span>
            <span className="cockpit-hud__dim">·</span>
            <span className="cockpit-trace__row-kind">tool</span>
            <span>{t.name}</span>
            <span className={'cockpit-trace__row-dur' + statusClass}>{dur}</span>
          </div>
        )
      })}
      {streaming && <div className="cockpit-trace__streaming">▊ STREAMING</div>}
    </div>
  )
}
