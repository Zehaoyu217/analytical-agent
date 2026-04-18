import { beforeEach, describe, expect, it } from 'vitest'
import { useRightRailStore } from '../right-rail-store'

describe('rightRailStore', () => {
  beforeEach(() => {
    useRightRailStore.setState({ mode: 'trace', traceTab: 'timeline' })
  })

  it('defaults to trace/timeline', () => {
    const s = useRightRailStore.getState()
    expect(s.mode).toBe('trace')
    expect(s.traceTab).toBe('timeline')
  })

  it('setMode switches modes', () => {
    useRightRailStore.getState().setMode('graph')
    expect(useRightRailStore.getState().mode).toBe('graph')
  })

  it('returnToTrace resets mode to trace', () => {
    useRightRailStore.getState().setMode('digest')
    useRightRailStore.getState().returnToTrace()
    expect(useRightRailStore.getState().mode).toBe('trace')
  })

  it('cycleMode cycles trace -> graph -> digest -> ingest -> trace', () => {
    const { cycleMode } = useRightRailStore.getState()
    cycleMode()
    expect(useRightRailStore.getState().mode).toBe('graph')
    cycleMode()
    expect(useRightRailStore.getState().mode).toBe('digest')
    cycleMode()
    expect(useRightRailStore.getState().mode).toBe('ingest')
    cycleMode()
    expect(useRightRailStore.getState().mode).toBe('trace')
  })

  it('toggleMode opens a drawer and toggles back to trace on second call', () => {
    const { toggleMode } = useRightRailStore.getState()
    toggleMode('graph')
    expect(useRightRailStore.getState().mode).toBe('graph')
    toggleMode('graph')
    expect(useRightRailStore.getState().mode).toBe('trace')
  })

  it('setTraceTab switches tabs', () => {
    useRightRailStore.getState().setTraceTab('raw')
    expect(useRightRailStore.getState().traceTab).toBe('raw')
  })
})
