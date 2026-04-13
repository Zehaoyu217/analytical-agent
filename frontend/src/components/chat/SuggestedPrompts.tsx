import { BookOpen, Database, FileSearch, Wrench } from 'lucide-react'

interface Prompt {
  icon: React.ElementType
  title: string
  text: string
}

/**
 * Hand-picked prompts for an empty conversation. Clicking a card populates the
 * draft input via the chat store — it does not submit. Phase-local content:
 * revisit alongside slash-command UX in P3/P4.
 */
const PROMPTS: Prompt[] = [
  {
    icon: Database,
    title: 'Summarize a dataset',
    text: 'Summarize this dataset: ',
  },
  {
    icon: FileSearch,
    title: 'Explore traces',
    text: 'Explain the trace replay infrastructure in this repo.',
  },
  {
    icon: BookOpen,
    title: 'Ask the wiki',
    text: "What's in the wiki about skill creation?",
  },
  {
    icon: Wrench,
    title: 'Create a skill',
    text: 'Help me scaffold a new skill for ',
  },
]

interface SuggestedPromptsProps {
  onSelect: (text: string) => void
}

export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps) {
  return (
    <div className="grid grid-cols-2 gap-2 max-w-lg w-full mt-6">
      {PROMPTS.map((p) => {
        const Icon = p.icon
        return (
          <button
            key={p.title}
            onClick={() => onSelect(p.text)}
            className="flex items-start gap-2.5 p-3 rounded-xl bg-surface-800 hover:bg-surface-700 border border-surface-700 hover:border-surface-600 text-left transition-colors group"
          >
            <Icon
              className="w-4 h-4 text-brand-400 flex-shrink-0 mt-0.5 group-hover:text-brand-300 transition-colors"
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-xs font-medium text-surface-200">{p.title}</p>
              <p className="text-xs text-surface-500 mt-0.5 truncate">{p.text}</p>
            </div>
          </button>
        )
      })}
    </div>
  )
}
