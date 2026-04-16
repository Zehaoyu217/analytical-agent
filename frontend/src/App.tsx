import { useEffect, useState } from 'react'
import { useBranding, prefetchBranding } from '@/hooks/useBranding'
import { AnnouncerProvider } from '@/components/a11y/Announcer'
import { SkipToContent } from '@/components/a11y/SkipToContent'
import { CommandPalette } from '@/components/command-palette/CommandPalette'
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
import { AgentsSection } from '@/sections/AgentsSection'
import { SkillsSection } from '@/sections/SkillsSection'
import { PromptsSection } from '@/sections/PromptsSection'
import { ContextSection } from '@/sections/ContextSection'
import { DevtoolsSection } from '@/sections/DevtoolsSection'
import { SettingsSection } from '@/sections/SettingsSection'

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
        id: CMD.TOGGLE_THEME,
        keys: [],
        label: 'Toggle theme',
        description: 'Switch between dark and light themes',
        category: 'Theme',
        action: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
        icon: 'Sun',
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
    ]
    return () => {
      for (const dispose of disposers) dispose()
    }
  }, [registerCommand, openPalette, openHelp, theme, setTheme])

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

  // Sync browser tab title with branding config.
  useEffect(() => {
    document.title = branding.ui_title
  }, [branding.ui_title])

  if (monitorMatch) {
    return <MonitorPage sessionId={monitorMatch[1]} />
  }

  return (
    <ThemeProvider>
      <AnnouncerProvider>
        <CommandRegistryProvider>
          <SkipToContent />
          <ShortcutWiring />
          <div className="flex h-dvh overflow-hidden bg-canvas text-surface-100">
            <IconRail />
            <div className="flex-1 min-w-0 min-h-0 overflow-hidden">
              <SectionContent />
            </div>
          </div>
          <CommandPalette />
          <ShortcutsHelp />
        </CommandRegistryProvider>
      </AnnouncerProvider>
    </ThemeProvider>
  )
}
