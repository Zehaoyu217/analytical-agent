/**
 * Command registry types + default command ids.
 * Ported from reference/web/lib/shortcuts.ts. Commands for features that do
 * not yet exist (share, export, notifications) are intentionally omitted.
 */

export type ShortcutCategory =
  | 'Chat'
  | 'Navigation'
  | 'Model'
  | 'Theme'
  | 'View'
  | 'Help'
  | 'DevTools'

export const SHORTCUT_CATEGORIES: ShortcutCategory[] = [
  'Chat',
  'Navigation',
  'View',
  'DevTools',
  'Theme',
  'Model',
  'Help',
]

export interface Command {
  id: string
  /** One or more key combo strings, e.g. ["mod+k", "mod+shift+p"] */
  keys: string[]
  label: string
  description: string
  category: ShortcutCategory
  action: () => void
  /** Return false to disable this command contextually */
  when?: () => boolean
  /** If true, fires even when an input/textarea is focused */
  global?: boolean
  /** Icon name from lucide-react, optional */
  icon?: string
}

/** IDs for all default commands — used to register/look up */
export const CMD = {
  OPEN_PALETTE: 'open-palette',
  NEW_CONVERSATION: 'new-conversation',
  TOGGLE_SIDEBAR: 'toggle-sidebar',
  OPEN_SETTINGS: 'open-settings',
  TOGGLE_THEME: 'toggle-theme',
  FOCUS_CHAT: 'focus-chat',
  SHOW_HELP: 'show-help',
  FOCUS_DEVTOOLS: 'focus-devtools',
  CYCLE_RAIL: 'cycle-rail',
  PREV_CONVERSATION: 'prev-conversation',
  NEXT_CONVERSATION: 'next-conversation',
  GLOBAL_SEARCH: 'global-search',
  SWITCH_1: 'switch-conversation-1',
  SWITCH_2: 'switch-conversation-2',
  SWITCH_3: 'switch-conversation-3',
  SWITCH_4: 'switch-conversation-4',
  SWITCH_5: 'switch-conversation-5',
  SWITCH_6: 'switch-conversation-6',
  SWITCH_7: 'switch-conversation-7',
  SWITCH_8: 'switch-conversation-8',
  SWITCH_9: 'switch-conversation-9',
} as const

export type CommandId = (typeof CMD)[keyof typeof CMD]
