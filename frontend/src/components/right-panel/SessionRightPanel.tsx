import { useState, useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { ArtifactsPanel } from './ArtifactsPanel'
import { ScratchpadPanel } from './ScratchpadPanel'
import { TodosPanel } from './TodosPanel'
import { TerminalPanel } from './TerminalPanel'
import { ResizeHandle } from '@/components/layout/ResizeHandle'
import { useResizablePanel } from '@/hooks/useResizablePanel'
import { cn } from '@/lib/utils'

type Tab = 'traces' | 'tasks' | 'scratchpad'

const TAB_LABELS: Record<Tab, string> = {
  traces: 'Traces',
  tasks: 'Tasks',
  scratchpad: 'Scratchpad',
}

const TAB_TITLES: Record<Tab, string> = {
  traces: 'Tool calls, execution log, and generated artifacts',
  tasks: 'Agent task list — populated when the agent uses todo_write',
  scratchpad: 'Agent reasoning and intermediate findings via write_working',
}

export function SessionRightPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('traces')
  const scratchpad = useChatStore((s) => s.scratchpad)
  const todos = useChatStore((s) => s.todos)
  const verticalSplit = useResizablePanel(
    Math.max(200, Math.floor((typeof window !== 'undefined' ? window.innerHeight : 800) / 2 - 30)),
    80,
    700,
    'vertical',
  )

  const rightPanelOpen = useChatStore((s) => s.rightPanelOpen)

  const hasScratchpad = scratchpad.length > 0
  const hasTodos = todos.length > 0
  const hasActiveTodo = todos.some((t) => t.status === 'in_progress')

  // Auto-switch to Tasks tab when the agent first writes todos,
  // but only if the right panel is already open.
  const [autoSwitched, setAutoSwitched] = useState(false)

  useEffect(() => {
    if (hasTodos && !autoSwitched && rightPanelOpen) {
      setActiveTab('tasks')
      setAutoSwitched(true)
    }
  }, [hasTodos, autoSwitched, rightPanelOpen])

  // Reset so next agent run can auto-switch again
  useEffect(() => {
    if (!hasTodos) {
      setAutoSwitched(false)
    }
  }, [hasTodos])

  return (
    <aside
      className="flex flex-col w-full border-l border-surface-700/60 bg-surface-900"
      aria-label="Session state"
    >
      {/* ── Tab bar ────────────────────────────────────────── */}
      <div role="tablist" aria-label="Session panel" className="flex flex-shrink-0 border-b border-surface-700/60">
        {(['traces', 'tasks', 'scratchpad'] as Tab[]).map((tab) => {
          const isActive = activeTab === tab
          const dot =
            (tab === 'scratchpad' && hasScratchpad) ||
            (tab === 'tasks' && hasTodos)
          const dotActive = tab === 'tasks' && hasActiveTodo

          return (
            <button
              key={tab}
              id={`tab-${tab}`}
              aria-controls={`panel-${tab}`}
              title={TAB_TITLES[tab]}
              onClick={() => setActiveTab(tab)}
              aria-selected={isActive}
              role="tab"
              className={cn(
                'flex items-center gap-1.5 px-3 py-2.5',
                'text-[10px] font-mono font-semibold tracking-[0.18em] uppercase',
                'border-b transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent/50',
                isActive
                  ? 'border-brand-accent/80 text-surface-200'
                  : 'border-transparent text-surface-600 hover:text-surface-400',
              )}
            >
              {TAB_LABELS[tab]}
              {dot && (
                <span
                  className={cn(
                    'w-1 h-1 rounded-full flex-shrink-0',
                    dotActive ? 'bg-brand-accent animate-pulse' : 'bg-brand-accent',
                  )}
                  aria-label="has content"
                />
              )}
            </button>
          )
        })}
      </div>

      {/* ── Traces tab: Progress (tool log) + Artifacts ───── */}
      {activeTab === 'traces' && (
        <div id="panel-traces" role="tabpanel" aria-labelledby="tab-traces" className="flex flex-col flex-1 min-h-0">
          {/* Progress — resizable top pane */}
          <div
            className="flex flex-col min-h-0 overflow-hidden"
            style={{ height: verticalSplit.size, flexShrink: 0 }}
          >
            <TerminalPanel />
          </div>

          <ResizeHandle direction="vertical" onMouseDown={verticalSplit.onMouseDown} />

          {/* Artifacts — fills remaining height */}
          <div className="flex flex-col flex-1 min-h-0">
            <ArtifactsPanel />
          </div>
        </div>
      )}

      {/* ── Tasks tab ──────────────────────────────────────── */}
      {activeTab === 'tasks' && (
        <div id="panel-tasks" role="tabpanel" aria-labelledby="tab-tasks" className="flex flex-col flex-1 min-h-0">
          <TodosPanel />
        </div>
      )}

      {/* ── Scratchpad tab ─────────────────────────────────── */}
      {activeTab === 'scratchpad' && (
        <div id="panel-scratchpad" role="tabpanel" aria-labelledby="tab-scratchpad" className="flex flex-col flex-1 min-h-0">
          <ScratchpadPanel />
        </div>
      )}
    </aside>
  )
}
