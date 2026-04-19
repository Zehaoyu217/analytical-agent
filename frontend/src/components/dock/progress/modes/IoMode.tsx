import { useChatStore } from '@/lib/store'
import type { ProgressStep } from '@/lib/selectors/progressSteps'

interface IoModeProps {
  step: ProgressStep
}

/**
 * INPUT/OUTPUT view for a single step. For Python execution this is the script
 * (stdin) and stdout/preview. For other tools it falls back to the recorded
 * input preview and result preview so the same view works generically.
 */
export function IoMode({ step }: IoModeProps) {
  const entry = useChatStore((s) =>
    s.toolCallLog.find((t) => t.id === step.toolCallIds[0]),
  )

  if (!entry) {
    return <div className="cockpit-trace__empty">no input/output captured</div>
  }

  const input = entry.inputPreview?.trim() ?? ''
  const output = (entry.stdout ?? entry.preview ?? '').trim()

  return (
    <div className="flex flex-col gap-3">
      <section>
        <div className="label-cap mb-1">Input</div>
        {input ? (
          <pre className="mono whitespace-pre-wrap break-words rounded border border-line-2 bg-bg-0 p-2 text-[11.5px] leading-[1.5] text-fg-1">
            {input}
          </pre>
        ) : (
          <div className="mono text-[11px] text-fg-3">no input recorded</div>
        )}
      </section>
      <section>
        <div className="label-cap mb-1">Output</div>
        {output ? (
          <pre className="mono whitespace-pre-wrap break-words rounded border border-line-2 bg-bg-0 p-2 text-[11.5px] leading-[1.5] text-fg-1">
            {output}
          </pre>
        ) : (
          <div className="mono text-[11px] text-fg-3">
            {entry.status === 'pending' ? 'running…' : 'no output captured'}
          </div>
        )}
      </section>
    </div>
  )
}
