import { beforeEach, describe, expect, it } from "vitest";
import {
  DOCK_W_MAX,
  DOCK_W_MIN,
  THREAD_W_MAX,
  THREAD_W_MIN,
  useUiStore,
} from "../ui-store";

const PERSIST_KEY = "ds:ui";
const LEGACY_THREAD_W = "ds:threadW";
const LEGACY_DOCK_W = "ds:dockW";

function resetStore(): void {
  useUiStore.setState({
    v: 1,
    threadW: 200,
    dockW: 320,
    threadsOpen: true,
    dockOpen: true,
    dockTab: "progress",
    density: "default",
    threadsOverridden: false,
    dockOverridden: false,
  });
  // Wipe all persisted state AFTER setState so the persist middleware doesn't
  // re-seed ds:ui with the defaults we just set.
  localStorage.clear();
}

describe("ui-store", () => {
  beforeEach(() => {
    resetStore();
  });

  it("exposes schema defaults without any persisted state", () => {
    const s = useUiStore.getState();
    expect(s.threadW).toBe(200);
    expect(s.dockW).toBe(320);
    expect(s.threadsOpen).toBe(true);
    expect(s.dockOpen).toBe(true);
    expect(s.dockTab).toBe("progress");
    expect(s.density).toBe("default");
  });

  it("clamps setThreadW below the minimum", () => {
    useUiStore.getState().setThreadW(100);
    expect(useUiStore.getState().threadW).toBe(THREAD_W_MIN);
  });

  it("clamps setThreadW above the maximum", () => {
    useUiStore.getState().setThreadW(1000);
    expect(useUiStore.getState().threadW).toBe(THREAD_W_MAX);
  });

  it("clamps setDockW to its bounds and rounds non-integers", () => {
    useUiStore.getState().setDockW(9999);
    expect(useUiStore.getState().dockW).toBe(DOCK_W_MAX);
    useUiStore.getState().setDockW(50);
    expect(useUiStore.getState().dockW).toBe(DOCK_W_MIN);
    useUiStore.getState().setDockW(300.7);
    expect(useUiStore.getState().dockW).toBe(301);
  });

  it("flips override flags on user toggle, not on auto setter", () => {
    useUiStore.getState().toggleThreads();
    expect(useUiStore.getState().threadsOverridden).toBe(true);
    expect(useUiStore.getState().threadsOpen).toBe(false);

    useUiStore.getState().resetThreadsOverride();
    useUiStore.getState().setAutoThreads(true);
    expect(useUiStore.getState().threadsOverridden).toBe(false);
    expect(useUiStore.getState().threadsOpen).toBe(true);

    useUiStore.getState().toggleDock();
    expect(useUiStore.getState().dockOverridden).toBe(true);
    expect(useUiStore.getState().dockOpen).toBe(false);
  });

  it("setDensity mirrors onto document.documentElement.dataset.density", () => {
    useUiStore.getState().setDensity("compact");
    expect(document.documentElement.dataset.density).toBe("compact");
    useUiStore.getState().setDensity("cozy");
    expect(document.documentElement.dataset.density).toBe("cozy");
    useUiStore.getState().setDensity("default");
    expect(document.documentElement.dataset.density).toBeUndefined();
  });

  it("rehydrates schema-valid persisted state", async () => {
    localStorage.setItem(
      PERSIST_KEY,
      JSON.stringify({
        state: {
          v: 1,
          threadW: 220,
          dockW: 360,
          threadsOpen: false,
          dockOpen: true,
          dockTab: "artifacts",
          density: "compact",
        },
        version: 1,
      }),
    );
    await useUiStore.persist.rehydrate();
    const s = useUiStore.getState();
    expect(s.threadW).toBe(220);
    expect(s.dockW).toBe(360);
    expect(s.threadsOpen).toBe(false);
    expect(s.dockTab).toBe("artifacts");
    expect(s.density).toBe("compact");
  });

  it("falls back to defaults when persisted JSON is corrupt", async () => {
    localStorage.setItem(PERSIST_KEY, "{not-json");
    await useUiStore.persist.rehydrate();
    const s = useUiStore.getState();
    expect(s.threadW).toBe(200);
    expect(s.dockW).toBe(320);
  });

  it("falls back when persisted state fails schema validation", async () => {
    localStorage.setItem(
      PERSIST_KEY,
      JSON.stringify({
        state: { v: 1, threadW: 9999, dockW: 320, dockTab: "progress" },
        version: 1,
      }),
    );
    await useUiStore.persist.rehydrate();
    expect(useUiStore.getState().threadW).toBe(200);
  });

  it("migrates legacy ds:threadW / ds:dockW into the new store", async () => {
    localStorage.setItem(LEGACY_THREAD_W, "220");
    localStorage.setItem(LEGACY_DOCK_W, "360");
    await useUiStore.persist.rehydrate();
    const s = useUiStore.getState();
    expect(s.threadW).toBe(220);
    expect(s.dockW).toBe(360);
  });
});
