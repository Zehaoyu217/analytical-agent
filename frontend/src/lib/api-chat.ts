/**
 * api-chat.ts — thin wrapper for the chat endpoints.
 *
 * Re-exports streamChatMessage (SSE) from ./api.ts.
 */

export { streamChatMessage } from './api'
export type { ChatStreamEvent } from './api'
