import { useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { ThemeProvider } from '@/components/layout/ThemeProvider'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { ChatWindow } from './ChatWindow'
import { ChatInput } from './ChatInput'

function ChatLayoutInner() {
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const createConversation = useChatStore((s) => s.createConversation)

  // Ensure we always have at least one conversation so the input area is usable.
  useEffect(() => {
    if (conversations.length === 0) {
      createConversation()
    } else if (
      !activeConversationId ||
      !conversations.some((c) => c.id === activeConversationId)
    ) {
      // Fall back to the most recent conversation if the active id is stale.
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
    <div className="flex h-dvh bg-surface-950 text-surface-100 overflow-hidden">
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
    </div>
  )
}

export function ChatLayout() {
  return (
    <ThemeProvider>
      <ChatLayoutInner />
    </ThemeProvider>
  )
}
