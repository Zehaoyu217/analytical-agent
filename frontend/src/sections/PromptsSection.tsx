import { FileText } from 'lucide-react'

export function PromptsSection() {
  return (
    <div className="flex flex-col h-full bg-surface-950 text-surface-100 overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-4 border-b border-surface-800 flex-shrink-0">
        <FileText className="w-4 h-4 text-surface-500" aria-hidden />
        <h1 className="font-mono text-xs font-semibold text-surface-300 uppercase tracking-widest">
          PROMPTS
        </h1>
      </header>

      <main className="flex-1 min-h-0 flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="font-mono text-xs text-surface-600 uppercase tracking-widest">
            Coming soon
          </p>
          <p className="text-xs text-surface-700 max-w-xs">
            Prompt library and template management will be available here.
          </p>
        </div>
      </main>
    </div>
  )
}
