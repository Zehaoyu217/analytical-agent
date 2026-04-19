import type { ToolCallEntry } from '@/lib/store'

export interface ProgressStep {
  id: string
  index: number
  title: string
  kind: 'tool' | 'reason' | 'compact' | 'a2a' | 'turn'
  status: 'queued' | 'running' | 'ok' | 'err'
  startedAt?: number
  finishedAt?: number
  thinkingPreview?: string
  toolCallIds: string[]
  artifactIds: string[]
  children?: ProgressStep[]
}

const cache = new WeakMap<ToolCallEntry[], ProgressStep[]>()

function kindOf(name: string): ProgressStep['kind'] {
  if (name === '__compact__') return 'compact'
  if (name.startsWith('a2a:')) return 'a2a'
  return 'tool'
}

const TITLE_OVERRIDES: Record<string, string> = {
  execute_python: 'Running Python',
}

function titleOf(name: string): string {
  return TITLE_OVERRIDES[name] ?? name
}

function statusOf(t: ToolCallEntry): ProgressStep['status'] {
  if (t.status === 'pending') return 'running'
  if (t.status === 'error' || t.status === 'blocked') return 'err'
  return 'ok'
}

export function selectProgressSteps(log: ToolCallEntry[]): ProgressStep[] {
  const cached = cache.get(log)
  if (cached) return cached
  const steps: ProgressStep[] = log.map((t, i) => ({
    id: t.id,
    index: t.step ?? i,
    title: titleOf(t.name),
    kind: kindOf(t.name),
    status: statusOf(t),
    startedAt: t.startedAt,
    finishedAt: t.finishedAt,
    toolCallIds: [t.id],
    artifactIds: t.artifactIds ?? [],
  }))
  cache.set(log, steps)
  return steps
}
