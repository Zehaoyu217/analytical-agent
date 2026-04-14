// Models are fetched live from GET /api/models (see api-backend.ts).
// This fallback is only used before the API responds.
export const DEFAULT_MODEL = 'claude-sonnet-4-6'

export const API_ROUTES = {
  chat: '/api/chat',
  stream: '/api/stream',
} as const

export const MAX_MESSAGE_LENGTH = 100_000
