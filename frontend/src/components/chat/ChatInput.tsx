import { useCallback, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { useDevtoolsStore } from '@/stores/devtools'
import { sendChatMessage } from '@/lib/api-chat'
import { cn } from '@/lib/utils'
import { MAX_MESSAGE_LENGTH } from '@/lib/constants'

interface ChatInputProps {
  conversationId: string
}

export function ChatInput({ conversationId }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === conversationId),
  )
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessage = useChatStore((s) => s.updateMessage)
  const setConversationSessionId = useChatStore((s) => s.setConversationSessionId)

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value.slice(0, MAX_MESSAGE_LENGTH)
    setInput(value)
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

    // Placeholder assistant message so the user sees something while waiting
    const assistantId = addMessage(conversationId, {
      role: 'assistant',
      content: '',
      status: 'sending',
    })

    try {
      const result = await sendChatMessage(text, conversation?.sessionId ?? null)
      updateMessage(conversationId, assistantId, {
        content: result.response,
        status: 'complete',
        traceId: result.session_id,
      })
      setConversationSessionId(conversationId, result.session_id)
      // Pre-select the trace in DevTools so it's ready if the user opens the
      // DevTools sidebar. Does NOT auto-open the sidebar.
      const devtools = useDevtoolsStore.getState()
      devtools.setSelectedTrace(result.session_id)
      devtools.setActiveTab('traces')
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
    adjustHeight,
  ])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSubmit = !!input.trim() && !isSending

  return (
    <div className="border-t border-surface-800 bg-surface-900/50 backdrop-blur-sm px-4 py-3">
      <div className="max-w-3xl mx-auto">
        {error && (
          <div
            role="alert"
            className="mb-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
          >
            {error}
          </div>
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
