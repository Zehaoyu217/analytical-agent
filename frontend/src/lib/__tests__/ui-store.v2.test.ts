import { describe, it, expect, beforeEach } from 'vitest'
import { useUiStore } from '@/lib/ui-store'

describe('ui-store v2', () => {
  beforeEach(() => {
    localStorage.clear()
    useUiStore.setState({
      progressExpanded: [],
      artifactView: 'grid',
      recentCommandIds: [],
      traceTab: 'context',
    } as never)
  })

  it('toggleProgressExpanded adds and removes step ids', () => {
    useUiStore.getState().toggleProgressExpanded('s1')
    expect(useUiStore.getState().progressExpanded).toEqual(['s1'])
    useUiStore.getState().toggleProgressExpanded('s1')
    expect(useUiStore.getState().progressExpanded).toEqual([])
  })

  it('setArtifactView switches mode', () => {
    useUiStore.getState().setArtifactView('list')
    expect(useUiStore.getState().artifactView).toBe('list')
  })

  it('pushRecentCommand deduplicates and caps at 5', () => {
    for (const id of ['a', 'b', 'c', 'd', 'e', 'f', 'a']) {
      useUiStore.getState().pushRecentCommand(id)
    }
    const ids = useUiStore.getState().recentCommandIds
    expect(ids.length).toBeLessThanOrEqual(5)
    expect(ids[0]).toBe('a')
  })

  it('setTraceTab lives in ui-store now', () => {
    useUiStore.getState().setTraceTab('io')
    expect(useUiStore.getState().traceTab).toBe('io')
  })
})
