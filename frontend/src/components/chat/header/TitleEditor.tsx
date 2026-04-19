import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/lib/store'

interface TitleEditorProps {
  conversationId: string
  triggerSignal?: number
}

export function TitleEditor({ conversationId, triggerSignal }: TitleEditorProps) {
  const title = useChatStore(
    (s) => s.conversations.find((c) => c.id === conversationId)?.title ?? '',
  )
  const update = useChatStore((s) => s.updateConversationTitle)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!editing) setDraft(title)
  }, [title, editing])

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [editing])

  useEffect(() => {
    if (triggerSignal !== undefined && triggerSignal > 0) {
      setEditing(true)
    }
  }, [triggerSignal])

  const commit = () => {
    update(conversationId, draft)
    setEditing(false)
  }

  const cancel = () => {
    setDraft(title)
    setEditing(false)
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            commit()
          }
          if (e.key === 'Escape') {
            e.preventDefault()
            cancel()
          }
        }}
        maxLength={200}
        className="bg-transparent text-[14.5px] font-semibold tracking-[-0.01em] outline-none"
        style={{ color: 'var(--fg-0)', minWidth: 120 }}
      />
    )
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className="text-[14.5px] font-semibold tracking-[-0.01em]"
      style={{ color: 'var(--fg-0)' }}
    >
      {title || 'Untitled'}
    </button>
  )
}
