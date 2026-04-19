import { useChatStore } from '@/lib/store'
import { TextRenderer } from '@/components/artifact/renderers/TextRenderer'
import { HtmlRenderer } from '@/components/artifact/renderers/HtmlRenderer'
import { TableRenderer } from '@/components/artifact/renderers/TableRenderer'
import { CsvRenderer } from '@/components/artifact/renderers/CsvRenderer'
import { VegaLiteRenderer } from '@/components/artifact/renderers/VegaLiteRenderer'
import { MermaidRenderer } from '@/components/artifact/renderers/MermaidRenderer'

interface ArtifactPageProps {
  id: string
}

export function ArtifactPage({ id }: ArtifactPageProps) {
  const artifact = useChatStore((s) => s.artifacts.find((a) => a.id === id))
  if (!artifact) {
    return (
      <div className="flex h-dvh items-center justify-center bg-bg-0 p-6 text-fg-2">
        Artifact not found.
      </div>
    )
  }
  const R =
    {
      'vega-lite': VegaLiteRenderer,
      mermaid: MermaidRenderer,
      'table-json': TableRenderer,
      csv: CsvRenderer,
      html: HtmlRenderer,
      text: TextRenderer,
    }[artifact.format] ?? TextRenderer
  return (
    <div className="flex h-dvh flex-col bg-bg-0 text-fg-0">
      <header className="flex h-10 items-center gap-2 border-b border-line-2 bg-bg-1 px-3">
        <span className="mono rounded bg-bg-2 px-1.5 py-0.5 text-[10.5px] uppercase text-fg-2">
          {artifact.type}
        </span>
        <h1 className="flex-1 truncate text-[14.5px]">{artifact.title}</h1>
      </header>
      <main className="flex-1 overflow-hidden">
        <R content={artifact.content} />
      </main>
    </div>
  )
}
