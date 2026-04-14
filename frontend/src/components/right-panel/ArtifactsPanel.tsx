export function ArtifactsPanel(): React.ReactElement {
  return (
    <div className="flex flex-col flex-1 min-h-0 p-3">
      <p className="text-[10px] font-mono font-semibold tracking-widest text-surface-500 uppercase mb-2">
        Artifacts
      </p>
      <div className="border-t border-surface-800 mb-4" />
      <p className="text-xs font-mono text-surface-500">No artifacts yet.</p>
      <p className="text-xs font-mono text-surface-600 mt-1 leading-relaxed">
        This panel will show charts, tables, and analysis outputs produced during
        the agent session.
      </p>
    </div>
  )
}

import React from 'react'
