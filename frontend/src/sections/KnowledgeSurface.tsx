import { useEffect, type ReactNode } from 'react'
import { CheckCircle2, Download, Network, Sprout, Upload } from 'lucide-react'
import { SurfacePage } from '@/components/surface/SurfacePage'
import { DrawerSlot } from '@/components/surface/DrawerSlot'
import { WikiTree } from '@/components/wiki/WikiTree'
import { WikiArticle } from '@/components/wiki/WikiArticle'
import { GraphPanel } from '@/components/graph/GraphPanel'
import { IngestPanel } from '@/components/ingest/IngestPanel'
import { DigestPanel } from '@/components/digest/DigestPanel'
import { GardenerPanel } from '@/components/gardener/GardenerPanel'
import { useSurfacesStore } from '@/lib/surfaces-store'
import {
  formatAgo,
  usePipelineStore,
  type DigestResultSummary,
  type GardenerResultSummary,
  type IngestResultSummary,
  type MaintainResultSummary,
  type PhaseState,
  type PipelineStatus,
} from '@/lib/pipeline-store'
import type { PipelinePhase } from '@/components/pipeline/PipelineAction'
import { cn } from '@/lib/utils'

const REFRESH_INTERVAL_MS = 30_000

export function KnowledgeSurface() {
  const drawer = useSurfacesStore((s) => s.knowledgeDrawer)
  const setDrawer = useSurfacesStore((s) => s.setKnowledgeDrawer)
  const selected = useSurfacesStore((s) => s.selectedWikiPath)
  const setSelected = useSurfacesStore((s) => s.setSelectedWikiPath)
  const closeDrawer = () => setDrawer(null)

  const ingest = usePipelineStore((s) => s.ingest)
  const digest = usePipelineStore((s) => s.digest)
  const maintain = usePipelineStore((s) => s.maintain)
  const gardener = usePipelineStore((s) => s.gardener)
  const digestPending = usePipelineStore((s) => s.digestPending)
  const refreshStatus = usePipelineStore((s) => s.refreshStatus)
  const runDigest = usePipelineStore((s) => s.runDigest)
  const runMaintain = usePipelineStore((s) => s.runMaintain)

  useEffect(() => {
    void refreshStatus()
    const id = window.setInterval(() => void refreshStatus(), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [refreshStatus])

  const handleDigest = async (): Promise<void> => {
    const result = await runDigest()
    if (result && result.entries > 0) setDrawer('digest')
  }

  const handleMaintain = async (): Promise<void> => {
    await runMaintain()
  }

  const digestDimmed = digestPending === 0
  const maintainDimmed = isMaintainClean(maintain.lastResult)

  const toolbar = (
    <div
      role="toolbar"
      aria-label="Knowledge pipeline"
      className="flex items-center gap-1.5"
    >
      <PipelineToolbarButton
        phase="ingest"
        label="Ingest"
        icon={<Upload size={13} aria-hidden />}
        state={ingest}
        onClick={() => setDrawer('ingest')}
      />
      <PipelineToolbarButton
        phase="digest"
        label="Digest"
        icon={<Download size={13} aria-hidden />}
        state={digest}
        onClick={handleDigest}
        dimmed={digestDimmed}
        dimmedHint={digestDimmed ? 'Nothing pending to digest' : undefined}
      />
      <PipelineToolbarButton
        phase="maintain"
        label="Maintain"
        icon={<CheckCircle2 size={13} aria-hidden />}
        state={maintain}
        onClick={handleMaintain}
        dimmed={maintainDimmed}
        dimmedHint={maintainDimmed ? 'Nothing to maintain' : undefined}
      />
      <PipelineToolbarButton
        phase="gardener"
        label="Tend"
        icon={<Sprout size={13} aria-hidden />}
        state={gardener}
        onClick={() => setDrawer('gardener')}
      />
      <span aria-hidden className="mx-1 h-5 w-px bg-line" />
      <ToolbarToggleButton
        active={drawer === 'graph'}
        onClick={() => setDrawer(drawer === 'graph' ? null : 'graph')}
        icon={<Network size={13} aria-hidden />}
        label="Graph"
      />
    </div>
  )

  const drawerContent =
    drawer === 'ingest' ? (
      <DrawerSlot eyebrow="KNOWLEDGE" title="Ingest" onClose={closeDrawer}>
        <IngestPanel open onClose={closeDrawer} embedded />
      </DrawerSlot>
    ) : drawer === 'digest' ? (
      <DrawerSlot eyebrow="KNOWLEDGE" title="Digest" onClose={closeDrawer}>
        <DigestPanel open onClose={closeDrawer} embedded />
      </DrawerSlot>
    ) : drawer === 'graph' ? (
      <DrawerSlot eyebrow="KNOWLEDGE" title="Second-Brain Graph" onClose={closeDrawer}>
        <GraphPanel open onClose={closeDrawer} embedded />
      </DrawerSlot>
    ) : drawer === 'gardener' ? (
      <DrawerSlot eyebrow="KNOWLEDGE" title="Gardener" onClose={closeDrawer}>
        <GardenerPanel open onClose={closeDrawer} embedded />
      </DrawerSlot>
    ) : undefined

  return (
    <SurfacePage
      eyebrow="WIKI"
      title="Knowledge"
      toolbar={toolbar}
      drawer={drawerContent}
      drawerOpen={drawer !== null}
      bodyClassName="!overflow-hidden"
    >
      <div className="flex h-full flex-col overflow-hidden">
        <div className="grid flex-1 grid-cols-[260px_1fr] overflow-hidden">
          <div className="overflow-hidden border-r border-line">
            <WikiTree selectedPath={selected} onSelect={setSelected} />
          </div>
          <div className="overflow-hidden">
            <WikiArticle path={selected} onNavigate={setSelected} />
          </div>
        </div>
      </div>
    </SurfacePage>
  )
}

interface PipelineToolbarButtonProps {
  phase: PipelinePhase
  label: string
  icon: ReactNode
  state: PhaseState
  onClick: () => void | Promise<void>
  dimmed?: boolean
  dimmedHint?: string
}

function PipelineToolbarButton({
  phase,
  label,
  icon,
  state,
  onClick,
  dimmed = false,
  dimmedHint,
}: PipelineToolbarButtonProps) {
  const running = state.status === 'running'
  const errored = state.status === 'error'
  const done = state.status === 'done'
  const idle = state.status === 'idle'
  const showDimmed = dimmed && idle
  const baseDetail = buildDetail(phase, state)
  const detail = showDimmed && dimmedHint ? `${dimmedHint} · ${baseDetail}` : baseDetail
  const ariaLabel = `${label} — ${detail}`

  return (
    <button
      type="button"
      onClick={() => {
        if (running || showDimmed) return
        void onClick()
      }}
      disabled={running || showDimmed}
      aria-busy={running}
      aria-disabled={showDimmed || undefined}
      aria-label={ariaLabel}
      title={detail}
      data-phase={phase}
      data-status={state.status}
      data-dimmed={showDimmed ? 'true' : undefined}
      className={cn(
        'flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-[12px] transition-colors focus-ring',
        running && 'cursor-wait border-line bg-bg-1 text-fg-1 opacity-80',
        done && 'border-acc-line bg-acc-dim text-acc',
        errored && 'border-red-500/40 bg-red-500/10 text-red-400',
        !running &&
          !done &&
          !errored &&
          !showDimmed &&
          'border-line bg-bg-1 text-fg-1 hover:bg-bg-2 hover:text-fg-0',
        showDimmed &&
          'cursor-not-allowed border-line/60 bg-bg-1/60 text-fg-3 opacity-60',
      )}
    >
      <span
        aria-hidden
        className={cn('flex items-center', running && 'animate-spin')}
      >
        {icon}
      </span>
      <span>{label}</span>
      <StatusDot status={state.status} />
    </button>
  )
}

function StatusDot({ status }: { status: PipelineStatus }) {
  if (status === 'idle') return null
  return (
    <span
      aria-hidden
      data-testid="pipeline-status-dot"
      className={cn(
        'ml-0.5 inline-block h-1.5 w-1.5 rounded-full',
        status === 'running' && 'animate-pulse bg-fg-2',
        status === 'done' && 'bg-acc',
        status === 'error' && 'bg-red-400',
      )}
    />
  )
}

function isMaintainClean(result: MaintainResultSummary | null): boolean {
  if (!result) return false
  return (
    result.lint_errors === 0 &&
    result.lint_warnings === 0 &&
    result.stale_count === 0 &&
    result.open_contradictions === 0 &&
    result.habit_proposals === 0
  )
}

function buildDetail(phase: PipelinePhase, state: PhaseState): string {
  if (state.status === 'running') return 'Running…'
  if (state.status === 'error') return state.errorMessage ?? 'Error'
  const ago = formatAgo(state.lastRunAt)
  const result = state.lastResult
  if (!result) return ago === 'never' ? 'Not run yet' : `Last run: ${ago}`
  if (phase === 'ingest') {
    const r = result as IngestResultSummary
    const count = r.sources_added
    return `Last run: ${ago} · ${count} source${count === 1 ? '' : 's'} added`
  }
  if (phase === 'digest') {
    const r = result as DigestResultSummary
    const pending = r.pending > 0 ? ` · ${r.pending} pending` : ''
    return `Last run: ${ago} · ${r.entries} ${r.entries === 1 ? 'entry' : 'entries'}${pending}`
  }
  if (phase === 'gardener') {
    const r = result as GardenerResultSummary
    const cost = r.total_cost_usd > 0 ? ` · $${r.total_cost_usd.toFixed(4)}` : ''
    return `Last run: ${ago} · ${r.proposals_added} proposal${r.proposals_added === 1 ? '' : 's'}${cost}`
  }
  const r = result as MaintainResultSummary
  if (r.lint_errors) return `Last run: ${ago} · ${r.lint_errors} lint err`
  if (r.lint_warnings) return `Last run: ${ago} · ${r.lint_warnings} lint warn`
  return `Last run: ${ago} · clean`
}

interface ToolbarToggleButtonProps {
  active: boolean
  onClick: () => void
  icon: ReactNode
  label: string
}

function ToolbarToggleButton({
  active,
  onClick,
  icon,
  label,
}: ToolbarToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-[12px]',
        'transition-colors focus-ring',
        active
          ? 'border-acc-line bg-acc-dim text-acc'
          : 'border-line bg-bg-1 text-fg-1 hover:bg-bg-2 hover:text-fg-0',
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
