import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, XCircle } from 'lucide-react'
import { listAgentGroups, type AgentGroup } from '@/lib/api-agents'
import { cn } from '@/lib/utils'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function formatSessionDate(iso: string): string {
  const d = new Date(iso)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}/${hh}:${min}`
}

function navigateToSession(sessionId: string): void {
  window.location.href = `#/monitor/${sessionId}`
}

export function AgentsTab(): React.ReactElement {
  const [state, setState] = useState<LoadState>('idle')
  const [groups, setGroups] = useState<AgentGroup[]>([])
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const refresh = useCallback(async () => {
    setState('loading')
    setError(null)
    try {
      const data = await listAgentGroups()
      setGroups(data)
      setState('ready')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load agents'
      setError(message)
      setState('error')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const toggleCollapsed = useCallback((role: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(role)) {
        next.delete(role)
      } else {
        next.add(role)
      }
      return next
    })
  }, [])

  const q = filter.trim().toLowerCase()
  const filteredGroups = q
    ? groups
        .map((g) => ({
          ...g,
          sessions: g.sessions.filter(
            (s) =>
              g.role.toLowerCase().includes(q) ||
              s.session_id.toLowerCase().includes(q),
          ),
        }))
        .filter((g) => g.sessions.length > 0)
    : groups

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-800 flex-shrink-0 gap-2">
        <h2 className="text-xs font-semibold text-surface-300 uppercase tracking-wide flex-shrink-0">
          Agents
        </h2>
        <input
          type="search"
          placeholder="filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className={cn(
            'flex-1 min-w-0 bg-surface-800 border border-surface-700 rounded px-2 py-0.5',
            'text-xs font-mono text-surface-200 placeholder:text-surface-600',
            'focus:outline-none focus:border-brand-500 focus:ring-0',
          )}
          aria-label="Filter agents"
        />
        <button
          type="button"
          onClick={() => void refresh()}
          className="text-xs text-surface-500 hover:text-surface-200 flex-shrink-0"
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
        className="flex-1 min-h-0 overflow-y-auto pb-2"
        role="list"
        aria-label="Agent sessions by role"
      >
        {state === 'loading' && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            Loading agents…
          </p>
        )}

        {state === 'ready' && filteredGroups.length === 0 && (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            No agent sessions recorded.
          </p>
        )}

        {filteredGroups.map((group) => {
          const isCollapsed = collapsed.has(group.role)
          return (
            <div key={group.role} role="listitem">
              <button
                type="button"
                onClick={() => toggleCollapsed(group.role)}
                className={cn(
                  'w-full flex items-center gap-1.5 px-3 py-1.5 text-left',
                  'text-surface-300 hover:text-surface-100 hover:bg-surface-800/40',
                  'transition-colors border-b border-surface-800/60',
                )}
                aria-expanded={!isCollapsed}
              >
                {isCollapsed ? (
                  <ChevronRight className="w-3 h-3 flex-shrink-0 text-surface-500" aria-hidden />
                ) : (
                  <ChevronDown className="w-3 h-3 flex-shrink-0 text-surface-500" aria-hidden />
                )}
                <span className="text-xs font-mono font-medium uppercase tracking-wider flex-1 truncate">
                  {group.role}
                </span>
                <span className="text-[10px] font-mono text-surface-500 flex-shrink-0">
                  {group.sessions.length}
                </span>
              </button>

              {!isCollapsed && (
                <div className="pl-4 pr-2 py-0.5 space-y-px">
                  {group.sessions.map((session) => (
                    <button
                      key={session.session_id}
                      type="button"
                      onClick={() => navigateToSession(session.session_id)}
                      className={cn(
                        'w-full flex items-center gap-2 px-2 py-1 rounded text-left',
                        'text-surface-400 hover:text-surface-200 hover:bg-surface-800/60',
                        'transition-colors group',
                      )}
                      title={`Session ${session.session_id}`}
                    >
                      {session.outcome === 'ok' ? (
                        <CheckCircle2
                          className="w-3.5 h-3.5 flex-shrink-0 text-emerald-500"
                          aria-label="Done"
                        />
                      ) : (
                        <XCircle
                          className="w-3.5 h-3.5 flex-shrink-0 text-red-400"
                          aria-label="Failed"
                        />
                      )}
                      <span className="flex-1 min-w-0 font-mono text-[11px] truncate text-surface-300">
                        {formatSessionDate(session.started_at)}
                      </span>
                      <span
                        className={cn(
                          'text-[10px] font-mono flex-shrink-0 uppercase tracking-wider',
                          session.outcome === 'ok' ? 'text-emerald-600' : 'text-red-500',
                        )}
                      >
                        {session.outcome === 'ok' ? 'DONE' : 'FAILED'}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
