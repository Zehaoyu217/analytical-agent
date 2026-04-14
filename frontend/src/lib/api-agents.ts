/**
 * api-agents.ts — typed wrapper around the trace API for agent session data.
 *
 * Mirrors fields from backend/app/api/trace_api.py TraceSummary.
 */

const BASE_URL = ''

export interface AgentSession {
  session_id: string
  started_at: string
  ended_at: string
  duration_ms: number
  turn_count: number
  outcome: 'ok' | 'error'
  level_label: string
}

export interface AgentGroup {
  role: string
  sessions: AgentSession[]
}

interface TraceSummary {
  session_id: string
  started_at: string
  ended_at: string
  duration_ms: number
  level: number
  level_label: string
  turn_count: number
  outcome: 'ok' | 'error'
}

interface TraceListResponse {
  traces: TraceSummary[]
}

export async function listAgentGroups(): Promise<AgentGroup[]> {
  const res = await fetch(`${BASE_URL}/api/trace/traces`)
  if (!res.ok) {
    throw new Error(`Failed to fetch traces: ${res.status} ${res.statusText}`)
  }
  const data = (await res.json()) as TraceListResponse
  const traces = data.traces ?? []

  const groupMap = new Map<string, AgentSession[]>()
  for (const t of traces) {
    const session: AgentSession = {
      session_id: t.session_id,
      started_at: t.started_at,
      ended_at: t.ended_at,
      duration_ms: t.duration_ms,
      turn_count: t.turn_count,
      outcome: t.outcome,
      level_label: t.level_label,
    }
    const existing = groupMap.get(t.level_label)
    if (existing) {
      existing.push(session)
    } else {
      groupMap.set(t.level_label, [session])
    }
  }

  const groups: AgentGroup[] = []
  const sortedKeys = [...groupMap.keys()].sort()
  for (const key of sortedKeys) {
    const sessions = groupMap.get(key) ?? []
    sessions.sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
    )
    groups.push({ role: key, sessions })
  }

  return groups
}
