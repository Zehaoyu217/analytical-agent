/**
 * ui-store — shell-level UI state: panel widths, open/closed, dock tab, density.
 *
 * Persisted under `ds:ui` via zustand/persist with a zod schema gate. Legacy
 * localStorage keys `ds:threadW` / `ds:dockW` are read once on first load and
 * folded into the store, then scheduled for cleanup.
 *
 * Transient fields (`threadsOverridden`, `dockOverridden`) are not persisted —
 * they reset every session so auto-collapse logic re-takes ownership.
 */

import { create } from "zustand";
import { persist, type PersistStorage } from "zustand/middleware";
import { z } from "zod";

export const THREAD_W_MIN = 160;
export const THREAD_W_MAX = 360;
export const DOCK_W_MIN = 240;
export const DOCK_W_MAX = 480;

export const THREADS_BREAKPOINT = 1100;
export const DOCK_BREAKPOINT = 900;

const clamp = (n: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, n));

export const UiPersistedSchema = z.object({
  v: z.literal(1).default(1),
  threadW: z.number().int().min(THREAD_W_MIN).max(THREAD_W_MAX).default(200),
  dockW: z.number().int().min(DOCK_W_MIN).max(DOCK_W_MAX).default(320),
  threadsOpen: z.boolean().default(true),
  dockOpen: z.boolean().default(true),
  dockTab: z.enum(["progress", "context", "artifacts"]).default("progress"),
  density: z.enum(["compact", "default", "cozy"]).default("default"),
});

export type UiPersisted = z.infer<typeof UiPersistedSchema>;
export type DockTab = UiPersisted["dockTab"];
export type Density = UiPersisted["density"];

export interface UiStore extends UiPersisted {
  /** User intentionally overrode auto-collapse for the thread list. */
  threadsOverridden: boolean;
  /** User intentionally overrode auto-collapse for the dock. */
  dockOverridden: boolean;

  setThreadW: (w: number) => void;
  setDockW: (w: number) => void;
  toggleThreads: () => void;
  toggleDock: () => void;
  setDockTab: (tab: DockTab) => void;
  setDensity: (d: Density) => void;

  /** Auto-collapse hook: set without flipping the override bit. */
  setAutoThreads: (open: boolean) => void;
  setAutoDock: (open: boolean) => void;

  resetThreadsOverride: () => void;
  resetDockOverride: () => void;
}

const PERSIST_KEY = "ds:ui";
const LEGACY_THREAD_W_KEY = "ds:threadW";
const LEGACY_DOCK_W_KEY = "ds:dockW";

interface RawPersistEnvelope {
  state: unknown;
  version?: number;
}

/**
 * zustand/persist PersistStorage<UiPersisted>. We wrap localStorage so that
 *   1. corrupt JSON returns null (defaults apply, no throw),
 *   2. schema failures return null,
 *   3. legacy `ds:threadW` / `ds:dockW` are migrated on first load.
 */
function createZodStorage(): PersistStorage<UiPersisted> {
  return {
    getItem: (name) => {
      if (typeof localStorage === "undefined") return null;
      try {
        const raw = localStorage.getItem(name);
        if (!raw) {
          // First-load migration from legacy keys.
          const legacyThread = readIntKey(LEGACY_THREAD_W_KEY);
          const legacyDock = readIntKey(LEGACY_DOCK_W_KEY);
          if (legacyThread === null && legacyDock === null) return null;

          const migrated = UiPersistedSchema.parse({
            v: 1,
            threadW: legacyThread ?? undefined,
            dockW: legacyDock ?? undefined,
          });
          return { state: migrated, version: 1 };
        }

        const parsed = JSON.parse(raw) as RawPersistEnvelope;
        const state = UiPersistedSchema.safeParse(parsed?.state);
        if (!state.success) return null;
        return { state: state.data, version: parsed.version ?? 1 };
      } catch {
        return null;
      }
    },
    setItem: (name, value) => {
      if (typeof localStorage === "undefined") return;
      try {
        localStorage.setItem(name, JSON.stringify(value));
        // Clean up legacy keys once we've persisted new state.
        localStorage.removeItem(LEGACY_THREAD_W_KEY);
        localStorage.removeItem(LEGACY_DOCK_W_KEY);
      } catch {
        /* storage full / disabled — defaults remain in-memory */
      }
    },
    removeItem: (name) => {
      if (typeof localStorage === "undefined") return;
      try {
        localStorage.removeItem(name);
      } catch {
        /* no-op */
      }
    },
  };
}

function readIntKey(key: string): number | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export const useUiStore = create<UiStore>()(
  persist(
    (set) => ({
      v: 1,
      threadW: 200,
      dockW: 320,
      threadsOpen: true,
      dockOpen: true,
      dockTab: "progress",
      density: "default",

      threadsOverridden: false,
      dockOverridden: false,

      setThreadW: (w) =>
        set({ threadW: clamp(Math.round(w), THREAD_W_MIN, THREAD_W_MAX) }),
      setDockW: (w) =>
        set({ dockW: clamp(Math.round(w), DOCK_W_MIN, DOCK_W_MAX) }),

      toggleThreads: () =>
        set((s) => ({
          threadsOpen: !s.threadsOpen,
          threadsOverridden: true,
        })),
      toggleDock: () =>
        set((s) => ({
          dockOpen: !s.dockOpen,
          dockOverridden: true,
        })),

      setDockTab: (tab) => set({ dockTab: tab }),
      setDensity: (d) => {
        set({ density: d });
        if (typeof document !== "undefined") {
          if (d === "default") {
            document.documentElement.removeAttribute("data-density");
          } else {
            document.documentElement.dataset.density = d;
          }
        }
      },

      setAutoThreads: (open) => set({ threadsOpen: open }),
      setAutoDock: (open) => set({ dockOpen: open }),

      resetThreadsOverride: () => set({ threadsOverridden: false }),
      resetDockOverride: () => set({ dockOverridden: false }),
    }),
    {
      name: PERSIST_KEY,
      version: 1,
      storage: createZodStorage(),
      partialize: (s): UiPersisted => ({
        v: 1,
        threadW: s.threadW,
        dockW: s.dockW,
        threadsOpen: s.threadsOpen,
        dockOpen: s.dockOpen,
        dockTab: s.dockTab,
        density: s.density,
      }),
    },
  ),
);

// ── Selectors ────────────────────────────────────────────────────────────
export const selectThreadW = (s: UiStore): number => s.threadW;
export const selectDockW = (s: UiStore): number => s.dockW;
export const selectDockTab = (s: UiStore): DockTab => s.dockTab;
export const selectThreadsOpen = (s: UiStore): boolean => s.threadsOpen;
export const selectDockOpen = (s: UiStore): boolean => s.dockOpen;
export const selectDensity = (s: UiStore): Density => s.density;
