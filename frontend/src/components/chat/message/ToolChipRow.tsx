import { useMemo, useState } from 'react'
import { useChatStore, type Message } from '@/lib/store'
import { ToolChip } from './ToolChip'

interface ToolChipRowProps {
  messageId: string
  status?: Message['status']
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function ToolChipRow({ messageId, status }: ToolChipRowProps) {
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const entries = useMemo(
    () => toolCallLog.filter((entry) => entry.messageId === messageId),
    [toolCallLog, messageId],
  )
  const [expanded, setExpanded] = useState(false)

  if (entries.length === 0) return null

  // While streaming we show the live chip stream; once complete, fold to a
  // single summary pill (expandable) so the conversation stays focused on the
  // final response.
  const isComplete = status === 'complete'
  if (isComplete && !expanded) {
    const totalMs = entries.reduce((sum, e) => {
      if (e.startedAt === undefined || e.finishedAt === undefined) return sum
      return sum + (e.finishedAt - e.startedAt)
    }, 0)
    const errored = entries.some((e) => e.status === 'error' || e.status === 'blocked')
    return (
      <div className="mt-2">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="inline-flex items-center gap-[7px] rounded-md border px-[9px] py-1 text-[11.5px]"
          style={{
            borderColor: 'var(--line-2)',
            background: 'var(--bg-1)',
            color: 'var(--fg-1)',
          }}
          aria-expanded="false"
          aria-label={`Show ${entries.length} tool call${entries.length === 1 ? '' : 's'}`}
        >
          <span
            className="inline-block rounded-full"
            style={{
              background: errored ? 'var(--err)' : 'var(--ok)',
              width: 5,
              height: 5,
            }}
          />
          <span className="mono" style={{ color: 'var(--fg-0)' }}>
            {entries.length} tool{entries.length === 1 ? '' : 's'}
          </span>
          {totalMs > 0 && (
            <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
              · {formatDuration(totalMs)}
            </span>
          )}
          <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
            · show
          </span>
        </button>
      </div>
    )
  }

  return (
    <div className="mt-2">
      {entries.map((entry) => (
        <ToolChip key={entry.id} entry={entry} />
      ))}
      {isComplete && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="ml-1 text-[11px] underline-offset-2 hover:underline"
          style={{ color: 'var(--fg-3)' }}
        >
          hide
        </button>
      )}
    </div>
  )
}
