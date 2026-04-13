import { memo, useCallback, useState } from 'react'
import {
  AlertCircle,
  Bot,
  Check,
  ChevronDown,
  Copy,
  User,
  Wrench,
} from 'lucide-react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { Message } from '@/lib/store'
import type { ContentBlock, ToolUseContent } from '@/lib/types'
import { cn, extractTextContent, formatDate } from '@/lib/utils'
import { MarkdownContent } from './MarkdownContent'

interface MessageBubbleProps {
  message: Message
  conversationId?: string
}

function StreamingCursor() {
  return (
    <span
      aria-hidden="true"
      className="inline-block w-1.5 h-4 bg-current ml-0.5 align-middle animate-[streaming-cursor_1s_infinite]"
    />
  )
}

/**
 * Placeholder renderer for tool_use blocks. Our backend doesn't emit these yet,
 * so this is forward-compat only — keeps the component safe if a ContentBlock
 * of type `tool_use` ever arrives without crashing the render path.
 */
function ToolUsePlaceholder({ block }: { block: ToolUseContent }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-surface-700/60 bg-surface-850 px-3 py-2 text-xs text-surface-400">
      <Wrench className="w-3.5 h-3.5 text-brand-400" aria-hidden />
      <span className="font-mono">[tool call: {block.name}]</span>
    </div>
  )
}

function AssistantContent({
  blocks,
  isStreaming,
  isError,
}: {
  blocks: ContentBlock[]
  isStreaming: boolean
  isError: boolean
}) {
  const hasTools = blocks.some((b) => b.type === 'tool_use')

  if (!hasTools) {
    const text = blocks
      .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
      .map((b) => b.text)
      .join('')
    return (
      <div
        className={cn(
          'rounded-2xl px-4 py-3 text-sm rounded-tl-sm',
          isError
            ? 'bg-red-950 border border-red-800 text-red-200'
            : 'bg-surface-800 text-surface-100',
        )}
      >
        {text ? (
          <MarkdownContent content={text} />
        ) : isStreaming ? null : (
          <span className="text-surface-400 italic">(empty response)</span>
        )}
        {isStreaming && <StreamingCursor />}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      {blocks.map((block, i) => {
        if (block.type === 'text') {
          if (!block.text.trim()) return null
          return (
            <div
              key={i}
              className="rounded-2xl px-4 py-3 text-sm bg-surface-800 text-surface-100 rounded-tl-sm"
            >
              <MarkdownContent content={block.text} />
              {isStreaming && i === blocks.length - 1 && <StreamingCursor />}
            </div>
          )
        }

        if (block.type === 'tool_use') {
          return <ToolUsePlaceholder key={block.id || i} block={block} />
        }

        // tool_result blocks: no standalone rendering for P2 (would pair with tool_use).
        return null
      })}

      {isStreaming && blocks[blocks.length - 1]?.type === 'tool_use' && (
        <div className="px-2 py-1 text-xs text-surface-500 animate-pulse">Working…</div>
      )}
    </div>
  )
}

export const MessageBubble = memo(function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.status === 'error'
  // Our backend doesn't stream yet; status === 'sending' (pending) drives the cursor as forward-compat.
  const isStreaming = message.status === 'streaming' || message.status === 'sending'

  const [copied, setCopied] = useState(false)

  // Normalise content to a blocks array so the assistant path always handles both shapes.
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
      className={cn('group flex gap-3 animate-fade-in', isUser && 'flex-row-reverse')}
      aria-label={isUser ? 'You' : isError ? 'Error from assistant' : 'Assistant'}
    >
      {/* Avatar — purely decorative, role conveyed by article label */}
      <div
        aria-hidden="true"
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
          isUser
            ? 'bg-brand-600 text-white'
            : isError
              ? 'bg-red-900 text-red-300'
              : 'bg-surface-700 text-surface-300',
        )}
      >
        {isUser ? (
          <User className="w-4 h-4" aria-hidden="true" />
        ) : isError ? (
          <AlertCircle className="w-4 h-4" aria-hidden="true" />
        ) : (
          <Bot className="w-4 h-4" aria-hidden="true" />
        )}
      </div>

      {/* Content + hover actions */}
      <div className={cn('flex-1 min-w-0 max-w-2xl', isUser && 'flex flex-col items-end')}>
        <div className="relative">
          {isUser ? (
            <div className="rounded-2xl px-4 py-3 text-sm bg-brand-600 text-white rounded-tr-sm">
              <p className="whitespace-pre-wrap break-words">{textOnly}</p>
            </div>
          ) : (
            <AssistantContent blocks={blocks} isStreaming={isStreaming} isError={isError} />
          )}
        </div>

        {/* Hover action row */}
        <div
          className={cn(
            'flex items-center gap-1 mt-1 px-1',
            'opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity',
            isUser ? 'flex-row-reverse' : 'flex-row',
          )}
        >
          <span className="text-xs text-surface-600 select-none">
            {formatDate(message.timestamp)}
          </span>

          <button
            onClick={handleCopy}
            aria-label={copied ? 'Copied' : 'Copy message'}
            className="p-1 rounded text-surface-500 hover:text-surface-300 hover:bg-surface-700 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>

          {/* Assistant-only: single-action dropdown (copy). Retry/edit are deferred
              until the chat API supports them. */}
          {!isUser && (
            <DropdownMenuPrimitive.Root>
              <DropdownMenuPrimitive.Trigger asChild>
                <button
                  aria-label="More message actions"
                  className="p-1 rounded text-surface-500 hover:text-surface-300 hover:bg-surface-700 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500"
                >
                  <ChevronDown className="w-3.5 h-3.5" aria-hidden />
                </button>
              </DropdownMenuPrimitive.Trigger>
              <DropdownMenuPrimitive.Portal>
                <DropdownMenuPrimitive.Content
                  align="start"
                  sideOffset={4}
                  className="z-50 min-w-32 bg-surface-800 border border-surface-700 rounded-lg shadow-xl p-1 text-sm animate-fade-in"
                >
                  <DropdownMenuPrimitive.Item
                    onSelect={handleCopy}
                    className="flex items-center gap-2 px-3 py-1.5 rounded text-surface-300 hover:bg-surface-700 hover:text-surface-100 cursor-pointer focus:outline-none focus:bg-surface-700"
                  >
                    <Copy className="w-3.5 h-3.5" aria-hidden /> Copy
                  </DropdownMenuPrimitive.Item>
                </DropdownMenuPrimitive.Content>
              </DropdownMenuPrimitive.Portal>
            </DropdownMenuPrimitive.Root>
          )}
        </div>
      </div>
    </article>
  )
})
