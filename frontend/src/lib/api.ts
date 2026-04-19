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

export interface SessionContextSnapshot extends ContextSnapshot {
  session_id: string
}

export interface CompactionDiff {
  session_id: string
  compaction_id: number
  timestamp: string
  tokens_before: number
  tokens_after: number
  tokens_freed: number
  trigger_utilization: number
  information_loss_pct: number
  loss_severity: 'LOW' | 'MEDIUM' | 'HIGH'
  removed: Array<{ name: string; tokens: number }>
  survived: string[]
}

export async function fetchSessionContext(sessionId: string): Promise<SessionContextSnapshot> {
  const res = await fetch(`${BASE_URL}/context/${encodeURIComponent(sessionId)}`)
  if (!res.ok) throw new Error(`context fetch failed (${res.status})`)
  return res.json()
}

export async function fetchContextHistory(
  sessionId: string,
): Promise<{ session_id: string; history: ContextSnapshot['compaction_history'] }> {
  const res = await fetch(`${BASE_URL}/context/${encodeURIComponent(sessionId)}/history`)
  if (!res.ok) throw new Error(`history fetch failed (${res.status})`)
  return res.json()
}

export async function fetchCompactionDiff(
  sessionId: string,
  compactionId: number,
): Promise<CompactionDiff> {
  const res = await fetch(
    `${BASE_URL}/context/${encodeURIComponent(sessionId)}/compaction/${compactionId}`,
  )
  if (!res.ok) throw new Error(`compaction diff fetch failed (${res.status})`)
  return res.json()
}

export async function listContextSessions(): Promise<{ sessions: string[] }> {
  const res = await fetch(`${BASE_URL}/context/sessions`)
  if (!res.ok) throw new Error(`sessions list failed (${res.status})`)
  return res.json()
}

export interface ChatResponse {
  session_id: string
  response: string
  charts?: Array<Record<string, unknown>>  // Vega-Lite JSON specs
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

// ── SSE streaming chat ────────────────────────────────────────────────────────

export interface ChatStreamEvent {
  type:
    | 'turn_start'
    | 'tool_call'
    | 'tool_result'
    | 'scratchpad_delta'
    | 'todos_update'
    | 'micro_compact'
    | 'turn_end'
    | 'error'
    | 'a2a_start'
    | 'a2a_end'
    | 'artifact'
  // turn_start
  session_id?: string
  step?: number
  // tool_call
  name?: string
  input_preview?: string
  // tool_result
  status?: 'ok' | 'error' | 'blocked'
  artifact_ids?: string[]
  preview?: string
  stdout?: string
  // turn_end
  final_text?: string
  stop_reason?: string
  steps?: number
  charts?: Array<Record<string, unknown>>
  // error
  message?: string
  // a2a_start
  task_preview?: string
  tools_allowed?: string[]
  // a2a_end
  artifact_id?: string
  ok?: boolean
  summary?: string
  // scratchpad_delta
  content?: string
  // todos_update
  todos?: Array<{ id: string; content: string; status: 'pending' | 'in_progress' | 'completed' }>
  // micro_compact
  dropped_messages?: number
  chars_before?: number
  chars_after?: number
  tokens_before?: number
  tokens_after?: number
  // artifact event fields
  id?: string
  title?: string
  format?: string
  artifact_type?: string
  artifact_content?: string
  artifact_metadata?: Record<string, unknown>
  created_at?: number
}

export interface StreamChatOptions {
  datasetPath?: string | null
  /**
   * When true, tell the backend to suppress side-effecting tools and run in
   * plan-only mode. Backend enforces this via tool filtering in `chat_api.py`
   * and a system-prompt rider; the flag here only controls the request
   * payload so the two sides stay in sync.
   */
  planMode?: boolean
  model?: string
  extendedThinking?: boolean
  signal?: AbortSignal
}

/**
 * Stream chat events from POST /api/chat/stream.
 * Yields one ChatStreamEvent per SSE frame; ends when the stream closes.
 *
 * Legacy positional signature (`message, sessionId, datasetPath, signal`)
 * is preserved for backwards compatibility — callers that need `planMode`
 * must use the options-object form.
 */
export async function* streamChatMessage(
  message: string,
  sessionId: string | null,
  datasetPathOrOptions?: string | null | StreamChatOptions,
  legacySignal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const options: StreamChatOptions =
    typeof datasetPathOrOptions === 'object' && datasetPathOrOptions !== null
      ? datasetPathOrOptions
      : { datasetPath: datasetPathOrOptions ?? null, signal: legacySignal }

  const res = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      dataset_path: options.datasetPath ?? null,
      plan_mode: options.planMode ?? false,
      ...(options.model ? { model: options.model } : {}),
      ...(options.extendedThinking ? { extended_thinking: true } : {}),
    }),
    signal: options.signal,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`chat stream failed (${res.status}): ${body}`)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6)) as ChatStreamEvent
        } catch {
          // skip malformed frames
        }
      }
    }
  }
}
