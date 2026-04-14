import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ImageIcon, StickyNote, Terminal } from 'lucide-react'
import { useChatStore, type RightPanelTab } from '@/lib/store'
import { cn } from '@/lib/utils'
import { ArtifactsPanel } from './ArtifactsPanel'
import { ScratchpadPanel } from './ScratchpadPanel'
import { TerminalPanel } from './TerminalPanel'

const ICON_RAIL_WIDTH = 44
const PANEL_OPEN_WIDTH = 280

type TabDef = { id: RightPanelTab; icon: React.ElementType; label: string }

const TABS: TabDef[] = [
  { id: 'artifacts', icon: ImageIcon, label: 'Artifacts' },
  { id: 'scratchpad', icon: StickyNote, label: 'Scratchpad' },
  { id: 'tools', icon: Terminal, label: 'Tool Calls' },
]

export function RightPanel(): React.ReactElement {
  const rightPanelOpen = useChatStore((s) => s.rightPanelOpen)
  const rightPanelTab = useChatStore((s) => s.rightPanelTab)
  const toggleRightPanel = useChatStore((s) => s.toggleRightPanel)
  const setRightPanelTab = useChatStore((s) => s.setRightPanelTab)

  const handleTabClick = (id: RightPanelTab): void => {
    if (!rightPanelOpen || rightPanelTab !== id) {
      setRightPanelTab(id)
    } else {
      toggleRightPanel()
    }
  }

  return (
    <motion.aside
      className={cn(
        'flex flex-row h-full bg-surface-900 border-l border-surface-800',
        'relative flex-shrink-0 z-20',
      )}
      animate={{ width: rightPanelOpen ? PANEL_OPEN_WIDTH : ICON_RAIL_WIDTH }}
      transition={{ duration: 0.2, ease: 'easeInOut' }}
      aria-label="Right panel"
    >
      {/* Tab content — rendered before icon rail so rail sits on top (right edge) */}
      <AnimatePresence mode="wait">
        {rightPanelOpen && (
          <motion.div
            key={rightPanelTab}
            className="flex-1 flex flex-col min-h-0 overflow-hidden min-w-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
          >
            {rightPanelTab === 'artifacts' && <ArtifactsPanel />}
            {rightPanelTab === 'scratchpad' && <ScratchpadPanel />}
            {rightPanelTab === 'tools' && <TerminalPanel />}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Icon rail — fixed width on the right edge of the panel */}
      <div
        className={cn(
          'flex flex-col items-center py-2 gap-0.5 flex-shrink-0',
          'w-[44px] border-l border-surface-800',
        )}
      >
        {TABS.map(({ id, icon: Icon, label }) => {
          const isActive = rightPanelOpen && rightPanelTab === id
          return (
            <button
              key={id}
              onClick={() => handleTabClick(id)}
              title={label}
              aria-label={label}
              className={cn(
                'w-full flex justify-center items-center px-0 py-2',
                'rounded-md text-xs font-medium transition-colors',
                isActive
                  ? 'bg-surface-800 text-surface-100'
                  : 'text-surface-500 hover:text-surface-300 hover:bg-surface-800/60',
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            </button>
          )
        })}
      </div>
    </motion.aside>
  )
}
