import { useState } from 'react'
import { cn } from '@/lib/utils'

interface ScratchpadPreviewProps {
  content: string
}

export function ScratchpadPreview({ content }: ScratchpadPreviewProps) {
  const [expanded, setExpanded] = useState(false)
  if (!content.trim()) {
    return <div className="mono text-[10.5px] text-fg-3">Scratchpad empty</div>
  }
  const lines = content.split('\n')
  const shown = expanded ? lines.slice(0, 20) : lines.slice(0, 3)
  return (
    <div>
      <pre className={cn('mono whitespace-pre-wrap text-[11px] text-fg-1')}>
        {shown.join('\n')}
      </pre>
      {lines.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mono mt-1 text-[10.5px] text-acc hover:underline focus-ring rounded"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  )
}
