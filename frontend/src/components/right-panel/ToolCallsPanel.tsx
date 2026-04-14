import React from 'react'
import { CheckCircle, XCircle, Clock, Ban } from 'lucide-react'
import { useChatStore, type ToolCallEntry, type ToolCallStatus } from '@/lib/store'
import { cn } from '@/lib/utils'

function StatusIcon({ status }: { status: ToolCallStatus }) {
  if (status === 'ok') return <CheckCircle className="w-3 h-3 text-emerald-400 flex-shrink-0" />
  if (status === 'error') return <XCircle className="w-3 h-3 text-red-400 flex-shrink-0" />
  if (status === 'blocked') return <Ban className="w-3 h-3 text-amber-400 flex-shrink-0" />
  return <Clock className="w-3 h-3 text-surface-500 flex-shrink-0 animate-pulse" />
}

function ToolCallRow({ entry }: { entry: ToolCallEntry }) {
  return (
    <div
      className={cn(
        'rounded border px-2.5 py-2 space-y-1',
        entry.status === 'error'
          ? 'border-red-900/50 bg-red-950/20'
          : entry.status === 'blocked'
            ? 'border-amber-900/50 bg-amber-950/20'
            : 'border-surface-800 bg-surface-900/50',
      )}
    >
      <div className="flex items-center gap-1.5">
        <StatusIcon status={entry.status} />
        <span className="text-[11px] font-mono font-semibold text-surface-200 truncate">
          {entry.name}
        </span>
        <span className="ml-auto text-[10px] font-mono text-surface-600 flex-shrink-0">
          s{entry.step}
        </span>
      </div>
      {entry.inputPreview && (
        <p className="text-[10px] font-mono text-surface-500 truncate leading-relaxed pl-4">
          {entry.inputPreview}
        </p>
      )}
      {entry.preview && entry.status !== 'pending' && (
        <p
          className={cn(
            'text-[10px] font-mono leading-relaxed pl-4 line-clamp-2',
            entry.status === 'error' ? 'text-red-400' : 'text-surface-400',
          )}
        >
          {entry.preview}
        </p>
      )}
    </div>
  )
}

export function ToolCallsPanel(): React.ReactElement {
  const toolCallLog = useChatStore((s) => s.toolCallLog)

  return (
    <div className="flex flex-col flex-1 min-h-0 p-3">
      <p className="text-[10px] font-mono font-semibold tracking-widest text-surface-500 uppercase mb-2">
        Tool Calls
      </p>
      <div className="border-t border-surface-800 mb-3" />

      {toolCallLog.length === 0 ? (
        <div>
          <p className="text-xs font-mono text-surface-500">No tool calls yet.</p>
          <p className="text-xs font-mono text-surface-600 mt-1 leading-relaxed">
            Tool invocations will appear here as the agent works.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 overflow-y-auto flex-1 min-h-0">
          {toolCallLog.map((entry) => (
            <ToolCallRow key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
