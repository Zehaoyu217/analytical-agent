import { useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { RightPanel } from '@/components/right-panel/RightPanel'
import { ChatWindow } from './ChatWindow'
import { ChatInput } from './ChatInput'

export function ChatLayout() {
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const createConversation = useChatStore((s) => s.createConversation)
  const createConversationRemote = useChatStore((s) => s.createConversationRemote)

  // Ensure we always have at least one conversation so the input area is usable.
  // Try remote-first so server id is source of truth — future appendTurn() calls
  // depend on the conversation existing on the backend. Fall back to a local-only
  // conversation if the backend is unreachable (offline dev).
  useEffect(() => {
    if (conversations.length === 0) {
      createConversationRemote('New Conversation').catch(() => {
        createConversation()
      })
    } else if (
      !activeConversationId ||
      !conversations.some((c) => c.id === activeConversationId)
    ) {
      useChatStore.getState().setActiveConversation(conversations[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Global shortcut: Cmd/Ctrl+Shift+D toggles the DevTools sidebar tab.
  // If closed or on a different tab → open sidebar and focus DevTools.
  // If already on DevTools → collapse the sidebar.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isShortcut =
        (e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'D' || e.key === 'd')
      if (!isShortcut) return
      e.preventDefault()
      const state = useChatStore.getState()
      if (state.sidebarOpen && state.sidebarTab === 'devtools') {
        state.toggleSidebar()
      } else {
        state.focusDevTools()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="flex h-full bg-surface-950 text-surface-100 overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Header />
        <main
          id="main-content"
          aria-label="Chat"
          className="flex flex-col flex-1 min-h-0"
        >
          {activeConversationId ? (
            <>
              <ChatWindow conversationId={activeConversationId} />
              <ChatInput conversationId={activeConversationId} />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-surface-500">
              Select or create a conversation
            </div>
          )}
        </main>
      </div>
      <RightPanel />
    </div>
  )
}

