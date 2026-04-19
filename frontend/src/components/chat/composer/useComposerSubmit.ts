import { useCallback, useRef, useState } from 'react'
import { nanoid } from 'nanoid'
import { useChatStore, type Artifact } from '@/lib/store'
import { useDevtoolsStore } from '@/stores/devtools'
import { streamChatMessage } from '@/lib/api-chat'
import { backend } from '@/lib/api-backend'
import type { A2aContent, ContentBlock } from '@/lib/types'

export interface ComposerSubmitResult {
  submit: (text: string) => Promise<void>
  stop: () => void
  isSending: boolean
  error: string | null
  clearError: () => void
}

export function useComposerSubmit(conversationId: string): ComposerSubmitResult {
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const submit = useCallback(
    async (rawText: string) => {
      const text = rawText.trim()
      if (!text || isSending) return

      const state = useChatStore.getState()
      const conversation = state.conversations.find((c) => c.id === conversationId)
      const {
        addMessage,
        updateMessage,
        setConversationSessionId,
        setConversationContext,
        pushToolCall,
        updateToolCallById,
        clearToolCallLog,
        setScratchpad,
        clearScratchpad,
        setTodos,
        clearTodos,
        setRightPanelTab,
        addArtifact,
        clearArtifacts,
        clearAttachedFiles,
      } = state

      setError(null)
      setIsSending(true)
      const controller = new AbortController()
      abortControllerRef.current = controller

      addMessage(conversationId, { role: 'user', content: text, status: 'complete' })
      backend.conversations
        .appendTurn(conversationId, 'user', text)
        .catch((err: unknown) => window.console?.warn?.('persist user turn failed', err))

      const assistantId = addMessage(conversationId, {
        role: 'assistant',
        content: '',
        status: 'sending',
      })

      clearToolCallLog()
      clearScratchpad()
      clearTodos()
      clearArtifacts()

      const pendingToolCallIds = new Map<string, string>()
      const a2aBlocksByStep = new Map<number, A2aContent>()
      let finalSessionId = conversation?.sessionId ?? null
      let finalResponseText = ''

      try {
        const stream = streamChatMessage(text, conversation?.sessionId ?? null, {
          planMode: useChatStore.getState().planMode,
          signal: controller.signal,
          ...(conversation?.model ? { model: conversation.model } : {}),
          ...(conversation?.extendedThinking ? { extendedThinking: true } : {}),
        })

        for await (const event of stream) {
          if (event.type === 'turn_start') {
            if (event.session_id) finalSessionId = event.session_id
            updateMessage(conversationId, assistantId, { status: 'streaming' })
          } else if (event.type === 'tool_call') {
            setRightPanelTab('tools')
            const entryKey = `${event.step}-${event.name}`
            const storeId = pushToolCall({
              step: event.step ?? 0,
              name: event.name ?? '',
              inputPreview: event.input_preview ?? '',
              status: 'pending',
              startedAt: Date.now(),
              messageId: assistantId,
            })
            pendingToolCallIds.set(entryKey, storeId)
          } else if (event.type === 'tool_result') {
            const entryKey = `${event.step}-${event.name}`
            const storeId = pendingToolCallIds.get(entryKey)
            if (storeId) {
              updateToolCallById(storeId, {
                status: event.status ?? 'ok',
                preview: event.preview,
                stdout: event.stdout ?? event.preview ?? '',
                artifactIds: event.artifact_ids,
                finishedAt: Date.now(),
              })
            }
          } else if (event.type === 'a2a_start') {
            const block: A2aContent = {
              type: 'a2a',
              task: event.task_preview ?? '',
              artifactId: '',
              summary: '',
              status: 'pending',
            }
            a2aBlocksByStep.set(event.step ?? 0, block)
            updateMessage(conversationId, assistantId, {
              content: [...a2aBlocksByStep.values()] as ContentBlock[],
            })
          } else if (event.type === 'a2a_end') {
            const step = event.step ?? 0
            const existing = a2aBlocksByStep.get(step)
            if (existing) {
              a2aBlocksByStep.set(step, {
                ...existing,
                artifactId: event.artifact_id ?? '',
                summary: event.summary ?? '',
                status: event.ok !== false ? 'complete' : 'error',
              })
              updateMessage(conversationId, assistantId, {
                content: [...a2aBlocksByStep.values()] as ContentBlock[],
              })
            }
          } else if (event.type === 'artifact') {
            const artifact: Artifact = {
              id: event.id ?? nanoid(),
              type: (event.artifact_type as Artifact['type']) ?? 'chart',
              title: event.title ?? 'Artifact',
              content: event.artifact_content ?? '',
              format: (event.format as Artifact['format']) ?? 'vega-lite',
              session_id: event.session_id ?? '',
              created_at: event.created_at ?? Date.now() / 1000,
              metadata: event.artifact_metadata ?? {},
            }
            addArtifact(artifact)
            const currentConv = useChatStore
              .getState()
              .conversations.find((c) => c.id === conversationId)
            const currentMsg = currentConv?.messages.find((m) => m.id === assistantId)
            updateMessage(conversationId, assistantId, {
              artifactIds: [...(currentMsg?.artifactIds ?? []), artifact.id],
            })
            setRightPanelTab('artifacts')
          } else if (event.type === 'context_snapshot') {
            const existing = useChatStore
              .getState()
              .conversations.find((c) => c.id === conversationId)?.context
            setConversationContext(conversationId, {
              layers: (event.layers ?? []).map((l) => ({
                id: l.id,
                label: l.label,
                tokens: l.tokens,
                maxTokens: l.max_tokens,
              })),
              loadedFiles: (event.loaded_files ?? []).map((f) => ({
                id: f.id,
                name: f.name,
                size: f.size,
                kind: f.kind,
              })),
              scratchpad: existing?.scratchpad ?? '',
              totalTokens: event.total_tokens ?? 0,
              budgetTokens: event.budget_tokens ?? 200_000,
            })
          } else if (event.type === 'scratchpad_delta') {
            setScratchpad(event.content ?? '')
          } else if (event.type === 'todos_update') {
            setTodos(event.todos ?? [])
          } else if (event.type === 'micro_compact') {
            const saved = (event.tokens_before ?? 0) - (event.tokens_after ?? 0)
            const now = Date.now()
            pushToolCall({
              step: event.step ?? 0,
              name: '__compact__',
              inputPreview: '',
              status: 'ok',
              preview: `compacted ${event.dropped_messages ?? 0} msgs · ~${saved.toLocaleString()} tokens freed`,
              startedAt: now,
              finishedAt: now,
              messageId: assistantId,
            })
          } else if (event.type === 'turn_end') {
            finalResponseText = event.final_text ?? ''
            const charts = event.charts ?? []
            const a2aBlocks = [...a2aBlocksByStep.values()] as ContentBlock[]
            const textBlock = finalResponseText
              ? [{ type: 'text' as const, text: finalResponseText }]
              : []

            const currentConvState = useChatStore
              .getState()
              .conversations.find((c) => c.id === conversationId)
            const currentMsgState = currentConvState?.messages.find(
              (m) => m.id === assistantId,
            )
            const alreadyHasArtifacts =
              (currentMsgState?.artifactIds ?? []).length > 0
            if (!alreadyHasArtifacts && charts.length > 0) {
              const newArtifactIds: string[] = []
              for (const spec of charts) {
                const artifactId = nanoid()
                addArtifact({
                  id: artifactId,
                  type: 'chart',
                  title: typeof spec.title === 'string' ? spec.title : 'Chart',
                  content: JSON.stringify(spec),
                  format: 'vega-lite',
                  session_id: finalSessionId ?? '',
                  created_at: Date.now() / 1000,
                  metadata: {},
                })
                newArtifactIds.push(artifactId)
              }
              updateMessage(conversationId, assistantId, { artifactIds: newArtifactIds })
              if (charts.length > 0) setRightPanelTab('artifacts')
            }

            const content: ContentBlock[] | string =
              a2aBlocks.length > 0 ? [...a2aBlocks, ...textBlock] : finalResponseText
            updateMessage(conversationId, assistantId, {
              content,
              status: 'complete',
              traceId: finalSessionId ?? undefined,
            })
            if (finalSessionId) setConversationSessionId(conversationId, finalSessionId)
          } else if (event.type === 'error') {
            const msg = event.message ?? 'Agent error'
            updateMessage(conversationId, assistantId, { content: msg, status: 'error' })
            setError(msg)
            return
          }
        }

        if (finalSessionId) {
          setConversationSessionId(conversationId, finalSessionId)
          const devtools = useDevtoolsStore.getState()
          devtools.setSelectedTrace(finalSessionId)
          devtools.setActiveTab('traces')
        }
        if (finalResponseText) {
          backend.conversations
            .appendTurn(conversationId, 'assistant', finalResponseText)
            .catch((err: unknown) =>
              window.console?.warn?.('persist assistant turn failed', err),
            )
        }
        clearAttachedFiles(conversationId)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          updateMessage(conversationId, assistantId, { status: 'complete' })
        } else {
          const msg = err instanceof Error ? err.message : 'Unknown error'
          updateMessage(conversationId, assistantId, { content: msg, status: 'error' })
          setError(msg)
        }
      } finally {
        setIsSending(false)
        abortControllerRef.current = null
      }
    },
    [conversationId, isSending],
  )

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return { submit, stop, isSending, error, clearError }
}
