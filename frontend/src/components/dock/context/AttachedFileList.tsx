import type { AttachedFile } from '@/lib/store'

interface AttachedFileListProps {
  files: AttachedFile[]
}

export function AttachedFileList({ files }: AttachedFileListProps) {
  if (files.length === 0) return null
  return (
    <ul className="flex flex-col gap-1">
      {files.map((f) => (
        <li key={f.id} className="mono flex items-center justify-between text-[11px] text-fg-2">
          <span className="truncate">{f.name}</span>
          <span className="text-fg-3">{(f.size / 1024).toFixed(1)} KB</span>
        </li>
      ))}
    </ul>
  )
}
