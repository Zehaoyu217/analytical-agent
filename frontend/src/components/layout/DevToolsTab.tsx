import {
  Activity,
  Layers,
  PlayCircle,
  Scale,
  FileText,
  Clock,
} from 'lucide-react'
import { useDevtoolsStore } from '@/stores/devtools'
import { useSelectionUrlSync } from '@/devtools/sop/useSelectionUrlSync'
import { TracesList } from '@/devtools/TracesList'
import { ContextInspector } from '@/devtools/ContextInspector'
import { SessionReplay } from '@/devtools/sop/SessionReplay'
import { JudgeVariance } from '@/devtools/sop/JudgeVariance'
import { PromptInspector } from '@/devtools/sop/PromptInspector'
import { CompactionTimeline } from '@/devtools/sop/CompactionTimeline'
import { cn } from '@/lib/utils'

type DevToolsSubTab =
  | 'traces'
  | 'context'
  | 'sop-sessions'
  | 'sop-judge'
  | 'sop-prompt'
  | 'sop-timeline'

interface SubTabDef {
  id: DevToolsSubTab
  label: string
  icon: React.ElementType
}

const SUB_TABS: SubTabDef[] = [
  { id: 'traces', label: 'Traces', icon: Activity },
  { id: 'context', label: 'Context', icon: Layers },
  { id: 'sop-sessions', label: 'Sessions', icon: PlayCircle },
  { id: 'sop-judge', label: 'Judge', icon: Scale },
  { id: 'sop-prompt', label: 'Prompt', icon: FileText },
  { id: 'sop-timeline', label: 'Timeline', icon: Clock },
]

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-full items-center justify-center px-6 py-10 text-center">
      <p className="text-xs text-surface-500">{message}</p>
    </div>
  )
}

export function DevToolsTab() {
  const activeTab = useDevtoolsStore((s) => s.activeTab)
  const setActiveTab = useDevtoolsStore((s) => s.setActiveTab)
  const selectedTraceId = useDevtoolsStore((s) => s.selectedTraceId)
  const selectedStepId = useDevtoolsStore((s) => s.selectedStepId)

  // Keep trace/step selection in sync with URL query params (same as old DevToolsPanel).
  useSelectionUrlSync()

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Sub-tab row — compact, scrolls horizontally on narrow widths */}
      <div
        role="tablist"
        aria-label="DevTools sections"
        className={cn(
          'flex items-center gap-0.5 flex-shrink-0',
          'border-b border-surface-800 bg-surface-900/60',
          'px-2 py-1.5 overflow-x-auto',
        )}
      >
        {SUB_TABS.map(({ id, label, icon: Icon }) => {
          const isActive = activeTab === id
          return (
            <button
              key={id}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(id)}
              title={label}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium flex-shrink-0',
                'transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500',
                isActive
                  ? 'bg-surface-800 text-surface-100'
                  : 'text-surface-500 hover:text-surface-300 hover:bg-surface-800/60',
              )}
            >
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{label}</span>
            </button>
          )
        })}
      </div>

      {/* Active sub-tab content */}
      <div className="flex-1 min-h-0 overflow-auto">
        {activeTab === 'traces' && <TracesList />}
        {activeTab === 'context' && <ContextInspector />}
        {activeTab === 'sop-sessions' && <SessionReplay />}
        {activeTab === 'sop-judge' &&
          (selectedTraceId ? (
            <JudgeVariance traceId={selectedTraceId} />
          ) : (
            <EmptyState message="Select a trace from the Traces tab." />
          ))}
        {activeTab === 'sop-prompt' &&
          (selectedTraceId && selectedStepId ? (
            <PromptInspector traceId={selectedTraceId} stepId={selectedStepId} />
          ) : (
            <EmptyState message="Select a trace+step from the Traces tab." />
          ))}
        {activeTab === 'sop-timeline' &&
          (selectedTraceId ? (
            <CompactionTimeline traceId={selectedTraceId} />
          ) : (
            <EmptyState message="Select a trace from the Traces tab." />
          ))}
      </div>
    </div>
  )
}
