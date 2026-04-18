import type { DigestEntry as Entry } from '@/lib/digest-store'
import './digest.css'

interface DigestEntryProps {
  entry: Entry
  onApply: (id: string) => void
  onSkip: (id: string) => void
}

export function DigestEntry({ entry, onApply, onSkip }: DigestEntryProps) {
  const className = entry.applied ? 'digest-entry applied' : 'digest-entry'
  return (
    <div data-testid="digest-entry" className={className}>
      <span className="digest-entry__id">[{entry.id}]</span>
      <span className="digest-entry__line">{entry.line}</span>
      {!entry.applied && (
        <span className="digest-entry__actions">
          <button type="button" onClick={() => onApply(entry.id)}>
            apply
          </button>
          <button type="button" onClick={() => onSkip(entry.id)}>
            skip
          </button>
        </span>
      )}
    </div>
  )
}
