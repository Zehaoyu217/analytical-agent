import { memo, useCallback, useState } from 'react'
import { Check, Copy, RotateCcw, Wrench } from 'lucide-react'
import type { Message, Artifact } from '@/lib/store'
import { useChatStore } from '@/lib/store'
import type { ContentBlock, ToolUseContent } from '@/lib/types'
import { cn, extractTextContent, formatDate } from '@/lib/utils'
import { MarkdownContent } from './MarkdownContent'
import { SubagentCard } from './SubagentCard'
import { VegaChart } from './VegaChart'
import { MermaidDiagram } from './MermaidDiagram'
import { DataTable } from '@/components/right-panel/DataTable'

interface MessageBubbleProps {
  message: Message
  onRegenerate?: () => void
}

function StreamingCursor() {
  return (
    <span
      aria-hidden="true"
      className="inline-block w-[2px] h-[14px] bg-brand-400 ml-0.5 align-middle animate-[streaming-cursor_1s_infinite]"
    />
  )
}

/**
 * Placeholder renderer for tool_use blocks. Forward-compat only.
 */
function ToolUsePlaceholder({ block }: { block: ToolUseContent }) {
  return (
    <div className="flex items-center gap-2 border-l-2 border-surface-700 pl-3 py-1 text-xs text-surface-500">
      <Wrench className="w-3 h-3 text-brand-accent/60 flex-shrink-0" aria-hidden />
      <span className="font-mono text-surface-600">{block.name}</span>
    </div>
  )
}

/**
 * Render a single artifact inline.
 */
function InlineArtifact({ artifact }: { artifact: Artifact }) {
  if (artifact.format === 'vega-lite') {
    return <VegaChart spec={artifact.content} />
  }
  if (artifact.format === 'mermaid') {
    return <MermaidDiagram code={artifact.content} />
  }
  if (artifact.format === 'table-json') {
    return <DataTable content={artifact.content} />
  }
  return (
    <div
      className="text-xs text-surface-400 overflow-auto max-h-64"
      dangerouslySetInnerHTML={{ __html: artifact.content }}
    />
  )
}

function AssistantContent({
  blocks,
  isStreaming,
  isError,
  inlineArtifacts,
}: {
  blocks: ContentBlock[]
  isStreaming: boolean
  isError: boolean
  inlineArtifacts: Artifact[]
}) {
  const hasTools = blocks.some((b) => b.type === 'tool_use')

  if (!hasTools) {
    const text = blocks
      .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
      .map((b) => b.text)
      .join('')
    return (
      <div className="flex flex-col gap-3 w-full">
        <div className={cn(isError ? 'text-red-300' : 'text-surface-100')}>
          {text ? (
            <MarkdownContent content={text} />
          ) : isStreaming ? null : (
            <span className="text-surface-700 italic text-xs font-mono">empty response</span>
          )}
          {isStreaming && <StreamingCursor />}
        </div>
        {inlineArtifacts.map((artifact) => (
          <InlineArtifact key={artifact.id} artifact={artifact} />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 w-full">
      {blocks.map((block, i) => {
        if (block.type === 'text') {
          if (!block.text.trim()) return null
          return (
            <div key={i} className="text-surface-100">
              <MarkdownContent content={block.text} />
              {isStreaming && i === blocks.length - 1 && <StreamingCursor />}
            </div>
          )
        }

        if (block.type === 'tool_use') {
          return <ToolUsePlaceholder key={block.id || i} block={block} />
        }

        if (block.type === 'chart') {
          return <VegaChart key={i} spec={block.spec} />
        }

        if (block.type === 'a2a') {
          return <SubagentCard key={i} entry={block} />
        }

        return null
      })}

      {isStreaming && blocks[blocks.length - 1]?.type === 'tool_use' && (
        <div className="flex items-center gap-1.5 py-1">
          <span className="w-1 h-1 rounded-full bg-brand-accent animate-pulse" />
          <span className="text-[10px] font-mono text-surface-600 tracking-wider">working</span>
        </div>
      )}

      {inlineArtifacts.map((artifact) => (
        <InlineArtifact key={artifact.id} artifact={artifact} />
      ))}
    </div>
  )
}

export const MessageBubble = memo(function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.status === 'error'
  const isStreaming = message.status === 'streaming' || message.status === 'sending'

  const [copied, setCopied] = useState(false)

  const allArtifacts = useChatStore((s) => s.artifacts)
  const inlineArtifacts: Artifact[] = (message.artifactIds ?? [])
    .map((id) => allArtifacts.find((a) => a.id === id))
    .filter((a): a is Artifact => a !== undefined)

  const blocks: ContentBlock[] = Array.isArray(message.content)
    ? (message.content as ContentBlock[])
    : [{ type: 'text', text: message.content }]

  const textOnly = extractTextContent(message.content)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(textOnly)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable
    }
  }, [textOnly])

  return (
    <article
      className={cn(
        'group animate-fade-in pl-3 pr-2 pt-2 pb-2 rounded-r-sm',
        isUser
          ? 'border-l-2 border-green-500/50 bg-green-950/[0.04]'
          : isError
            ? 'border-l-2 border-error/50'
            : 'border-l-2 border-brand-400/70',
      )}
      aria-label={isUser ? 'User' : isError ? 'Error from agent' : 'Agent'}
    >
      {/* Role + timestamp */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={cn(
            'text-[10px] font-mono font-semibold tracking-[0.18em] uppercase',
            isUser ? 'text-green-400/80' : isError ? 'text-red-400' : 'text-brand-400',
          )}
        >
          {isUser ? 'USR' : isError ? 'ERR' : 'AGENT'}
        </span>
        <span className="w-px h-2.5 bg-surface-700 flex-shrink-0" aria-hidden />
        <span className="text-[9px] font-mono text-surface-700 select-none tabular-nums">
          {formatDate(message.timestamp)}
        </span>
        {isStreaming && (
          <span className="flex items-center gap-1">
            <span className="w-1 h-1 rounded-full bg-brand-accent animate-pulse" aria-hidden />
            <span className="text-[9px] font-mono text-brand-accent/70 tracking-wider">streaming</span>
          </span>
        )}
      </div>

      {/* Content */}
      <div className={cn('text-[13px] leading-[1.75]', isUser ? 'text-surface-200' : '')}>
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{textOnly}</p>
        ) : (
          <AssistantContent
            blocks={blocks}
            isStreaming={isStreaming}
            isError={isError}
            inlineArtifacts={inlineArtifacts}
          />
        )}
      </div>

      {/* Hover action row */}
      <div className="flex items-center gap-1 mt-2.5 opacity-40 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
        <button
          onClick={handleCopy}
          aria-label={copied ? 'Copied' : 'Copy message'}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded text-surface-600 hover:text-surface-300 hover:bg-surface-800 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent/60"
        >
          {copied ? (
            <Check className="w-3 h-3 text-green-400" aria-hidden />
          ) : (
            <Copy className="w-3 h-3" aria-hidden />
          )}
          <span className="text-[9px] font-mono tracking-wider">
            {copied ? 'copied' : 'copy'}
          </span>
        </button>
        {!isUser && onRegenerate && (
          <button
            onClick={onRegenerate}
            aria-label="Regenerate response"
            className="flex items-center gap-1.5 px-2 py-0.5 rounded text-surface-600 hover:text-surface-300 hover:bg-surface-800 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent/60"
          >
            <RotateCcw className="w-3 h-3" aria-hidden />
            <span className="text-[9px] font-mono tracking-wider">retry</span>
          </button>
        )}
      </div>
    </article>
  )
})
