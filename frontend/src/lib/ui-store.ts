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

export const ACCENT_SWATCHES = [
  "#e0733a", // orange (default — Claude brand)
  "#a3e635", // lime
  "#22d3ee", // cyan
  "#c084fc", // violet
  "#f472b6", // pink
] as const;
export type AccentColor = (typeof ACCENT_SWATCHES)[number];
const ACCENT_DEFAULT: AccentColor = "#e0733a";

export const UiPersistedSchema = z.object({
  v: z.literal(3).default(3),
  threadW: z.number().int().min(THREAD_W_MIN).max(THREAD_W_MAX).default(200),
  dockW: z.number().int().min(DOCK_W_MIN).max(DOCK_W_MAX).default(320),
  threadsOpen: z.boolean().default(true),
  dockOpen: z.boolean().default(true),
  dockTab: z.enum(["progress", "context", "artifacts"]).default("progress"),
  density: z.enum(["compact", "default", "cozy"]).default("default"),
  progressExpanded: z.array(z.string()).default([]),
  artifactView: z.enum(["grid", "list"]).default("grid"),
  recentCommandIds: z.array(z.string()).default([]),
  traceTab: z
    .preprocess(
      // Migrate retired values from older persisted state.
      (v) => (v === "timeline" || v === "raw" ? "context" : v),
      z.enum(["context", "io"]),
    )
    .default("context"),
  // v3 additions — Tweaks panel knobs
  accent: z.enum(ACCENT_SWATCHES).default(ACCENT_DEFAULT),
  dockPosition: z.enum(["right", "bottom", "off"]).default("right"),
  msgStyle: z.enum(["flat", "bordered"]).default("flat"),
  thinkMode: z.enum(["tab", "inline"]).default("tab"),
  uiFont: z.enum(["mono", "sans"]).default("mono"),
  railMode: z.enum(["icon", "expand"]).default("icon"),
  agentRunning: z.boolean().default(true),
});

export type UiPersisted = z.infer<typeof UiPersistedSchema>;
export type DockTab = UiPersisted["dockTab"];
export type Density = UiPersisted["density"];
export type ArtifactView = UiPersisted["artifactView"];
export type TraceTab = UiPersisted["traceTab"];
export type DockPosition = UiPersisted["dockPosition"];
export type MsgStyle = UiPersisted["msgStyle"];
export type ThinkMode = UiPersisted["thinkMode"];
export type UiFont = UiPersisted["uiFont"];
export type RailMode = UiPersisted["railMode"];

export interface UiStore extends UiPersisted {
  /** User intentionally overrode auto-collapse for the thread list. */
  threadsOverridden: boolean;
  /** User intentionally overrode auto-collapse for the dock. */
  dockOverridden: boolean;
  /** Tweaks panel open state — transient. */
  tweaksOpen: boolean;
  setTweaksOpen: (open: boolean) => void;
  toggleTweaks: () => void;

  setThreadW: (w: number) => void;
  setDockW: (w: number) => void;
  toggleThreads: () => void;
  toggleDock: () => void;
  setThreadsOpen: (open: boolean) => void;
  setDockOpen: (open: boolean) => void;
  setDockTab: (tab: DockTab) => void;
  setDensity: (d: Density) => void;

  toggleProgressExpanded: (stepId: string) => void;
  setArtifactView: (view: ArtifactView) => void;
  pushRecentCommand: (id: string) => void;
  setTraceTab: (tab: TraceTab) => void;

  // Tweaks panel setters
  setAccent: (c: AccentColor) => void;
  setDockPosition: (p: DockPosition) => void;
  setMsgStyle: (s: MsgStyle) => void;
  setThinkMode: (m: ThinkMode) => void;
  setUiFont: (f: UiFont) => void;
  setRailMode: (r: RailMode) => void;
  setAgentRunning: (running: boolean) => void;

  /** Auto-collapse hook: set without flipping the override bit. */
  setAutoThreads: (open: boolean) => void;
  setAutoDock: (open: boolean) => void;

  resetThreadsOverride: () => void;
  resetDockOverride: () => void;
}

const PERSIST_KEY = "ds:ui";
const LEGACY_THREAD_W_KEY = "ds:threadW";
const LEGACY_DOCK_W_KEY = "ds:dockW";
const RECENT_COMMAND_CAP = 5;

interface RawPersistEnvelope {
  state: unknown;
  version?: number;
}

