import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoCollapse } from "../useAutoCollapse";
import { useUiStore } from "@/lib/ui-store";

function setViewport(w: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: w,
  });
  window.dispatchEvent(new Event("resize"));
}

function resetUi(): void {
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
}

beforeEach(() => {
  resetUi();
  vi.spyOn(window, "requestAnimationFrame").mockImplementation(
    (cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    },
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useAutoCollapse", () => {
  it("syncs initial state to viewport width on first mount", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 800,
    });
    renderHook(() => useAutoCollapse());
    const s = useUiStore.getState();
    expect(s.threadsOpen).toBe(false);
    expect(s.dockOpen).toBe(false);
  });

  it("collapses threads when crossing below 1100px", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1400,
    });
    const { rerender } = renderHook(() => useAutoCollapse());
    expect(useUiStore.getState().threadsOpen).toBe(true);

    act(() => setViewport(1000));
    rerender();
    expect(useUiStore.getState().threadsOpen).toBe(false);
  });

  it("collapses dock when crossing below 900px", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1200,
    });
    const { rerender } = renderHook(() => useAutoCollapse());
    expect(useUiStore.getState().dockOpen).toBe(true);

    act(() => setViewport(800));
    rerender();
    expect(useUiStore.getState().dockOpen).toBe(false);
  });

  it("restores threads when crossing back above 1100px", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 900,
    });
    const { rerender } = renderHook(() => useAutoCollapse());
    expect(useUiStore.getState().threadsOpen).toBe(false);

    act(() => setViewport(1300));
    rerender();
    expect(useUiStore.getState().threadsOpen).toBe(true);
  });
});
