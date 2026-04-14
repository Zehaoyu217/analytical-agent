import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { useDevtoolsStore } from '@/stores/devtools'
import { streamChatMessage } from '@/lib/api-chat'
import { backend, type SlashCommand } from '@/lib/api-backend'
import { cn } from '@/lib/utils'
import { MAX_MESSAGE_LENGTH } from '@/lib/constants'

interface ChatInputProps {
  conversationId: string
}

export function ChatInput({ conversationId }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [slashCommands, setSlashCommands] = useState<SlashCommand[] | null>(null)
  const [slashHighlight, setSlashHighlight] = useState(0)
  const [slashLocked, setSlashLocked] = useState(false)
  const slashFetchRef = useRef<Promise<SlashCommand[]> | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessage = useChatStore((s) => s.updateMessage)
  const setConversationSessionId = useChatStore((s) => s.setConversationSessionId)
  const pushToolCall = useChatStore((s) => s.pushToolCall)
  const updateToolCallById = useChatStore((s) => s.updateToolCallById)
  const clearToolCallLog = useChatStore((s) => s.clearToolCallLog)
  const setRightPanelTab = useChatStore((s) => s.setRightPanelTab)

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  // Slash menu visibility — only when value starts with "/" AND the user
  // hasn't just picked a command (slashLocked). Locking closes the menu after
  // a pick so the next Enter submits the message instead of re-firing the
  // command. Lock clears the moment the user edits the input again.
  const showSlashMenu = input.startsWith('/') && !slashLocked
  const slashQuery = showSlashMenu ? input.slice(1).toLowerCase() : ''

  const filteredCommands = useMemo(() => {
    if (!showSlashMenu || !slashCommands) return []
    if (!slashQuery) return slashCommands
    return slashCommands.filter(
      (c) =>
        c.id.toLowerCase().includes(slashQuery) ||
        c.label.toLowerCase().includes(slashQuery),
    )
  }, [slashCommands, slashQuery, showSlashMenu])

  // Reset highlight whenever the filtered list shrinks.
  useEffect(() => {
    if (slashHighlight >= filteredCommands.length) {
      setSlashHighlight(0)
    }
  }, [filteredCommands.length, slashHighlight])

  // Lazy-fetch the slash command list on the first time the user types "/".
  useEffect(() => {
    if (!showSlashMenu) return
    if (slashCommands !== null) return
    if (slashFetchRef.current) return
    slashFetchRef.current = backend.slash
      .list()
      .then((list) => {
        setSlashCommands(list)
        return list
      })
      .catch((err: unknown) => {
        // Keep the chat usable even if slash endpoint is unreachable.
        if (typeof window !== 'undefined') {
          window.console?.warn?.('slash list failed', err)
        }
        setSlashCommands([])
        return []
      })
  }, [showSlashMenu, slashCommands])

  const pickSlashCommand = useCallback(
    (cmd: SlashCommand) => {
      setInput(cmd.label)
      setSlashLocked(true)
      // Fire-and-forget; we don't want execute failures to block the UX.
      backend.slash
        .execute(cmd.id, {}, conversationId)
        .catch((err: unknown) => {
          if (typeof window !== 'undefined') {
            window.console?.warn?.('slash execute failed', err)
          }
        })
      requestAnimationFrame(() => {
        textareaRef.current?.focus()
        adjustHeight()
      })
    },
    [conversationId, adjustHeight],
  )

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value.slice(0, MAX_MESSAGE_LENGTH)
    setInput(value)
    setSlashLocked(false)
    adjustHeight()
  }

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text || isSending) return

    setInput('')
    setError(null)
    setIsSending(true)

    // Reset textarea height after clearing
    requestAnimationFrame(() => adjustHeight())

    // Optimistic user message
    addMessage(conversationId, {
      role: 'user',
      content: text,
      status: 'complete',
    })

    // Persist the user turn to the backend — fire-and-forget so the streaming
    // path is never blocked. The active conversation id may or may not be a
    // valid backend id; the backend validates ^[A-Za-z0-9_-]{1,64}$ which
    // nanoid() satisfies.
    backend.conversations
      .appendTurn(conversationId, 'user', text)
      .catch((err: unknown) => {
        if (typeof window !== 'undefined') {
          window.console?.warn?.('persist user turn failed', err)
        }
      })

    // Placeholder assistant message so the user sees something while waiting
    const assistantId = addMessage(conversationId, {
      role: 'assistant',
      content: '',
      status: 'sending',
    })

    // Clear tool call log from any previous turn
    clearToolCallLog()

    // Map from tool call entry ID → store entry ID so we can update on result
    const pendingToolCallIds = new Map<string, string>()
    let finalSessionId = conversation?.sessionId ?? null
    let finalResponseText = ''

    try {
      const stream = streamChatMessage(text, conversation?.sessionId ?? null)
      for await (const event of stream) {
        if (event.type === 'turn_start') {
          if (event.session_id) finalSessionId = event.session_id
          updateMessage(conversationId, assistantId, { status: 'streaming' })
        } else if (event.type === 'tool_call') {
          // Open the Tools tab in the right panel on first tool call
          setRightPanelTab('tools')
          const entryKey = `${event.step}-${event.name}`
          const storeId = pushToolCall({
            step: event.step ?? 0,
            name: event.name ?? '',
            inputPreview: event.input_preview ?? '',
            status: 'pending',
          })
          pendingToolCallIds.set(entryKey, storeId)
        } else if (event.type === 'tool_result') {
          const entryKey = `${event.step}-${event.name}`
          const storeId = pendingToolCallIds.get(entryKey)
          if (storeId) {
            updateToolCallById(storeId, {
              status: event.status ?? 'ok',
              preview: event.preview,
              artifactIds: event.artifact_ids,
            })
          }
        } else if (event.type === 'turn_end') {
          const responseText = event.final_text ?? ''
          finalResponseText = responseText
          const charts = event.charts ?? []
          const content =
            charts.length > 0
              ? [
                  { type: 'text' as const, text: responseText },
                  ...charts.map((spec) => ({ type: 'chart' as const, spec })),
                ]
              : responseText
          updateMessage(conversationId, assistantId, {
            content,
            status: 'complete',
            traceId: finalSessionId ?? undefined,
          })
          if (finalSessionId) setConversationSessionId(conversationId, finalSessionId)
        } else if (event.type === 'error') {
          const msg = event.message ?? 'Agent error'
          updateMessage(conversationId, assistantId, {
            content: msg,
            status: 'error',
          })
          setError(msg)
          return
        }
      }

      if (finalSessionId) {
        setConversationSessionId(conversationId, finalSessionId)
        const devtools = useDevtoolsStore.getState()
        devtools.setSelectedTrace(finalSessionId)
        devtools.setActiveTab('traces')
      }

      // Persist the assistant response (fire-and-forget).
      if (finalResponseText) {
        backend.conversations
          .appendTurn(conversationId, 'assistant', finalResponseText)
          .catch((err: unknown) => {
            if (typeof window !== 'undefined') {
              window.console?.warn?.('persist assistant turn failed', err)
            }
          })
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed'
      updateMessage(conversationId, assistantId, {
        content: message,
        status: 'error',
      })
      setError(message)
    } finally {
      setIsSending(false)
    }
  }, [
    input,
    isSending,
    conversationId,
    conversation?.sessionId,
    addMessage,
    updateMessage,
    setConversationSessionId,
    pushToolCall,
    updateToolCallById,
    clearToolCallLog,
    setRightPanelTab,
    adjustHeight,
  ])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashMenu && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashHighlight((h) => (h + 1) % filteredCommands.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashHighlight(
          (h) => (h - 1 + filteredCommands.length) % filteredCommands.length,
        )
        return
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        const cmd = filteredCommands[slashHighlight] ?? filteredCommands[0]
        if (cmd) pickSlashCommand(cmd)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setInput('')
        setSlashLocked(false)
        requestAnimationFrame(() => adjustHeight())
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSubmit = !!input.trim() && !isSending

  return (
    <div className="border-t border-surface-800 bg-surface-900/50 backdrop-blur-sm px-4 py-3">
      <div className="max-w-3xl mx-auto relative">
        {error && (
          <div
            role="alert"
            className="mb-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
          >
            {error}
          </div>
        )}

        {showSlashMenu && filteredCommands.length > 0 && (
          <ul
            role="listbox"
            aria-label="Slash commands"
            className={cn(
              'absolute bottom-full left-0 right-0 mb-2 z-30',
              'rounded-lg border border-surface-700 bg-surface-900 shadow-lg',
              'max-h-64 overflow-y-auto py-1',
            )}
          >
            {filteredCommands.map((cmd, index) => {
              const isActive = index === slashHighlight
              return (
                <li
                  key={cmd.id}
                  role="option"
                  aria-selected={isActive}
                  onMouseEnter={() => setSlashHighlight(index)}
                  onMouseDown={(e) => {
                    // Use mousedown so the textarea keeps focus.
                    e.preventDefault()
                    pickSlashCommand(cmd)
                  }}
                  className={cn(
                    'flex items-baseline gap-3 px-3 py-2 cursor-pointer text-sm',
                    isActive
                      ? 'bg-surface-800 text-surface-100'
                      : 'text-surface-300 hover:bg-surface-800/70',
                  )}
                >
                  <span className="font-mono text-brand-400 flex-shrink-0">
                    {cmd.label}
                  </span>
                  <span className="text-xs text-surface-500 truncate">
                    {cmd.description}
                  </span>
                </li>
              )
            })}
          </ul>
        )}

        <div
          className={cn(
            'flex items-end gap-2 rounded-xl border bg-surface-800 px-3 py-2',
            'border-surface-700 focus-within:border-brand-500 transition-colors',
          )}
        >
          <label htmlFor="chat-input" className="sr-only">
            Message
          </label>
          <textarea
            id="chat-input"
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Send a message…"
            rows={1}
            disabled={isSending}
            aria-label="Message"
            className={cn(
              'flex-1 resize-none bg-transparent text-sm text-surface-100',
              'placeholder:text-surface-500 focus:outline-none',
              'min-h-[24px] max-h-[200px] py-0.5',
              'disabled:opacity-60',
            )}
          />

          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            aria-label="Send message"
            type="button"
            className={cn(
              'p-1.5 rounded-lg transition-colors flex-shrink-0',
              canSubmit
                ? 'bg-brand-600 text-white hover:bg-brand-700'
                : 'bg-surface-700 text-surface-500 cursor-not-allowed',
            )}
          >
            <Send className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <p className="mt-1.5 px-1 text-xs text-surface-600">
          Press Enter to send, Shift+Enter for a new line.
        </p>
      </div>
    </div>
  )
}
