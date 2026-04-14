import { Settings } from 'lucide-react'
import { SettingsTab } from '@/components/sidebar/SettingsTab'

export function SettingsSection() {
  return (
    <div className="flex flex-col h-full bg-surface-950 text-surface-100 overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-surface-800 flex-shrink-0">
        <Settings className="w-4 h-4 text-surface-500" aria-hidden />
        <h1 className="font-mono text-xs font-semibold text-surface-300 uppercase tracking-widest">
          SETTINGS
        </h1>
      </header>

      {/* Reuse existing SettingsTab */}
      <div className="flex-1 min-h-0 flex flex-col">
        <SettingsTab />
      </div>
    </div>
  )
}
