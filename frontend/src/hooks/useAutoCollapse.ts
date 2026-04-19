/**
 * useAutoCollapse — keeps ThreadList (1100px) and Dock (900px) aligned with
 * viewport width unless the user has explicitly toggled them.
 *
 * Triggers only on boundary crossings so manual toggles at steady viewport
 * widths aren't clobbered by re-renders.
 */

import { useEffect, useRef } from "react";
import { useViewportWidth } from "./useViewportWidth";
import {
  useUiStore,
  THREADS_BREAKPOINT,
  DOCK_BREAKPOINT,
} from "@/lib/ui-store";

export function useAutoCollapse(): void {
  const vw = useViewportWidth();
  const prev = useRef<number | null>(null);

  useEffect(() => {
    const previous = prev.current;
    prev.current = vw;
    if (vw === 0) return;
    if (previous === null) {
      // First observation — sync store to viewport without flagging override.
      const { threadsOverridden, dockOverridden, setAutoThreads, setAutoDock } =
        useUiStore.getState();
      if (!threadsOverridden) setAutoThreads(vw >= THREADS_BREAKPOINT);
      if (!dockOverridden) setAutoDock(vw >= DOCK_BREAKPOINT);
      return;
    }

    const crossed = (limit: number): boolean =>
      (previous < limit && vw >= limit) || (previous >= limit && vw < limit);

    const state = useUiStore.getState();

    if (crossed(THREADS_BREAKPOINT)) {
      state.resetThreadsOverride();
      state.setAutoThreads(vw >= THREADS_BREAKPOINT);
    }
    if (crossed(DOCK_BREAKPOINT)) {
      state.resetDockOverride();
      state.setAutoDock(vw >= DOCK_BREAKPOINT);
    }
  }, [vw]);
}
