import type { ComponentType, SVGProps } from "react";
import {
  ClipboardList,
  Download,
  FileText,
  Gauge,
  Layers,
  MessageSquare,
  Monitor,
  Moon,
  Network,
  Puzzle,
  Settings,
  SlidersHorizontal,
  Sun,
} from "lucide-react";
import { useChatStore, type SectionId } from "@/lib/store";
import { useTheme } from "@/components/layout/ThemeProvider";
import { FlyoutTooltip } from "@/components/layout/FlyoutTooltip";
import { useUiStore, selectRailMode } from "@/lib/ui-store";
import { cn } from "@/lib/utils";

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;

interface SectionDef {
  id: SectionId;
  icon: IconComponent;
  label: string;
  hint?: string;
}

const SECTIONS: SectionDef[] = [
  { id: "chat", icon: MessageSquare, label: "Chat", hint: "⌘⇧1" },
  { id: "agents", icon: Monitor, label: "Agents", hint: "⌘⇧2" },
  { id: "skills", icon: Puzzle, label: "Skills", hint: "⌘⇧3" },
  { id: "prompts", icon: FileText, label: "Prompts", hint: "⌘⇧4" },
  { id: "context", icon: Layers, label: "Context", hint: "⌘⇧5" },
  { id: "health", icon: Gauge, label: "Health", hint: "⌘⇧6" },
  { id: "graph", icon: Network, label: "Graph", hint: "⌘⇧7" },
  { id: "digest", icon: ClipboardList, label: "Digest", hint: "⌘⇧8" },
  { id: "ingest", icon: Download, label: "Ingest", hint: "⌘⇧9" },
];

// Small presentational piece — used for the nine sections and the bottom
// theme/settings toggles. Ensures consistent sizing, hit-area, and the 2px
// accent bar for active state.
interface RailButtonProps {
  icon: IconComponent;
  label: string;
  hint?: string;
  active?: boolean;
  expanded?: boolean;
  onClick: () => void;
}

function RailButton({
  icon: Icon,
  label,
  hint,
  active = false,
  expanded = false,
  onClick,
}: RailButtonProps) {
  const button = (
    <button
      type="button"
      aria-label={label}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
      className={cn(
        "relative flex h-9 items-center rounded-md",
        expanded ? "w-full justify-start gap-2 px-2" : "w-9 justify-center",
        "transition-colors duration-100",
        "focus-ring",
        active
          ? "bg-acc-dim text-acc"
          : "text-fg-1 hover:bg-bg-2 hover:text-fg-0",
      )}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute -left-[10px] top-2 h-[22px] w-[2px] rounded-r-full bg-acc"
        />
      )}
      <Icon size={16} aria-hidden="true" />
      {expanded && (
        <span className="font-mono text-[11px] uppercase tracking-wider">
          {label}
        </span>
      )}
    </button>
  );
  if (expanded) return button;
  return (
    <FlyoutTooltip label={label} hint={hint}>
      {button}
    </FlyoutTooltip>
  );
}

// Brand/profile mark at the bottom of the rail. Purely decorative in the
// current design — will grow up to a menu trigger in a later step.
function BrandMark() {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "mt-2 flex h-7 w-7 items-center justify-center rounded-full",
        "text-[11px] font-semibold text-white",
        "shadow-[0_1px_2px_rgba(0,0,0,0.10),inset_0_1px_0_rgba(255,255,255,0.18)]",
      )}
      style={{
        background:
          "linear-gradient(135deg, oklch(0.72 0.09 35), oklch(0.58 0.11 30))",
        letterSpacing: "-0.02em",
      }}
    >
      M
    </div>
  );
}

export function IconRail() {
  const activeSection = useChatStore((s) => s.activeSection);
  const setActiveSection = useChatStore((s) => s.setActiveSection);
  const { theme, setTheme } = useTheme();
  const railMode = useUiStore(selectRailMode);
  const setTweaksOpen = useUiStore((s) => s.setTweaksOpen);
  const isDark = theme === "dark";
  const expanded = railMode === "expand";

  return (
    <nav
      aria-label="Main navigation"
      data-rail-mode={railMode}
      className={cn(
        "flex h-full flex-shrink-0 flex-col items-stretch",
        expanded ? "w-[148px] px-2" : "w-[52px] items-center",
        "bg-bg-1 border-r border-line-2",
        "pt-[10px] pb-[10px]",
      )}
    >
      <div
        className={cn(
          "flex flex-1 flex-col gap-[2px]",
          expanded ? "items-stretch" : "items-center",
        )}
      >
        {SECTIONS.map((section) => (
          <RailButton
            key={section.id}
            icon={section.icon}
            label={section.label}
            hint={section.hint}
            active={activeSection === section.id}
            expanded={expanded}
            onClick={() => setActiveSection(section.id)}
          />
        ))}
      </div>

      <div
        className={cn(
          "flex flex-col gap-[2px]",
          expanded ? "items-stretch" : "items-center",
        )}
      >
        <RailButton
          icon={isDark ? Sun : Moon}
          label={isDark ? "Light mode" : "Dark mode"}
          hint="⌘⇧L"
          expanded={expanded}
          onClick={() => setTheme(isDark ? "light" : "dark")}
        />
        <RailButton
          icon={SlidersHorizontal}
          label="Tweaks"
          hint="⌘,"
          expanded={expanded}
          onClick={() => setTweaksOpen(true)}
        />
        <RailButton
          icon={Settings}
          label="Settings"
          expanded={expanded}
          active={activeSection === "settings"}
          onClick={() => setActiveSection("settings")}
        />
        <BrandMark />
      </div>
    </nav>
  );
}
