import { useEffect, useState } from 'react'
import { useBranding, prefetchBranding } from '@/hooks/useBranding'
import { AnnouncerProvider } from '@/components/a11y/Announcer'
import { SkipToContent } from '@/components/a11y/SkipToContent'
import { CommandPalette } from '@/components/command-palette/CommandPalette'
import { GlobalSearchPanel } from '@/components/search/GlobalSearchPanel'
import { ShortcutsHelp } from '@/components/shortcuts/ShortcutsHelp'
import { ThemeProvider, useTheme } from '@/components/layout/ThemeProvider'
import {
  CommandRegistryProvider,
  useCommandRegistry,
} from '@/hooks/useCommandRegistry'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { CMD } from '@/lib/shortcuts'
import { MonitorPage } from '@/pages/MonitorPage'
import { ChatPane } from '@/components/chat/ChatPane'
import { AppShell } from '@/components/shell/AppShell'
import { useChatStore, type SectionId } from '@/lib/store'
import { useUiStore } from '@/lib/ui-store'
import { useDigestStore } from '@/lib/digest-store'
import { useSkillsStore } from '@/lib/skills-store'
import { AgentsSection } from '@/sections/AgentsSection'
import { SkillsSection } from '@/sections/SkillsSection'
import { PromptsSection } from '@/sections/PromptsSection'
import { ContextSection } from '@/sections/ContextSection'
import { HealthSection } from '@/sections/HealthSection'
import { SettingsSection } from '@/sections/SettingsSection'
import { GraphPanel } from '@/components/graph/GraphPanel'
import { DigestPanel } from '@/components/digest/DigestPanel'
import { IngestPanel } from '@/components/ingest/IngestPanel'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { ArtifactViewer } from '@/components/artifact/ArtifactViewer'
import { ArtifactPage } from '@/routes/ArtifactPage'

interface SectionShortcut {
  id: string
  key: string
  section: SectionId
  label: string
}

// Keep this in IconRail order (9 sections) so the digits map to the visual
// rail 1..9 top-to-bottom. `mod+shift+N` is global — the conversation-scoped
// `mod+N` digit shortcut continues to switch conversation slots.
export const SECTION_SHORTCUTS: readonly SectionShortcut[] = [
  { id: CMD.OPEN_SECTION_CHAT, key: 'mod+shift+1', section: 'chat', label: 'Open Chat' },
  { id: CMD.OPEN_SECTION_AGENTS, key: 'mod+shift+2', section: 'agents', label: 'Open Agents' },
  { id: CMD.OPEN_SECTION_SKILLS, key: 'mod+shift+3', section: 'skills', label: 'Open Skills' },
  { id: CMD.OPEN_SECTION_PROMPTS, key: 'mod+shift+4', section: 'prompts', label: 'Open Prompts' },
  { id: CMD.OPEN_SECTION_CONTEXT, key: 'mod+shift+5', section: 'context', label: 'Open Context' },
  { id: CMD.OPEN_SECTION_HEALTH, key: 'mod+shift+6', section: 'health', label: 'Open Health' },
  { id: CMD.OPEN_SECTION_GRAPH, key: 'mod+shift+7', section: 'graph', label: 'Open Graph' },
  { id: CMD.OPEN_SECTION_DIGEST, key: 'mod+shift+8', section: 'digest', label: 'Open Digest' },
  { id: CMD.OPEN_SECTION_INGEST, key: 'mod+shift+9', section: 'ingest', label: 'Open Ingest' },
]

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const handler = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  return hash
}

