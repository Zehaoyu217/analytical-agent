import { create } from 'zustand'
import type { ContextSnapshot } from '../lib/api'

export const DEVTOOLS_MIN_HEIGHT = 160
export const DEVTOOLS_MAX_HEIGHT_FRACTION = 0.85
export const DEVTOOLS_DEFAULT_HEIGHT = 420

interface DevtoolsState {
  isOpen: boolean
  activeTab: 'events' | 'skills' | 'config' | 'wiki' | 'evals' | 'context'
          | 'traces'
          | 'sop-sessions' | 'sop-judge' | 'sop-prompt' | 'sop-timeline'
  contextSnapshot: ContextSnapshot | null
  selectedTraceId: string | null
  selectedStepId: string | null
  panelHeight: number
  toggle: () => void
  setActiveTab: (tab: DevtoolsState['activeTab']) => void
  setContextSnapshot: (snapshot: ContextSnapshot) => void
  setSelectedTrace: (traceId: string | null) => void
  setSelectedStep: (stepId: string | null) => void
  setPanelHeight: (height: number) => void
}

function clampPanelHeight(height: number): number {
  const maxByViewport =
    typeof window === 'undefined'
      ? Number.POSITIVE_INFINITY
      : Math.round(window.innerHeight * DEVTOOLS_MAX_HEIGHT_FRACTION)
  const min = DEVTOOLS_MIN_HEIGHT
  return Math.max(min, Math.min(height, maxByViewport))
}

export const useDevtoolsStore = create<DevtoolsState>((set) => ({
  isOpen: false,
  activeTab: 'traces',
  contextSnapshot: null,
  selectedTraceId: null,
  selectedStepId: null,
  panelHeight: DEVTOOLS_DEFAULT_HEIGHT,
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setContextSnapshot: (snapshot) => set({ contextSnapshot: snapshot }),
  setSelectedTrace: (traceId) =>
    set({ selectedTraceId: traceId, selectedStepId: null }),
  setSelectedStep: (stepId) => set({ selectedStepId: stepId }),
  setPanelHeight: (height) => set({ panelHeight: clampPanelHeight(height) }),
}))
