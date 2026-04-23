/**
 * api-backend.ts — typed HTTP client for the BE1 backend endpoints.
 *
 * Field names mirror the Pydantic models in:
 *   backend/app/api/conversations_api.py
 *   backend/app/api/settings_api.py
 *   backend/app/api/files_api.py
 *   backend/app/api/slash_api.py
 *
 * Base URL is empty in dev (vite proxy handles /api); it can stay empty in
 * production since the frontend is served from the same origin as the backend.
 */

const BASE_URL = ''

export type TurnRole = 'user' | 'assistant' | 'system'

export interface ConversationSummary {
  id: string
  title: string
  created_at: number
  updated_at: number
  turn_count: number
  pinned?: boolean
  frozen_at?: number | null
}

export interface ConversationTurn {
  role: TurnRole
  content: string
  timestamp: number
}

export interface Conversation {
  id: string
  title: string
  created_at: number
  updated_at: number
  turns: ConversationTurn[]
  pinned?: boolean
  frozen_at?: number | null
}

export interface ConversationPatchPayload {
  title?: string
  pinned?: boolean
  frozen_at?: number | null
}

export interface BulkDeleteRequest {
  older_than?: number
  include_pinned?: boolean
  include_frozen?: boolean
}

export interface BulkDeleteResponse {
  deleted_ids: string[]
  preserved_count: number
}

export type ThemePreference = 'light' | 'dark' | 'system'

export interface UserSettings {
  theme: ThemePreference
  model: string
  send_on_enter: boolean
}

export type FileKind = 'file' | 'dir'

export interface FileNode {
  path: string
  name: string
  kind: FileKind
  size: number | null
  modified: number
}

export interface FileTreeResponse {
  root: string
  entries: FileNode[]
  truncated: boolean
}

export type FileEncoding = 'utf-8' | 'base64'

export interface FileReadResponse {
  path: string
  size: number
  content: string
  encoding: FileEncoding
}

export interface SlashCommand {
  id: string
  label: string
  description: string
}

export interface ModelEntry {
  id: string
  label: string
  description: string
}

export interface ModelGroup {
  provider: string
  label: string
  models: ModelEntry[]
  available: boolean
  note: string
}

export interface ModelsResponse {
  groups: ModelGroup[]
}

export interface DataInfo {
  db_name: string
  tables: string[]
}

export interface BrandingConfig {
  agent_name: string
  agent_persona: string
  ui_title: string
  ui_accent_color: string
  ui_spinner_phrases: string[]
}

export interface SessionSearchResult {
  session_id: string
  message_id: string
  snippet: string
  role: string
  timestamp: number
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
  const res = await fetch(`${BASE_URL}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${method} ${path} failed (${res.status}): ${text}`)
  }
  // DELETE may return an empty body or a small JSON object — either way we
  // don't surface it. Treat as void.
  if (res.status === 204) return undefined as T
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return undefined as T
  }
  return (await res.json()) as T
}

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number] => entry[1] !== undefined,
  )
  if (entries.length === 0) return ''
  const usp = new URLSearchParams()
  for (const [key, value] of entries) {
    usp.set(key, String(value))
  }
  return `?${usp.toString()}`
}

export const backend = {
  conversations: {
    list: (): Promise<ConversationSummary[]> =>
      request<ConversationSummary[]>('GET', '/api/conversations'),
    create: (title: string): Promise<Conversation> =>
      request<Conversation>('POST', '/api/conversations', { title }),
    get: (id: string): Promise<Conversation> =>
      request<Conversation>('GET', `/api/conversations/${encodeURIComponent(id)}`),
    appendTurn: (
      id: string,
      role: TurnRole,
      content: string,
    ): Promise<Conversation> =>
      request<Conversation>(
        'POST',
        `/api/conversations/${encodeURIComponent(id)}/turns`,
        { role, content },
      ),
    delete: (id: string): Promise<void> =>
      request<void>('DELETE', `/api/conversations/${encodeURIComponent(id)}`),
    bulkDelete: (payload: BulkDeleteRequest): Promise<BulkDeleteResponse> =>
      request<BulkDeleteResponse>(
        'POST',
        '/api/conversations/bulk-delete',
        payload,
      ),
    patch: (id: string, payload: ConversationPatchPayload): Promise<Conversation> =>
      request<Conversation>(
        'PATCH',
        `/api/conversations/${encodeURIComponent(id)}`,
        payload,
      ),
  },
  settings: {
    get: (): Promise<UserSettings> => request<UserSettings>('GET', '/api/settings'),
    put: (payload: UserSettings): Promise<UserSettings> =>
      request<UserSettings>('PUT', '/api/settings', payload),
  },
  files: {
    tree: (path?: string): Promise<FileTreeResponse> =>
      request<FileTreeResponse>('GET', `/api/files/tree${qs({ path })}`),
    read: (path: string): Promise<FileReadResponse> =>
      request<FileReadResponse>('GET', `/api/files/read${qs({ path })}`),
  },
  models: {
    list: (): Promise<ModelsResponse> => request<ModelsResponse>('GET', '/api/models'),
  },
  data: {
    info: (): Promise<DataInfo> => request<DataInfo>('GET', '/api/data/info'),
  },
  config: {
    branding: (): Promise<BrandingConfig> =>
      request<BrandingConfig>('GET', '/api/config/branding'),
  },
  slash: {
    list: (): Promise<SlashCommand[]> =>
      request<SlashCommand[]>('GET', '/api/slash'),
  },
  sessions: {
    search: (q: string, limit = 10): Promise<SessionSearchResult[]> =>
      request<SessionSearchResult[]>(
        'GET',
        `/api/sessions/search${qs({ q, limit })}`,
      ),
  },
}
