import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Side = "right" | "left";

interface FlyoutTooltipProps {
  label: string;
  hint?: string;
  side?: Side;
  /** The trigger — typically a button. */
  children: ReactNode;
}

/**
 * Inverted pill tooltip used along the icon rail.
 *
 * Appears on pointer hover or keyboard focus; the bubble sits outside the
 * rail so it never clips against siblings. Rendered in-flow beside the
 * trigger rather than portaled — the rail column is narrow and the bubble
 * is short enough that overlap with adjacent items isn't an issue.
 */
export function FlyoutTooltip({
  label,
  hint,
  side = "right",
  children,
}: FlyoutTooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  return (
    <div
      className="relative flex"
      onPointerEnter={() => setOpen(true)}
      onPointerLeave={() => setOpen(false)}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={() => setOpen(false)}
    >
      <div aria-describedby={open ? id : undefined} className="flex">
        {children}
      </div>
      <div
        role="tooltip"
        id={id}
        className={cn(
          "pointer-events-none absolute top-1/2 z-50 -translate-y-1/2",
          "whitespace-nowrap rounded-md px-2 py-1 text-[12px] font-medium",
          "bg-fg-0 text-bg-0 shadow-lg",
          "transition-opacity duration-150",
          open ? "opacity-100" : "opacity-0",
          side === "right" ? "left-full ml-3" : "right-full mr-3",
        )}
      >
        <span>{label}</span>
        {hint && (
          <span className="mono ml-2 text-[10.5px] opacity-70">{hint}</span>
        )}
      </div>
    </div>
  );
}
