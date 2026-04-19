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
  Sun,
} from "lucide-react";
import { useChatStore, type SectionId } from "@/lib/store";
import { useTheme } from "@/components/layout/ThemeProvider";
import { FlyoutTooltip } from "@/components/layout/FlyoutTooltip";
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
  onClick: () => void;
}

function RailButton({
  icon: Icon,
  label,
  hint,
  active = false,
  onClick,
}: RailButtonProps) {
  return (
    <FlyoutTooltip label={label} hint={hint}>
      <button
        type="button"
        aria-label={label}
        aria-current={active ? "page" : undefined}
        onClick={onClick}
        className={cn(
          "relative flex h-9 w-9 items-center justify-center rounded-md",
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
      </button>
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
  const isDark = theme === "dark";

  return (
    <nav
      aria-label="Main navigation"
      className={cn(
        "flex h-full w-[52px] flex-shrink-0 flex-col items-center",
        "bg-bg-1 border-r border-line-2",
        "pt-[10px] pb-[10px]",
      )}
    >
      <div className="flex flex-1 flex-col items-center gap-[2px]">
        {SECTIONS.map((section) => (
          <RailButton
            key={section.id}
            icon={section.icon}
            label={section.label}
            hint={section.hint}
            active={activeSection === section.id}
            onClick={() => setActiveSection(section.id)}
          />
        ))}
      </div>

      <div className="flex flex-col items-center gap-[2px]">
        <RailButton
          icon={isDark ? Sun : Moon}
          label={isDark ? "Light mode" : "Dark mode"}
          hint="⌘⇧L"
          onClick={() => setTheme(isDark ? "light" : "dark")}
        />
        <RailButton
          icon={Settings}
          label="Settings"
          hint="⌘,"
          active={activeSection === "settings"}
          onClick={() => setActiveSection("settings")}
        />
        <BrandMark />
      </div>
    </nav>
  );
}
