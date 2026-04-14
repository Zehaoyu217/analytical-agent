import { useEffect, useRef } from 'react'
import embed, { type VisualizationSpec } from 'vega-embed'

interface VegaChartProps {
  spec: Record<string, unknown>
}

export function VegaChart({ spec }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const vegaSpec = spec as VisualizationSpec
    let view: { finalize(): void } | undefined

    embed(el, vegaSpec, {
      actions: { export: true, source: false, editor: false, compiled: false },
      theme: 'dark',
      config: {
        background: 'transparent',
        font: 'JetBrains Mono, ui-monospace, monospace',
        axis: {
          labelColor: '#a1a1aa',
          titleColor: '#a1a1aa',
          gridColor: '#27272a',
          domainColor: '#3f3f46',
          tickColor: '#3f3f46',
        },
        legend: {
          labelColor: '#a1a1aa',
          titleColor: '#a1a1aa',
        },
        title: {
          color: '#f4f4f5',
          fontSize: 13,
          fontWeight: 600,
        },
        view: {
          stroke: 'transparent',
        },
      },
    })
      .then((result) => {
        view = result.view
      })
      .catch((err: unknown) => {
        if (el) {
          el.textContent = `Chart error: ${err instanceof Error ? err.message : String(err)}`
        }
      })

    return () => {
      view?.finalize()
    }
  }, [spec])

  return (
    <div
      ref={containerRef}
      className="my-2 rounded-lg overflow-hidden bg-surface-850 border border-surface-700/60"
    />
  )
}
