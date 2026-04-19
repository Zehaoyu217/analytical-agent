import { cn } from '@/lib/utils'

interface ContextBudgetBarProps {
  totalTokens: number
  budgetTokens: number
}

function fmtK(n: number): string {
  return n >= 1000 ? `${Math.round(n / 100) / 10}k` : `${n}`
}

export function ContextBudgetBar({ totalTokens, budgetTokens }: ContextBudgetBarProps) {
  const pct = Math.min(100, Math.round((totalTokens / Math.max(1, budgetTokens)) * 100))
  const tone = pct >= 85 ? 'err' : pct >= 60 ? 'warn' : 'ok'
  return (
    <div aria-label="Context budget">
      <div className="mono mb-1 flex items-center justify-between text-[10.5px] text-fg-3">
        <span>{fmtK(totalTokens)}</span>
        <span>{fmtK(budgetTokens)}</span>
      </div>
      <div
        data-tone={tone}
        className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-2"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            'h-full transition-[width]',
            tone === 'ok' && 'bg-fg-2',
            tone === 'warn' && 'bg-warn',
            tone === 'err' && 'bg-err',
          )}
          style={{ width: `${pct}%` }}
        />
        <div
          aria-hidden
          className="absolute top-0 h-full w-px bg-line-2"
          style={{ left: '80%' }}
        />
      </div>
    </div>
  )
}
