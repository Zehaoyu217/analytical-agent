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
import { SessionLayout } from '@/components/session/SessionLayout'
import { IconRail } from '@/components/layout/IconRail'
import { useChatStore } from '@/lib/store'
import { useDigestStore } from '@/lib/digest-store'
import { DigestPanel } from '@/components/digest/DigestPanel'
import { HealthPanel } from '@/components/health/HealthPanel'
import { SkillsPanel } from '@/components/skills/SkillsPanel'
import { useSkillsStore, countToday } from '@/lib/skills-store'
import { GraphPanel } from '@/components/graph/GraphPanel'
import { IngestPanel } from '@/components/ingest/IngestPanel'
import { useIngestStore, countRecentFailures } from '@/lib/ingest-store'
import { TopbarButton } from '@/components/ui/TopbarButton'
import { AgentsSection } from '@/sections/AgentsSection'
import { SkillsSection } from '@/sections/SkillsSection'
import { PromptsSection } from '@/sections/PromptsSection'
import { ContextSection } from '@/sections/ContextSection'
import { DevtoolsSection } from '@/sections/DevtoolsSection'
import { HealthSection } from '@/sections/HealthSection'
import { SettingsSection } from '@/sections/SettingsSection'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const handler = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  return hash
}

function ShortcutWiring() {
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
        id: CMD.FOCUS_DEVTOOLS,
        keys: ['mod+shift+d'],
        label: 'Open DevTools',
        description: 'Switch to the DevTools section',
        category: 'DevTools',
        action: () => setActiveSection('devtools'),
        icon: 'Terminal',
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

  switch (activeSection) {
    case 'chat':
      return <SessionLayout />
    case 'agents':
      return <AgentsSection />
    case 'skills':
      return <SkillsSection />
    case 'prompts':
      return <PromptsSection />
    case 'context':
      return <ContextSection />
    case 'devtools':
      return <DevtoolsSection />
    case 'health':
      return <HealthSection />
    case 'settings':
      return <SettingsSection />
    default:
      return <SessionLayout />
  }
}

// Kick off the branding fetch before any component mounts.
prefetchBranding()

export default function App() {
  const hash = useHashRoute()
  const monitorMatch = hash.match(/^#\/monitor\/(.+)$/)
  const branding = useBranding()
  const [digestOpen, setDigestOpen] = useState(false)
  const [healthOpen, setHealthOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(false)
  const [graphOpen, setGraphOpen] = useState(false)
  const [ingestOpen, setIngestOpen] = useState(false)
  const ingestRecent = useIngestStore((s) => s.recent)
  const ingestFailures = countRecentFailures(ingestRecent)
  const digestUnread = useDigestStore((s) => s.unread)
  const pendingCount = useDigestStore((s) => s.pending.length)
  const refreshPending = useDigestStore((s) => s.refreshPending)
  const digestCount = digestUnread + pendingCount
  const skillEvents = useSkillsStore((s) => s.events)
  const refreshSkills = useSkillsStore((s) => s.refresh)
  const skillsTodayCount = countToday(skillEvents)

  // Sync browser tab title with branding config.
  useEffect(() => {
    document.title = branding.ui_title
  }, [branding.ui_title])

  // Background refresh of pending proposals so the topbar badge stays current.
  useEffect(() => {
    void refreshPending()
    const t = window.setInterval(() => void refreshPending(), 30_000)
    return () => window.clearInterval(t)
  }, [refreshPending])

  // Background refresh of skills telemetry so the SKILLS badge stays current.
  useEffect(() => {
    void refreshSkills()
    const t = window.setInterval(() => void refreshSkills(), 30_000)
    return () => window.clearInterval(t)
  }, [refreshSkills])

  if (monitorMatch) {
    return <MonitorPage sessionId={monitorMatch[1]} />
  }

  return (
    <ErrorBoundary name="App">
      <ThemeProvider>
        <AnnouncerProvider>
          <CommandRegistryProvider>
            <SkipToContent />
            <ShortcutWiring />
            <div className="flex h-dvh overflow-hidden bg-canvas text-surface-100">
              <IconRail />
              <div className="flex-1 min-w-0 min-h-0 overflow-hidden">
                <ErrorBoundary name="SectionContent">
                  <SectionContent />
                </ErrorBoundary>
              </div>
            </div>
            <TopbarButton
              slot={0}
              label="DIGEST"
              count={digestCount}
              active={digestOpen}
              unread={digestCount > 0}
              onClick={() => setDigestOpen((v) => !v)}
              ariaLabel="Toggle second-brain digest panel"
            />
            <TopbarButton
              slot={1}
              label="HEALTH"
              active={healthOpen}
              onClick={() => setHealthOpen((v) => !v)}
              ariaLabel="Toggle second-brain health panel"
            />
            <TopbarButton
              slot={2}
              label="SKILLS"
              count={skillsTodayCount}
              active={skillsOpen}
              unread={skillsTodayCount > 0}
              onClick={() => setSkillsOpen((v) => !v)}
              ariaLabel="Toggle skills usage panel"
            />
            <TopbarButton
              slot={3}
              label="GRAPH"
              active={graphOpen}
              onClick={() => setGraphOpen((v) => !v)}
              ariaLabel="Toggle knowledge graph panel"
            />
            <TopbarButton
              slot={4}
              label="INGEST"
              count={ingestFailures}
              active={ingestOpen}
              unread={ingestFailures > 0}
              onClick={() => setIngestOpen((v) => !v)}
              ariaLabel="Toggle ingest drop-zone panel"
            />
            <DigestPanel open={digestOpen} onClose={() => setDigestOpen(false)} />
            <HealthPanel open={healthOpen} onClose={() => setHealthOpen(false)} />
            <SkillsPanel open={skillsOpen} onClose={() => setSkillsOpen(false)} />
            <GraphPanel open={graphOpen} onClose={() => setGraphOpen(false)} />
            <IngestPanel open={ingestOpen} onClose={() => setIngestOpen(false)} />
            <CommandPalette />
            <GlobalSearchPanel />
            <ShortcutsHelp />
          </CommandRegistryProvider>
        </AnnouncerProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
