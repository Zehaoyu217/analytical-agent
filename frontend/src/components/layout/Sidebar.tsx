import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare,
  FolderOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  Wrench,
  Bot,
  Layers,
} from 'lucide-react'
import { useCallback } from 'react'
import { useChatStore, type SidebarTab } from '@/lib/store'
import { cn } from '@/lib/utils'
import { DevToolsTab } from './DevToolsTab'
import { HistoryTab } from '@/components/sidebar/HistoryTab'
import { SettingsTab } from '@/components/sidebar/SettingsTab'
import { FilesTab } from '@/components/sidebar/FilesTab'
import { AgentsTab } from '@/components/sidebar/AgentsTab'
import { SkillsTab } from '@/components/sidebar/SkillsTab'

const COLLAPSED_WIDTH = 60

type TabDef = { id: SidebarTab; icon: React.ElementType; label: string }

const TABS: TabDef[] = [
  { id: 'chats', icon: MessageSquare, label: 'Chats' },
  { id: 'agents', icon: Bot, label: 'Agents' },
  { id: 'skills', icon: Layers, label: 'Skills' },
  { id: 'history', icon: Clock, label: 'History' },
  { id: 'files', icon: FolderOpen, label: 'Files' },
  { id: 'devtools', icon: Wrench, label: 'DevTools' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const sidebarOpen = useChatStore((s) => s.sidebarOpen)
  const sidebarWidth = useChatStore((s) => s.sidebarWidth)
  const sidebarTab = useChatStore((s) => s.sidebarTab)
  const toggleSidebar = useChatStore((s) => s.toggleSidebar)
  const setSidebarTab = useChatStore((s) => s.setSidebarTab)
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)
  const createConversation = useChatStore((s) => s.createConversation)
  const createConversationRemote = useChatStore((s) => s.createConversationRemote)

  // Try remote-first so the server id is the source of truth (which keeps
  // future appendTurn calls valid). If the remote call fails, fall back to
  // the existing in-memory-only flow so the chat UI never breaks.
  const handleCreate = useCallback((): string => {
    // Kick off remote creation; when it resolves the store will contain the
    // new conversation at the head of the list and activeConversationId will
    // point at it.
    createConversationRemote('New Conversation').catch((err: unknown) => {
      if (typeof window !== 'undefined') {
        window.console?.warn?.('create conversation on backend failed', err)
      }
      // Remote failed — fall back to the original in-memory-only path.
      createConversation()
    })
    // Return a usable id immediately. If the store has no active conversation
    // yet (first-ever "New" click before the remote promise resolves), create
    // an optimistic local one so callers never receive an empty string.
    const existing = useChatStore.getState().activeConversationId
    return existing ?? createConversation()
  }, [createConversation, createConversationRemote])

  // Global Cmd/Ctrl+B is now owned by the command registry in App.tsx.

  const handleTabClick = (id: SidebarTab) => {
    if (!sidebarOpen) toggleSidebar()
    setSidebarTab(id)
  }

  return (
    <motion.aside
      className={cn(
        'flex flex-col h-full bg-surface-900 border-r border-surface-800',
        'relative flex-shrink-0 z-20',
      )}
      animate={{ width: sidebarOpen ? sidebarWidth : COLLAPSED_WIDTH }}
      transition={{ duration: 0.2, ease: 'easeInOut' }}
      aria-label="Navigation sidebar"
    >
      {/* Top bar: app name + tabs + collapse toggle */}
      <div
        className={cn(
          'flex border-b border-surface-800 flex-shrink-0',
          sidebarOpen ? 'flex-row items-center' : 'flex-col items-center py-2 gap-1',
        )}
      >
        {sidebarOpen && (
          <span className="flex-1 text-sm font-semibold text-surface-100 px-4 py-3 truncate">
            Analytical Agent
          </span>
        )}

        <div
          className={cn(
            'flex',
            sidebarOpen
              ? 'flex-row items-center gap-0.5 pr-1 py-1.5'
              : 'flex-col w-full px-1.5 gap-0.5',
          )}
        >
          {TABS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => handleTabClick(id)}
              title={label}
              aria-label={label}
              className={cn(
                'flex items-center gap-2 rounded-md text-xs font-medium transition-colors',
                sidebarOpen ? 'px-2.5 py-1.5' : 'w-full justify-center px-0 py-2',
                sidebarOpen && sidebarTab === id
                  ? 'bg-surface-800 text-surface-100'
                  : 'text-surface-500 hover:text-surface-300 hover:bg-surface-800/60',
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              {sidebarOpen && <span>{label}</span>}
            </button>
          ))}
        </div>

        <button
          onClick={toggleSidebar}
          title={sidebarOpen ? 'Collapse sidebar (Cmd+B)' : 'Expand sidebar (Cmd+B)'}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          className={cn(
            'p-2 rounded-md text-surface-500 hover:text-surface-300 hover:bg-surface-800/60 transition-colors',
            sidebarOpen ? 'mr-1' : 'my-0.5',
          )}
        >
          {sidebarOpen ? (
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        {sidebarOpen && (
          <motion.div
            key={sidebarTab}
            className="flex-1 flex flex-col min-h-0 overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
          >
            {sidebarTab === 'chats' && (
              <ChatsTab
                conversations={conversations}
                activeConversationId={activeConversationId}
                onSelect={setActiveConversation}
                onCreate={handleCreate}
              />
            )}
            {sidebarTab === 'agents' && <AgentsTab />}
            {sidebarTab === 'skills' && <SkillsTab />}
            {sidebarTab === 'history' && <HistoryTab />}
            {sidebarTab === 'files' && <FilesTab />}
            {sidebarTab === 'devtools' && <DevToolsTab />}
            {sidebarTab === 'settings' && <SettingsTab />}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.aside>
  )
}

interface ChatsTabProps {
  conversations: ReturnType<typeof useChatStore.getState>['conversations']
  activeConversationId: string | null
  onSelect: (id: string) => void
  onCreate: () => string
}

function ChatsTab({
  conversations,
  activeConversationId,
  onSelect,
  onCreate,
}: ChatsTabProps) {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-3 py-2 flex-shrink-0">
        <button
          onClick={() => onCreate()}
          className={cn(
            'w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm',
            'bg-brand-600 text-white hover:bg-brand-700 transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
          )}
        >
          <Plus className="w-4 h-4" aria-hidden="true" />
          <span>New chat</span>
        </button>
      </div>
      <div
        className="flex-1 min-h-0 overflow-y-auto px-2 pb-2 space-y-0.5"
        role="list"
        aria-label="Conversations"
      >
        {conversations.length === 0 ? (
          <p className="px-3 py-6 text-xs text-surface-500 text-center">
            No conversations yet.
          </p>
        ) : (
          conversations.map((c) => {
            const isActive = c.id === activeConversationId
            return (
              <button
                key={c.id}
                role="listitem"
                onClick={() => onSelect(c.id)}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-md text-sm truncate transition-colors',
                  isActive
                    ? 'bg-surface-800 text-surface-100'
                    : 'text-surface-400 hover:bg-surface-800/60 hover:text-surface-200',
                )}
                title={c.title}
              >
                {c.title}
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

