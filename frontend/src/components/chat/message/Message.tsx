import { useMemo } from 'react'
import type { Message as MessageRecord } from '@/lib/store'
import type { ContentBlock } from '@/lib/types'
import { MarkdownContent } from '../MarkdownContent'
import { SubagentCard } from '../SubagentCard'
import { Avatar } from './Avatar'
import { MessageHeader } from './MessageHeader'
import { Callout } from './Callout'
import { ToolChipRow } from './ToolChipRow'
import { ArtifactPillRow } from './ArtifactPillRow'
import { AttachedFileChip } from './AttachedFileChip'

interface MessageProps {
  message: MessageRecord
  attachedNames?: string[]
}

function formatTimestamp(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function isBlocks(c: MessageRecord['content']): c is ContentBlock[] {
  return Array.isArray(c)
}

type TextBlock = Extract<ContentBlock, { type: 'text' }>
type CalloutBlock = Extract<ContentBlock, { type: 'callout' }>
type A2aBlock = Extract<ContentBlock, { type: 'a2a' }>

export function Message({ message, attachedNames = [] }: MessageProps) {
  const isUser = message.role === 'user'
  const blocks = useMemo<ContentBlock[]>(() => {
    if (isBlocks(message.content)) return message.content
    return message.content ? [{ type: 'text', text: message.content }] : []
  }, [message.content])

  const textBlocks = blocks.filter((b): b is TextBlock => b.type === 'text')
  const callouts = blocks.filter((b): b is CalloutBlock => b.type === 'callout')
  const a2as = blocks.filter((b): b is A2aBlock => b.type === 'a2a')

  const onCopy = () => {
    const text = textBlocks.map((b) => b.text).join('\n\n')
    if (text) void navigator.clipboard?.writeText(text)
  }

  return (
    <div
      className="flex gap-3.5 border-b py-[18px]"
      style={{ borderColor: 'var(--line-2)' }}
    >
      <Avatar role={message.role} initial={isUser ? 'M' : 'D'} />
      <div className="min-w-0 flex-1">
        <MessageHeader
          name={isUser ? 'Master' : 'DS Agent'}
          timestamp={formatTimestamp(message.timestamp)}
          onCopy={onCopy}
        />
        {textBlocks.length > 0 && (
          <div className="text-[14px] leading-[1.6]" style={{ color: 'var(--fg-0)' }}>
            {textBlocks.map((b, i) => (
              <MarkdownContent key={i} content={b.text} />
            ))}
          </div>
        )}
        {callouts.map((c, i) => (
          <Callout key={i} kind={c.kind} label={c.label} text={c.text} />
        ))}
        {!isUser && <ToolChipRow messageId={message.id} status={message.status} />}
        {(message.artifactIds?.length ?? 0) > 0 && (
          <ArtifactPillRow artifactIds={message.artifactIds ?? []} />
        )}
        {a2as.map((a, i) => (
          <SubagentCard key={i} entry={a} />
        ))}
        {attachedNames.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {attachedNames.map((name) => (
              <AttachedFileChip key={name} name={name} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