export function ShortcutWiring() {
  const { registerCommand, openPalette, openHelp } = useCommandRegistry()
  const { theme, setTheme } = useTheme()
  const conversations = useChatStore((s) => s.conversations)
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)
  const createConversationRemote = useChatStore((s) => s.createConversationRemote)
  const createConversation = useChatStore((s) => s.createConversation)
  const toggleSidebar = useChatStore((s) => s.toggleSidebar)
  const setActiveSection = useChatStore((s) => s.setActiveSection)
  const openSearch = useChatStore((s) => s.openSearch)

  useKeyboardShortcuts()

  useEffect(() => {
    const disposers = [
      registerCommand({
        id: CMD.OPEN_PALETTE,
        keys: ['mod+k'],
        label: 'Open command palette',
        description: 'Search and run any command',
        category: 'Navigation',
        action: openPalette,
        global: true,
        icon: 'Search',
      }),
      registerCommand({
        id: CMD.NEW_CONVERSATION,
        keys: ['mod+n'],
        label: 'New conversation',
        description: 'Start a new chat session',
        category: 'Chat',
        action: () => {
          createConversationRemote('New Conversation').catch(() => createConversation())
        },
        icon: 'Plus',
      }),
      registerCommand({
        id: CMD.TOGGLE_SIDEBAR,
        keys: ['mod+b'],
        label: 'Toggle sidebar',
        description: 'Show or hide the left panel',
        category: 'View',
        action: toggleSidebar,
        icon: 'PanelLeft',
      }),
      registerCommand({
        id: CMD.OPEN_SETTINGS,
        keys: ['mod+,'],
        label: 'Open settings',
        description: 'Go to the settings section',
        category: 'Navigation',
        action: () => setActiveSection('settings'),
        icon: 'Settings',
      }),
      registerCommand({
        id: CMD.TOGGLE_THEME,
        keys: [],
        label: 'Toggle theme',
        description: 'Switch between dark and light themes',
        category: 'Theme',
        action: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
        icon: 'Sun',
      }),
      registerCommand({
        id: CMD.FOCUS_CHAT,
        keys: ['mod+l'],
        label: 'Focus chat input',
        description: 'Move focus to the chat message box',
        category: 'Chat',
        action: () => {
          const el = document.querySelector<HTMLElement>('[data-chat-input]')
          el?.focus()
        },
        icon: 'MessageSquare',
      }),
      registerCommand({
        id: CMD.SHOW_HELP,
        keys: ['mod+/'],
        label: 'Show keyboard shortcuts',
        description: 'View all available keyboard shortcuts',
        category: 'Help',
        action: openHelp,
        global: true,
        icon: 'HelpCircle',
      }),
      registerCommand({
        id: CMD.PREV_CONVERSATION,
        keys: ['mod+shift+['],
        label: 'Previous conversation',
        description: 'Switch to the previous conversation',
        category: 'Navigation',
        when: () => conversations.length > 1,
        action: () => {
          const idx = conversations.findIndex((c) => c.id === activeConversationId)
          if (idx > 0) setActiveConversation(conversations[idx - 1].id)
        },
      }),
      registerCommand({
        id: CMD.NEXT_CONVERSATION,
        keys: ['mod+shift+]'],
        label: 'Next conversation',
        description: 'Switch to the next conversation',
        category: 'Navigation',
        when: () => conversations.length > 1,
        action: () => {
          const idx = conversations.findIndex((c) => c.id === activeConversationId)
          if (idx >= 0 && idx < conversations.length - 1)
            setActiveConversation(conversations[idx + 1].id)
        },
      }),
      registerCommand({
        id: CMD.GLOBAL_SEARCH,
        keys: ['mod+shift+f'],
        label: 'Global search',
        description: 'Search across all conversations',
        category: 'Navigation',
        action: openSearch,
        global: true,
        icon: 'Search',
      }),
      ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) =>
        registerCommand({
          id: CMD[`SWITCH_${n}` as keyof typeof CMD],
          keys: [`mod+${n}`],
          label: `Switch to conversation ${n}`,
          description: `Go to conversation slot ${n}`,
          category: 'Navigation',
          when: () => conversations.length >= n,
          action: () => {
            const target = conversations[n - 1]
            if (target) setActiveConversation(target.id)
          },
        })
      ),
      registerCommand({
        id: CMD.TOGGLE_DOCK,
        keys: ['mod+j'],
        label: 'Toggle dock',
        description: 'Show or hide the right dock (progress / context / raw)',
        category: 'View',
        action: () => useUiStore.getState().toggleDock(),
        global: true,
        icon: 'PanelRight',
      }),
      registerCommand({
        id: CMD.CYCLE_MODEL,
        keys: ['mod+shift+m'],
        label: 'Cycle model',
        description: 'Advance the active conversation to the next model',
        category: 'Model',
        action: () => {
          const w = window as Window & { __dsAgentCycleModel?: (dir: 1 | -1) => void }
          w.__dsAgentCycleModel?.(1)
        },
        global: true,
      }),
      registerCommand({
        id: CMD.TOGGLE_EXTENDED,
        keys: ['mod+shift+e'],
        label: 'Toggle extended thinking',
        description: 'Enable or disable extended thinking for the active conversation',
        category: 'Model',
        action: () => {
          const state = useChatStore.getState()
          const conv = state.conversations.find((c) => c.id === state.activeConversationId)
          if (!conv) return
          state.setConversationExtendedThinking(conv.id, !conv.extendedThinking)
        },
        global: true,
      }),
      ...SECTION_SHORTCUTS.map(({ id, key, section, label }) =>
        registerCommand({
          id,
          keys: [key],
          label,
          description: `Jump to the ${section} section`,
          category: 'Navigation',
          action: () => setActiveSection(section),
          global: true,
        }),
      ),
    ]
    return () => {
      for (const dispose of disposers) dispose()
    }
  }, [
    registerCommand, openPalette, openHelp, theme, setTheme,
    conversations, activeConversationId, setActiveConversation,
    createConversationRemote, createConversation, toggleSidebar,
    setActiveSection, openSearch,
  ])

  return null
}

