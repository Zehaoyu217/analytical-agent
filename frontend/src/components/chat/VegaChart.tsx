import { useRef, useEffect, useState } from 'react'
import embed, { type Result, type VisualizationSpec } from 'vega-embed'
import { CHART_COLOR_SCALE } from '@/lib/design-tokens'

interface VegaChartProps {
  spec: string | Record<string, unknown>
}

const FONT = 'JetBrains Mono, ui-monospace, monospace'

const DARK_THEME_CONFIG = {
  background: 'transparent',
  font: FONT,
  title: {
    color: '#f4f4f5',
    fontSize: 13,
    fontWeight: 600 as const,
    font: FONT,
    anchor: 'start' as const,
    offset: 8,
  },
  axis: {
    labelColor: '#a1a1aa',
    titleColor: '#a1a1aa',
    gridColor: 'rgba(255,255,255,0.05)',
    domainColor: '#3f3f46',
    tickColor: '#3f3f46',
    labelFontSize: 11,
    titleFontSize: 12,
    labelFont: FONT,
    titleFont: FONT,
    labelPadding: 6,
  },
  legend: {
    labelColor: '#a1a1aa',
    titleColor: '#f4f4f5',
    labelFontSize: 11,
    titleFontSize: 12,
    labelFont: FONT,
    titleFont: FONT,
    orient: 'bottom' as const,
    padding: 10,
  },
  view: {
    strokeWidth: 0,
  },
  range: {
    category: [...CHART_COLOR_SCALE],
  },
}

const TOOLTIP_OPTS = {
  theme: 'dark' as const,
  style: {
    'background-color': '#18181b',
    'border': '1px solid rgba(255,255,255,0.1)',
    'border-radius': '6px',
    'padding': '6px 10px',
    'font-family': FONT,
    'font-size': '11px',
    'color': '#f4f4f5',
    'box-shadow': '0 4px 16px rgba(0,0,0,0.6)',
  },
}

function enhanceMarkTooltip(spec: Record<string, unknown>): Record<string, unknown> {
  if (!spec || typeof spec !== 'object') return spec
  if (!spec.mark && !spec.encoding) return spec
  const result = { ...spec }
  if (result.encoding && !(result.encoding as Record<string, unknown>).tooltip) {
    result.encoding = {
      ...(result.encoding as Record<string, unknown>),
      tooltip: { content: 'data' },
    }
  }
  return result
}

function enhanceSpec(spec: Record<string, unknown>): Record<string, unknown> {
  if (!spec || typeof spec !== 'object') return spec

  if (Array.isArray(spec.layer)) {
    return { ...spec, layer: (spec.layer as Record<string, unknown>[]).map(enhanceMarkTooltip) }
  }
  if (Array.isArray(spec.hconcat)) {
    return { ...spec, hconcat: (spec.hconcat as Record<string, unknown>[]).map(enhanceSpec) }
  }
  if (Array.isArray(spec.vconcat)) {
    return { ...spec, vconcat: (spec.vconcat as Record<string, unknown>[]).map(enhanceSpec) }
  }

  const enhanced = enhanceMarkTooltip(spec)
  if (!enhanced.params && !enhanced.selection && enhanced.mark) {
    const markType = typeof enhanced.mark === 'string' ? enhanced.mark : (enhanced.mark as Record<string, unknown>)?.type
    if (markType && ['bar', 'point', 'circle', 'line', 'area', 'rect'].includes(markType as string)) {
      enhanced.params = [
        { name: 'hover', select: { type: 'point', on: 'pointerover', clear: 'pointerout' } },
      ]
      const enc = enhanced.encoding as Record<string, unknown> | undefined
      if (enc && !enc.opacity) {
        enhanced.encoding = {
          ...enc,
          opacity: { condition: { param: 'hover', value: 1 }, value: 0.7 },
        }
      }
    }
  }
  return enhanced
}

export function VegaChart({ spec }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<Result | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!containerRef.current || !spec) return

    let cancelled = false

    async function render() {
      try {
        setError(null)
        const parsed: Record<string, unknown> =
          typeof spec === 'string' ? JSON.parse(spec) : (spec as Record<string, unknown>)
        const enhanced = enhanceSpec(parsed)
        const specWidth = enhanced.width
        const specHeight = enhanced.height
        const hasFixedDimensions =
          typeof specWidth === 'number' && typeof specHeight === 'number'

        const themed: Record<string, unknown> = {
          ...enhanced,
          config: {
            ...DARK_THEME_CONFIG,
            ...((enhanced.config as Record<string, unknown>) ?? {}),
          },
        }

        // Always use container width so charts fill the panel instead of
        // rendering at the spec's original (often tiny) pixel width.
        themed.width = 'container'
        themed.autosize = { type: 'fit', contains: 'padding' }
        if (hasFixedDimensions) {
          // Keep original height; width fills the available container.
          themed.height = specHeight
        }

        if (cancelled) return

        const result = await embed(containerRef.current!, themed as VisualizationSpec, {
          actions: { export: true, source: false, compiled: false, editor: false },
          renderer: 'svg',
          tooltip: TOOLTIP_OPTS,
        })

        if (!cancelled) {
          resultRef.current = result
        } else {
          result.finalize()
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to render chart')
        }
      }
    }

    render()

    return () => {
      cancelled = true
      if (resultRef.current) {
        resultRef.current.finalize()
        resultRef.current = null
      }
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [spec])

  if (error) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded bg-error-bg border border-error/40 text-xs text-error font-mono">
        Chart error: {error}
      </div>
    )
  }

  // Derive a minimum height from the spec so the chart isn't collapsed before
  // Vega finishes rendering. Width is always 100% (filled in render()).
  let minHeight = 220
  try {
    const parsed =
      typeof spec === 'string' ? JSON.parse(spec) : (spec as Record<string, unknown>)
    if (typeof parsed.height === 'number') {
      minHeight = Math.max(parsed.height, 180)
    }
  } catch {
    // ignore
  }

  return (
    <div
      style={{ minHeight }}
      className="w-full my-2 rounded overflow-hidden bg-surface-850 border border-surface-700/60"
    >
      <div ref={containerRef} className="w-full [&_svg]:w-full [&_svg]:max-w-full" />
    </div>
  )
}
