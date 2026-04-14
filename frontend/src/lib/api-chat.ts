/**
 * api-chat.ts — thin wrapper for the chat endpoints.
 *
 * Re-exports sendChatMessage (JSON) and streamChatMessage (SSE) from ./api.ts.
 */

export { sendChatMessage, streamChatMessage } from './api'
export type { ChatResponse, ChatStreamEvent } from './api'
