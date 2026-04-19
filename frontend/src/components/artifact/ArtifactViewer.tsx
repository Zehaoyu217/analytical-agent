import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import FocusTrap from 'focus-trap-react'
import { Copy, Download, ExternalLink, X } from 'lucide-react'
import { useArtifactNav } from '@/lib/hooks/useArtifactNav'
import type { Artifact } from '@/lib/store'
import { cn } from '@/lib/utils'
import { TextRenderer } from './renderers/TextRenderer'
import { HtmlRenderer } from './renderers/HtmlRenderer'
import { TableRenderer } from './renderers/TableRenderer'
import { CsvRenderer } from './renderers/CsvRenderer'
import { VegaLiteRenderer } from './renderers/VegaLiteRenderer'
import { MermaidRenderer } from './renderers/MermaidRenderer'

function Renderer({ artifact }: { artifact: Artifact }) {
  switch (artifact.format) {
    case 'vega-lite':
      return <VegaLiteRenderer content={artifact.content} />
    case 'mermaid':
      return <MermaidRenderer content={artifact.content} />
    case 'table-json':
      return <TableRenderer content={artifact.content} />
    case 'csv':
      return <CsvRenderer content={artifact.content} />
    case 'html':
      return <HtmlRenderer content={artifact.content} />
    case 'text':
    default:
      return <TextRenderer content={artifact.content} />
  }
}

function filenameFor(a: Artifact): string {
  const slug = a.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40) || 'artifact'
  const ext =
    a.format === 'csv' ? 'csv' :
    a.format === 'html' ? 'html' :
    a.format === 'mermaid' ? 'mmd' :
    a.format === 'table-json' || a.format === 'vega-lite' ? 'json' :
    'txt'
  return `${slug}.${ext}`
}

function download(a: Artifact): void {
  const mime =
    a.format === 'csv' ? 'text/csv' :
    a.format === 'html' ? 'text/html' :
    a.format === 'vega-lite' || a.format === 'table-json' ? 'application/json' :
    'text/plain'
  const blob = new Blob([a.content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filenameFor(a)
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

function IconBtn({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded focus-ring',
        'text-fg-2 hover:bg-bg-2 hover:text-fg-0',
      )}
    >
      {children}
    </button>
  )
}

export function ArtifactViewer() {
  const [openId, setOpenId] = useState<string | null>(null)
  const { current, next, prev } = useArtifactNav(openId)

  useEffect(() => {
    const onFocus = (e: Event) => {
      const detail = (e as CustomEvent).detail as { id?: string } | undefined
      if (detail?.id) setOpenId(detail.id)
    }
    window.addEventListener('focusArtifact', onFocus as EventListener)
    return () => window.removeEventListener('focusArtifact', onFocus as EventListener)
  }, [])

  useEffect(() => {
    if (!openId) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenId(null)
        return
      }
      if (e.key === 'ArrowRight') setOpenId(next())
      else if (e.key === 'ArrowLeft') setOpenId(prev())
      else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'c' && current) {
        e.preventDefault()
        void navigator.clipboard.writeText(current.content)
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's' && current) {
        e.preventDefault()
        download(current)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [openId, next, prev, current])

  if (!openId || !current) return null

  return createPortal(
    <FocusTrap
      focusTrapOptions={{
        allowOutsideClick: true,
        escapeDeactivates: false,
        initialFocus: false,
        fallbackFocus: () => document.body,
        tabbableOptions: { displayCheck: 'none' },
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={current.title}
        className="fixed inset-0 z-50 flex flex-col bg-bg-0"
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpenId(null)
        }}
      >
        <header className="flex h-10 items-center gap-2 border-b border-line-2 bg-bg-1 px-3">
          <span className="mono rounded bg-bg-2 px-1.5 py-0.5 text-[10.5px] uppercase text-fg-2">
            {current.type}
          </span>
          <h2 className="flex-1 truncate text-[14.5px] text-fg-0">{current.title}</h2>
          <IconBtn label="Copy" onClick={() => void navigator.clipboard.writeText(current.content)}>
            <Copy className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Download" onClick={() => download(current)}>
            <Download className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Open in new window" onClick={() => window.open(`#/artifact/${current.id}`)}>
            <ExternalLink className="h-3.5 w-3.5" />
          </IconBtn>
          <IconBtn label="Close" onClick={() => setOpenId(null)}>
            <X className="h-3.5 w-3.5" />
          </IconBtn>
        </header>
        <main className="flex-1 overflow-hidden">
          <Renderer artifact={current} />
        </main>
        <footer className="mono flex h-7 items-center justify-between border-t border-line-2 bg-bg-1 px-3 text-[10.5px] text-fg-3">
          <span>{new Date(current.created_at * 1000).toLocaleString()}</span>
          <span>← → cycle · ⌘C copy · ⌘S download · ESC close</span>
        </footer>
      </div>
    </FocusTrap>,
    document.body,
  )
}
