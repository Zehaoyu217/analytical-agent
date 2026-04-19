import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useViewportWidth } from "../useViewportWidth";

afterEach(() => {
  vi.restoreAllMocks();
});

/** Drain any pending rAF callbacks (jsdom schedules them on a real timer). */
function flushRaf(): void {
  const g = globalThis as unknown as {
    requestAnimationFrame?: (cb: FrameRequestCallback) => number;
  };
  if (typeof g.requestAnimationFrame === "function") {
    // Nothing to do — the spy we install below invokes the cb synchronously.
  }
}

describe("useViewportWidth", () => {
  it("returns the current window.innerWidth on mount", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
    });
    const { result } = renderHook(() => useViewportWidth());
    expect(result.current).toBe(1280);
  });

  it("updates once per animation frame during resize storms", () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
    });
    const rafSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((cb: FrameRequestCallback) => {
        cb(0);
        return 1;
      });
    const { result } = renderHook(() => useViewportWidth());

    act(() => {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: 900,
      });
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("resize"));
    });
    flushRaf();

    expect(result.current).toBe(900);
    // 3 resize events, but only the first schedules a frame thanks to throttling.
    expect(rafSpy).toHaveBeenCalledTimes(1);
  });

  it("cleans up listeners on unmount", () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useViewportWidth());
    const addedResize = add.mock.calls.filter((c) => c[0] === "resize").length;
    unmount();
    const removedResize = remove.mock.calls.filter(
      (c) => c[0] === "resize",
    ).length;
    expect(removedResize).toBeGreaterThanOrEqual(addedResize);
  });
});
