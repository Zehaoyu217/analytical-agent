import { File, FileCode, FileText, Image, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FileAttachmentProps {
  file: File
  onRemove?: () => void
  className?: string
}

function getFileIcon(type: string) {
  if (type.startsWith('image/')) return Image
  if (type.startsWith('text/')) return FileText
  if (
    type.includes('javascript') ||
    type.includes('typescript') ||
    type.includes('json') ||
    type.includes('xml')
  ) {
    return FileCode
  }
  return File
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

/**
 * UI-only preview for an attached file. Wiring into `ChatInput` is deferred to
 * P4 — this component exists now so the import graph is stable and styling
 * lands with the rest of the message pipeline.
 */
export function FileAttachment({ file, onRemove, className }: FileAttachmentProps) {
  const Icon = getFileIcon(file.type)
  const isImage = file.type.startsWith('image/')

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 px-2.5 py-1.5 rounded-lg',
        'bg-surface-700 border border-surface-600 text-sm',
        'max-w-48 hover:border-surface-500 transition-colors',
        className,
      )}
    >
      <Icon className="w-3.5 h-3.5 text-surface-400 flex-shrink-0" aria-hidden />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-surface-200 truncate">{file.name}</p>
        {!isImage && (
          <p className="text-xs text-surface-500">{formatFileSize(file.size)}</p>
        )}
      </div>
      {onRemove && (
        <button
          onClick={onRemove}
          aria-label={`Remove ${file.name}`}
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded text-surface-500 hover:text-surface-300 hover:bg-surface-600 transition-all"
        >
          <X className="w-3 h-3" aria-hidden />
        </button>
      )}
    </div>
  )
}
