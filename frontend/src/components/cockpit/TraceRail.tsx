import { useChatStore } from '@/lib/store'
import { useRightRailStore, type TraceTab } from '@/lib/right-rail-store'
import { TimelineMode } from '@/components/dock/progress/modes/TimelineMode'
import { ContextMode } from '@/components/dock/progress/modes/ContextMode'
import { RawMode } from '@/components/dock/progress/modes/RawMode'

interface TabDef {
  id: TraceTab
  label: string
}

const TABS: TabDef[] = [
  { id: 'timeline', label: 'TIMELINE' },
  { id: 'context', label: 'CONTEXT' },
  { id: 'raw', label: 'RAW' },
]

export function TraceRail() {
  const tab = useRightRailStore((s) => s.traceTab)
  const setTab = useRightRailStore((s) => s.setTraceTab)
  const toolCallLog = useChatStore((s) => s.toolCallLog)
  const activeId = useChatStore((s) => s.activeConversationId)
  const messageCount = useChatStore(
    (s) => s.conversations.find((c) => c.id === activeId)?.messages.length ?? 0,
  )
  const eventCount = toolCallLog.length + messageCount

  return (
    <div className="cockpit-trace" role="region" aria-label="Agent trace">
      <div className="cockpit-trace__tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className="cockpit-trace__tab"
            data-active={tab === t.id}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        <div className="cockpit-trace__count">{eventCount} events</div>
      </div>
      {tab === 'timeline' && <TimelineMode />}
      {tab === 'context' && <ContextMode />}
      {tab === 'raw' && <RawMode />}
      <div className="cockpit-trace__footer">
        <span>auto-scroll on</span>
        <span>⌘\ to switch</span>
      </div>
    </div>
  )
}
