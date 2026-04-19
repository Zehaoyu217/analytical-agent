import type { ToolCallEntry } from '@/lib/store'

interface ToolChipProps {
  entry: ToolCallEntry
}

const STATUS_COLOR: Record<ToolCallEntry['status'], string> = {
  pending: 'var(--fg-2)',
  ok: 'var(--ok)',
  error: 'var(--err)',
  blocked: 'var(--warn)',
}

export function ToolChip({ entry }: ToolChipProps) {
  const ms =
    entry.startedAt !== undefined && entry.finishedAt !== undefined
      ? entry.finishedAt - entry.startedAt
      : null
  return (
    <button
      type="button"
      onClick={() => {
        window.dispatchEvent(
          new CustomEvent('scrollToTrace', { detail: { entryId: entry.id } }),
        )
      }}
      className="mb-[5px] mr-[6px] inline-flex items-center gap-[7px] rounded-md border px-[9px] py-1 text-[11.5px]"
      style={{
        borderColor: 'var(--line-2)',
        background: 'var(--bg-1)',
        color: 'var(--fg-1)',
      }}
    >
      <span
        className="inline-block rounded-full"
        style={{
          background: STATUS_COLOR[entry.status],
          width: 5,
          height: 5,
        }}
      />
      <span className="mono" style={{ color: 'var(--fg-0)' }}>
        {entry.name}
      </span>
      {entry.inputPreview && (
        <span className="mono" style={{ color: 'var(--fg-2)' }}>
          {entry.inputPreview}
        </span>
      )}
      {ms !== null && (
        <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
          · {ms}ms
        </span>
      )}
      {entry.rows && (
        <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
          · {entry.rows}
        </span>
      )}
    </button>
  )
}
