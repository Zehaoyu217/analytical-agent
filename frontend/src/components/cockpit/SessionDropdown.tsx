import { useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/store'

interface SessionDropdownProps {
  onClose: () => void
}

export function SessionDropdown({ onClose }: SessionDropdownProps) {
  const conversations = useChatStore((s) => s.conversations)
  const activeId = useChatStore((s) => s.activeConversationId)
  const setActive = useChatStore((s) => s.setActiveConversation)
  const createRemote = useChatStore((s) => s.createConversationRemote)
  const createLocal = useChatStore((s) => s.createConversation)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const recent = conversations.slice(0, 8)

  return (
    <div ref={ref} role="menu" aria-label="Sessions" className="cockpit-dropdown">
      <button
        type="button"
        className="cockpit-dropdown__item cockpit-dropdown__item--new"
        onClick={() => {
          createRemote('New Conversation').catch(() => createLocal())
          onClose()
        }}
      >
        + NEW SESSION <span className="cockpit-dropdown__short">⌘N</span>
      </button>
      <div className="cockpit-dropdown__sep" />
      {recent.map((c) => (
        <button
          key={c.id}
          type="button"
          role="menuitem"
          onClick={() => {
            setActive(c.id)
            onClose()
          }}
          className={
            'cockpit-dropdown__item' +
            (c.id === activeId ? ' cockpit-dropdown__item--active' : '')
          }
        >
          <span className="cockpit-dropdown__short">
            {(c.sessionId || c.id).slice(0, 7)}
          </span>
          <span className="cockpit-dropdown__title">{c.title || 'untitled'}</span>
        </button>
      ))}
      {recent.length === 0 && (
        <div className="cockpit-dropdown__empty">no sessions yet</div>
      )}
    </div>
  )
}
