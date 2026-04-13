const BASE_URL = '/api'

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${BASE_URL}/health`)
  return res.json()
}

export interface ContextSnapshot {
  total_tokens: number
  max_tokens: number
  utilization: number
  compaction_needed: boolean
  layers: Array<{
    name: string
    tokens: number
    compactable: boolean
    items: Array<{ name: string; tokens: number }>
  }>
  compaction_history: Array<{
    id: number
    timestamp: string
    tokens_before: number
    tokens_after: number
    tokens_freed: number
    trigger_utilization: number
    removed: Array<{ name: string; tokens: number }>
    survived: string[]
  }>
}

export async function fetchContext(): Promise<ContextSnapshot> {
  const res = await fetch(`${BASE_URL}/context`)
  return res.json()
}

export interface ChatResponse {
  session_id: string
  response: string
}

export async function sendChatMessage(
  message: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`chat failed (${res.status}): ${body}`)
  }
  return res.json()
}

export interface TraceListItem {
  session_id: string
  started_at: string
  ended_at: string
  duration_ms: number
  level: number
  level_label: string
  turn_count: number
  llm_call_count: number
  total_input_tokens: number
  total_output_tokens: number
  outcome: string
  final_grade: 'A' | 'B' | 'C' | 'F' | null
  step_ids: string[]
  trace_mode: string
  judge_runs_cached: number
}

export async function listTraces(): Promise<TraceListItem[]> {
  const res = await fetch(`${BASE_URL}/trace/traces`)
  if (!res.ok) {
    throw new Error(`listTraces failed: ${res.status}`)
  }
  const body = (await res.json()) as { traces: TraceListItem[] }
  return body.traces
}
