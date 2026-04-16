import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { nanoid } from 'nanoid'
import { Send, Square } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { useDevtoolsStore } from '@/stores/devtools'
import { streamChatMessage } from '@/lib/api-chat'
import { backend, type SlashCommand } from '@/lib/api-backend'
import { cn } from '@/lib/utils'
import { MAX_MESSAGE_LENGTH } from '@/lib/constants'
import type { A2aContent, ContentBlock } from '@/lib/types'
import type { Artifact } from '@/lib/store'

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
  const abortControllerRef = useRef<AbortController | null>(null)

  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessage = useChatStore((s) => s.updateMessage)
  const setConversationSessionId = useChatStore((s) => s.setConversationSessionId)
  const pushToolCall = useChatStore((s) => s.pushToolCall)
  const updateToolCallById = useChatStore((s) => s.updateToolCallById)
  const clearToolCallLog = useChatStore((s) => s.clearToolCallLog)
  const setScratchpad = useChatStore((s) => s.setScratchpad)
  const clearScratchpad = useChatStore((s) => s.clearScratchpad)
  const setTodos = useChatStore((s) => s.setTodos)
  const clearTodos = useChatStore((s) => s.clearTodos)
  const setRightPanelTab = useChatStore((s) => s.setRightPanelTab)
  const addArtifact = useChatStore((s) => s.addArtifact)
  const clearArtifacts = useChatStore((s) => s.clearArtifacts)
  const draftInput = useChatStore((s) => s.draftInput)
  const setDraftInput = useChatStore((s) => s.setDraftInput)
  const planMode = useChatStore((s) => s.planMode)
  const togglePlanMode = useChatStore((s) => s.togglePlanMode)

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  // Sync draftInput from store → local state (used by suggested prompts and regenerate).
  useEffect(() => {
    if (!draftInput) return
    setInput(draftInput)
    setDraftInput('')
    requestAnimationFrame(() => {
      adjustHeight()
      textareaRef.current?.focus()
    })
  }, [draftInput, setDraftInput, adjustHeight])

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

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text || isSending) return

    setInput('')
    setError(null)
    setIsSending(true)
    const controller = new AbortController()
    abortControllerRef.current = controller

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

    // Clear tool call log, scratchpad, todos, and artifacts from any previous turn
    clearToolCallLog()
    clearScratchpad()
    clearTodos()
    clearArtifacts()

    // Map from tool call entry ID → store entry ID so we can update on result
    const pendingToolCallIds = new Map<string, string>()
    // A2A blocks accumulate in-message as sub-agent events arrive
    const a2aBlocksByStep = new Map<number, A2aContent>()
    let finalSessionId = conversation?.sessionId ?? null
    let finalResponseText = ''

    try {
      const stream = streamChatMessage(text, conversation?.sessionId ?? null, {
        planMode,
        signal: controller.signal,
      })
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
            startedAt: Date.now(),
          })
          pendingToolCallIds.set(entryKey, storeId)
        } else if (event.type === 'tool_result') {
          const entryKey = `${event.step}-${event.name}`
          const storeId = pendingToolCallIds.get(entryKey)
          if (storeId) {
            updateToolCallById(storeId, {
              status: event.status ?? 'ok',
              preview: event.preview,
              stdout: event.stdout ?? event.preview ?? '',
              artifactIds: event.artifact_ids,
              finishedAt: Date.now(),
            })
          }
        } else if (event.type === 'a2a_start') {
          const a2aBlock: A2aContent = {
            type: 'a2a',
            task: event.task_preview ?? '',
            artifactId: '',
            summary: '',
            status: 'pending',
          }
          a2aBlocksByStep.set(event.step ?? 0, a2aBlock)
          // Show the pending sub-agent card inline in the message
          updateMessage(conversationId, assistantId, {
            content: [...a2aBlocksByStep.values()] as ContentBlock[],
          })
        } else if (event.type === 'a2a_end') {
          const step = event.step ?? 0
          const existing = a2aBlocksByStep.get(step)
          if (existing) {
            a2aBlocksByStep.set(step, {
              ...existing,
              artifactId: event.artifact_id ?? '',
              summary: event.summary ?? '',
              status: event.ok !== false ? 'complete' : 'error',
            })
            updateMessage(conversationId, assistantId, {
              content: [...a2aBlocksByStep.values()] as ContentBlock[],
            })
          }
        } else if (event.type === 'artifact') {
          const artifact: Artifact = {
            id: event.id ?? nanoid(),
            type: (event.artifact_type as Artifact['type']) ?? 'chart',
            title: event.title ?? 'Artifact',
            content: event.artifact_content ?? '',
            format: (event.format as Artifact['format']) ?? 'vega-lite',
            session_id: event.session_id ?? '',
            created_at: event.created_at ?? Date.now() / 1000,
            metadata: event.artifact_metadata ?? {},
          }
          addArtifact(artifact)
          // Also add artifact ID to the current assistant message
          const currentConv = useChatStore.getState().conversations.find(
            (c) => c.id === conversationId,
          )
          const currentMsg = currentConv?.messages.find((m) => m.id === assistantId)
          updateMessage(conversationId, assistantId, {
            artifactIds: [...(currentMsg?.artifactIds ?? []), artifact.id],
          })
          // Open the artifacts tab
          setRightPanelTab('artifacts')
        } else if (event.type === 'scratchpad_delta') {
          setScratchpad(event.content ?? '')
        } else if (event.type === 'todos_update') {
          setTodos(event.todos ?? [])
        } else if (event.type === 'micro_compact') {
          const saved = (event.tokens_before ?? 0) - (event.tokens_after ?? 0)
          const now = Date.now()
          pushToolCall({
            step: event.step ?? 0,
            name: '__compact__',
            inputPreview: '',
            status: 'ok',
            preview: `compacted ${event.dropped_messages ?? 0} msgs · ~${saved.toLocaleString()} tokens freed`,
            startedAt: now,
            finishedAt: now,
          })
        } else if (event.type === 'turn_end') {
          const responseText = event.final_text ?? ''
          finalResponseText = responseText
          const charts = event.charts ?? []
          const a2aBlocks = [...a2aBlocksByStep.values()] as ContentBlock[]
          const textBlock = responseText
            ? [{ type: 'text' as const, text: responseText }]
            : []

          // Backward compat: create artifact store entries for charts that arrived
          // via turn_end (when backend doesn't emit separate artifact events).
          const currentConvState = useChatStore.getState().conversations.find(
            (c) => c.id === conversationId,
          )
          const currentMsgState = currentConvState?.messages.find((m) => m.id === assistantId)
          const alreadyHasArtifacts = (currentMsgState?.artifactIds ?? []).length > 0
          if (!alreadyHasArtifacts && charts.length > 0) {
            const newArtifactIds: string[] = []
            for (const spec of charts) {
              const artifactId = nanoid()
              addArtifact({
                id: artifactId,
                type: 'chart',
                title: typeof spec.title === 'string' ? spec.title : 'Chart',
                content: JSON.stringify(spec),
                format: 'vega-lite',
                session_id: finalSessionId ?? '',
                created_at: Date.now() / 1000,
                metadata: {},
              })
              newArtifactIds.push(artifactId)
            }
            updateMessage(conversationId, assistantId, { artifactIds: newArtifactIds })
            if (charts.length > 0) setRightPanelTab('artifacts')
          }

          const content: ContentBlock[] | string =
            a2aBlocks.length > 0
              ? [...a2aBlocks, ...textBlock]
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
      if (err instanceof Error && err.name === 'AbortError') {
        // User stopped generation — mark message complete with whatever arrived
        updateMessage(conversationId, assistantId, {
          content: finalResponseText || '',
          status: 'complete',
        })
        if (finalSessionId) setConversationSessionId(conversationId, finalSessionId)
        return
      }
      const message = err instanceof Error ? err.message : 'Request failed'
      updateMessage(conversationId, assistantId, {
        content: message,
        status: 'error',
      })
      setError(message)
    } finally {
      abortControllerRef.current = null
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
    setScratchpad,
    clearScratchpad,
    setTodos,
    clearTodos,
    setRightPanelTab,
    addArtifact,
    clearArtifacts,
    adjustHeight,
    planMode,
  ])

  // Listen for programmatic submit events (e.g. regenerate from MessageBubble).
  useEffect(() => {
    const handler = () => { handleSubmit() }
    window.addEventListener('chat:submit', handler)
    return () => window.removeEventListener('chat:submit', handler)
  }, [handleSubmit])

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
    <div className="bg-canvas px-2 pb-3 pt-1">
      <div className="relative">
        {/* Error banner floats above the card */}
        {error && (
          <div
            role="alert"
            className="mb-2 flex items-center gap-2 text-[11px] font-mono text-error"
          >
            <span className="select-none" aria-hidden>!</span>
            {error}
          </div>
        )}

        {/* Slash command menu anchors to the bottom of this relative container */}
        {showSlashMenu && filteredCommands.length > 0 && (
          <ul
            role="listbox"
            aria-label="Slash commands"
            className={cn(
              'absolute bottom-full left-0 right-0 mb-1 z-30',
              'border border-surface-700/60 bg-surface-900 shadow-2xl',
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
                    e.preventDefault()
                    pickSlashCommand(cmd)
                  }}
                  className={cn(
                    'flex items-baseline gap-3 px-4 py-2 cursor-pointer',
                    isActive
                      ? 'bg-surface-800 text-surface-100'
                      : 'text-surface-400 hover:bg-surface-800/60',
                  )}
                >
                  <span className="font-mono text-[11px] text-brand-400 flex-shrink-0">
                    {cmd.label}
                  </span>
                  <span className="text-[11px] font-mono text-surface-600 truncate">
                    {cmd.description}
                  </span>
                </li>
              )
            })}
          </ul>
        )}

        {/* Floating input card */}
        <div className="bg-surface-900/80 border border-surface-700/60 px-4 pt-3 pb-2">
          <div className="flex items-end gap-3">
            {/* Terminal prompt glyph */}
            <span
              className="font-mono text-surface-500 text-sm select-none flex-shrink-0 pb-[3px]"
              aria-hidden
            >
              ›
            </span>

            <label htmlFor="chat-input" className="sr-only">
              Message
            </label>
            <textarea
              id="chat-input"
              ref={textareaRef}
              value={input}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="Enter a prompt…"
              rows={1}
              disabled={isSending}
              aria-label="Message"
              className={cn(
                'flex-1 resize-none bg-transparent',
                'text-[13px] font-mono text-surface-100',
                'placeholder:text-surface-600',
                'focus:outline-none',
                'min-h-[24px] max-h-[200px] leading-[1.75]',
                'disabled:opacity-50',
              )}
            />

            {isSending ? (
              <button
                onClick={handleStop}
                aria-label="Stop generation"
                type="button"
                className="p-2.5 transition-colors flex-shrink-0 mb-0.5 text-surface-500 hover:text-error"
              >
                <Square className="w-4 h-4" aria-hidden="true" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                aria-label="Send message"
                type="button"
                className={cn(
                  'p-1 transition-colors flex-shrink-0 mb-0.5',
                  canSubmit
                    ? 'text-brand-accent hover:text-brand-400'
                    : 'text-surface-700 cursor-not-allowed',
                )}
              >
                <Send className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            )}
          </div>

          <div className="mt-2 flex items-center justify-between gap-4">
            <p className="text-[9px] font-mono tracking-[0.18em] text-surface-600 uppercase">
              {!input.trim() && !isSending
                ? 'type / for commands'
                : 'Enter · Send \u00A0/\u00A0 Shift+Enter · New line'}
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={togglePlanMode}
                disabled={isSending}
                role="switch"
                aria-checked={planMode}
                aria-label="Plan mode — propose a plan instead of executing tools"
                title={
                  planMode
                    ? 'Plan Mode ON — agent will propose a plan and wait for approval'
                    : 'Plan Mode OFF — agent will execute tools as needed'
                }
                className={cn(
                  'group flex items-center gap-1.5 select-none',
                  'font-mono text-[9px] tracking-[0.25em] uppercase',
                  'border px-2 py-1 transition-colors',
                  'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent/60',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  planMode
                    ? 'border-brand-accent/70 text-brand-accent bg-brand-accent/10 hover:bg-brand-accent/15'
                    : 'border-surface-700/60 text-surface-600 hover:text-surface-400 hover:border-surface-600',
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    'inline-block w-1.5 h-1.5 rounded-full transition-colors',
                    planMode ? 'bg-brand-accent' : 'bg-surface-700 group-hover:bg-surface-600',
                  )}
                />
                plan
              </button>
              {!isSending && (
                <p className="text-[9px] font-mono text-surface-600 tabular-nums">
                  ⌘K \u00A0·\u00A0 ⌘/
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
