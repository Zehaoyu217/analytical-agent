export function EventDetailDrawer(): React.ReactElement {
  return (
    <div className="h-[240px] shrink-0 border-t border-surface-800 flex flex-col">
      {/* Drawer header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-surface-800 shrink-0">
        <span className="font-mono text-[10px] text-surface-500 uppercase tracking-widest">
          Event Details
        </span>
      </div>

      {/* Empty state */}
      <div className="flex-1 flex flex-col justify-center px-4">
        <div className="w-32 h-px bg-surface-800 mb-3" />
        <p className="font-mono text-[11px] text-surface-600 leading-relaxed">
          Select a trace event to inspect its input/output,
          <br />
          guardrail outcomes, and artifact links.
        </p>
      </div>
    </div>
  )
}
