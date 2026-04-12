import { renderHook, act } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useDevtoolsStore } from '../../../stores/devtools'
import { useSelectionUrlSync } from '../useSelectionUrlSync'

describe('useSelectionUrlSync', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    useDevtoolsStore.setState({
      selectedTraceId: null,
      selectedStepId: null,
    })
  })

  it('reads ?trace= and ?step= from URL on mount', () => {
    window.history.replaceState(null, '', '/?trace=trace-1&step=s2')
    renderHook(() => useSelectionUrlSync())
    const s = useDevtoolsStore.getState()
    expect(s.selectedTraceId).toBe('trace-1')
    expect(s.selectedStepId).toBe('s2')
  })

  it('writes selection back to URL when store changes', () => {
    renderHook(() => useSelectionUrlSync())
    act(() => {
      useDevtoolsStore.getState().setSelectedTrace('trace-xyz')
    })
    expect(window.location.search).toContain('trace=trace-xyz')
  })

  it('clears query params when trace is cleared', () => {
    window.history.replaceState(null, '', '/?trace=old&step=s1')
    renderHook(() => useSelectionUrlSync())
    act(() => {
      useDevtoolsStore.getState().setSelectedTrace(null)
    })
    expect(window.location.search).not.toContain('trace=')
    expect(window.location.search).not.toContain('step=')
  })

  it('uses replaceState (not pushState) so history does not grow', () => {
    const historyLengthBefore = window.history.length
    renderHook(() => useSelectionUrlSync())
    act(() => {
      useDevtoolsStore.getState().setSelectedTrace('t1')
      useDevtoolsStore.getState().setSelectedTrace('t2')
      useDevtoolsStore.getState().setSelectedTrace('t3')
    })
    expect(window.history.length).toBe(historyLengthBefore)
  })
})
