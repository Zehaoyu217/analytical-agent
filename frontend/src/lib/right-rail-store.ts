import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export type RailMode = 'trace' | 'graph' | 'digest' | 'ingest'
export type TraceTab = 'timeline' | 'context' | 'raw'

const MODE_CYCLE: RailMode[] = ['trace', 'graph', 'digest', 'ingest']

interface RightRailState {
  mode: RailMode
  traceTab: TraceTab
  setMode: (mode: RailMode) => void
  setTraceTab: (tab: TraceTab) => void
  cycleMode: () => void
  returnToTrace: () => void
  toggleMode: (mode: Exclude<RailMode, 'trace'>) => void
}

export const useRightRailStore = create<RightRailState>()(
  persist(
    (set, get) => ({
      mode: 'trace',
      traceTab: 'timeline',
      setMode: (mode) => set({ mode }),
      setTraceTab: (traceTab) => set({ traceTab }),
      cycleMode: () => {
        const i = MODE_CYCLE.indexOf(get().mode)
        set({ mode: MODE_CYCLE[(i + 1) % MODE_CYCLE.length] })
      },
      returnToTrace: () => set({ mode: 'trace' }),
      toggleMode: (mode) =>
        set({ mode: get().mode === mode ? 'trace' : mode }),
    }),
    {
      name: 'cc-right-rail',
      storage: createJSONStorage(() => localStorage),
    },
  ),
)
