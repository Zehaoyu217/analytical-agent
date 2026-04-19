import { useEffect, useRef, useState } from 'react'
import { TextRenderer } from './TextRenderer'

interface MermaidRendererProps {
  content: string
}

export function MermaidRenderer({ content }: MermaidRendererProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const m = await import('mermaid')
        const { svg } = await m.default.render(`m-${Date.now()}`, content)
        if (mounted && ref.current) ref.current.innerHTML = svg
      } catch {
        if (mounted) setFailed(true)
      }
    })()
    return () => {
      mounted = false
    }
  }, [content])

  if (failed) return <TextRenderer content={content} />
  return <div ref={ref} className="flex h-full w-full items-center justify-center p-4" />
}
