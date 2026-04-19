/**
 * useViewportWidth — reactive viewport width, rAF-throttled.
 *
 * Updates at most once per animation frame during resize storms. Subscribes to
 * `resize` and `orientationchange`. Returns 0 on the server so the first render
 * matches regardless of viewport.
 */

import { useEffect, useState } from "react";

function readWidth(): number {
  if (typeof window === "undefined") return 0;
  return window.innerWidth;
}

export function useViewportWidth(): number {
  const [width, setWidth] = useState<number>(readWidth);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let rafId = 0;
    let pendingWidth = readWidth();

    const flush = (): void => {
      rafId = 0;
      setWidth(pendingWidth);
    };

    const onResize = (): void => {
      pendingWidth = window.innerWidth;
      if (rafId !== 0) return;
      rafId = window.requestAnimationFrame(flush);
    };

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });

    // Sync once on mount so late-mounted consumers see the current width.
    setWidth(readWidth());

    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
      if (rafId !== 0) window.cancelAnimationFrame(rafId);
    };
  }, []);

  return width;
}
