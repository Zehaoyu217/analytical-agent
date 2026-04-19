import { useMemo } from 'react'
import { useChatStore } from '@/lib/store'
import { selectProgressSteps } from '@/lib/selectors/progressSteps'
import { StepCard } from './progress/StepCard'

export function DockProgress() {
  const log = useChatStore((s) => s.toolCallLog)
  const steps = useMemo(() => selectProgressSteps(log), [log])

  const running = steps.filter((s) => s.status === 'running').length
  const ok = steps.filter((s) => s.status === 'ok').length

  if (steps.length === 0) {
    return (
      <div className="flex h-full flex-col gap-2 p-4">
        <div className="label-cap">No steps yet</div>
        <div className="mono text-[10.5px] text-fg-3">Waiting for agent…</div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col" aria-label="Agent progress">
      <div className="flex items-center justify-between border-b border-line-2 px-3 py-2">
        <div className="label-cap">Progress</div>
        <div className="mono text-[10.5px] text-fg-3">
          {running} running · {ok} done · {steps.length} total
        </div>
      </div>
      {/* Marching-ants activity bar — only while a step is running */}
      <div className="relative h-px bg-line-2">
        {running > 0 && <div className="ants absolute inset-0" />}
      </div>
      <div className="flex-1 overflow-y-auto">
        {steps.map((s) => (
          <StepCard key={s.id} step={s} />
        ))}
      </div>
    </div>
  )
}