/**
 * zustand/persist PersistStorage<UiPersisted>. We wrap localStorage so that
 *   1. corrupt JSON returns null (defaults apply, no throw),
 *   2. schema failures return null,
 *   3. legacy `ds:threadW` / `ds:dockW` are migrated on first load,
 *   4. v1 payloads are upgraded by backfilling the new v2 fields.
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
            v: 3,
            threadW: legacyThread ?? undefined,
            dockW: legacyDock ?? undefined,
          });
          return { state: migrated, version: 3 };
        }

        const parsed = JSON.parse(raw) as RawPersistEnvelope;
        // Backfill v2/v3 fields onto older payloads before zod validates.
        const stateCandidate =
          parsed?.state && typeof parsed.state === "object"
            ? {
                progressExpanded: [],
                artifactView: "grid",
                recentCommandIds: [],
                traceTab: "context",
                accent: ACCENT_DEFAULT,
                dockPosition: "right",
                msgStyle: "flat",
                thinkMode: "tab",
                uiFont: "mono",
                railMode: "icon",
                agentRunning: true,
                ...(parsed.state as Record<string, unknown>),
                v: 3,
              }
            : parsed?.state;
        const state = UiPersistedSchema.safeParse(stateCandidate);
        if (!state.success) return null;
        return { state: state.data, version: 3 };
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
      v: 3,
      threadW: 200,
      dockW: 320,
      threadsOpen: true,
      dockOpen: true,
      dockTab: "progress",
      density: "default",
      progressExpanded: [],
      artifactView: "grid",
      recentCommandIds: [],
      traceTab: "context",
      accent: ACCENT_DEFAULT,
      dockPosition: "right",
      msgStyle: "flat",
      thinkMode: "tab",
      uiFont: "mono",
      railMode: "icon",
      agentRunning: true,

      threadsOverridden: false,
      dockOverridden: false,
      tweaksOpen: false,
      setTweaksOpen: (open) => set({ tweaksOpen: open }),
      toggleTweaks: () => set((s) => ({ tweaksOpen: !s.tweaksOpen })),

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
      setThreadsOpen: (open) => set({ threadsOpen: open, threadsOverridden: true }),
      setDockOpen: (open) => set({ dockOpen: open, dockOverridden: true }),

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

      toggleProgressExpanded: (stepId) =>
        set((s) => ({
          progressExpanded: s.progressExpanded.includes(stepId)
            ? s.progressExpanded.filter((id) => id !== stepId)
            : [...s.progressExpanded, stepId],
        })),
      setArtifactView: (view) => set({ artifactView: view }),
      pushRecentCommand: (id) =>
        set((s) => {
          const next = [id, ...s.recentCommandIds.filter((x) => x !== id)].slice(
            0,
            RECENT_COMMAND_CAP,
          );
          return { recentCommandIds: next };
        }),
      setTraceTab: (tab) => set({ traceTab: tab }),

      setAccent: (c) => set({ accent: c }),
      setDockPosition: (p) => set({ dockPosition: p }),
      setMsgStyle: (s) => set({ msgStyle: s }),
      setThinkMode: (m) => set({ thinkMode: m }),
      setUiFont: (f) => set({ uiFont: f }),
      setRailMode: (r) => set({ railMode: r }),
      setAgentRunning: (running) => set({ agentRunning: running }),

      setAutoThreads: (open) => set({ threadsOpen: open }),
      setAutoDock: (open) => set({ dockOpen: open }),

      resetThreadsOverride: () => set({ threadsOverridden: false }),
      resetDockOverride: () => set({ dockOverridden: false }),
    }),
    {
      name: PERSIST_KEY,
      version: 3,
      storage: createZodStorage(),
      partialize: (s): UiPersisted => ({
        v: 3,
        threadW: s.threadW,
        dockW: s.dockW,
        threadsOpen: s.threadsOpen,
        dockOpen: s.dockOpen,
        dockTab: s.dockTab,
        density: s.density,
        progressExpanded: s.progressExpanded,
        artifactView: s.artifactView,
        recentCommandIds: s.recentCommandIds,
        traceTab: s.traceTab,
        accent: s.accent,
        dockPosition: s.dockPosition,
        msgStyle: s.msgStyle,
        thinkMode: s.thinkMode,
        uiFont: s.uiFont,
        railMode: s.railMode,
        agentRunning: s.agentRunning,
      }),
      migrate: (persisted, fromVersion) => {
        if (fromVersion < 3 && persisted && typeof persisted === "object") {
          const merged = {
            progressExpanded: [],
            artifactView: "grid",
            recentCommandIds: [],
            traceTab: "context",
            accent: ACCENT_DEFAULT,
            dockPosition: "right",
            msgStyle: "flat",
            thinkMode: "tab",
            uiFont: "mono",
            railMode: "icon",
            agentRunning: true,
            ...(persisted as Record<string, unknown>),
            v: 3,
          };
          return merged as unknown as UiPersisted;
        }
        return persisted as UiPersisted;
      },
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
export const selectArtifactView = (s: UiStore): ArtifactView => s.artifactView;
export const selectProgressExpanded = (s: UiStore): string[] => s.progressExpanded;
export const selectTraceTab = (s: UiStore): TraceTab => s.traceTab;
export const selectRecentCommandIds = (s: UiStore): string[] => s.recentCommandIds;
export const selectAccent = (s: UiStore): AccentColor => s.accent;
export const selectDockPosition = (s: UiStore): DockPosition => s.dockPosition;
export const selectMsgStyle = (s: UiStore): MsgStyle => s.msgStyle;
export const selectThinkMode = (s: UiStore): ThinkMode => s.thinkMode;
export const selectUiFont = (s: UiStore): UiFont => s.uiFont;
export const selectRailMode = (s: UiStore): RailMode => s.railMode;
export const selectAgentRunning = (s: UiStore): boolean => s.agentRunning;
