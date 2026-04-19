import { useMemo } from 'react'
import { useChatStore } from '@/lib/store'
import { ToolChip } from './ToolChip'

interface ToolChipRowProps {
  messageId: string
}

export function ToolChipRow({ messageId }: ToolChipRowProps) {
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const entries = useMemo(
    () => toolCallLog.filter((entry) => entry.messageId === messageId),
    [toolCallLog, messageId],
  )
  if (entries.length === 0) return null
  return (
    <div className="mt-2">
      {entries.map((entry) => (
        <ToolChip key={entry.id} entry={entry} />
      ))}
    </div>
  )
}
