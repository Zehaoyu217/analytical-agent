import { cn } from '@/lib/utils'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string
}

/**
 * Tiny shimmer placeholder. Kept here (not in shadcn's ui/) because nothing
 * else needs it yet and it avoids pulling in a full ui kit during P2.
 */
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-[shimmer_2s_linear_infinite] rounded-md bg-surface-800/60',
        'bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.04),transparent)] bg-[length:200%_100%]',
        className,
      )}
      {...props}
    />
  )
}
