import { useRef, useState } from 'react'
import { Loader2, Paperclip } from 'lucide-react'
import { useChatStore } from '@/lib/store'

const ICON_BTN = 'flex h-7 w-7 items-center justify-center rounded-md transition-colors'
const ACCEPTED = '.csv,.parquet,.json,.jsonl,.ndjson,.xlsx,.xls'

interface AttachButtonProps {
  conversationId: string
}

export function AttachButton({ conversationId }: AttachButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const uploadDataset = useChatStore((s) => s.uploadDataset)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // always clear so the same file can be picked again
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      await uploadDataset(conversationId, file)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      // Surface loudly — the paperclip looking "done" after a failure would
      // leave the user thinking the file is available to the agent when it
      // isn't. Alert is blunt but honest.
      window.alert(`Upload failed: ${msg}`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={onPick}
      />
      <button
        type="button"
        title={error ? `Last upload failed: ${error}` : 'Upload dataset (CSV, XLSX, Parquet, JSON)'}
        aria-label="Upload dataset"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className={ICON_BTN}
        style={{ color: uploading ? 'var(--acc)' : 'var(--fg-2)' }}
      >
        {uploading ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Paperclip size={14} />
        )}
      </button>
    </>
  )
}
