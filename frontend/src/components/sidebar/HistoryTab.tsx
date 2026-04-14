import { useCallback, useEffect, useState } from 'react'
import { useChatStore } from '@/lib/store'
import { backend, type ConversationSummary } from '@/lib/api-backend'
import { cn, formatDate } from '@/lib/utils'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

export function HistoryTab() {
  const [state, setState] = useState<LoadState>('idle')
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const loadConversation = useChatStore((s) => s.loadConversation)
  const activeConversationId = useChatStore((s) => s.activeConversationId)

  const refresh = useCallback(async () => {
    setState('loading')
    setError(null)
    try {
      const list = await backend.conversations.list()
      setConversations(list)
      setState('ready')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load history'
      setError(message)
      setState('error')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleSelect = useCallback(
    async (id: string) => {
      try {
        await loadConversation(id)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load conversation'
        setError(message)
      }
    },
    [loadConversation],
  )

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-800 flex-shrink-0">
        <h2 className="text-xs font-semibold text-surface-300 uppercase tracking-wide">
          History
        </h2>
        <button
          type="button"
          onClick={() => void refresh()}
          className="text-xs text-surface-400 hover:text-surface-200"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mx-3 my-2 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300"
        >
          {error}
        </div>
      )}

      <div
        className="flex-1 min-h-0 overflow-y-auto px-2 pb-2 space-y-0.5"
        role="list"
        aria-label="Past conversations"
      >
        {state === 'loading' && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            Loading conversations…
          </p>
        )}

        {state === 'ready' && conversations.length === 0 && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            No past conversations yet.
          </p>
        )}

        {conversations.map((c) => {
          const isActive = c.id === activeConversationId
          const updated = formatDate(Math.round(c.updated_at * 1000))
          return (
            <button
              key={c.id}
              role="listitem"
              onClick={() => void handleSelect(c.id)}
              className={cn(
                'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                'flex items-start justify-between gap-2',
                isActive
                  ? 'bg-surface-800 text-surface-100'
                  : 'text-surface-400 hover:bg-surface-800/60 hover:text-surface-200',
              )}
              title={c.title}
            >
              <div className="flex-1 min-w-0">
                <div className="truncate">{c.title}</div>
                <div className="text-xs text-surface-500 mt-0.5">{updated}</div>
              </div>
              <span
                className={cn(
                  'text-[10px] font-mono px-1.5 py-0.5 rounded-full flex-shrink-0',
                  'bg-surface-800 text-surface-400',
                )}
                aria-label={`${c.turn_count} turns`}
              >
                {c.turn_count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
