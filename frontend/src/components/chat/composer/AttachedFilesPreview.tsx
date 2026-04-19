import { Paperclip, X } from 'lucide-react'
import { useChatStore } from '@/lib/store'

interface AttachedFilesPreviewProps {
  conversationId: string
}

export function AttachedFilesPreview({ conversationId }: AttachedFilesPreviewProps) {
  const files = useChatStore(
    (s) => s.conversations.find((c) => c.id === conversationId)?.attachedFiles,
  )
  const removeAttachedFile = useChatStore((s) => s.removeAttachedFile)
  if (!files || files.length === 0) return null
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {files.map((f) => (
        <span
          key={f.id}
          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11.5px]"
          style={{
            borderColor: 'var(--line-2)',
            background: 'var(--bg-2)',
            color: 'var(--fg-1)',
          }}
        >
          <Paperclip size={11} style={{ color: 'var(--fg-2)' }} />
          <span className="mono">{f.name}</span>
          <button
            type="button"
            aria-label={`remove ${f.name}`}
            onClick={() => removeAttachedFile(conversationId, f.id)}
            className="ml-0.5 flex h-3 w-3 items-center justify-center rounded-[2px]"
            style={{ color: 'var(--fg-3)' }}
          >
            <X size={9} />
          </button>
        </span>
      ))}
    </div>
  )
}
