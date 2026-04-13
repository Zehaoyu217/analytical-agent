import { useEffect, useRef, useState } from 'react'
import { sendChatMessage } from '../lib/api'
import { useChatStore } from '../stores/chat'
import { useDevtoolsStore } from '../stores/devtools'

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages)
  const sending = useChatStore((s) => s.sending)
  const error = useChatStore((s) => s.error)
  const sessionId = useChatStore((s) => s.sessionId)
  const appendMessage = useChatStore((s) => s.appendMessage)
  const setSending = useChatStore((s) => s.setSending)
  const setError = useChatStore((s) => s.setError)
  const setSessionId = useChatStore((s) => s.setSessionId)
  const newSession = useChatStore((s) => s.newSession)
  const setSelectedTrace = useDevtoolsStore((s) => s.setSelectedTrace)
  const setActiveTab = useDevtoolsStore((s) => s.setActiveTab)

  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    setError(null)
    setSending(true)
    appendMessage({ role: 'user', text, timestamp: Date.now() })
    try {
      const { session_id, response } = await sendChatMessage(text, sessionId)
      setSelectedTrace(session_id)
      setActiveTab('traces')
      if (sessionId !== session_id) {
        setSessionId(session_id)
      }
      appendMessage({
        role: 'assistant',
        text: response,
        traceId: session_id,
        timestamp: Date.now(),
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'request failed'
      setError(msg)
    } finally {
      setSending(false)
    }
  }

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        background: '#0a0a0f',
        color: '#e0e0e8',
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          borderBottom: '1px solid #14141f',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>Analytical Agent</span>
          <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>
            {sessionId ? `session ${sessionId}` : 'no session yet'}
          </span>
        </div>
        <button
          onClick={newSession}
          disabled={messages.length === 0 && !sessionId}
          style={{
            background: 'none',
            border: '1px solid #2a2a3a',
            color: '#94a3b8',
            cursor: messages.length === 0 && !sessionId ? 'default' : 'pointer',
            fontSize: 11,
            fontFamily: 'monospace',
            padding: '4px 10px',
            borderRadius: 3,
            opacity: messages.length === 0 && !sessionId ? 0.5 : 1,
          }}
        >
          new
        </button>
      </header>

      <div
        ref={listRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: 0,
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              margin: 'auto',
              textAlign: 'center',
              color: '#4a4a5a',
              maxWidth: 360,
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            <div style={{ fontSize: 20, fontWeight: 300, marginBottom: 8, color: '#94a3b8' }}>
              Start a conversation
            </div>
            <div>
              Every turn is recorded as a trace. Open dev tools with <code>Cmd+Shift+D</code> to
              inspect prompts, judge variance, and compaction as the conversation runs.
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <ChatBubble key={i} role={msg.role} text={msg.text} />)
        )}
      </div>

      {error && (
        <div
          style={{
            padding: '6px 16px',
            color: '#f87171',
            background: '#1f0f14',
            borderTop: '1px solid #3a1f29',
            fontSize: 11,
            fontFamily: 'monospace',
          }}
        >
          {error}
        </div>
      )}

      <form
        onSubmit={handleSend}
        style={{
          display: 'flex',
          gap: 8,
          padding: 12,
          borderTop: '1px solid #14141f',
        }}
      >
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask something…"
          disabled={sending}
          aria-label="Chat message"
          style={{
            flex: 1,
            background: '#14141f',
            border: '1px solid #2a2a3a',
            color: '#e0e0e8',
            padding: '8px 12px',
            fontSize: 13,
            fontFamily: 'inherit',
            borderRadius: 3,
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={sending || !draft.trim()}
          style={{
            background: sending || !draft.trim() ? '#2a2a3a' : '#818cf8',
            border: 'none',
            color: sending || !draft.trim() ? '#64748b' : '#0a0a0f',
            cursor: sending || !draft.trim() ? 'default' : 'pointer',
            padding: '8px 18px',
            fontSize: 13,
            fontWeight: 500,
            borderRadius: 3,
          }}
        >
          {sending ? '…' : 'send'}
        </button>
      </form>
    </div>
  )
}

function ChatBubble({ role, text }: { role: 'user' | 'assistant'; text: string }) {
  const isUser = role === 'user'
  return (
    <div
      style={{
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '72%',
        background: isUser ? '#1e1b4b' : '#14141f',
        color: '#e0e0e8',
        padding: '10px 14px',
        borderRadius: 8,
        fontSize: 13,
        lineHeight: 1.5,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: '#64748b',
          fontFamily: 'monospace',
          marginBottom: 4,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
        }}
      >
        {role}
      </div>
      {text}
    </div>
  )
}
