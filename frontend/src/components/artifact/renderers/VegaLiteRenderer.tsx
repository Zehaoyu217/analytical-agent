import { useEffect, useRef, useState } from 'react'
import { TextRenderer } from './TextRenderer'

interface VegaLiteRendererProps {
  content: string
}

export function VegaLiteRenderer({ content }: VegaLiteRendererProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let mounted = true
    let view: { finalize: () => void } | null = null
    ;(async () => {
      try {
        const embed = await import('vega-embed')
        if (!mounted || !ref.current) return
        const spec = JSON.parse(content) as unknown
        const result = await embed.default(ref.current, spec as object, { actions: false })
        view = result.view as unknown as { finalize: () => void }
        if (mounted) setLoaded(true)
      } catch {
        if (mounted) setFailed(true)
      }
    })()
    return () => {
      mounted = false
      view?.finalize()
    }
  }, [content])

  if (failed) return <TextRenderer content={content} />
  return (
    <div className="flex h-full w-full items-center justify-center p-4">
      {!loaded && <div className="mono text-[12px] text-fg-3">Loading chart…</div>}
      <div ref={ref} className="max-h-full max-w-full" />
    </div>
  )
}
