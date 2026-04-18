import { useEffect, useMemo, useState } from 'react'
import { useGraphStore, computeLayout } from '@/lib/graph-store'
import './graph.css'

interface GraphPanelProps {
  open: boolean
  onClose: () => void
  embedded?: boolean
}

const CANVAS_WIDTH = 330
const CANVAS_HEIGHT = 420

export function GraphPanel({ open, onClose, embedded = false }: GraphPanelProps) {
  const nodes = useGraphStore((s) => s.nodes)
  const edges = useGraphStore((s) => s.edges)
  const note = useGraphStore((s) => s.note)
  const error = useGraphStore((s) => s.error)
  const center = useGraphStore((s) => s.center)
  const refresh = useGraphStore((s) => s.refresh)
  const setCenter = useGraphStore((s) => s.setCenter)

  const [draft, setDraft] = useState<string>('')
  const [hovered, setHovered] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    void refresh()
  }, [open, refresh])

  useEffect(() => {
    setDraft(center ?? '')
  }, [center])

  const layout = useMemo(
    () =>
      computeLayout(nodes, edges, {
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
      }),
    [nodes, edges],
  )
  const positions = useMemo(() => {
    const m = new Map(layout.map((n) => [n.id, n]))
    return m
  }, [layout])

  if (!open) return null

  const handleGo = () => {
    const trimmed = draft.trim()
    void setCenter(trimmed ? trimmed : null)
  }

  const isEmpty = nodes.length === 0

  return (
    <aside
      className={'graph-panel' + (embedded ? ' graph-panel--embedded' : '')}
      aria-label="Second-brain graph viz"
    >
      <div className="graph-panel__header">
        <div>
          <div className="graph-panel__title">GRAPH</div>
          <div className="graph-panel__meta">
            {nodes.length} nodes · {edges.length} edges
          </div>
        </div>
        <button
          type="button"
          className="graph-panel__close"
          onClick={onClose}
          aria-label="close"
        >
          ×
        </button>
      </div>

      <div className="graph-panel__controls">
        <span className="graph-panel__input-label">CENTER</span>
        <input
          type="text"
          className="graph-panel__input"
          placeholder="clm_… or blank"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleGo()
          }}
          aria-label="graph center node id"
          data-testid="graph-center-input"
        />
        <button
          type="button"
          className="graph-panel__go"
          onClick={handleGo}
          data-testid="graph-go"
        >
          GO
        </button>
      </div>

      {error && <div className="graph-panel__empty">error: {error}</div>}

      {isEmpty ? (
        <div className="graph-panel__empty">
          {note ?? 'no graph data yet'}
        </div>
      ) : (
        <svg
          className="graph-panel__canvas"
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
          role="img"
          aria-label="knowledge graph"
          data-testid="graph-svg"
        >
          {edges.map((e, i) => {
            const a = positions.get(e.src)
            const b = positions.get(e.dst)
            if (!a || !b) return null
            return (
              <line
                key={`${e.src}-${e.dst}-${e.kind}-${i}`}
                className="graph-edge"
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                data-testid="graph-edge"
              />
            )
          })}
          {layout.map((n) => (
            <g key={n.id}>
              <circle
                className={`graph-node graph-node--${n.kind}`}
                cx={n.x}
                cy={n.y}
                r={6}
                onMouseEnter={() => setHovered(n.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => void setCenter(n.id)}
                data-testid="graph-node"
                data-node-id={n.id}
              >
                <title>{n.label}</title>
              </circle>
              {hovered === n.id && (
                <text
                  className="graph-label graph-label--active"
                  x={n.x + 10}
                  y={n.y + 3}
                >
                  {n.label}
                </text>
              )}
            </g>
          ))}
        </svg>
      )}

      <div className="graph-panel__legend">
        <span>
          <span
            className="graph-panel__legend-dot"
            style={{ background: '#e0733a' }}
          />
          claim
        </span>
        <span>
          <span
            className="graph-panel__legend-dot"
            style={{ background: '#60a5fa' }}
          />
          wiki
        </span>
        <span>
          <span
            className="graph-panel__legend-dot"
            style={{ background: '#a1a1aa' }}
          />
          source
        </span>
      </div>
    </aside>
  )
}
