import React from 'react'
import { useChatStore } from '@/lib/store'
import { VegaChart } from '@/components/chat/VegaChart'
import type { ContentBlock } from '@/lib/types'

function extractChartSpecs(
  content: string | ContentBlock[],
): Array<Record<string, unknown>> {
  if (typeof content === 'string') return []
  return content
    .filter((b): b is Extract<ContentBlock, { type: 'chart' }> => b.type === 'chart')
    .map((b) => b.spec)
}

export function ArtifactsPanel(): React.ReactElement {
  const activeId = useChatStore((s) => s.activeConversationId)
  const conversation = useChatStore((s) =>
    s.conversations.find((c) => c.id === activeId),
  )

  const charts = (conversation?.messages ?? [])
    .filter((m) => m.role === 'assistant')
    .flatMap((m) => extractChartSpecs(m.content))

  return (
    <div className="flex flex-col flex-1 min-h-0 p-3">
      <p className="text-[10px] font-mono font-semibold tracking-widest text-surface-500 uppercase mb-2">
        Artifacts
      </p>
      <div className="border-t border-surface-800 mb-3" />

      {charts.length === 0 ? (
        <div>
          <p className="text-xs font-mono text-surface-500">No artifacts yet.</p>
          <p className="text-xs font-mono text-surface-600 mt-1 leading-relaxed">
            Charts and analysis outputs will appear here during the session.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0">
          {charts.map((spec, i) => (
            <div key={i} className="rounded border border-surface-800 bg-surface-900/50 p-2">
              <VegaChart spec={spec} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