function SectionContent() {
  const activeSection = useChatStore((s) => s.activeSection)
  const setActiveSection = useChatStore((s) => s.setActiveSection)
  const backToChat = () => setActiveSection('chat')

  switch (activeSection) {
    case 'chat':
      return <ChatPane />
    case 'agents':
      return <AgentsSection />
    case 'skills':
      return <SkillsSection />
    case 'prompts':
      return <PromptsSection />
    case 'context':
      return <ContextSection />
    case 'health':
      return <HealthSection />
    case 'graph':
      return <GraphPanel open onClose={backToChat} embedded={false} />
    case 'digest':
      return <DigestPanel open onClose={backToChat} embedded={false} />
    case 'ingest':
      return <IngestPanel open onClose={backToChat} embedded={false} />
    case 'settings':
      return <SettingsSection />
    default:
      return <ChatPane />
  }
}

// Kick off the branding fetch before any component mounts.
prefetchBranding()

export default function App() {
  const hash = useHashRoute()
  const monitorMatch = hash.match(/^#\/monitor\/(.+)$/)
  const artifactMatch = hash.match(/^#\/artifact\/(.+)$/)
  const branding = useBranding()
  const refreshPending = useDigestStore((s) => s.refreshPending)
  const refreshSkills = useSkillsStore((s) => s.refresh)

  // Sync browser tab title with branding config.
  useEffect(() => {
    document.title = branding.ui_title
  }, [branding.ui_title])

  // Background refresh so HUD badges stay current.
  useEffect(() => {
    void refreshPending()
    void refreshSkills()
    const t = window.setInterval(() => {
      void refreshPending()
      void refreshSkills()
    }, 30_000)
    return () => window.clearInterval(t)
  }, [refreshPending, refreshSkills])

  if (monitorMatch) {
    return <MonitorPage sessionId={monitorMatch[1]} />
  }

  if (artifactMatch) {
    return (
      <ErrorBoundary name="ArtifactPage">
        <ThemeProvider>
          <ArtifactPage id={artifactMatch[1]} />
        </ThemeProvider>
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary name="App">
      <ThemeProvider>
        <AnnouncerProvider>
          <CommandRegistryProvider>
            <SkipToContent />
            <ShortcutWiring />
            <AppShell>
              <ErrorBoundary name="SectionContent">
                <SectionContent />
              </ErrorBoundary>
            </AppShell>
            <CommandPalette />
            <GlobalSearchPanel />
            <ShortcutsHelp />
            <ArtifactViewer />
          </CommandRegistryProvider>
        </AnnouncerProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
