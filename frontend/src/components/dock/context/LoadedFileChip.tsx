import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LoadedFile } from '@/lib/store'

interface LoadedFileChipProps {
  file: LoadedFile
  onUnload?: (id: string) => void
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function LoadedFileChip({ file, onUnload }: LoadedFileChipProps) {
  return (
    <div className={cn('flex items-center gap-2 rounded bg-bg-2 px-2 py-1')}>
      <span className="mono rounded bg-bg-1 px-1 text-[9.5px] uppercase text-fg-2">{file.kind}</span>
      <span className="flex-1 truncate text-[12px] text-fg-1">{file.name}</span>
      <span className="mono text-[10.5px] text-fg-3">{fmtSize(file.size)}</span>
      {onUnload && (
        <button
          type="button"
          aria-label={`Unload ${file.name}`}
          onClick={() => onUnload(file.id)}
          className="inline-flex h-4 w-4 items-center justify-center rounded text-fg-3 hover:bg-bg-1 hover:text-fg-0 focus-ring"
        >
          <X className="h-3 w-3" aria-hidden />
        </button>
      )}
    </div>
  )
}
