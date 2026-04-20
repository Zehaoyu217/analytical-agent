import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type SettingsSection =
  | 'models'
  | 'sandbox'
  | 'memory'
  | 'ingest'
  | 'integrity'
  | 'theme'
  | 'hotkeys'
  | 'hooks'

export type MemoryFilter = 'all' | 'user' | 'feedback' | 'project' | 'reference'
export type KnowledgeDrawer = 'ingest' | 'digest' | 'graph' | 'gardener' | null

interface SurfacesStore {
  // Knowledge
  knowledgeDrawer: KnowledgeDrawer
  setKnowledgeDrawer: (d: KnowledgeDrawer) => void
  selectedWikiPath: string | null
  setSelectedWikiPath: (p: string | null) => void
  knowledgeSearch: string
  setKnowledgeSearch: (q: string) => void

  // Memory
  memorySplitFrac: number
  setMemorySplitFrac: (f: number) => void
  memoryFilter: MemoryFilter
  setMemoryFilter: (f: MemoryFilter) => void
  memorySearch: string
  setMemorySearch: (q: string) => void
  selectedMemoryName: string | null
  setSelectedMemoryName: (n: string | null) => void

  // Integrity
  integrityDate: string | null
  setIntegrityDate: (d: string | null) => void

  // Library
  selectedLibraryItemId: string | null
  setSelectedLibraryItemId: (id: string | null) => void

  // Settings overlay
  settingsOverlayOpen: boolean
  openSettings: () => void
  closeSettings: () => void
  settingsSearch: string
  setSettingsSearch: (q: string) => void
  settingsActiveSection: SettingsSection
  setSettingsActiveSection: (s: SettingsSection) => void
}

const STORAGE_KEY = 'ds:surfaces'

export const useSurfacesStore = create<SurfacesStore>()(
  persist(
    (set) => ({
      knowledgeDrawer: null,
      setKnowledgeDrawer: (d) => set({ knowledgeDrawer: d }),
      selectedWikiPath: null,
      setSelectedWikiPath: (p) => set({ selectedWikiPath: p }),
      knowledgeSearch: '',
      setKnowledgeSearch: (q) => set({ knowledgeSearch: q }),

      memorySplitFrac: 0.4,
      setMemorySplitFrac: (f) => set({ memorySplitFrac: clamp(f, 0.2, 0.8) }),
      memoryFilter: 'all',
      setMemoryFilter: (f) => set({ memoryFilter: f }),
      memorySearch: '',
      setMemorySearch: (q) => set({ memorySearch: q }),
      selectedMemoryName: null,
      setSelectedMemoryName: (n) => set({ selectedMemoryName: n }),

      integrityDate: null,
      setIntegrityDate: (d) => set({ integrityDate: d }),

      selectedLibraryItemId: null,
      setSelectedLibraryItemId: (id) => set({ selectedLibraryItemId: id }),

      settingsOverlayOpen: false,
      openSettings: () => set({ settingsOverlayOpen: true }),
      closeSettings: () => set({ settingsOverlayOpen: false, settingsSearch: '' }),
      settingsSearch: '',
      setSettingsSearch: (q) => set({ settingsSearch: q }),
      settingsActiveSection: 'models',
      setSettingsActiveSection: (s) =>
        set({ settingsActiveSection: s, settingsSearch: '' }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        memorySplitFrac: state.memorySplitFrac,
        memoryFilter: state.memoryFilter,
        knowledgeDrawer: state.knowledgeDrawer,
        selectedWikiPath: state.selectedWikiPath,
        settingsActiveSection: state.settingsActiveSection,
      }),
    },
  ),
)

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n))
}
