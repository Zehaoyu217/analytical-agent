/**
 * Message content types shared across chat components.
 *
 * Ported selectively from `reference/web/lib/types.ts`. Only the content-block
 * primitives live here — the rest of the store's shapes (Message, Conversation,
 * Settings) stay in `store.ts` to avoid circular imports and keep the store's
 * surface area narrow.
 */

export interface TextContent {
  type: 'text'
  text: string
}

export interface ToolUseContent {
  type: 'tool_use'
  id: string
  name: string
  input: Record<string, unknown>
  // UI-only fields: track execution state without a separate lookup
  result?: string
  is_error?: boolean
  is_running?: boolean
  started_at?: number
  completed_at?: number
}

export interface ToolResultContent {
  type: 'tool_result'
  tool_use_id: string
  content: string | ContentBlock[]
  is_error?: boolean
}

export interface ChartContent {
  type: 'chart'
  spec: Record<string, unknown>  // Vega-Lite JSON spec
}

export type ContentBlock = TextContent | ToolUseContent | ToolResultContent | ChartContent
