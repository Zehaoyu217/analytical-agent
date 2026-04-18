import { useRightRailStore, type RailMode } from '@/lib/right-rail-store'
import { TraceRail } from './TraceRail'
import { GraphPanel } from '@/components/graph/GraphPanel'
import { DigestPanel } from '@/components/digest/DigestPanel'
import { IngestPanel } from '@/components/ingest/IngestPanel'

const LABELS: Record<Exclude<RailMode, 'trace'>, string> = {
  graph: 'GRAPH',
  digest: 'DIGEST',
  ingest: 'INGEST',
}

export function RightRail() {
  const mode = useRightRailStore((s) => s.mode)
  const returnToTrace = useRightRailStore((s) => s.returnToTrace)

  if (mode === 'trace') {
    return <TraceRail />
  }

  return (
    <div className="cockpit-summon" role="region" aria-label={LABELS[mode]}>
      <div className="cockpit-summon__header">
        <button
          type="button"
          className="cockpit-summon__back"
          onClick={returnToTrace}
          aria-label="back to trace"
        >
          ←
        </button>
        <span className="cockpit-summon__label">{LABELS[mode]}</span>
        <span className="cockpit-summon__hidden-note">trace hidden</span>
      </div>
      <div className="cockpit-summon__body">
        {mode === 'graph' && (
          <GraphPanel open onClose={returnToTrace} embedded />
        )}
        {mode === 'digest' && (
          <DigestPanel open onClose={returnToTrace} embedded />
        )}
        {mode === 'ingest' && (
          <IngestPanel open onClose={returnToTrace} embedded />
        )}
      </div>
    </div>
  )
}
