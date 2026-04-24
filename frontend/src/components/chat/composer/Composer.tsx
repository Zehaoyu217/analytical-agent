import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Send, Square } from 'lucide-react'
import { useChatStore } from '@/lib/store'
import { useCommandRegistry } from '@/hooks/useCommandRegistry'
import { backend, type SlashCommand } from '@/lib/api-backend'
import { MAX_MESSAGE_LENGTH } from '@/lib/constants'
import { filterSlashCommands } from './slash'
import { SlashMenu } from './SlashMenu'
import { PlanToggle } from './PlanToggle'
import { IconRow } from './IconRow'
import { ModelPicker } from './ModelPicker'
import { ExtendedToggle } from './ExtendedToggle'
import { AttachedFilesPreview } from './AttachedFilesPreview'
import { useComposerSubmit } from './useComposerSubmit'

interface ComposerProps {
  conversationId: string
}

export function Composer({ conversationId }: ComposerProps) {
  const [input, setInput] = useState('')
  const [slashCommands, setSlashCommands] = useState<SlashCommand[] | null>(null)
  const [slashHighlight, setSlashHighlight] = useState(0)
  const [slashLocked, setSlashLocked] = useState(false)
  const slashFetchRef = useRef<Promise<SlashCommand[]> | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const draftInput = useChatStore((s) => s.draftInput)
  const setDraftInput = useChatStore((s) => s.setDraftInput)
  const planMode = useChatStore((s) => s.planMode)
  const togglePlanMode = useChatStore((s) => s.togglePlanMode)
  const clearActiveConversation = useChatStore((s) => s.clearActiveConversation)
  const createConversation = useChatStore((s) => s.createConversation)
  const setActiveSection = useChatStore((s) => s.setActiveSection)
  const duplicateConversation = useChatStore((s) => s.duplicateConversation)
  const frozen = useChatStore((s) => {
    const conv = s.conversations.find((c) => c.id === conversationId)
    return typeof conv?.frozenAt === 'number' && conv.frozenAt > 0
  })
  const { openHelp } = useCommandRegistry()
  const { submit, stop, isSending } = useComposerSubmit(conversationId)

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  useEffect(() => {
    if (!draftInput) return
    setInput(draftInput)
    setDraftInput('')
    requestAnimationFrame(() => {
      adjustHeight()
      textareaRef.current?.focus()
    })
  }, [draftInput, setDraftInput, adjustHeight])

  const showSlashMenu = input.startsWith('/') && !slashLocked
  const slashQuery = showSlashMenu ? input.slice(1) : ''
  const filtered = useMemo(
    () =>
      showSlashMenu && slashCommands ? filterSlashCommands(slashCommands, slashQuery) : [],
    [slashCommands, slashQuery, showSlashMenu],
  )

  useEffect(() => {
    if (slashHighlight >= filtered.length) setSlashHighlight(0)
  }, [filtered.length, slashHighlight])

  useEffect(() => {
    if (!showSlashMenu || slashCommands !== null || slashFetchRef.current) return
    slashFetchRef.current = backend.slash
      .list()
      .then((list) => {
        setSlashCommands(list)
        return list
      })
      .catch((err: unknown) => {
        window.console?.warn?.('slash list failed', err)
        setSlashCommands([])
        return []
      })
  }, [showSlashMenu, slashCommands])

  const pickSlashCommand = useCallback(
    (cmd: SlashCommand) => {
      switch (cmd.id) {
        case 'help':
          openHelp()
          break
        case 'clear':
          clearActiveConversation()
          break
        case 'new':
          createConversation()
          break
        case 'settings':
          setActiveSection('settings')
          break
      }
      setInput('')
      setSlashLocked(true)
      requestAnimationFrame(() => {
        textareaRef.current?.focus()
        adjustHeight()
      })
    },
    [openHelp, clearActiveConversation, createConversation, setActiveSection, adjustHeight],
  )

  const handleSend = useCallback(async () => {
    const text = input
    setInput('')
    requestAnimationFrame(() => adjustHeight())
    await submit(text)
  }, [input, submit, adjustHeight])

  const hasText = input.trim().length > 0

  if (frozen) {
    return (
      <div
        className="rounded-[12px] border p-3 text-[12.5px]"
        style={{
          borderColor: 'var(--line)',
          background: 'var(--bg-1)',
          color: 'var(--fg-2)',
        }}
        role="status"
      >
        <div className="mb-2">
          This conversation is frozen. Duplicate it to continue.
        </div>
        <button
          type="button"
          onClick={() => {
            void duplicateConversation(conversationId).catch((err: unknown) => {
              // eslint-disable-next-line no-console
              console.error('duplicate failed', err)
            })
          }}
          className="rounded-lg px-3 py-1.5 text-[12.5px] font-medium"
          style={{ background: 'var(--acc)', color: 'var(--acc-fg)' }}
        >
          Duplicate
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      {showSlashMenu && (
        <SlashMenu
          commands={filtered}
          highlight={slashHighlight}
          onHover={setSlashHighlight}
          onPick={pickSlashCommand}
        />
      )}
      <div
        className="rounded-[12px] border p-[10px]"
        style={{
          borderColor: 'var(--line)',
          background: 'var(--bg-1)',
          boxShadow: 'var(--shadow-1)',
        }}
      >
        <AttachedFilesPreview conversationId={conversationId} />
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => {
            setInput(e.target.value.slice(0, MAX_MESSAGE_LENGTH))
            setSlashLocked(false)
            adjustHeight()
          }}
          placeholder="Ask the agent anything…"
          className="min-h-[22px] w-full resize-none bg-transparent px-1 pb-0.5 pt-1 text-[14px] leading-[1.55] outline-none"
          style={{ color: 'var(--fg-0)' }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (showSlashMenu && filtered[slashHighlight]) {
                pickSlashCommand(filtered[slashHighlight])
                return
              }
              handleSend()
            }
          }}
        />
        <div className="mt-1 flex items-center gap-1">
          <IconRow conversationId={conversationId} />
          <div
            className="mx-1.5 h-4 w-px"
            style={{ background: 'var(--line-2)' }}
          />
          <ModelPicker conversationId={conversationId} />
          <ExtendedToggle conversationId={conversationId} />
          <PlanToggle enabled={planMode} onToggle={togglePlanMode} />
          <div className="flex-1" />
          <span
            className="mr-1 flex items-center gap-[3px] text-[11px]"
            style={{ color: 'var(--fg-3)' }}
          >
            <span className="kbd">⌘</span>
            <span className="kbd">↵</span>
          </span>
          {isSending ? (
            <button
              type="button"
              onClick={stop}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium"
              style={{ background: 'var(--bg-2)', color: 'var(--fg-1)' }}
            >
              <Square size={12} /> Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!hasText}
              aria-label="Send"
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed"
              style={{
                background: hasText ? 'var(--acc)' : 'var(--bg-2)',
                color: hasText ? 'var(--acc-fg)' : 'var(--fg-3)',
              }}
            >
              Send <Send size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
