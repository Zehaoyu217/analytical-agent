import { useCallback, useEffect, useRef } from 'react'
import { useDevtoolsStore } from '../stores/devtools'
import { ContextInspector } from './ContextInspector'
import { TracesList } from './TracesList'
import { SessionReplay } from './sop/SessionReplay'
import { JudgeVariance } from './sop/JudgeVariance'
import { PromptInspector } from './sop/PromptInspector'
import { CompactionTimeline } from './sop/CompactionTimeline'
import { useSelectionUrlSync } from './sop/useSelectionUrlSync'

const TABS = [
  'traces', 'events', 'skills', 'config', 'wiki', 'evals', 'context',
  'sop-sessions', 'sop-judge', 'sop-prompt', 'sop-timeline',
] as const

function Placeholder({ name }: { name: string }) {
  return (
    <div style={{ color: '#4a4a5a', padding: 16, fontSize: 12 }}>
      {name} tab — not yet implemented
    </div>
  )
}

export function DevToolsPanel() {
  const isOpen = useDevtoolsStore((s) => s.isOpen)
  const activeTab = useDevtoolsStore((s) => s.activeTab)
  const setActiveTab = useDevtoolsStore((s) => s.setActiveTab)
  const selectedTraceId = useDevtoolsStore((s) => s.selectedTraceId)
  const selectedStepId = useDevtoolsStore((s) => s.selectedStepId)
  const panelHeight = useDevtoolsStore((s) => s.panelHeight)
  const setPanelHeight = useDevtoolsStore((s) => s.setPanelHeight)
  const toggle = useDevtoolsStore((s) => s.toggle)
  useSelectionUrlSync()

  const draggingRef = useRef(false)

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = true
    document.body.style.cursor = 'ns-resize'
    document.body.style.userSelect = 'none'
  }, [])

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingRef.current) return
      // Distance from cursor to the bottom of the viewport (minus status bar height).
      const next = window.innerHeight - e.clientY - 32
      setPanelHeight(next)
    }
    function onUp() {
      if (!draggingRef.current) return
      draggingRef.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [setPanelHeight])

  if (!isOpen) return null

  return (
    <div
      style={{
        height: panelHeight,
        flexShrink: 0,
        background: '#0a0a0f',
        color: '#e0e0e8',
        fontFamily: 'monospace',
        fontSize: 11,
        display: 'flex',
        flexDirection: 'column',
        borderTop: '1px solid #2a2a3a',
      }}
    >
      <div
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize developer tools"
        onMouseDown={onDragStart}
        style={{
          height: 4,
          cursor: 'ns-resize',
          background: '#14141f',
          borderBottom: '1px solid #2a2a3a',
        }}
      />

      <div
        style={{
          display: 'flex',
          gap: 16,
          padding: '6px 12px',
          borderBottom: '1px solid #2a2a3a',
          background: '#14141f',
          alignItems: 'center',
        }}
      >
        <span style={{ color: '#818cf8', fontWeight: 600 }}>⚙ DEV</span>
        <div style={{ display: 'flex', gap: 12, flex: 1, overflowX: 'auto' }}>
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                color: activeTab === tab ? '#818cf8' : '#94a3b8',
                borderBottom: activeTab === tab ? '1px solid #818cf8' : 'none',
                cursor: 'pointer',
                fontSize: 11,
                fontFamily: 'monospace',
                textTransform: 'capitalize',
                padding: '0 4px 4px',
                whiteSpace: 'nowrap',
              }}
            >
              {tab}
            </button>
          ))}
        </div>
        <button
          onClick={toggle}
          aria-label="Close developer tools"
          style={{
            background: 'none',
            border: '1px solid #2a2a3a',
            color: '#64748b',
            cursor: 'pointer',
            fontSize: 11,
            fontFamily: 'monospace',
            padding: '2px 8px',
            borderRadius: 3,
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {activeTab === 'traces' && <TracesList />}
        {activeTab === 'context' && <ContextInspector />}
        {activeTab === 'sop-sessions' && <SessionReplay />}
        {activeTab === 'sop-judge' && (
          selectedTraceId
            ? <JudgeVariance traceId={selectedTraceId} />
            : <div className="sop-empty">Select a trace from the Traces tab.</div>
        )}
        {activeTab === 'sop-prompt' && (
          selectedTraceId && selectedStepId
            ? <PromptInspector traceId={selectedTraceId} stepId={selectedStepId} />
            : <div className="sop-empty">Select a trace+step from the Traces tab.</div>
        )}
        {activeTab === 'sop-timeline' && (
          selectedTraceId
            ? <CompactionTimeline traceId={selectedTraceId} />
            : <div className="sop-empty">Select a trace from the Traces tab.</div>
        )}
        {!['traces', 'context', 'sop-sessions', 'sop-judge', 'sop-prompt', 'sop-timeline'].includes(activeTab) && (
          <Placeholder name={activeTab} />
        )}
      </div>
    </div>
  )
}
