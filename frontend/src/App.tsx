import { useEffect, useState } from 'react'
import { AnnouncerProvider } from '@/components/a11y/Announcer'
import { SkipToContent } from '@/components/a11y/SkipToContent'
import { CommandPalette } from '@/components/command-palette/CommandPalette'
import { ShortcutsHelp } from '@/components/shortcuts/ShortcutsHelp'
import { ChatLayout } from '@/components/chat/ChatLayout'
import { ThemeProvider, useTheme } from '@/components/layout/ThemeProvider'
import {
  CommandRegistryProvider,
  useCommandRegistry,
} from '@/hooks/useCommandRegistry'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { CMD } from '@/lib/shortcuts'
import { useChatStore } from '@/lib/store'
import { MonitorPage } from '@/pages/MonitorPage'

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const handler = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  return hash
}

/**
 * Registers the default command set and wires up the global keyboard listener.
 * Must render inside <CommandRegistryProvider> and <ThemeProvider>.
 */
function ShortcutWiring() {
  const { registerCommand, openPalette, openHelp } = useCommandRegistry()
  const { theme, setTheme } = useTheme()
  const toggleSidebar = useChatStore((s) => s.toggleSidebar)

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
        id: CMD.TOGGLE_SIDEBAR,
        keys: ['mod+b'],
        label: 'Toggle sidebar',
        description: 'Show or hide the navigation sidebar',
        category: 'View',
        action: toggleSidebar,
        global: true,
        icon: 'PanelLeftClose',
      }),
      registerCommand({
        id: CMD.TOGGLE_THEME,
        keys: [],
        label: 'Toggle theme',
        description: 'Cycle through light, dark, and system themes',
        category: 'Theme',
        action: () => {
          const next = theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark'
          setTheme(next)
        },
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
  }, [registerCommand, openPalette, openHelp, toggleSidebar, theme, setTheme])

  return null
}

export default function App() {
  const hash = useHashRoute()
  const monitorMatch = hash.match(/^#\/monitor\/(.+)$/)

  if (monitorMatch) {
    return <MonitorPage sessionId={monitorMatch[1]} />
  }

  return (
    <ThemeProvider>
      <AnnouncerProvider>
        <CommandRegistryProvider>
          <SkipToContent />
          <ShortcutWiring />
          <ChatLayout />
          <CommandPalette />
          <ShortcutsHelp />
        </CommandRegistryProvider>
      </AnnouncerProvider>
    </ThemeProvider>
  )
}
