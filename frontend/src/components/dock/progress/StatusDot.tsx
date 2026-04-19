import { cn } from '@/lib/utils'

interface StatusDotProps {
  status: 'queued' | 'running' | 'ok' | 'err'
  className?: string
}

export function StatusDot({ status, className }: StatusDotProps) {
  return (
    <span
      data-status={status}
      aria-label={`status: ${status}`}
      className={cn(
        'inline-block h-1.5 w-1.5 rounded-full',
        status === 'queued' && 'bg-fg-3',
        status === 'running' && 'bg-acc animate-pulse',
        status === 'ok' && 'bg-ok',
        status === 'err' && 'bg-err',
        className,
      )}
    />
  )
}
