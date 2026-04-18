import { useEffect, useState } from 'react'
import { fetchContext, fetchSessionContext } from '../lib/api'
import { useDevtoolsStore } from '../stores/devtools'
import { useChatStore } from '../lib/store'

interface KbRecallState {
  hits: Array<{ id: string }>
  skippedReason: string | null
  available: boolean
}

const LAYER_COLORS: Record<string, string> = {
  system: '#ef4444',
  l1_always: '#f97316',
  l2_skill: '#f59e0b',
  memory: '#eab308',
  knowledge: '#22c55e',
  conversation: '#818cf8',
}

export function ContextInspector() {
  const { contextSnapshot, setContextSnapshot } = useDevtoolsStore()

  // Prefer the active conversation's session; fall back to global context
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const activeSessionId =
    conversations.find((c) => c.id === activeConversationId)?.sessionId ?? null

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        const data = activeSessionId
          ? await fetchSessionContext(activeSessionId)
          : await fetchContext()
        if (!cancelled) setContextSnapshot(data)
      } catch {
        // keep showing last snapshot if fetch fails
      }
    }

    refresh()
    const interval = setInterval(refresh, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [activeSessionId, setContextSnapshot])

  const [kbRecall, setKbRecall] = useState<KbRecallState>({
    hits: [],
    skippedReason: null,
    available: false,
  })

  useEffect(() => {
    if (!activeSessionId) {
      setKbRecall({ hits: [], skippedReason: null, available: false })
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(
          `/api/sb/memory/session/${encodeURIComponent(activeSessionId)}`,
        )
        if (cancelled) return
        if (res.status === 404) {
          setKbRecall({ hits: [], skippedReason: null, available: false })
          return
        }
        const body = (await res.json()) as {
          hits?: Array<{ id: string }>
          skipped_reason?: string | null
        }
        setKbRecall({
          hits: body.hits ?? [],
          skippedReason: body.skipped_reason ?? null,
          available: true,
        })
      } catch {
        if (!cancelled) {
          setKbRecall({ hits: [], skippedReason: null, available: false })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeSessionId])

  if (!contextSnapshot) {
    return (
      <div style={{ color: '#94a3b8', padding: 16, fontFamily: 'monospace', fontSize: 11 }}>
        {activeSessionId ? `Loading context for session ${activeSessionId.slice(0, 12)}…` : 'Loading context…'}
      </div>
    )
  }

  const { total_tokens, max_tokens, utilization, layers, compaction_history } = contextSnapshot

  const sessionLabel = activeSessionId
    ? activeSessionId.slice(0, 12) + '…'
    : 'global'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Session indicator banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '5px 10px',
          borderBottom: '1px solid #1c1c24',
          background: '#0f0f16',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: activeSessionId ? '#22c55e' : '#3f3f46',
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {activeSessionId ? 'active session' : 'global context'}
        </span>
        <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#4a4a5a' }}>
          {sessionLabel}
        </span>
        <span style={{ flex: 1 }} />
        <span
          style={{
            fontSize: 10,
            fontFamily: 'monospace',
            color: utilization > 0.9 ? '#f87171' : utilization > 0.75 ? '#f59e0b' : '#4a4a5a',
          }}
        >
          {(utilization * 100).toFixed(1)}% used
        </span>
      </div>

      {/* Main content — two columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1, overflow: 'hidden' }}>
        {/* Left: layers */}
        <div style={{ overflowY: 'auto', padding: 8, borderRight: '1px solid #1c1c24' }}>
          <div style={{ color: '#818cf8', fontSize: 10, textTransform: 'uppercase', marginBottom: 8, letterSpacing: 1, fontFamily: 'monospace' }}>
            Context Layers — {total_tokens.toLocaleString()} / {max_tokens.toLocaleString()} tok
          </div>
          {layers.map((layer) => (
            <div
              key={layer.name}
              style={{
                background: '#14141f',
                border: '1px solid #1c1c24',
                borderLeft: `3px solid ${LAYER_COLORS[layer.name] ?? '#64748b'}`,
                borderRadius: 4,
                padding: 8,
                marginBottom: 6,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'monospace' }}>
                <span style={{ color: LAYER_COLORS[layer.name] ?? '#64748b', fontWeight: 600 }}>
                  {layer.name.toUpperCase()}
                </span>
                <span style={{ color: '#4a4a5a' }}>{layer.tokens.toLocaleString()} tok</span>
              </div>
              {layer.items.length > 0 && (
                <div style={{ marginTop: 4, fontSize: 9, color: '#94a3b8', lineHeight: 1.5, fontFamily: 'monospace' }}>
                  {layer.items.map((item, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{i === layer.items.length - 1 ? '└' : '├'} {item.name}</span>
                      <span>{item.tokens}t</span>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ color: '#4a4a5a', fontSize: 9, marginTop: 4, fontFamily: 'monospace' }}>
                {layer.compactable ? 'Compactable' : 'Never compacted'}
              </div>
            </div>
          ))}

          {kbRecall.available && (
            <div
              data-testid="kb-recall-section"
              style={{
                background: '#14141f',
                border: '1px solid #1c1c24',
                borderLeft: '3px solid #e0733a',
                borderRadius: 4,
                padding: 8,
                marginBottom: 6,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 10,
                  fontFamily: 'monospace',
                }}
              >
                <span style={{ color: '#e0733a', fontWeight: 600, letterSpacing: 1 }}>
                  KB RECALL
                </span>
                <span style={{ color: '#4a4a5a' }}>{kbRecall.hits.length} hit{kbRecall.hits.length === 1 ? '' : 's'}</span>
              </div>
              {kbRecall.hits.length === 0 ? (
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 9,
                    color: '#4a4a5a',
                    fontFamily: 'monospace',
                  }}
                >
                  {kbRecall.skippedReason ? `no recall · ${kbRecall.skippedReason}` : 'no recall'}
                </div>
              ) : (
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 9,
                    color: '#94a3b8',
                    lineHeight: 1.5,
                    fontFamily: 'monospace',
                  }}
                >
                  {kbRecall.hits.map((h, i) => (
                    <div key={h.id}>
                      {i === kbRecall.hits.length - 1 ? '└' : '├'} {h.id}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: compaction history */}
        <div style={{ overflowY: 'auto', padding: 8 }}>
          <div style={{ color: '#818cf8', fontSize: 10, textTransform: 'uppercase', marginBottom: 8, letterSpacing: 1, fontFamily: 'monospace' }}>
            Compaction History
          </div>
          {compaction_history.length === 0 ? (
            <div style={{ color: '#4a4a5a', fontSize: 10, fontFamily: 'monospace' }}>No compactions yet</div>
          ) : (
            compaction_history.map((event) => (
              <div
                key={event.id}
                style={{
                  background: '#14141f',
                  border: '1px solid #1c1c24',
                  borderLeft: '3px solid #f59e0b',
                  borderRadius: 4,
                  padding: 8,
                  marginBottom: 8,
                  fontSize: 9,
                  color: '#94a3b8',
                  fontFamily: 'monospace',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ color: '#f59e0b', fontWeight: 600, fontSize: 10 }}>
                    COMPACTION #{event.id}
                  </span>
                  <span style={{ color: '#4a4a5a' }}>
                    {new Date(event.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}{' '}
                    {new Date(event.timestamp).toLocaleTimeString(undefined, { hour12: false })}
                  </span>
                </div>
                <div>Trigger: {(event.trigger_utilization * 100).toFixed(1)}%</div>
                <div>Before: {event.tokens_before.toLocaleString()}t → After: {event.tokens_after.toLocaleString()}t</div>
                <div style={{ color: '#4ade80' }}>Freed: {event.tokens_freed.toLocaleString()} tokens</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
