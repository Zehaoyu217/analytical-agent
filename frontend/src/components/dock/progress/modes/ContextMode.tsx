import { useChatStore } from '@/lib/store'
import { extractTextContent } from '@/lib/utils'
import type { ProgressStep } from '@/lib/selectors/progressSteps'

interface ContextModeProps {
  step: ProgressStep
}

function formatTime(ts: number): string {
  return new Date(ts).toTimeString().slice(0, 8)
}

/**
 * Per-step context view. Shows only the conversation turn that produced this
 * specific tool call — not aggregated session-wide tool history.
 */
export function ContextMode({ step }: ContextModeProps) {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === activeId),
  )
  const entry = useChatStore((s) =>
    s.toolCallLog.find((t) => t.id === step.toolCallIds[0]),
  )

  if (!conversation || !entry) {
    return <div className="cockpit-trace__empty">no context for this step</div>
  }

  const owningMessage = entry.messageId
    ? conversation.messages.find((m) => m.id === entry.messageId)
    : undefined
  const userTurn = (() => {
    if (!owningMessage) return undefined
    const idx = conversation.messages.indexOf(owningMessage)
    for (let i = idx - 1; i >= 0; i -= 1) {
      if (conversation.messages[i].role === 'user') return conversation.messages[i]
    }
    return undefined
  })()

  return (
    <div className="flex flex-col gap-2">
      {userTurn && (
        <div>
          <div className="label-cap mb-1">User prompt</div>
          <div className="text-[12px] leading-[1.5] text-fg-1">
            {extractTextContent(userTurn.content).slice(0, 320) || '[no text]'}
          </div>
          <div className="mono mt-1 text-[10.5px] text-fg-3">
            {formatTime(userTurn.timestamp)}
          </div>
        </div>
      )}
      <div>
        <div className="label-cap mb-1">This call</div>
        <div className="mono text-[11.5px] text-fg-1">
          {step.title}
          {entry.inputPreview && (
            <>
              {' '}
              <span className="text-fg-3">·</span>{' '}
              <span className="text-fg-2">{entry.inputPreview}</span>
            </>
          )}
        </div>
        <div className="mono mt-1 text-[10.5px] text-fg-3">
          status: {entry.status}
          {entry.startedAt && entry.finishedAt && (
            <> · {entry.finishedAt - entry.startedAt}ms</>
          )}
        </div>
      </div>
    </div>
  )
}
