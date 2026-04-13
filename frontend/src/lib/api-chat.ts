/**
 * api-chat.ts — thin wrapper for the chat endpoint.
 *
 * Re-exports `sendChatMessage` from `./api.ts`, which already posts to
 * /api/chat with the correct shape and throws on non-2xx responses.
 */

export { sendChatMessage } from './api'
export type { ChatResponse } from './api'
