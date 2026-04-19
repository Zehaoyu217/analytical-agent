import { cn } from '@/lib/utils'

interface StatusDotProps {
  status: 'queued' | 'running' | 'ok' | 'err'
  className?: string
}

/**
 * Step indicator matching the DS-Agent handoff (design_handoff_ds_agent/progress.jsx):
 * - queued  → outlined dot
 * - running → outlined ring with concentric pulse + inner spinner
 * - ok      → filled accent with draw-on checkmark
 * - err     → filled error with X glyph
 */
export function StatusDot({ status, className }: StatusDotProps) {
  if (status === 'running') {
    return (
      <span
        data-status="running"
        aria-label="status: running"
        className={cn(
          'pulse-ring relative inline-flex h-[21px] w-[21px] flex-shrink-0 items-center justify-center rounded-full border border-acc bg-bg-1',
          className,
        )}
        style={{ boxShadow: '0 0 0 3px var(--acc-dim)' }}
      >
        <span
          className="spin block rounded-full"
          style={{
            width: 11,
            height: 11,
            border: '1.5px solid var(--acc-dim)',
            borderTopColor: 'var(--acc)',
            borderRightColor: 'var(--acc)',
          }}
        />
      </span>
    )
  }

  if (status === 'ok') {
    return (
      <span
        data-status="ok"
        aria-label="status: ok"
        className={cn(
          'scale-in inline-flex h-[21px] w-[21px] flex-shrink-0 items-center justify-center rounded-full border border-ok bg-ok text-bg-0',
          className,
        )}
      >
        <svg className="draw-check" width="11" height="11" viewBox="0 0 16 16" fill="none">
          <path
            d="M3 8.5 6.5 12 13 4.5"
            stroke="currentColor"
            strokeWidth="2.25"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    )
  }

  if (status === 'err') {
    return (
      <span
        data-status="err"
        aria-label="status: err"
        className={cn(
          'scale-in inline-flex h-[21px] w-[21px] flex-shrink-0 items-center justify-center rounded-full border border-err bg-err text-bg-0',
          className,
        )}
      >
        <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
          <path
            d="M4 4 12 12 M12 4 4 12"
            stroke="currentColor"
            strokeWidth="2.25"
            strokeLinecap="round"
          />
        </svg>
      </span>
    )
  }

  // queued
  return (
    <span
      data-status="queued"
      aria-label="status: queued"
      className={cn(
        'inline-flex h-[21px] w-[21px] flex-shrink-0 items-center justify-center rounded-full border border-line bg-bg-1',
        className,
      )}
    >
      <span className="block h-[5px] w-[5px] rounded-full bg-fg-3" />
    </span>
  )
}
