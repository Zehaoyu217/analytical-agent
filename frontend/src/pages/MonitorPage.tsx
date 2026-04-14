import { ChevronLeft } from 'lucide-react'
import { SessionHeader } from '@/components/monitor/SessionHeader'
import { TraceTimeline } from '@/components/monitor/TraceTimeline'
import { EventDetailDrawer } from '@/components/monitor/EventDetailDrawer'

interface MonitorPageProps {
  sessionId: string
}

export function MonitorPage({ sessionId }: MonitorPageProps): React.ReactElement {
  function handleBack(): void {
    window.location.hash = ''
  }

  return (
    <div className="flex flex-col h-dvh bg-[#09090b] text-surface-100 overflow-hidden">
      {/* Session header bar */}
      <div className="flex items-center h-14 shrink-0 border-b border-surface-800 bg-[#09090b]">
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center justify-center w-10 h-10 ml-2 mr-1 rounded text-surface-400 hover:text-surface-100 hover:bg-surface-800 transition-colors shrink-0"
          aria-label="Back to chat"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="flex-1 min-w-0 h-full">
          <SessionHeader sessionId={sessionId} />
        </div>
      </div>

      {/* Trace timeline — grows to fill remaining space */}
      <div className="flex-1 min-h-0">
        <TraceTimeline sessionId={sessionId} />
      </div>

      {/* Event detail drawer — fixed height at bottom */}
      <EventDetailDrawer />
    </div>
  )
}
