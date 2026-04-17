import { useEffect, useMemo, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Search, MessageSquare, User, Bot } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { backend, type SessionSearchResult } from '@/lib/api-backend'
import { cn } from '@/lib/utils'

const SEARCH_DEBOUNCE_MS = 200
const RESULT_LIMIT = 20

type FetchState =
  | { status: 'idle' }
  | { status: 'loading'; query: string }
  | { status: 'ok'; query: string; results: SessionSearchResult[] }
  | { status: 'error'; query: string; message: string }

function formatTimestamp(ts: number): string {
  // Backend timestamps are unix seconds.
  const d = new Date(ts * 1000)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  return sameDay
    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function roleIcon(role: string) {
  if (role === 'user') return <User className="w-3 h-3" aria-hidden="true" />
  if (role === 'assistant') return <Bot className="w-3 h-3" aria-hidden="true" />
  return <MessageSquare className="w-3 h-3" aria-hidden="true" />
}

interface GroupedResults {
  sessionId: string
  results: SessionSearchResult[]
}

function groupBySession(results: SessionSearchResult[]): GroupedResults[] {
  const map = new Map<string, SessionSearchResult[]>()
  for (const r of results) {
    const list = map.get(r.session_id)
    if (list) {
      list.push(r)
    } else {
      map.set(r.session_id, [r])
    }
  }
  return Array.from(map.entries()).map(([sessionId, results]) => ({
    sessionId,
    results,
  }))
}

export function GlobalSearchPanel() {
  const open = useChatStore((s) => s.searchPanelOpen)
  const closeSearch = useChatStore((s) => s.closeSearch)

  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [fetchState, setFetchState] = useState<FetchState>({ status: 'idle' })
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Reset state when panel opens.
  useEffect(() => {
    if (open) {
      setQuery('')
      setActiveIndex(0)
      setFetchState({ status: 'idle' })
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [open])

  // Debounced search. The latest pending request wins; older responses are dropped.
  useEffect(() => {
    if (!open) return
    const trimmed = query.trim()
    if (!trimmed) {
      setFetchState({ status: 'idle' })
      return
    }

    let cancelled = false
    setFetchState({ status: 'loading', query: trimmed })

    const timer = setTimeout(() => {
      backend.sessions
        .search(trimmed, RESULT_LIMIT)
        .then((results) => {
          if (cancelled) return
          setFetchState({ status: 'ok', query: trimmed, results })
        })
        .catch((err: unknown) => {
          if (cancelled) return
          const message = err instanceof Error ? err.message : 'Search failed'
          setFetchState({ status: 'error', query: trimmed, message })
        })
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query, open])

  const flatResults: SessionSearchResult[] =
    fetchState.status === 'ok' ? fetchState.results : []

  const grouped = useMemo<GroupedResults[]>(
    () => groupBySession(flatResults),
    [flatResults],
  )

  // Clamp activeIndex when results change.
  useEffect(() => {
    setActiveIndex((i) => Math.min(i, Math.max(flatResults.length - 1, 0)))
  }, [flatResults.length])

  // Scroll active item into view.
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${activeIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  const navigateToResult = (result: SessionSearchResult) => {
    closeSearch()
    window.location.hash = `#/monitor/${encodeURIComponent(result.session_id)}`
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, flatResults.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const result = flatResults[activeIndex]
      if (result) navigateToResult(result)
    }
  }

  let flatIdx = 0

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && closeSearch()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            'fixed left-1/2 top-[15%] -translate-x-1/2 z-50',
            'w-full max-w-2xl',
            'bg-surface-900 border border-surface-700 rounded-xl shadow-2xl',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          )}
          onKeyDown={handleKeyDown}
          aria-label="Global session search"
        >
          <Dialog.Title className="sr-only">Global session search</Dialog.Title>
          <Dialog.Description className="sr-only">
            Search across all past sessions by message content.
          </Dialog.Description>
          {/* Search input */}
          <div className="flex items-center gap-2 px-3 py-3 border-b border-surface-800">
            <Search className="w-4 h-4 text-surface-500 flex-shrink-0" aria-hidden="true" />
            <input
              ref={inputRef}
              id="global-search-input"
              role="combobox"
              aria-label="Search sessions"
              aria-expanded={flatResults.length > 0}
              aria-controls="global-search-listbox"
              aria-activedescendant={
                flatResults[activeIndex]
                  ? `search-result-${flatResults[activeIndex].message_id}`
                  : undefined
              }
              aria-autocomplete="list"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActiveIndex(0)
              }}
              placeholder="Search across all sessions..."
              className={cn(
                'flex-1 bg-transparent text-sm text-surface-100',
                'placeholder:text-surface-500 focus:outline-none',
              )}
            />
            <kbd
              aria-label="Press Escape to close"
              className="hidden sm:inline-flex items-center h-5 px-1.5 rounded text-[10px] font-mono bg-surface-800 border border-surface-700 text-surface-500"
            >
              Esc
            </kbd>
          </div>

          {/* Results */}
          <div
            ref={listRef}
            id="global-search-listbox"
            role="listbox"
            aria-label="Search results"
            className="overflow-y-auto max-h-[420px] py-1"
          >
            {fetchState.status === 'idle' && !query.trim() && (
              <div className="py-10 text-center text-sm text-surface-500">
                Type to search across past sessions
              </div>
            )}
            {fetchState.status === 'loading' && (
              <div className="py-10 text-center text-sm text-surface-500" role="status">
                Searching...
              </div>
            )}
            {fetchState.status === 'error' && (
              <div className="py-10 text-center text-sm text-red-400" role="alert">
                {fetchState.message}
              </div>
            )}
            {fetchState.status === 'ok' && flatResults.length === 0 && (
              <div className="py-10 text-center text-sm text-surface-500">
                No matches for &ldquo;{fetchState.query}&rdquo;
              </div>
            )}
            {fetchState.status === 'ok' &&
              grouped.map((group) => (
                <div key={group.sessionId}>
                  <div className="flex items-center gap-2 px-3 py-1.5">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-surface-600">
                      {group.sessionId.slice(0, 8)}
                    </span>
                    <span className="text-[10px] text-surface-700">
                      · {group.results.length} match
                      {group.results.length === 1 ? '' : 'es'}
                    </span>
                  </div>
                  {group.results.map((result) => {
                    const idx = flatIdx++
                    const isActive = idx === activeIndex
                    return (
                      <div key={result.message_id} data-index={idx}>
                        <button
                          type="button"
                          id={`search-result-${result.message_id}`}
                          role="option"
                          aria-selected={isActive}
                          onClick={() => navigateToResult(result)}
                          onMouseEnter={() => setActiveIndex(idx)}
                          className={cn(
                            'w-full text-left flex items-start gap-3 px-3 py-2',
                            'transition-colors duration-75',
                            isActive
                              ? 'bg-surface-800 text-surface-50'
                              : 'text-surface-200 hover:bg-surface-850',
                          )}
                        >
                          <span
                            className={cn(
                              'flex-shrink-0 mt-0.5',
                              result.role === 'user'
                                ? 'text-accent-500'
                                : 'text-surface-500',
                            )}
                          >
                            {roleIcon(result.role)}
                          </span>
                          <span className="flex-1 min-w-0">
                            <span
                              className="block text-sm leading-snug truncate"
                              title={result.snippet}
                            >
                              {result.snippet}
                            </span>
                            <span className="block text-[10px] font-mono text-surface-600 mt-0.5">
                              {result.role}
                              {result.timestamp
                                ? ` · ${formatTimestamp(result.timestamp)}`
                                : ''}
                            </span>
                          </span>
                        </button>
                      </div>
                    )
                  })}
                </div>
              ))}
          </div>

          {/* Footer */}
          <div className="flex items-center gap-4 px-3 py-2 border-t border-surface-800 text-[10px] text-surface-600">
            <span className="flex items-center gap-1">
              <kbd className="inline-flex items-center h-4 px-1 rounded bg-surface-800 border border-surface-700 font-mono">
                ↑↓
              </kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="inline-flex items-center h-4 px-1 rounded bg-surface-800 border border-surface-700 font-mono">
                ↵
              </kbd>
              open session
            </span>
            <span className="flex items-center gap-1">
              <kbd className="inline-flex items-center h-4 px-1 rounded bg-surface-800 border border-surface-700 font-mono">
                Esc
              </kbd>
              close
            </span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
